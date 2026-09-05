import re
from curl_cffi import requests
from app.auth import get_authenticated_session


class UpdateTTClient:

    def __init__(self, cookies_str: str = None):
        # 🎯 1. แก้ไข Base URL ให้ตรงตาม Network Tab (/updatett/Updatett)
        self.base_url = "https://csmcbot.truecorp.co.th/updatett/Updatett"
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

        # 2. รายชื่อ 6 เขตที่อนุญาต
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
            "0820054606", "0970642598", "0820054570", "0834903149",
            "0910024273", "0824669506", "0993515969", "0826779358",
            "0968950525", "0852151700", "0829935069",
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

    def ensure_authenticated_session(self, force_refresh: bool = False):
        if force_refresh or not self.session.cookies:
            print("🔑 บังคับดึง Authenticated Session ใหม่ผ่าน app/auth.py...")
            self.session = requests.Session(impersonate="chrome120")
            auth_session = get_authenticated_session()
            if auth_session and auth_session.cookies:
                self.session.cookies.update(auth_session.cookies)
                print("✅ อัปเดต Cookie ใหม่ลงใน Session สำเร็จ")

    def set_cookies_from_string(self, cookie_header: str):
        if not cookie_header:
            return
        cookies_dict = {}
        for item in cookie_header.split(";"):
            if "=" in item:
                k, v = item.strip().split("=", 1)
                cookies_dict[k] = v
        self.session.cookies.update(cookies_dict)

    def get_full_ticket_text(self, item) -> str:
        if isinstance(item, str):
            return item.strip()
        if isinstance(item, dict):
            val = (
                item.get("text")
                or item.get("val")
                or item.get("label")
                or item.get("value")
                or item.get("ticketID")
                or item.get("ticketNo")
                or ""
            )
            return str(val).strip()
        return str(item).strip()

    def extract_ticket_id(self, item) -> str:
        text = self.get_full_ticket_text(item)
        match = re.search(r'(TT\d+)', text)
        if match:
            return match.group(1)
        return text.split()[0] if text else ""

    def is_target_technician(self, ticket_input) -> bool:
        ticket_text = self.get_full_ticket_text(ticket_input)
        if not ticket_text:
            return False

        ticket_text_lower = ticket_text.lower()
        for target in self.target_technicians:
            if target.lower() in ticket_text_lower:
                return True

        return False

    def fetch_all_tickets_from_web(
        self, zone: str = "2", worktype: str = "Corporate Service", retry: bool = True
    ) -> list:
        """ดึงรายการ Ticket โดยส่ง Key ให้ตรงกับ Form Data บนหน้าเว็บเป๊ะๆ"""
        self.ensure_authenticated_session()
        url = f"{self.base_url}/get_ticket"
        
        # 🎯 Payload ตาม Network Tab เป๊ะๆ (workType เป็น T ตัวใหญ่)
        payloads_to_try = [
            {
                "zone": str(zone),
                "workType": worktype,
                "includeClosedWithin24Hours": "No"
            },
            {
                "zone": str(zone),
                "workType": worktype,
                "includeClosedWithin24Hours": "Yes"  # เผื่อกรณีตั๋วอยู่ในโหมดปิดภายใน 24 ชม.
            }
        ]

        for payload in payloads_to_try:
            try:
                res = self.session.post(url, data=payload, headers=self.headers, timeout=30)
                print(f"🔍 [DEBUG] URL: {url} | Payload: {payload} | Status: {res.status_code}")

                if res.status_code == 200:
                    try:
                        data = res.json()
                    except Exception:
                        continue

                    tickets = []
                    if isinstance(data, list):
                        tickets = data
                    elif isinstance(data, dict):
                        tickets = (
                            data.get("ticket_list", [])
                            or data.get("tickets", [])
                            or data.get("data", [])
                        )
                    
                    if tickets:
                        print(f"✅ ดึงตั๋วสำเร็จ! เจอทั้งหมด {len(tickets)} ใบ")
                        return tickets
                    else:
                        print(f"⚠️ [DEBUG] JSON ตอบกลับมาเป็นค่าว่าง [] ( payload: {payload['includeClosedWithin24Hours']} )")

            except Exception as e:
                print(f"❌ Error fetching ticket list: {e}")

        print("⚠️ ทดลองทุกรูปแบบแล้ว ไม่พบตั๋วในระบบ")
        return []

    def fetch_filtered_tickets(
        self, zone: str = "WW BMA East", worktype: str = "Corporate Service"
    ) -> list:
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
        retry: bool = True
    ) -> dict:
        self.ensure_authenticated_session()
        ticket_id = self.extract_ticket_id(ticket_item)

        url = f"{self.base_url}/get_ticketDeatil"
        payload = {
            "ticketID": ticket_id,
            "zone": str(zone),
            "region": str(zone),
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
                
                address_info = str(data)
                if not any(dist in address_info for dist in self.allowed_districts):
                    return {}

                return data if isinstance(data, dict) else {"data": data}
            elif res.status_code == 404 and retry:
                self.ensure_authenticated_session(force_refresh=True)
                return self.get_ticket_detail(ticket_item, zone=zone, worktype=worktype, retry=False)
            else:
                return {}
        except Exception as e:
            print(f"Error fetching detail for Ticket: {e}")
            return {}

    def extract_customer_phone(self, raw_data: dict) -> str:
        if not raw_data:
            return None
            
        text_corp = f"{raw_data.get('custMobile', '')} {raw_data.get('custTel', '')} {raw_data.get('remark', '')} {str(raw_data)}"
        found_phones = re.findall(r'0[689]\d{8}', text_corp)
        
        for phone in found_phones:
            if phone not in self.tech_phones:
                return phone
                
        return None

    @staticmethod
    def parse_hold_sla(log_text: str, raw_data: dict = None) -> dict:
        """
        สกัดเวลานัดและเหตุผล (ปรับปรุง RegEx ให้ยืดหยุ่นขึ้นรองรับหลายแพทเทิร์น)
        """
        result = {"is_hold": False, "reschedule_time": None, "reason": None}
        
        # 1. เช็คสถานะ HOLD SLA
        if log_text and "HOLD SLA" in log_text.upper():
            result["is_hold"] = True

        if log_text:
            # Pattern 1: จับคำว่า to ตามด้วย วันที่/เวลา (เช่น to 15/06/2026 10:00 หรือ to 2026-06-15)
            time_match = re.search(r'to\s+([\d{1,2}/-]+\s*[\d{1,2}:]*)', log_text, re.IGNORECASE)

            # Pattern 2: ถ้าไม่เจอ to ให้ค้นหารูปแบบวันที่ + เวลา ทั่วไปในข้อความ (เช่น 15/06/2026 10:00 หรือ 15/06/2569)
            if not time_match:
                time_match = re.search(r'(\d{1,2}[/-]\d{1,2}[/-]\d{2,4}\s+\d{1,2}:\d{2})', log_text)

            # Pattern 3: ดึงข้อความในวงเล็บ (เช่น (15/06/2026 10:00))
            if not time_match:
                time_match = re.search(r'\(([\d{1,2}/-].*?)\)', log_text)

            if time_match:
                result["reschedule_time"] = time_match.group(1).strip()

            # สกัดเหตุผล
            reason_match = re.search(r'(เนื่องจาก.*)', log_text)
            if reason_match:
                result["reason"] = reason_match.group(1).strip()

        # Fallback: ถ้าหาจาก log_text ไม่เจอ ให้ลองดูในฟิลด์ JSON Direct (ถ้ามีส่งมา)
        if not result["reschedule_time"] and raw_data and isinstance(raw_data, dict):
            reschedule_from_dict = (
                raw_data.get("appointmentDate")
                or raw_data.get("appointment_date")
                or raw_data.get("appointDate")
                or raw_data.get("rescheduleTime")
            )
            if reschedule_from_dict:
                result["reschedule_time"] = str(reschedule_from_dict).strip()

        return result