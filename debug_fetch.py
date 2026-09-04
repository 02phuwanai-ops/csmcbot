import requests

base_url = "https://csmcbot.truecorp.co.th/updatett/Updatett"
headers = {
    "Accept": "application/json, text/javascript, */*; q=0.01",
    "Content-Type": "application/x-www-form-urlencoded; charset=UTF-8",
    "X-Requested-With": "XMLHttpRequest",
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"
}

# 1. ทดสอบยิงดึงรายละเอียด Ticket เชิงลึก (ระบุ Ticket ID จริงที่คุณเห็นบนหน้าเว็บ เช่น TT2026xxxxxx)
test_ticket_id = "TT202609127589"  # <--- ลองเปลี่ยนเป็น Ticket ID จริงที่มีบนหน้าเว็บตอนนี้

payload = {
    "ticketID": test_ticket_id,
    "zone": "2",
    "worktype": "Corporate Service"
}

endpoints = ["get_ticketDeatil", "get_activity_detail", "get_link_status"]

print(f"🔍 เริ่มทดสอบยิง API สำหรับ Ticket: {test_ticket_id}\n")

for ep in endpoints:
    url = f"{base_url}/{ep}"
    try:
        res = requests.post(url, data=payload, headers=headers, timeout=15)
        print(f"📌 Endpoint: {ep}")
        print(f"Status Code: {res.status_code}")
        if res.status_code == 200:
            print(f"Response Data (300 ตัวแรก):\n{res.text[:300]}\n")
        else:
            print(f"Error Response: {res.text[:100]}\n")
    except Exception as e:
        print(f"Error: {e}\n")