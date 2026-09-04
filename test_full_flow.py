# test_full_flow.py
from app.auth import scrape_all_region_tickets
from app.parser import parse_and_group_by_zone

if __name__ == "__main__":
    # ดึงทุก Ticket ใน Region "WW BMA East"
    raw_tickets = scrape_all_region_tickets(region_name="WW BMA East", headless=False)

    if raw_tickets:
        print("\n⏳ กำลังคัดกรองเฉพาะ 6 เขต และ ช่างทั้ง 5 คน...")
        summary = parse_and_group_by_zone(raw_tickets_detail=raw_tickets)

        print("\n------------------- ผลลัพธ์สรุปจริงประจำวัน -------------------")
        print(summary)
        print("----------------------------------------------------------------")