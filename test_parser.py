# test_parser.py
from app.parser import parse_and_group_by_zone

# จำลองข้อมูล Response ที่สแกนได้จากเซิร์ฟเวอร์
mock_raw_tickets = [
    {
        "ticket_detail": """
            <span id="select2-ticketID-container">TT202609050001</span>
            LOCATION : บริษัท ตัวอย่าง จำกัด สุขุมวิท 55
            [OPEN] ติดต่อคุณ สมชาย
        """,
        "circuit_detail": """
            J1234567 HOLD SLA (01/09/26 10:00 to 05/09/26 14:00) 0812345678
        """,
    }
]

# เรียกฟังก์ชันโดยระบุวันที่ทดสอบ (เช่น '05/09/26')
result = parse_and_group_by_zone(mock_raw_tickets, work_date="05/09/26")

print("--- ผลลัพธ์การ Dry Run ---")
print(result)
print("--------------------------")