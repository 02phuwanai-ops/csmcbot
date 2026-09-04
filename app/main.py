import os
from fastapi import FastAPI, Request, BackgroundTasks
from linebot import LineBotApi, WebhookHandler
from linebot.models import MessageEvent, TextMessage, TextSendMessage

from app.parser import parse_and_group_by_zone
from app.updatett import UpdateTTClient

app = FastAPI()

# 1. ดึง Token, Secret และ Cookie จาก Environment Variables บน Render
LINE_CHANNEL_ACCESS_TOKEN = os.getenv("LINE_CHANNEL_ACCESS_TOKEN", "")
LINE_CHANNEL_SECRET = os.getenv("LINE_CHANNEL_SECRET", "")
COOKIES_STR = os.getenv("COOKIES_STR", "")

# 2. เริ่มต้น Client พร้อม Cookie
client = UpdateTTClient(cookies_str=COOKIES_STR)

line_bot_api = LineBotApi(LINE_CHANNEL_ACCESS_TOKEN)
handler = WebhookHandler(LINE_CHANNEL_SECRET)


def generate_daily_report(
    selected_zones=None, selected_employees=None, work_date=""
):
    """ดึงข้อมูล Ticket ที่ผ่านการคัดกรองชื่อช่างในทีม แล้วแปลงเป็นข้อความตาม Format"""
    
    # ดึง Cookie ล่าสุดเสมอเพื่อความชัวร์ก่อนยิง API
    latest_cookies = os.getenv("COOKIES_STR", COOKIES_STR)
    if latest_cookies:
        client.set_cookies_from_string(latest_cookies)
    
    # 1. ดึงเฉพาะ ticket ที่ผ่านการเช็คชื่อช่าง 7 คน (คัดตั้งแต่ API Level)
    filtered_tickets = client.fetch_filtered_tickets()

    # 2. วนลูปยิง API ดึงรายละเอียดเชิงลึกเฉพาะ Ticket ที่ตรงตามเงื่อนไขช่าง
    raw_details = []
    for ticket in filtered_tickets:
        try:
            # ยิง POST ตรงเข้า /get_ticketDeatil
            detail = client.get_ticket_detail(ticket)
            if detail:  # จะได้เฉพาะอันที่ผ่าน 6 เขตพื้นที่กลับมา
                raw_details.append(detail)
        except Exception as e:
            print(f"Error processing ticket detail: {e}")
            continue

    # 3. ส่งเข้า Parser เพื่อแกะนัดหมายวันนี้และจัด Format
    line_message_text = parse_and_group_by_zone(
        raw_tickets_detail=raw_details,
        selected_employees=selected_employees,
        target_zones=selected_zones,
        work_date=work_date,
    )

    return line_message_text


def process_and_send_push(user_id: str):
    """ฟังก์ชันประมวลผลเบื้องหลัง (Background Task) ส่งผลลัพธ์ผ่าน Push Message"""
    try:
        report_text = generate_daily_report()
        
        # ป้องกันส่งข้อความว่างกรณีไม่พบงาน
        if not report_text:
            report_text = "ℹ️ ไม่พบบันทึกงานนัดหมายของช่างในทีมสำหรับวันนี้ครับ"

        line_bot_api.push_message(
            user_id, TextSendMessage(text=report_text)
        )
    except Exception as e:
        print(f"Error sending push message: {e}")
        line_bot_api.push_message(
            user_id,
            TextSendMessage(text=f"❌ เกิดข้อผิดพลาดในการดึงข้อมูล: {e}"),
        )


@app.post("/webhook")
async def callback(request: Request, background_tasks: BackgroundTasks):
    """Endpoint สำหรับรับ Webhook จาก LINE"""
    signature = request.headers.get("X-Line-Signature", "")
    body = (await request.body()).decode("utf-8")

    try:
        # ใช้ handler เพื่อประมวลผล Event
        events = handler.parser.parse(body, signature)
        for event in events:
            if isinstance(event, MessageEvent) and isinstance(event.message, TextMessage):
                msg_text = event.message.text.strip()
                user_id = event.source.user_id

                if msg_text in ["ดึงงานวันนี้", "งานวันนี้", "job", "Job"]:
                    # ตอบกลับทันทีใน 1 วินาที
                    line_bot_api.reply_message(
                        event.reply_token,
                        TextSendMessage(
                            text="⏳ รับคำสั่งเรียบร้อยแล้ว กำลังดึงข้อมูลงานนัดวันนี้ สักครู่นะครับ..."
                        ),
                    )
                    # โยนงานหนักเข้า Background Task ของ FastAPI
                    background_tasks.add_task(process_and_send_push, user_id)
    except Exception as e:
        print(f"Error handling webhook: {e}")

    return "OK"