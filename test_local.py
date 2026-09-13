# test_local.py
import json
from app.updatett import UpdateTTClient
from app.parser import parse_and_group_by_zone

def run_test():
    print("🚀 [1/3] กำลังเริ่มต้นเชื่อมต่อ และ ดึงตั๋วจากระบบ CSMC...")
    client = UpdateTTClient()

    # 1. ดึงตั๋วที่ผ่านการกรอง (รวม TT และ INC)
    filtered_tickets = client.fetch_filtered_tickets(zone="2", worktype="Corporate Service")
    print(f"📊 พบบันทึกตั๋วที่เข้าเงื่อนไข: {len(filtered_tickets)} รายการ\n")

    if not filtered_tickets:
        print("⚠️ ไม่พบตั๋วที่ตรงตามเงื่อนไขในระบบ")
        return

    # 2. ดึงรายละเอียดของแต่ละตั๋ว (แบบ Multi-threading ขนานกัน)
    print("🚀 [2/3] กำลังดึงรายละเอียด (Detail) ของแต่ละตั๋ว...")
    raw_tickets_detail = client.fetch_details_in_parallel(filtered_tickets, zone="2", worktype="Corporate Service", max_workers=8)

    print(f"\n✅ ดึงรายละเอียดสำเร็จทั้งหมด {len(raw_tickets_detail)} รายการ\n")

    # 3. นำข้อมูลไปแปลงผลผ่าน Parser
    print("🚀 [3/3] กำลังจัดกลุ่มและ Format ข้อความรายงาน...")
    print("=" * 50)
    
    # สามารถใส่วันที่จำลองได้ เช่น work_date="09/09/2026" หรือปล่อยว่างไว้เพื่อใช้วันนี้
    report_output = parse_and_group_by_zone(raw_tickets_detail)
    
    print(report_output)
    print("=" * 50)

if __name__ == "__main__":
    run_test()