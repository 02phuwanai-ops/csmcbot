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

TECH_PHONES = [
    "0820054606", "0970642598", "0820054570", "0834903149",
    "0910024273", "0824669506", "0993515969", "0826779358",
    "0968950525", "0852151700", "0829935069"
]


def clean_text(text: str) -> str:
    """ล้างช่องว่างส่วนเกิน"""
    return re.sub(r"\s+", " ", text or "").strip()


def extract_appointment_info(full_text: str) -> dict:
    """ดึงวันที่และเวลานัดหมายจาก Log / HOLD SLA"""
    hold_matches = re.findall(
        r"(?:to|-|ถึง)\s*(\d{2}/\d{2}/\d{2,4})\s*(\d{1,2}[:\.]\d{2})", full_text, re.IGNORECASE
    )
    if hold_matches:
        last_date, last_time = hold_matches[-1]
        h_parts = last_date.split("/")
        h_year = f"20{h_parts[2]}" if len(h_parts[2]) == 2 else h_parts[2]
        time_clean = last_time.replace(".", ":")
        
        dt_obj = None
        try:
            dt_obj = datetime.strptime(f"{h_parts[0]}/{h_parts[1]}/{h_year} {time_clean}", "%d/%m/%Y %H:%M")
        except ValueError:
            pass

        return {
            "date": f"{h_parts[0]}/{h_parts[1]}/{h_year}",
            "time": f"{time_clean} น.",
            "datetime_obj": dt_obj or datetime.max
        }

    text_without_expected = re.sub(
        r"ExpectedDate\s*:\s*\d{2}/\d{2}/\d{2,4}\s+\d{1,2}[:\.]\d{2}",
        "",
        full_text,
        flags=re.IGNORECASE
    )

    general_match = re.search(
        r"(\d{2}/\d{2}/\d{2,4})\s+(\d{1,2}[\.:]\d{2})", text_without_expected
    )
    if general_match:
        g_date, g_time = general_match.group(1), general_match.group(2)
        h_parts = g_date.split("/")
        h_year = f"20{h_parts[2]}" if len(h_parts[2]) == 2 else h_parts[2]
        time_clean = g_time.replace(".", ":")

        dt_obj = None
        try:
            dt_obj = datetime.strptime(f"{h_parts[0]}/{h_parts[1]}/{h_year} {time_clean}", "%d/%m/%Y %H:%M")
        except ValueError:
            pass

        return {
            "date": f"{h_parts[0]}/{h_parts[1]}/{h_year}",
            "time": f"{time_clean} น.",
            "datetime_obj": dt_obj or datetime.max
        }

    return None


