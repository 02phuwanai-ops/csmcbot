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
    "0968950525", "0852151700", "0829935069", "0829935011"
]


def clean_text(text: str) -> str:
    """ล้างช่องว่างส่วนเกิน"""
    return re.sub(r"\s+", " ", text or "").strip()


def extract_appointment_info(full_text: str) -> dict:
    """ดึงวันที่และเวลานัดหมายจาก Log / HOLD SLA"""
    
    # 1. ค้นหา Pattern 'to DD/MM/YY HH:MM' หรือ 'to DD/MM/YYYY HH:MM'
    hold_matches = re.findall(
        r"(?:to|-|ถึง)\s*(\d{1,2}[/\.-]\d{1,2}[/\.-]\d{2,4})\s*(\d{1,2}[:\.]\d{2})", full_text, re.IGNORECASE
    )
    if hold_matches:
        last_date, last_time = hold_matches[-1]
        h_parts = re.split(r"[/\.-]", last_date)
        if len(h_parts) == 3:
            h_year = f"20{h_parts[2]}" if len(h_parts[2]) == 2 else h_parts[2]
            time_clean = last_time.replace(".", ":")
            dt_obj = None
            try:
                dt_obj = datetime.strptime(f"{h_parts[0].zfill(2)}/{h_parts[1].zfill(2)}/{h_year} {time_clean}", "%d/%m/%Y %H:%M")
            except ValueError:
                pass

            return {
                "date": f"{h_parts[0].zfill(2)}/{h_parts[1].zfill(2)}/{h_year}",
                "time": f"{time_clean} น.",
                "datetime_obj": dt_obj or datetime.max
            }

    # 2. ค้นหา Pattern ภาษาไทย เช่น 'วันที่ 07/09/26 เวลา 09:00'
    thai_date_match = re.search(
        r"วันที่\s*(\d{1,2}[/\.-]\d{1,2}[/\.-]\d{2,4})\s*เวลา\s*(\d{1,2}[:\.]\d{2})", full_text, re.IGNORECASE
    )
    if thai_date_match:
        t_date, t_time = thai_date_match.group(1), thai_date_match.group(2)
        h_parts = re.split(r"[/\.-]", t_date)
        if len(h_parts) == 3:
            h_year = f"20{h_parts[2]}" if len(h_parts[2]) == 2 else h_parts[2]
            time_clean = t_time.replace(".", ":")
            dt_obj = None
            try:
                dt_obj = datetime.strptime(f"{h_parts[0].zfill(2)}/{h_parts[1].zfill(2)}/{h_year} {time_clean}", "%d/%m/%Y %H:%M")
            except ValueError:
                pass

            return {
                "date": f"{h_parts[0].zfill(2)}/{h_parts[1].zfill(2)}/{h_year}",
                "time": f"{time_clean} น.",
                "datetime_obj": dt_obj or datetime.max
            }

    # 3. ค้นหา General Match
    text_without_expected = re.sub(
        r"ExpectedDate\s*:\s*\d{1,2}[/\.-]\d{1,2}[/\.-]\d{2,4}\s+\d{1,2}[:\.]\d{2}",
        "",
        full_text,
        flags=re.IGNORECASE
    )

    general_match = re.search(
        r"(\d{1,2}[/\.-]\d{1,2}[/\.-]\d{2,4})\s+(\d{1,2}[\.:]\d{2})", text_without_expected
    )
    if general_match:
        g_date, g_time = general_match.group(1), general_match.group(2)
        h_parts = re.split(r"[/\.-]", g_date)
        if len(h_parts) == 3:
            h_year = f"20{h_parts[2]}" if len(h_parts[2]) == 2 else h_parts[2]
            time_clean = g_time.replace(".", ":")
            dt_obj = None
            try:
                dt_obj = datetime.strptime(f"{h_parts[0].zfill(2)}/{h_parts[1].zfill(2)}/{h_year} {time_clean}", "%d/%m/%Y %H:%M")
            except ValueError:
                pass

            return {
                "date": f"{h_parts[0].zfill(2)}/{h_parts[1].zfill(2)}/{h_year}",
                "time": f"{time_clean} น.",
                "datetime_obj": dt_obj or datetime.max
            }

    # Fallback
    return {
        "date": "ไม่ระบุวัน",
        "time": "ไม่ระบุเวลา",
        "datetime_obj": datetime.max
    }


