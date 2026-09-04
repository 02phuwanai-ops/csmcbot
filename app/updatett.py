import re
from curl_cffi import requests
from app.auth import get_authenticated_session


class UpdateTTClient:

    def __init__(self, cookies_str: str = None):
        self.base_url = "https://csmcbot.truecorp.co.th/updatett"
        # สร้าง Session ตั้งต้นแบบ API Pure
        self.session = requests.Session(impersonate="chrome120")

        # 1. รายชื่อช่าง 7 คน
        self.target_technicians = [
            "Wittaya Saomoke",
            "Supoj Kaeokhrueng",
            "Chakares Sudjai",
            "Kampol Sinchai",
            "Phuwanai Sopradit",
            "Naruenat Sompum",
            "Pollawat",
        ]

        # 2. รายชื่อ 6 เขตที่อนุญาตเท่านั้น
        self.allowed_districts = [
            "คลองเตย",
            "ยานนาวา",
            "ห้วยขวาง",
            "คันนายาว",
            "บางกะปิ",
            "คลองตัน",
        ]

        # 3. Blacklist เบอร์โทรช่าง
        self.tech_phones = [
            "0820054606",
            "0970642598",
            "0820054570",
            "0834903149",
            "0910024273",
            "0824669506",
            "0993515969",
            "0826779358",
            "0968950525",
            "0852151700",
            "0829935069",
        ]

        self.headers = {
            "accept": "application/json, text/javascript, */*; q=0.01",
            "accept-language": "th-GB,th;q=0.9,en-GB;q=0.8,en;q=0.7,th-TH;q=0.6",
            "content-type": "application/x-www-form-urlencoded; charset=UTF-8",
            "origin": "https://csmcbot.truecorp.co.th",
            "priority": "u=1, i",
            "referer": "https://csmcbot.truecorp.co.th/updatett/",
            "sec-ch-ua": '"Chromium";v="120", "Not?A_Brand";v="24", "Google Chrome";v="120"',
            "sec-ch-ua-mobile": "?0",
            "sec-ch-ua-platform": '"Windows"',
            "sec-fetch-dest": "empty",
            "sec-fetch-mode": "cors",
            "sec-fetch-site": "same-origin",
            "user-agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
            "x-requested-with": "XMLHttpRequest",
        }

        if cookies_str:
            self.set_cookies_from_string(cookies_str)

    def ensure_authenticated_session(self):
        """ทำการ Auto-Login ล่าสุด หาก Session เดิมยังไม่ได้ยืนยันตัวตน"""
        if not self.session or not self.session.cookies:
            print("🔑 ไม่พบ Cookie สะสม -> เริ่มทำ Auto-Login ผ่าน app/auth.py...")
            auth_session = get_authenticated_session()
            if auth_session and auth_session.cookies:
                self.session.cookies.update(auth_session.cookies)

    def set_cookies_from_string(self, cookie_header: str):
        """แปลง Cookie String ใส่ Session"""
        if not cookie_header:
            return
        cookies_dict = {}
        for item in cookie_header.split(";"):
            if "=" in item:
                k, v = item.strip().split("=", 1)
                cookies_dict[k] = v
        self.session.cookies.update(cookies_dict)

    def get_full_ticket_text(self, item) -> str:
        """สกัดแปลง Object หรือ String ของ Ticket ให้ได้ข้อความเต็มใน Dropdown"""
        if isinstance(item, str):
            return item.strip()
        if isinstance(item, dict):
            val = (
                item.get("text")
                or item.get("val")
                or item.get("label")
                or item.get("value")
                or item.get("ticketID")
                or ""
            )
            return str(val).strip()
        return str(item).strip()

    def extract_ticket_id(self, item) -> str:
        """สกัดเฉพาะรหัส TicketID สั้นๆ เช่น TT202608192600"""
        text = self.get_full_ticket_text(item)
        match = re.search(r'(TT\d+)', text)
        if match:
            return match.group(1)
        return text.split()[0] if text else ""

    def extract_tech_names(self, ticket_text: str) -> list:
        """
        ดึงข้อความภายในวงเล็บทั้งหมดออกมากรณีมีหลายช่าง
        เช่น: '... (Chakares Sudjai,Wittaya Saomoke)' -> ['Chakares Sudjai', 'Wittaya Saomoke']
        """
        if not ticket_text:
            return []

        matches = re.findall(r'\(([^)]+)\)', ticket_text)
        if not matches:
            return []

        last_bracket_content = matches[-1]
        names = [name.strip() for name in last_bracket_content.split(',')]
        return names

    def is_target_technician(self, ticket_input) -> bool:
        """
        ตรวจสอบว่ามีชื่อช่างในทีม 7 คนอยู่ในวงเล็บหรือไม่
        ถ้าไม่มีวงเล็บ หรือเป็นช่างคนอื่น จะตอบ False ทันที!
        """
        ticket_text = self.get_full_ticket_text(ticket_input)
        if not ticket_text:
            return False

        if "(" not in ticket_text or ")" not in ticket_text:
            return False

        tech_names = self.extract_tech_names(ticket_text)
        if not tech_names:
            return False

        for extracted_name in tech_names:
            for target in self.target_technicians:
                if target.lower() in extracted_name.lower():
                    return True

        return False

    def fetch_all_tickets_from_web(
        self, zone: str = "WW BMA East", worktype: str = "Corporate Service"
    ) -> list:
        """ดึงรายการ Ticket ทั้งหมดใน Dropdown ของ Zone (พร้อม Auto Login)"""
        self.ensure_authenticated_session()
        url = f"{self.base_url}/get_ticket"
        payload = {"zone": zone, "worktype": worktype}

        try:
            res = self.session.post(
                url, data=payload, headers=self.headers, timeout=30
            )
            if res.status_code == 200:
                data = res.json()
                if isinstance(data, list):
                    return data
                elif isinstance(data, dict):
                    return data.get("tickets", []) or data.get("data", [])
            else:
                print(f"⚠️ ยิงดึงรายการตั๋วไม่ผ่าน Status: {res.status_code}")
        except Exception as e:
            print(f"Error fetching ticket list: {e}")

        return []

    def fetch_filtered_tickets(
        self, zone: str = "WW BMA East", worktype: str = "Corporate Service"
    ) -> list:
        """
        คัดกรองเฉพาะ Ticket ที่มีชื่อช่างตรงกับทีม 7 คน ตั้งแต่ขั้นแรก
        """
        all_tickets = self.fetch_all_tickets_from_web(zone=zone, worktype=worktype)
        filtered_tickets = []

        for item in all_tickets:
            if self.is_target_technician(item):
                filtered_tickets.append(item)

        print(f"🎯 จากทั้งหมด {len(all_tickets)} รายการ -> คัดเหลือเฉพาะช่างในทีม {len(filtered_tickets)} รายการ")
        return filtered_tickets

    def get_ticket_detail(
        self,
        ticket_item,
        zone: str = "WW BMA East",
        worktype: str = "Corporate Service",
    ) -> dict:
        """
        ดึงรายละเอียด Ticket เฉพาะอันที่ผ่านการคัดชื่อช่างมาแล้ว
        """
        self.ensure_authenticated_session()
        full_ticket_val = self.get_full_ticket_text(ticket_item)

        url = f"{self.base_url}/get_ticketDeatil"
        payload = {
            "ticketID": full_ticket_val,
            "zone": zone,
            "worktype": worktype,
        }

        try:
            res = self.session.post(
                url, data=payload, headers=self.headers, timeout=30
            )

            if res.status_code == 200:
                data = res.json()
                if not data or not isinstance(data, (dict, list)):
                    return {}
                
                # ตรวจสอบพื้นที่ว่าอยู่ใน 6 เขตหรือไม่
                address_info = str(data)
                if not any(dist in address_info for dist in self.allowed_districts):
                    return {}

                return data if isinstance(data, dict) else {"data": data}
            else:
                return {}
        except Exception as e:
            print(f"Error fetching detail for Ticket: {e}")
            return {}

    def extract_customer_phone(self, raw_data: dict) -> str:
        """สกัดเฉพาะเบอร์ลูกค้าจริง"""
        if not raw_data:
            return None
            
        text_corp = f"{raw_data.get('custMobile', '')} {raw_data.get('custTel', '')} {raw_data.get('remark', '')} {str(raw_data)}"
        
        found_phones = re.findall(r'0[689]\d{8}', text_corp)
        
        for phone in found_phones:
            if phone not in self.tech_phones:
                return phone
                
        return None

    @staticmethod
    def parse_hold_sla(log_text: str) -> dict:
        """สกัดเฉพาะเวลานัดปลายทาง และเหตุผลกรณีมี HOLD SLA"""
        result = {
            "is_hold": False,
            "reschedule_time": None,
            "reason": None
        }
        
        if not log_text or "HOLD SLA" not in log_text:
            return result

        result["is_hold"] = True
        
        time_match = re.search(r'to\s+([\d/]+\s+[\d:]+)', log_text)
        if time_match:
            result["reschedule_time"] = time_match.group(1).strip()
        else:
            fallback_match = re.search(r'\((.*?)\)', log_text)
            if fallback_match:
                result["reschedule_time"] = fallback_match.group(1).strip()

        reason_match = re.search(r'(เนื่องจาก.*)', log_text)
        if reason_match:
            result["reason"] = reason_match.group(1).strip()

        return result