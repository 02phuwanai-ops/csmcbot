from app.update_tt import UpdateTTClient # ปรับ path ให้ตรงกับโครงสร้างโฟลเดอร์ของคุณ

client = UpdateTTClient()

# 1. ดึงรายการ Ticket
tickets = client.fetch_filtered_tickets()
print(f"พบตั๋วทั้งหมด: {len(tickets)} ใบ")

# 2. ลองดึงรายละเอียดตั๋วใบแรกมาดูวันนัด
if tickets:
    first_ticket = tickets[0]
    detail = client.get_ticket_detail(first_ticket)
    
    # ดึง log_text จากรายละเอียดตั๋ว (ปรับชื่อ key ให้ตรงตามที่ API ส่งกลับมา)
    log_text = detail.get("remark") or detail.get("log") or ""
    
    # ทดสอบฟังก์ชัน parse_hold_sla ตัวใหม่
    hold_info = client.parse_hold_sla(log_text, raw_data=detail)
    
    print("\n--- ผลการทดสอบดึงข้อมูล ---")
    print("Ticket:", client.extract_ticket_id(first_ticket))
    print("Is Hold:", hold_info["is_hold"])
    print("Reschedule Time (วันนัด):", hold_info["reschedule_time"])
    print("Reason:", hold_info["reason"])