def extract_circuit_id(full_text: str) -> str:
    """ดึง Circuit ID จาก Subject หรือ Body"""
    # 1. หาจาก Subject/Pattern เช่น |J01735|
    match_pipe = re.search(r"\|([A-Z]{1,4}\d{4,8}[A-Z]?)\|", full_text)
    if match_pipe:
        return match_pipe.group(1).upper()

    # 2. หาจากคำว่า Circuit:
    match_direct = re.search(r"Circuit\s*(?:ID)?\s*[:\=]?\s*([A-Z]{1,4}\d{4,8}[A-Z]?)", full_text, re.IGNORECASE)
    if match_direct:
        return match_direct.group(1).upper()

    # 3. Pattern ทั่วไป เช่น J01735, V16239B
    matches = re.findall(r"\b([VJIWS][D]?\d{4,6}[A-Z]?)\b", full_text, re.IGNORECASE)
    if matches:
        return matches[0].upper()

    return ""


def extract_customer_contact(full_text: str) -> tuple[str, str]:
    """ดึงชื่อและเบอร์ติดต่อลูกค้า โดยเช็กจากส่วนข้อมูลการติดต่อลูกค้าเป็นหลัก"""
    contact_name = ""
    phone_number = ""

    # 1. ค้นหาเบอร์โทรเจาะจงในโซน "ข้อมูลการติดต่อลูกค้า:"
    contact_section_m = re.search(
        r"ข้อมูลการติดต่อลูกค้า\s*:\s*(.*?)(?=Ticket Detail:|Location:|$)", 
        full_text, 
        re.IGNORECASE
    )
    
    target_text = contact_section_m.group(1) if contact_section_m else full_text

    # ค้นหาเบอร์โทรที่ไม่ใช่เบอร์ช่าง
    all_phones = re.findall(r"0[689]\d{8}", target_text)
    for ph in all_phones:
        if ph not in TECH_PHONES:
            phone_number = ph
            break

    # 2. ค้นหาชื่อลูกค้า
    cleaned_text_for_name = re.sub(r"(?:คุณ\s*){2,}", "คุณ ", target_text)
    name_m = re.search(r"(?:คุณ|Khun)\s*([ก-๙a-zA-Z]{2,15})", cleaned_text_for_name)
    if name_m:
        c_name = name_m.group(1).strip()
        invalid_words = ["ลูกค้า", "ช่าง", "แจ้ง", "เสีย", "ไม่รับสาย", "ขอ", "ติดตาม", "มอนิเตอร์", "ส่งมอบ", "ไม่มี"]
        if not any(word in c_name for word in invalid_words):
            contact_name = c_name

    if contact_name:
        contact_name = re.sub(r"^คุณ+", "", contact_name)
        contact_name = f"คุณ{contact_name}"

    return contact_name, phone_number

