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

# รายการเบอร์ช่างเพื่อคัดออกจากเบอร์ลูกค้า
TECH_PHONES = [
    "0820054606", "0970642598", "0820054570", "0834903149",
    "0910024273", "0824669506", "0993515969", "0826779358",
    "0968950525", "0852151700", "0829935069"
]


def clean_text(text: str) -> str:
    """ล้างช่องว่างส่วนเกิน"""
    return re.sub(r"\s+", " ", text or "").strip()

def extract_appointment_info(full_text: str, target_date_short: str) -> dict:
    """
    ดึงวันที่และเวลานัดหมายจาก Log / HOLD SLA
    เช่น: HOLD SLA (05/09/26 22:15 to 06/09/26 09:00) หรือ 04/09/2026 14:00
    """
    parts = target_date_short.split("/")
    day, month = parts[0], parts[1]
    raw_year = parts[2]

    # คำนวณปี 2 หลัก และ 4 หลัก ป้องกันการซ้ำซ้อน (202026)
    year_short = raw_year[-2:]
    year_full = f"20{year_short}"

    # 1. ค้นหา Pattern ช่วงวันที่ HOLD SLA: to DD/MM/YY(YY) HH:MM
    hold_matches = re.findall(
        r"to\s+(\d{2}/\d{2}/\d{2,4})\s+(\d{1,2}[:\.]\d{2})", full_text, re.IGNORECASE
    )
    if hold_matches:
        last_date, last_time = hold_matches[-1]
        
        # จัดรูปแบบวันที่ปลด Hold SLA ให้ถูกต้องโดยตรง
        h_parts = last_date.split("/")
        h_year = f"20{h_parts[2]}" if len(h_parts[2]) == 2 else h_parts[2]
        time_clean = last_time.replace(".", ":")
        
        return {
            "date": f"{h_parts[0]}/{h_parts[1]}/{h_year}",
            "time": f"{time_clean} น.",
        }

    # 2. ค้นหา Pattern ทั่วไปกรณีไม่มี Log HOLD SLA
    date_pattern = f"({re.escape(f'{day}/{month}/{year_short}')}|{re.escape(f'{day}/{month}/{year_full}')})"
    general_match = re.search(
        rf"{date_pattern}\s+(\d{{1,2}}[\.:]\d{{2}})", full_text
    )
    if general_match:
        time_clean = general_match.group(2).replace(".", ":")
        return {
            "date": f"{day}/{month}/{year_full}",
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
        if not isinstance(res_json, dict):
            continue

        # รวมข้อความทั้งหมดจาก JSON Response ให้ครอบคลุมทุก Key ที่เซิร์ฟเวอร์ส่งมา
        ticket_html = (
            res_json.get("ticket_detail", "")
            or res_json.get("detail", "")
            or res_json.get("html", "")
            or str(res_json)
        )
        circuit_html = res_json.get("circuit_detail", "")

        soup_ticket = BeautifulSoup(str(ticket_html), "html.parser")
        soup_circuit = BeautifulSoup(str(circuit_html), "html.parser")

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
        # ปรับ [A-Z] เป็น [A-SU-Z] เพื่อยกเว้นตัว T ไม่ให้จับโดน T2026...
        circuit_m = re.search(r"([A-SU-Z]\d{5,8}|J\d{5,8})", full_text)
        circuit_id = circuit_m.group(1) if circuit_m else ""

        loc_m = re.search(
            r"LOCATION[^\:]*:\s*(.*?)(?=\[OPEN\]|SMC|TK:|Splitter|รายชื่อช่าง|Add Activity|WONUM|Link Status|HOLD SLA|$)",
            full_text,
            re.IGNORECASE,
        )
        location_address = clean_text(loc_m.group(1)) if loc_m else ""
        
        # คลีนตัวเลขขยะ หรือคำว่า LOCATION VCARE ออกจากตัวสถานที่
        location_address = re.sub(r"^(?:T?\d+|LOCATION VCARE:)\s*", "", location_address, flags=re.IGNORECASE)
        location_address = clean_text(location_address)

        company_disp = f"{circuit_id} {location_address}".strip()
        # -------------------------------------------------------------
        # 4. ดึง ชื่อผู้ติดต่อ & เบอร์โทรศัพท์ (เน้นเบอร์มือถือลูกค้า)
        # -------------------------------------------------------------
        contact_name = "ลูกค้า"
        # ปรับแก้ให้รองรับคำว่า "คุณ" ที่มีเว้นวรรค และดึงชื่อ-นามสกุลได้ถูกต้อง
        name_m = re.search(r"(?:ติดต่อ|คุณ|Khun)\s*([ก-๙a-zA-Z]+(?:\s+[ก-๙a-zA-Z]+)?)", full_text)
        if name_m:
            c_name = name_m.group(1).strip()
            contact_name = c_name if c_name.startswith("คุณ") else f"คุณ{c_name}"

        # ค้นหาเบอร์มือถือที่ขึ้นต้นด้วย 06, 08, 09 ที่ไม่ใช่เบอร์ช่าง
        phone_number = "ไม่ระบุ"
        all_phones = re.findall(r"0[689]\d{8}", full_text)
        for ph in all_phones:
            if ph not in TECH_PHONES:
                phone_number = ph
                break

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