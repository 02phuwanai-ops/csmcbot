# app/parser.py
import re
from datetime import datetime
from bs4 import BeautifulSoup

ALIASES = {
    "K.Wittaya Saomoke": ["Wittaya Saomoke", "Wittaya", "Saomoke"],
    "K.Supoj Kaeokhrueng": ["Supoj Kaeokhrueng", "Supoj", "Kaeokhrueng"],
    "K.Chakares Sudjai": ["Chakares Sudjai", "Chakares", "Sudjai"],
    "K.Kampol Sinchai": ["Kampol Sinchai", "Kampol", "Sinchai"],
    "K.Phuwanai Sopradit": ["Phuwanai Sopradit", "Phuwanai", "Sopradit"],
}

MAIN_ZONES = [
    "พระโขนง",
    "คลองเตย",
    "ห้วยขวาง",
    "วัฒนา",
    "ลาดพร้าว",
    "วังทองหลาง",
]


def clean_text(text: str) -> str:
    """ล้างช่องว่างส่วนเกิน"""
    return re.sub(r"\s+", " ", text or "").strip()


def extract_appointment_info(full_text: str, target_date_short: str) -> dict:
    """
    ดึงวันที่และเวลานัดหมายจาก Log / HOLD SLA
    เช่น: HOLD SLA (07/06/26 17:30 to 04/09/26 14:00)
    """
    # 1. ค้นหา Pattern ช่วงวันที่ HOLD SLA: to DD/MM/YY HH:MM
    hold_matches = re.findall(
        r"to\s+(\d{2}/\d{2}/\d{2})\s+(\d{1,2}:\d{2})", full_text, re.IGNORECASE
    )
    if hold_matches:
        last_date_short, last_time = hold_matches[-1]
        if last_date_short == target_date_short:
            day, month, year = last_date_short.split("/")
            return {
                "date": f"{day}/{month}/20{year}",
                "time": f"{last_time} น.",
            }

    # 2. ค้นหา Pattern ทั่วไปที่มีวันที่ตรงกับ target_date_short ตามด้วยเวลา
    general_match = re.search(
        rf"{re.escape(target_date_short)}\s+(\d{{1,2}}[\.:]\d{{2}})", full_text
    )
    if general_match:
        time_clean = general_match.group(1).replace(".", ":")
        day, month, year = target_date_short.split("/")
        return {
            "date": f"{day}/{month}/20{year}",
            "time": f"{time_clean} น.",
        }

    return None


def parse_and_group_by_zone(
    raw_tickets_detail: list[dict],
    selected_employees: list = None,
    target_zones: list = None,
    work_date: str = "",
) -> str:
    """แกะข้อมูล คัดเฉพาะงานนัดวันนี้ และจัด Format ตามรูปแบบที่กำหนดสำหรับส่ง LINE"""

    # วันที่เป้าหมาย (รูปแบบ DD/MM/YY เช่น 04/09/26)
    today_dt = datetime.now()
    today_short = work_date if work_date else today_dt.strftime("%d/%m/%y")

    parsed_tickets = []

    for res_json in raw_tickets_detail:
        ticket_html = res_json.get("ticket_detail", "")
        circuit_html = res_json.get("circuit_detail", "")

        soup_ticket = BeautifulSoup(ticket_html, "html.parser")
        soup_circuit = BeautifulSoup(circuit_html, "html.parser")

        ticket_text = clean_text(soup_ticket.get_text(separator=" "))
        circuit_text = clean_text(soup_circuit.get_text(separator=" "))
        full_text = f"{ticket_text} {circuit_text}"

        # -------------------------------------------------------------
        # 1. เช็กนัดหมายว่าตรงกับ "วันนี้" หรือไม่ (ถ้าไม่ตรงให้ข้าม)
        # -------------------------------------------------------------
        appt_data = extract_appointment_info(full_text, today_short)
        if not appt_data:
            continue

        # -------------------------------------------------------------
        # 2. ดึง Ticket ID เจาะจง
        # -------------------------------------------------------------
        ticket_id = "N/A"
        selected_ticket_elem = soup_ticket.select_one("#select2-ticketID-container")
        if selected_ticket_elem:
            ticket_m = re.search(r"(TT\d{10,14})", selected_ticket_elem.get_text())
            if ticket_m:
                ticket_id = ticket_m.group(1)

        if ticket_id == "N/A":
            ticket_m = re.search(r"(TT\d{10,14})", full_text)
            ticket_id = ticket_m.group(1) if ticket_m else "N/A"

        # -------------------------------------------------------------
        # 3. ดึง Circuit ID & ชื่อบริษัท/สถานที่
        # -------------------------------------------------------------
        circuit_m = re.search(r"([A-Z]\d{5,8}|J\d{5,8})", full_text)
        circuit_id = circuit_m.group(1) if circuit_m else ""

        loc_m = re.search(
            r"LOCATION[^\:]*:\s*(.*?)(?=\[OPEN\]|SMC|TK:|Splitter|รายชื่อช่าง|Add Activity|WONUM|Link Status|HOLD SLA|$)",
            full_text,
            re.IGNORECASE,
        )
        location_address = clean_text(loc_m.group(1)) if loc_m else ""
        location_address = re.sub(r"^T\d+\s*", "", location_address)
        location_address = re.sub(r"^LOCATION VCARE:\s*", "", location_address, flags=re.IGNORECASE)

        company_disp = f"{circuit_id} {location_address}".strip()

        # -------------------------------------------------------------
        # 4. ดึง ชื่อผู้ติดต่อ & เบอร์โทรศัพท์ (เน้นเบอร์มือถือ)
        # -------------------------------------------------------------
        contact_name = "ลูกค้า"
        name_m = re.search(r"(?:ติดต่อ|คุณ|Khun)\s*([ก-๙a-zA-A]+)", full_text)
        if name_m:
            contact_name = f"คุณ{name_m.group(1)}"

        phone_number = "ไม่ระบุ"
        phone_m = re.search(r"(0[689]\d{8}|0\d{1,2}-\d{3}-\d{4})", full_text)
        if phone_m:
            phone_number = phone_m.group(1)

        parsed_tickets.append({
            "ticket_id": ticket_id,
            "company_info": company_disp or "ไม่ระบุสถานที่",
            "contact_person": contact_name,
            "phone": phone_number,
            "appt_date": appt_data["date"],
            "appt_time": appt_data["time"],
        })

    # -------------------------------------------------------------
    # 5. ประกอบร่างข้อความส่ง LINE ตามเป้าหมายที่กำหนด
    # -------------------------------------------------------------
    if not parsed_tickets:
        return "ไม่มีรายการงานซ่อมนัดวันนี้"

    output_blocks = []
    for t in parsed_tickets:
        block = (
            f"Ticket : {t['ticket_id']}\n"
            f"{t['company_info']}\n"
            f"ติดต่อ{t['contact_person']} : {t['phone']}\n"
            f"นัดลูกค้า {t['appt_date']} เวลา {t['appt_time']}"
        )
        output_blocks.append(block)

    return "\n\n".join(output_blocks)