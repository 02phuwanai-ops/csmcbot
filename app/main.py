# main.py
import os
from fastapi import FastAPI, Request, BackgroundTasks
from linebot import LineBotApi, WebhookHandler
from linebot.models import MessageEvent, TextMessage, TextSendMessage

from app.parser import parse_and_group_by_zone
from app.updatett import UpdateTTClient

app = FastAPI()
client = UpdateTTClient()

# ดึง Token และ Secret จาก Environment Variables บน Render
LINE_CHANNEL_ACCESS_TOKEN = os.getenv("LINE_CHANNEL_ACCESS_TOKEN", "")
LINE_CHANNEL_SECRET = os.getenv("LINE_CHANNEL_SECRET", "")

line_bot_api = LineBotApi(LINE_CHANNEL_ACCESS_TOKEN)
handler = WebhookHandler(LINE_CHANNEL_SECRET)


def generate_daily_report(
    selected_zones=None, selected_employees=None, work_date=""
):
    """ดึงข้อมูล Ticket ทั้งหมดจากระบบ แล้วแปลงเป็นข้อความตาม Format"""
    # 1. ดึงรายการ ticketID ทั้งหมดจากหน้าเว็บหลัก
    all_ticket_ids = client.fetch_all_tickets_from_web()

    # 2. วนลูปดึงรายละเอียดเชิงลึกของทุก Ticket
    raw_details = []
    for tid in all_ticket_ids:
        try:
            detail = client.get_ticket_detail(tid)
            if detail:
                raw_details.append(detail)
        except Exception:
            continue

    # 3. ส่งเข้า Parser เพื่อแกะนัดหมายวันนี้และจัด Format
    line_message_text = parse_and_group_by_zone(
        raw_tickets_detail=raw_details,
        selected_employees=selected_employees,
        target_zones=selected_zones,
        work_date=work_date,
    )

    return line_message_text


def process_and_reply(reply_token: str):
    """ฟังก์ชันประมวลผลเบื้องหลัง (Background Task) เพื่อส่งผลลัพธ์กลับ LINE"""
    try:
        report_text = generate_daily_report()
        line_bot_api.reply_message(
            reply_token, TextSendMessage(text=report_text)
        )
    except Exception as e:
        line_bot_api.reply_message(
            reply_token,
            TextSendMessage(text=f"❌ เกิดข้อผิดพลาดในการดึงข้อมูล: {e}"),
        )


@app.post("/webhook")
async def callback(request: Request, background_tasks: BackgroundTasks):
    """Endpoint สำหรับรับ Webhook จาก LINE"""
    signature = request.headers.get("X-Line-Signature", "")
    body = (await request.body()).decode("utf-8")

    try:
        handler.handle(body, signature)
    except Exception as e:
        print(f"Error handling webhook: {e}")

    return "OK"


@handler.add(MessageEvent, message=TextMessage)
def handle_message(event):
    msg_text = event.message.text.strip()

    # ดักจับคำสั่งจากมือถือ
    if msg_text in ["ดึงงานวันนี้", "งานวันนี้", "job", "Job"]:
        # 1. แจ้งเตือนผู้ใช้ก่อนเพราะการดึงข้อมูลใช้เวลาสักครู่
        line_bot_api.reply_message(
            event.reply_token,
            TextSendMessage(
                text="⏳ รับคำสั่งเรียบร้อยแล้ว กำลังดึงข้อมูลงานนัดวันนี้ สักครู่นะครับ..."
            ),
        )
        # 2. สั่งรันกระบวนการดึงข้อมูลและส่งผลลัพธ์ในภายหลัง
        process_and_reply(event.reply_token)