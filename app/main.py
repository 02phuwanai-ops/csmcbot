# app/main.py
import json
import logging
import os
import threading
import time
from datetime import datetime

import pytz
from fastapi import BackgroundTasks, FastAPI, HTTPException, Query, Request
from linebot import LineBotApi, WebhookHandler
from linebot.exceptions import InvalidSignatureError, LineBotApiError
from linebot.models import MessageEvent, TextMessage, TextSendMessage

# 📌 Import สำหรับ SDK v3 (เพื่อให้จุด Loading ขึ้นบนมือถือ)
from linebot.v3.messaging import (
    ApiClient,
    Configuration,
    MessagingApi,
    ShowLoadingAnimationRequest,
)

from app.parser import parse_and_group_by_zone
from app.updatett import UpdateTTClient


# 1. ตั้งค่า Logging ให้แสดงเฉพาะ WARNING/ERROR บน Production ( Render )
IS_PRODUCTION = os.getenv("RENDER", False)
logging.basicConfig(
    level=logging.WARNING if IS_PRODUCTION else logging.INFO,
    format="%(asctime)s - %(levelname)s - %(message)s"
)
logger = logger = logging.getLogger("csmcbot")

app = FastAPI(title="CSMCBot", docs_url=None, redoc_url=None)

# 2. ดึง Token และ Secret จาก Environment Variables
LINE_CHANNEL_ACCESS_TOKEN = os.getenv("LINE_CHANNEL_ACCESS_TOKEN", "")
LINE_CHANNEL_SECRET = os.getenv("LINE_CHANNEL_SECRET", "")

# Initialize Clients (รองรับทั้ง SDK v2 และ SDK v3)
client = UpdateTTClient()
line_bot_api = LineBotApi(LINE_CHANNEL_ACCESS_TOKEN)
handler = WebhookHandler(LINE_CHANNEL_SECRET)

# 📌 Configuration สำหรับ SDK v3
configuration = Configuration(access_token=LINE_CHANNEL_ACCESS_TOKEN)


# 3. Endpoint สำหรับ Render Health Check และ Uptime Robot
@app.get("/")
async def health_check():
    return {"status": "online", "service": "CSMCBot"}


def get_current_thailand_date() -> str:
    """ดึงวันที่ปัจจุบันของประเทศไทย ในรูปแบบ DD/MM/YYYY"""
    tz = pytz.timezone("Asia/Bangkok")
    now = datetime.now(tz)
    return now.strftime("%d/%m/%Y")


def generate_daily_report(selected_zones=None, selected_employees=None, work_date=None):
    """ดึงข้อมูล Ticket ที่ผ่านการคัดกรอง แล้วแปลงเป็นข้อความ"""
    
    if not work_date:
        work_date = get_current_thailand_date()

    filtered_tickets = client.fetch_filtered_tickets()

    logger.info(f"=== [DEBUG 1] ดึง filtered_tickets ได้ทั้งหมด: {len(filtered_tickets)} ใบ ===")

    raw_details = []
    for ticket in filtered_tickets:
        try:
            detail = client.get_ticket_detail(ticket)
            if detail:
                raw_details.append(detail)
        except Exception as e:
            logger.error(f"Error processing ticket detail: {e}")
            continue

    logger.info(f"=== [DEBUG 2] ผ่านเงื่อนไขเขตและแกะรายละเอียดสำเร็จ: {len(raw_details)} ใบ ===")

    line_message_text = parse_and_group_by_zone(
        raw_tickets_detail=raw_details,
        selected_employees=selected_employees,
        target_zones=selected_zones,
        work_date=work_date,
    )

    return line_message_text


def send_split_line_messages(target_id: str, full_text: str, reply_token: str = None, max_length: int = 3500):
    """
    ฟังก์ชันแบ่งส่งข้อความให้อยู่ในโควตาของ LINE API ป้องกัน Error 400
    - หั่นข้อความไม่เกิน 3,500 ตัวอักษรต่อบอลลูน
    - รวมเป็น List แล้วยิงพร้อมกันทีเดียว (ไม่เกิน 5 บอลลูนต่อ Request)
    """
    if not full_text or not full_text.strip():
        return

    lines = full_text.split("\n")
    chunks = []
    current_chunk = ""

    for line in lines:
        if len(current_chunk) + len(line) + 1 > max_length:
            if current_chunk.strip():
                chunks.append(current_chunk.strip())
            current_chunk = line + "\n"
        else:
            current_chunk += line + "\n"

    if current_chunk.strip():
        chunks.append(current_chunk.strip())

    if not chunks:
        return

    # ลิมิต LINE API ส่งได้สูงสุด 5 บอลลูนต่อ 1 Request
    chunks = chunks[:5]
    messages_to_send = [TextSendMessage(text=c) for c in chunks if c.strip()]

    if not messages_to_send:
        return

    # กรณีส่งตอบกลับผ่าน Webhook
    if reply_token:
        try:
            line_bot_api.reply_message(reply_token, messages_to_send)
            return
        except Exception as e:
            logger.warning(f"Reply message failed, switching to push_message: {e}")

    # กรณีส่งแบบ Push Message (Cron-Job หรือ Fallback)
    try:
        line_bot_api.push_message(target_id, messages_to_send)
    except LineBotApiError as e:
        logger.error(f"Push Message Error ({e.status_code}): {e.error.message}")


