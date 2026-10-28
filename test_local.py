# test_local.py
from app.updatett import UpdateTTClient
from app.parser import parse_and_group_by_zone, MAIN_ZONES, TEAM2_ZONES


def test_team1(client: UpdateTTClient):
    print("\n" + "=" * 50)
    print("🔵 [TEST TEAM 1] กำลังดึงและคัดกรองข้อมูลทีมที่ 1...")
    print("=" * 50)

    # 1. ดึงตั๋วของทีมที่ 1
    filtered_tickets = client.fetch_filtered_tickets(zone="2", worktype="Corporate Service")
    print(f"📊 พบบันทึกตั๋วทีมที่ 1 ที่เข้าเงื่อนไข: {len(filtered_tickets)} รายการ\n")

    if not filtered_tickets:
        print("⚠️ [Team 1] ไม่พบตั๋วที่ตรงตามเงื่อนไขในระบบ")
        return

    # 2. ดึงรายละเอียดของแต่ละตั๋ว
    print("🚀 [Team 1] กำลังดึงรายละเอียด (Detail) ของแต่ละตั๋ว...")
    raw_tickets_detail = []
    for t in filtered_tickets:
        detail = client.get_ticket_detail(t, is_team2=False)
        if detail:
            raw_tickets_detail.append(detail)

    print(f"\n✅ [Team 1] ผ่านเงื่อนไขเขตและแกะรายละเอียดสำเร็จ {len(raw_tickets_detail)} รายการ\n")

    # 3. จัดการ Format ข้อความ
    report_output = parse_and_group_by_zone(
        raw_tickets_detail=raw_tickets_detail,
        target_zones=MAIN_ZONES
    )
    
    print("📋 [ ผลลัพธ์รายงาน ทีมที่ 1 ]")
    print("-" * 50)
    print(report_output)
    print("-" * 50)


def test_team2(client: UpdateTTClient):
    print("\n" + "=" * 50)
    print("🟢 [TEST TEAM 2] กำลังดึงและคัดกรองข้อมูลทีมที่ 2...")
    print("=" * 50)

    # 1. ดึงตั๋วของทีมที่ 2
    filtered_tickets = client.fetch_filtered_tickets_team2(zone="2", worktype="Corporate Service")
    print(f"📊 พบบันทึกตั๋วทีมที่ 2 ที่เข้าเงื่อนไข: {len(filtered_tickets)} รายการ\n")

    if not filtered_tickets:
        print("⚠️ [Team 2] ไม่พบตั๋วที่ตรงตามเงื่อนไขในระบบ")
        return

    # 2. ดึงรายละเอียดของแต่ละตั๋ว (ใช้กฎเขตทีม 2: ราชเทวี, พญาไท, ปทุมวัน, ดินแดง)
    print("🚀 [Team 2] กำลังดึงรายละเอียด (Detail) ของแต่ละตั๋ว...")
    raw_tickets_detail = []
    for t in filtered_tickets:
        detail = client.get_ticket_detail(t, is_team2=True)
        if detail:
            raw_tickets_detail.append(detail)

    print(f"\n✅ [Team 2] ผ่านเงื่อนไขเขตและแกะรายละเอียดสำเร็จ {len(raw_tickets_detail)} รายการ\n")

    # 3. จัดการ Format ข้อความ
    report_output = parse_and_group_by_zone(
        raw_tickets_detail=raw_tickets_detail,
        target_zones=TEAM2_ZONES
    )
    
    print("📋 [ ผลลัพธ์รายงาน ทีมที่ 2 ]")
    print("-" * 50)
    print(report_output)
    print("-" * 50)


if __name__ == "__main__":
    client = UpdateTTClient()
    
    # 🎯 คุณสามารถเลือกรันเฉพาะทีม หรือ รันทั้งสองทีมพร้อมกันได้ตรงนี้:
    test_team1(client)   # ทดสอบทีมที่ 1
    #test_team2(client)   # ทดสอบทีมที่ 2