# app/main.py
import os
import logging
from datetime import datetime
import pytz
from fastapi import FastAPI, Request, BackgroundTasks
from linebot import LineBotApi, WebhookHandler
from linebot.exceptions import InvalidSignatureError, LineBotApiError
from linebot.models import MessageEvent, TextMessage, TextSendMessage

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

# Initialize Clients
client = UpdateTTClient()
line_bot_api = LineBotApi(LINE_CHANNEL_ACCESS_TOKEN)
handler = WebhookHandler(LINE_CHANNEL_SECRET)


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


def process_and_send_push(target_id: str):
    """ส่งผลลัพธ์ผ่าน Push Message รองรับทั้ง User ID และ Group ID"""
    try:
        report_text = generate_daily_report()
        if not report_text:
            report_text = "ℹ️ ไม่พบบันทึกงานนัดหมายของช่างในทีมสำหรับวันนี้ครับ"

        line_bot_api.push_message(target_id, TextSendMessage(text=report_text))
    except LineBotApiError as e:
        logger.error(f"LINE Push Error ({e.status_code}): {e.error.message}")
    except Exception as e:
        logger.error(f"Error sending push message: {e}")
        try:
            line_bot_api.push_message(
                target_id,
                TextSendMessage(text=f"❌ เกิดข้อผิดพลาดในการดึงข้อมูล: {e}"),
            )
        except Exception:
            pass


@app.post("/webhook")
async def callback(request: Request, background_tasks: BackgroundTasks):
    """Endpoint สำหรับรับ Webhook จาก LINE (รองรับทั้งแชตเดี่ยวและกลุ่ม)"""
    signature = request.headers.get("X-Line-Signature", "")
    body = (await request.body()).decode("utf-8")

    try:
        events = handler.parser.parse(body, signature)
        for event in events:
            if isinstance(event, MessageEvent) and isinstance(event.message, TextMessage):
                msg_text = event.message.text.strip()
                
                # 🎯 เช็กประเภทแหล่งที่มา (กลุ่ม, ห้องแชท, หรือผู้ใช้ทั่วไป)
                source_type = event.source.type
                if source_type == "group":
                    target_id = event.source.group_id
                elif source_type == "room":
                    target_id = event.source.room_id
                else:
                    target_id = event.source.user_id

                # คีย์เวิร์ดสำหรับดึงรายงาน
                if msg_text in ["ดึงงานวันนี้", "งานวันนี้", "job", "Job", "สรุป", "สรุปวันนี้", "งาน", "งานค้าง", "report"]:
                    line_bot_api.reply_message(
                        event.reply_token,
                        TextSendMessage(
                            text="⏳ รับคำสั่งเรียบร้อยแล้ว กำลังดึงข้อมูลงานนัดวันนี้ สักครู่นะครับ..."
                        ),
                    )
                    background_tasks.add_task(process_and_send_push, target_id)

                elif msg_text in ["สวัสดี", "เมนู", "help"]:
                    line_bot_api.reply_message(
                        event.reply_token,
                        TextSendMessage(
                            text="🤖 CSMCBot พร้อมใช้งาน!\n\nพิมพ์คำว่า 'สรุป' หรือ 'งานวันนี้' เพื่อดึงรายงานตั๋วงานประจำวันได้เลยครับ"
                        ),
                    )

    except InvalidSignatureError:
        logger.error("Invalid Signature. Check LINE_CHANNEL_SECRET.")
    except LineBotApiError as e:
        logger.error(f"LINE API Error ({e.status_code}): {e.error.message}")
    except Exception as e:
        logger.error(f"Error handling webhook: {e}")

    return "OK"