def process_and_send_reply(reply_token: str, target_id: str, user_id: str = None):
    """
    ดึงข้อมูลและส่งรายงานผ่าน Reply Message (สำหรับงานกดสั่ง manual 'สรุป')
    """
    is_processing = True

    def keep_loading_alive():
        target_user = user_id or target_id
        if target_user and not target_user.startswith(("G", "C")):
            while is_processing:
                time.sleep(50)
                if not is_processing:
                    break
                try:
                    with ApiClient(configuration) as api_client:
                        v3_api = MessagingApi(api_client)
                        v3_api.show_loading_animation(
                            ShowLoadingAnimationRequest(
                                chat_id=target_user, loading_seconds=60
                            )
                        )
                except Exception as e:
                    logger.warning(f"Could not refresh loading animation: {e}")

    loading_thread = threading.Thread(target=keep_loading_alive, daemon=True)
    loading_thread.start()

    try:
        report_text = generate_daily_report()
        if not report_text:
            report_text = "ℹ️ ไม่พบบันทึกงานนัดหมายของช่างในทีมสำหรับวันนี้ครับ"

        # ส่งข้อความแบบแมนนวล (ดึงทั้งวันนี้และวันถัดไป)
        send_split_line_messages(target_id=target_id, full_text=report_text, reply_token=reply_token)

    except Exception as e:
        logger.error(f"Error processing report: {e}")
        try:
            line_bot_api.reply_message(
                reply_token,
                TextSendMessage(text=f"❌ เกิดข้อผิดพลาดในการดึงข้อมูล: {e}")
            )
        except Exception:
            pass
    finally:
        is_processing = False


@app.post("/webhook")
async def callback(request: Request, background_tasks: BackgroundTasks):
    """Endpoint สำหรับรับ Webhook จาก Cloudflare Router / LINE"""
    body_bytes = await request.body()
    body = body_bytes.decode("utf-8")

    try:
        data = json.loads(body)
        events = data.get("events", [])

        for event_data in events:
            if event_data.get("type") == "message" and event_data.get("message", {}).get("type") == "text":
                msg_text = event_data["message"]["text"].strip()
                reply_token = event_data.get("replyToken")
                
                source = event_data.get("source", {})
                source_type = source.get("type")
                user_id = source.get("userId")

                if source_type == "group":
                    target_id = source.get("groupId")
                elif source_type == "room":
                    target_id = source.get("roomId")
                else:
                    target_id = user_id

                if msg_text == "สรุป":
                    if source_type in ["group", "room"]:
                        background_tasks.add_task(process_and_send_reply, reply_token, target_id, user_id)
                    else:
                        try:
                            if user_id:
                                with ApiClient(configuration) as api_client:
                                    line_bot_api_v3 = MessagingApi(api_client)
                                    line_bot_api_v3.show_loading_animation(
                                        ShowLoadingAnimationRequest(
                                            chat_id=user_id, loading_seconds=60
                                        )
                                    )
                        except Exception as e:
                            logger.warning(f"Could not show loading animation: {e}")

                        background_tasks.add_task(process_and_send_reply, reply_token, target_id, user_id)

                elif msg_text.lower() in ["สวัสดี", "เมนู", "help"]:
                    line_bot_api.reply_message(
                        reply_token,
                        TextSendMessage(
                            text="🤖 CSMCBot พร้อมใช้งาน!\n\nพิมพ์คำว่า 'สรุป' เพื่อดึงรายงานตั๋วงานประจำวันได้เลยครับ"
                        ),
                    )

    except LineBotApiError as e:
        logger.error(f"LINE API Error ({e.status_code}): {e.error.message}")
    except Exception as e:
        logger.error(f"Error handling webhook: {e}")

    return "OK"


# ==========================================
# 📌 ฟังก์ชันสำหรับ Cron-Job (โพสต์อัตโนมัติ)
# ==========================================

AUTO_POST_GROUP_ID = "C4c22bf241dc4c2a48d159beb39e59314"
CRON_SECRET_KEY = "30633063"


def execute_auto_report():
    """ฟังก์ชันทำงานเบื้องหลัง: ดึงเฉพาะงานวันนี้ และส่ง Push Message เข้ากลุ่ม LINE"""
    try:
        logger.info("⏰ เริ่มประมวลผลรายงานอัตโนมัติสำหรับ Cron-Job...")
        
        report_text = generate_daily_report()
        if not report_text:
            report_text = "ℹ️ ไม่พบบันทึกงานนัดหมายของช่างในทีมสำหรับวันนี้ครับ"

        # 📌 ตัดข้อความเอาเฉพาะส่วน "งานค้างนัดวันนี้" เพื่อลดความยาวข้อความในการส่งอัตโนมัติ
        if "----------------------------------" in report_text:
            report_text = report_text.split("----------------------------------")[0].strip()

        send_split_line_messages(target_id=AUTO_POST_GROUP_ID, full_text=report_text)
        logger.info("✅ [Cron-Job] ส่งรายงานเข้ากลุ่ม LINE เรียบร้อยแล้ว!")
    except Exception as e:
        logger.error(f"❌ [Cron-Job] เกิดข้อผิดพลาดในการส่งรายงาน: {e}")


@app.get("/api/trigger-cron-report")
async def trigger_cron_report(
    background_tasks: BackgroundTasks, 
    key: str = Query(..., description="Secret Key สำหรับยืนยันตัวตน")
):
    """Endpoint สำหรับให้ Cron-job.org ยิงเข้ามาตามเวลาที่กำหนด"""
    if key != CRON_SECRET_KEY:
        raise HTTPException(status_code=403, detail="Unauthorized key")

    background_tasks.add_task(execute_auto_report)
    return {"status": "success", "message": "Report task queued successfully"}