def parse_and_group_by_zone(
    raw_tickets_detail: list[dict],
    selected_employees: list = None,
    target_zones: list = None,
    work_date: str = "",
) -> str:
    """แกะข้อมูล คัดเฉพาะตั๋วที่ยังไม่ปิดงาน จัด Format และเรียงตามลำดับนัดหมาย"""

    today_dt = datetime.now()
    today_formatted = work_date if work_date else today_dt.strftime("%d/%m/%Y")
    
    t_parts = today_formatted.split("/")
    if len(t_parts[2]) == 2:
        today_formatted = f"{t_parts[0]}/{t_parts[1]}/20{t_parts[2]}"

    parsed_tickets = []

    for res_json in raw_tickets_detail:
        if not isinstance(res_json, dict):
            continue

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
        raw_json_str = clean_text(str(res_json))
        
        full_text = f"{ticket_text} {circuit_text} {raw_json_str}"

        # -------------------------------------------------------------
        # 0. กรองตั๋วที่ "ช่างแจ้งปิดงาน" ออก
        # -------------------------------------------------------------
        if "ช่างแจ้งปิดงาน" in full_text or "ขอปิดงาน" in full_text:
            continue

        # -------------------------------------------------------------
        # 1. ดึงข้อมูลวัน/เวลานัดหมาย
        # -------------------------------------------------------------
        appt_data = extract_appointment_info(full_text)
        if not appt_data:
            continue

        # -------------------------------------------------------------
        # 2. ดึง Ticket ID
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
        # 3. ดึง Circuit ID & ชื่อสถานที่ (กระชับ)
        # -------------------------------------------------------------
        # จับ Circuit ที่มี Prefix นำหน้า เช่น WDS51417, J02645, V02616
        circuit_m = re.search(r"\b([A-Z]{1,4}\d{4,8})\b", full_text)
        circuit_id = circuit_m.group(1) if circuit_m else ""

        loc_m = re.search(
            r"LOCATION[^\:]*:\s*(.*?)(?=\[OPEN\]|SMC|TK:|Splitter|รายชื่อช่าง|Add Activity|WONUM|Link Status|HOLD SLA|$)",
            full_text,
            re.IGNORECASE,
        )
        location_address = clean_text(loc_m.group(1)) if loc_m else ""
        
        # ตัดข้อความขยะ/ส่วนที่ไม่จำเป็นออก เช่น ไม่พบข้อมูล, ที่อยู่ตำบล/อำเภอ
        location_address = re.sub(r"^(?:T?\d+|LOCATION VCARE:)\s*", "", location_address, flags=re.IGNORECASE)
        location_address = re.sub(r"\s*(ไม่พบข้อมูล|กรุงเทพมหานคร|\d{5}).*", "", location_address, flags=re.IGNORECASE)
        # ตัดแขวง/เขตออกเพื่อความสั้นกระชับ
        location_address = re.sub(r"\s*(คลองเตยเหนือ|คลองเตย|คลองตันเหนือ|คลองตัน|ห้วยขวาง|บางกะปิ|สามเสนนอก|วัฒนา|พระโขนง|สุขุมวิท 23 - สุขุมวิท 23).*", "", location_address, flags=re.IGNORECASE)
        location_address = clean_text(location_address)

        circuit_disp = f"Circuit: {circuit_id} {location_address}".strip() if circuit_id else location_address

        # -------------------------------------------------------------
        # 4. ดึง ชื่อผู้ติดต่อ & เบอร์โทรศัพท์
        # -------------------------------------------------------------
        contact_name = ""
        name_m = re.search(r"(?:คุณ|Khun)\s*([ก-๙a-zA-Z]+)", full_text)
        if name_m:
            c_name = name_m.group(1).strip()
            if c_name not in ["ลูกค้า", "ช่าง"]:
                contact_name = f"คุณ{c_name}"

        phone_number = ""
        all_phones = re.findall(r"0[689]\d{8}", full_text)
        for ph in all_phones:
            if ph not in TECH_PHONES:
                phone_number = ph
                break

        # จัดข้อความผู้ติดต่อ
        contact_disp = ""
        if contact_name and phone_number:
            contact_disp = f"ติดต่อ{contact_name} : {phone_number}"
        elif contact_name:
            contact_disp = f"ติดต่อ{contact_name}"
        elif phone_number:
            contact_disp = f"ติดต่อคุณลูกค้า : {phone_number}"

        parsed_tickets.append({
            "ticket_id": ticket_id,
            "company_info": circuit_disp or "ไม่ระบุสถานที่",
            "contact_str": contact_disp,
            "appt_date": appt_data["date"],
            "appt_time": appt_data["time"],
            "datetime_obj": appt_data["datetime_obj"],
        })

    if not parsed_tickets:
        return "ไม่มีรายการงานซ่อมในระบบ"

    # -------------------------------------------------------------
    # 5. เรียงลำดับงานตาม วันที่ และ เวลา
    # -------------------------------------------------------------
    parsed_tickets.sort(key=lambda x: x["datetime_obj"])

    # -------------------------------------------------------------
    # 6. สร้าง Output แยกหมวดหมู่
    # -------------------------------------------------------------
    today_tickets = [t for t in parsed_tickets if t["appt_date"] == today_formatted]

    output_sections = []

    # ส่วนที่ 1: งานค้างวันนี้
    output_sections.append(f"📌 [ งานค้างนัดวันนี้ ({today_formatted}) ]")
    if today_tickets:
        for t in today_tickets:
            lines = [
                f"🎫 Ticket : {t['ticket_id']}",
                f"{t['company_info']}"
            ]
            if t['contact_str']:
                lines.append(t['contact_str'])
            lines.append(f"นัดลูกค้า {t['appt_date']} เวลา {t['appt_time']}")
            
            output_sections.append("\n".join(lines))
    else:
        output_sections.append("ไม่มีงานนัดวันนี้")

    output_sections.append("\n" + "="*30 + "\n")

    # ส่วนที่ 2: งานค้างทั้งหมด
    output_sections.append("📋 [ งานค้างทั้งหมด (เรียงตามวันนัด) ]")
    for t in parsed_tickets:
        lines = [
            f"🎫 Ticket : {t['ticket_id']}",
            f"{t['company_info']}"
        ]
        if t['contact_str']:
            lines.append(t['contact_str'])
        lines.append(f"นัดลูกค้า {t['appt_date']} เวลา {t['appt_time']}")

        output_sections.append("\n".join(lines))

    return "\n\n".join(output_sections)