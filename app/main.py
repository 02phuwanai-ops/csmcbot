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
logger = logging.getLogger("csmcbot")

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


def send_split_line_messages(target_id: str, full_text: str, reply_token: str = None, max_length: int = 4000):
    """
    ฟังก์ชันสำหรับตัดแบ่งข้อความยาวๆ เป็นหลายๆ ข้อความ (ไม่เกิน 4,000 ตัวอักษรต่อกล่อง) 
    เพื่อป้องกันไม่ให้เกินลิมิต 5,000 ตัวอักษรของ LINE API
    """
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

    # ส่งข้อความแรกผ่าน reply_message (ถ้ามี reply_token และเป็นการส่งตอบกลับ)
    first_index = 0
    if reply_token:
        try:
            line_bot_api.reply_message(reply_token, TextSendMessage(text=chunks[0]))
            first_index = 1
        except Exception as e:
            logger.warning(f"Reply message failed or token expired, switching to push: {e}")
            first_index = 0

    # ข้อความที่เหลือทั้งหมดส่งด้วย push_message
    for i in range(first_index, len(chunks)):
        line_bot_api.push_message(target_id, TextSendMessage(text=chunks[i]))


def process_and_send_reply(reply_token: str, target_id: str, user_id: str = None):
    """
    ดึงข้อมูลและส่งรายงานผ่าน Reply Message
    หาก reply_token หมดอายุหรือถูกใช้ไปแล้ว จะ Fallback ไปใช้ Push Message สำรอง
    มีระบบ Keep-Alive คอยส่ง Loading Animation ซ้ำทุกๆ 50 วินาที สำหรับแชตเดี่ยว
    """
    is_processing = True

    # 📌 ฟังก์ชันช่วยวนยิง Loading Animation ซ้ำทุกๆ 50 วินาที (เฉพาะแชตเดี่ยว)
    def keep_loading_alive():
        target_user = user_id or target_id
        if target_user and not target_user.startswith(("G", "C")):
            while is_processing:
                time.sleep(50)  # ยิงต่ออายุก่อนจะหมดขีดจำกัด 60 วินาทีของ LINE
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

    # เริ่ม Thread ทำหน้าที่ต่ออายุ Loading Animation ในพื้นหลัง
    loading_thread = threading.Thread(target=keep_loading_alive, daemon=True)
    loading_thread.start()

    try:
        report_text = generate_daily_report()
        if not report_text:
            report_text = "ℹ️ ไม่พบบันทึกงานนัดหมายของช่างในทีมสำหรับวันนี้ครับ"

        # แบ่งส่งข้อความอัตโนมัติป้องกันติด 5,000 ตัวอักษร
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
        # 🛑 หยุดตัววนยิง Loading Animation ทันทีเมื่อทำงานเสร็จ
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
                
                # 🎯 เช็กประเภทแหล่งที่มา (กลุ่ม, ห้องแชท, หรือผู้ใช้ทั่วไป)
                source = event_data.get("source", {})
                source_type = source.get("type")
                user_id = source.get("userId")

                if source_type == "group":
                    target_id = source.get("groupId")
                elif source_type == "room":
                    target_id = source.get("roomId")
                else:
                    target_id = user_id

                # คีย์เวิร์ดสำหรับดึงรายงาน
                if msg_text == "สรุป":
                    # 📌 กรณีพิมพ์ในกลุ่ม หรือ ห้องแชทหลายคน (ตัดข้อความตอบรับเบื้องต้นออกแล้ว)
                    if source_type in ["group", "room"]:
                        background_tasks.add_task(process_and_send_reply, reply_token, target_id, user_id)

                    # 📌 กรณีพิมพ์ในแชตเดี่ยว (1-on-1)
                    else:
                        # 1. แสดงไอคอน Loading Animation (เริ่มต้นตั้งไว้ 60 วินาที)
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

                        # 2. รันการดึงรายงานเป็น Background Task (ส่งรายงานด้วย reply_message ฟรี 100%)
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
# 📌 เพิ่มฟังก์ชันสำหรับ Cron-Job (โพสต์อัตโนมัติ)
# ==========================================

# 1. ใส่ Group ID ของกลุ่ม LINE ที่ต้องการให้โพสต์
AUTO_POST_GROUP_ID = "C4c22bf241dc4c2a48d159beb39e59314"

# 2. ตั้ง Secret Key เพื่อความปลอดภัย
CRON_SECRET_KEY = "30633063"


def execute_auto_report():
    """ฟังก์ชันทำงานเบื้องหลัง: ดึงรายงานและส่ง Push Message เข้ากลุ่ม LINE"""
    try:
        logger.info("⏰ เริ่มประมวลผลรายงานอัตโนมัติสำหรับ Cron-Job...")
        
        # ดึงรายงานด้วยฟังก์ชัน generate_daily_report()
        report_text = generate_daily_report()
        if not report_text:
            report_text = "ℹ️ ไม่พบบันทึกงานนัดหมายของช่างในทีมสำหรับวันนี้ครับ"

        # แบ่งส่งข้อความอัตโนมัติ ไม่เกิน 4,000 ตัวอักษรต่อบอลลูน
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

    # สั่งให้ประมวลผลใน Background Tasks เพื่อตอบกลับ Cron-Job ทันทีและป้องกัน Timeout
    background_tasks.add_task(execute_auto_report)
    
    return {"status": "success", "message": "Report task queued successfully"}