def parse_and_group_by_zone(
    raw_tickets_detail: list[dict],
    selected_employees: list = None,
    target_zones: list = None,
    work_date: str = "",
) -> str:
    """แกะข้อมูล จัดรูปแบบ และเรียงลำดับตั๋ว"""

    today_dt = datetime.now()
    today_formatted = work_date if work_date else today_dt.strftime("%d/%m/%Y")
    
    t_parts = today_formatted.split("/")
    if len(t_parts) == 3 and len(t_parts[2]) == 2:
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
        # 0. ตรวจสอบตั๋วปิดงาน (เฉพาะ "ช่างแจ้งปิดงาน" หรือ "ขอปิดงาน")
        # -------------------------------------------------------------
        if re.search(r"ช่าง(?:พื้นที่)?\s*.*?\s*ขอปิดงาน|ช่างแจ้งปิดงาน", full_text):
            continue

        # -------------------------------------------------------------
        # 1. ดึง Ticket ID
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
        # 2. ดึงข้อมูลวัน/เวลานัดหมาย
        # -------------------------------------------------------------
        appt_data = extract_appointment_info(full_text)

        # -------------------------------------------------------------
        # 3. ดึง Circuit ID & ชื่อสถานที่
        # -------------------------------------------------------------
        circuit_id = extract_circuit_id(full_text)

        loc_m = re.search(
            r"LOCATION[^\:]*:\s*(.*?)(?=\[OPEN\]|SMC|TK:|Splitter|รายชื่อช่าง|Add Activity|WONUM|Link Status|HOLD SLA|$)",
            full_text,
            re.IGNORECASE,
        )
        location_address = clean_text(loc_m.group(1)) if loc_m else ""
        
        location_address = re.sub(r"^(?:T?\d+|LOCATION VCARE:)\s*", "", location_address, flags=re.IGNORECASE)
        location_address = re.sub(r"\s*(ไม่พบข้อมูล|กรุงเทพมหานคร|\d{5}).*", "", location_address, flags=re.IGNORECASE)
        location_address = clean_text(location_address)

        circuit_disp = f"Circuit: {circuit_id} {location_address}".strip() if circuit_id else location_address

        # -------------------------------------------------------------
        # 4. ดึง ชื่อผู้ติดต่อ & เบอร์โทรศัพท์ (ถ้าไม่มีทั้งคู่ ให้เป็นค่าว่าง)
        # -------------------------------------------------------------
        contact_name, phone_number = extract_customer_contact(full_text)

        contact_disp = ""
        if contact_name and phone_number:
            contact_disp = f"ติดต่อ{contact_name} : {phone_number}"
        elif contact_name:
            contact_disp = f"ติดต่อ{contact_name}"
        elif phone_number:
            contact_disp = f"ติดต่อ : {phone_number}"
        # หากไม่มีเบอร์และไม่มีชื่อ contact_disp จะเป็น "" และถูกข้ามไป ไม่แสดงใน LINE

    if not parsed_tickets:
        return "ไม่มีรายการงานซ่อมในระบบ"

    # -------------------------------------------------------------
    # 5. เรียงลำดับงานตาม วันที่ และ เวลา
    # -------------------------------------------------------------
    parsed_tickets.sort(key=lambda x: x["datetime_obj"])

    # -------------------------------------------------------------
    # 6. สร้าง Output แยกหมวดหมู่ (จัด Format หน้า LINE ให้โปรและอ่านง่าย)
    # -------------------------------------------------------------
    today_tickets = [t for t in parsed_tickets if t["appt_date"] == today_formatted]

    output_sections = []

    # ส่วนที่ 1: งานค้างวันนี้
    output_sections.append(f"📌 [ งานค้างนัดวันนี้ ({today_formatted}) ]")
    if today_tickets:
        for t in today_tickets:
            lines = [
                f"🎫 : {t['ticket_id']}",
                f"{t['company_info']}"
            ]
            if t['contact_str']:
                lines.append(t['contact_str'])
            lines.append(f"นัดลูกค้า {t['appt_date']} เวลา {t['appt_time']}")
            
            output_sections.append("\n".join(lines))
    else:
        output_sections.append("ไม่มีงานนัดวันนี้")

    output_sections.append("----------------------------------")

    # ส่วนที่ 2: งานค้างทั้งหมด
    output_sections.append("📋 [ งานค้างทั้งหมด (เรียงตามวันนัด) ]")
    for t in parsed_tickets:
        lines = [
            f"🎫 : {t['ticket_id']}",
            f"{t['company_info']}"
        ]
        if t['contact_str']:
            lines.append(t['contact_str'])
        lines.append(f"นัดลูกค้า {t['appt_date']} เวลา {t['appt_time']}")

        output_sections.append("\n".join(lines))

    return "\n\n".join(output_sections)