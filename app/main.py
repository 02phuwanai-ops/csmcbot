import os
from datetime import datetime
import pytz
from fastapi import FastAPI, Request, BackgroundTasks
from linebot import LineBotApi, WebhookHandler
from linebot.exceptions import InvalidSignatureError, LineBotApiError
from linebot.models import MessageEvent, TextMessage, TextSendMessage

from app.parser import parse_and_group_by_zone
from app.updatett import UpdateTTClient

app = FastAPI()

# 1. ดึง Token และ Secret จาก Environment Variables
LINE_CHANNEL_ACCESS_TOKEN = os.getenv("LINE_CHANNEL_ACCESS_TOKEN", "")
LINE_CHANNEL_SECRET = os.getenv("LINE_CHANNEL_SECRET", "")

# Initialize Clients
client = UpdateTTClient()
line_bot_api = LineBotApi(LINE_CHANNEL_ACCESS_TOKEN)
handler = WebhookHandler(LINE_CHANNEL_SECRET)


def get_current_thailand_date() -> str:
    """ดึงวันที่ปัจจุบันของประเทศไทย ในรูปแบบ DD/MM/YYYY"""
    tz = pytz.timezone("Asia/Bangkok")
    now = datetime.now(tz)
    return now.strftime("%d/%m/%Y")


def generate_daily_report(selected_zones=None, selected_employees=None, work_date=None):
    """ดึงข้อมูล Ticket ที่ผ่านการคัดกรอง แล้วแปลงเป็นข้อความ"""
    
    # 1. กำหนดวันที่เป็น วันนี้ (เวลาไทย) หากไม่ได้ระบุมา
    if not work_date:
        work_date = get_current_thailand_date()

    # 2. ทำการ Auto-Login และดึงรายการ Ticket
    filtered_tickets = client.fetch_filtered_tickets()

    # === PRINT DEBUG LOGS ===
    print(f"=== [DEBUG 1] ดึง filtered_tickets ได้ทั้งหมด: {len(filtered_tickets)} ใบ ===")
    if filtered_tickets:
        print(f"=== [DEBUG 1.1] รายการตั๋วที่เจอ: {filtered_tickets} ===")

    raw_details = []
    for ticket in filtered_tickets:
        try:
            detail = client.get_ticket_detail(ticket)
            if detail:
                raw_details.append(detail)
        except Exception as e:
            print(f"Error processing ticket detail: {e}")
            continue

    print(f"=== [DEBUG 2] ผ่านเงื่อนไขเขตและแกะรายละเอียดสำเร็จ: {len(raw_details)} ใบ ===")

    # 3. แปลงรายละเอียดตั๋วเป็นข้อความรายงาน
    line_message_text = parse_and_group_by_zone(
        raw_tickets_detail=raw_details,
        selected_employees=selected_employees,
        target_zones=selected_zones,
        work_date=work_date,
    )

    return line_message_text


def process_and_send_push(user_id: str):
    """ส่งผลลัพธ์ผ่าน Push Message แบบ Background Task"""
    try:
        report_text = generate_daily_report()
        if not report_text:
            report_text = "ℹ️ ไม่พบบันทึกงานนัดหมายของช่างในทีมสำหรับวันนี้ครับ"

        line_bot_api.push_message(user_id, TextSendMessage(text=report_text))
    except LineBotApiError as e:
        print(f"LINE Push Error ({e.status_code}): {e.error.message}")
    except Exception as e:
        print(f"Error sending push message: {e}")
        try:
            line_bot_api.push_message(
                user_id,
                TextSendMessage(text=f"❌ เกิดข้อผิดพลาดในการดึงข้อมูล: {e}"),
            )
        except Exception:
            pass


@app.post("/webhook")
async def callback(request: Request, background_tasks: BackgroundTasks):
    """Endpoint สำหรับรับ Webhook จาก LINE"""
    signature = request.headers.get("X-Line-Signature", "")
    body = (await request.body()).decode("utf-8")

    try:
        events = handler.parser.parse(body, signature)
        for event in events:
            if isinstance(event, MessageEvent) and isinstance(event.message, TextMessage):
                msg_text = event.message.text.strip()
                user_id = event.source.user_id

                if msg_text in ["ดึงงานวันนี้", "งานวันนี้", "job", "Job", "สรุป", "สรุปวันนี้"]:
                    line_bot_api.reply_message(
                        event.reply_token,
                        TextSendMessage(
                            text="⏳ รับคำสั่งเรียบร้อยแล้ว กำลังดึงข้อมูลงานนัดวันนี้ สักครู่นะครับ..."
                        ),
                    )
                    background_tasks.add_task(process_and_send_push, user_id)

                elif msg_text in ["สวัสดี", "เมนู", "help"]:
                    line_bot_api.reply_message(
                        event.reply_token,
                        TextSendMessage(
                            text="🤖 CSMCBot พร้อมใช้งาน!\n\nพิมพ์คำว่า 'สรุป' หรือ 'งานวันนี้' เพื่อดึงรายงานตั๋วงานประจำวันได้เลยครับ"
                        ),
                    )

    except InvalidSignatureError:
        print("Invalid Signature. Check LINE_CHANNEL_SECRET.")
    except LineBotApiError as e:
        print(f"LINE API Error ({e.status_code}): {e.error.message}")
    except Exception as e:
        print(f"Error handling webhook: {e}")

    return "OK"