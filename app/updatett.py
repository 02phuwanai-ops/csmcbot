import re
from curl_cffi import requests
from app.auth import get_authenticated_session


class UpdateTTClient:

    def __init__(self, cookies_str: str = None):
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
                item.get("SUBJECT")
                or item.get("text")
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
        if isinstance(item, dict) and item.get("ticketID"):
            return str(item.get("ticketID")).strip()
            
        text = self.get_full_ticket_text(item)
        match = re.search(r'(TT\d+)', text)
        if match:
            return match.group(1)
        return text.split()[0] if text else ""

    def is_target_technician(self, ticket_input) -> bool:
        if isinstance(ticket_input, dict):
            subject = ticket_input.get("SUBJECT", str(ticket_input))
        else:
            subject = str(ticket_input)

        subject_lower = subject.lower()

        for target in self.target_technicians:
            if target.lower() in subject_lower:
                return True

        return False

    def fetch_all_tickets_from_web(
        self, zone: str = "2", worktype: str = "Corporate Service", retry: bool = True
    ) -> list:
        self.ensure_authenticated_session()
        url = f"{self.base_url}/get_ticket"
        
        target_zone = "2" if zone == "WW BMA East" or not zone else str(zone)

        payloads_to_try = [
            {
                "zone": target_zone,
                "workType": worktype,
                "includeClosedWithin24Hours": "No"
            },
            {
                "zone": target_zone,
                "workType": worktype,
                "includeClosedWithin24Hours": "Yes"
            }
        ]

        for payload in payloads_to_try:
            try:
                res = self.session.post(url, data=payload, headers=self.headers, timeout=30)
                if res.status_code == 200:
                    try:
                        data = res.json()
                    except Exception:
                        continue

                    raw_ticket_list = data.get("ticket_list", {}) if isinstance(data, dict) else data
                    tickets = []

                    if isinstance(raw_ticket_list, dict):
                        for t_id, t_info in raw_ticket_list.items():
                            if isinstance(t_info, dict):
                                t_info["ticketID"] = t_id
                                tickets.append(t_info)
                            else:
                                tickets.append({"ticketID": t_id, "SUBJECT": str(t_info)})
                    elif isinstance(raw_ticket_list, list):
                        tickets = raw_ticket_list
                    
                    if tickets:
                        print(f"✅ ดึงตั๋วสำเร็จ! เจอทั้งหมด {len(tickets)} ใบ")
                        return tickets

            except Exception as e:
                print(f"❌ Error fetching ticket list: {e}")

        print("⚠️ ทดลองทุกรูปแบบแล้ว ไม่พบตั๋วในระบบ")
        return []

    def fetch_filtered_tickets(
        self, zone: str = "2", worktype: str = "Corporate Service"
    ) -> list:
        all_tickets = self.fetch_all_tickets_from_web(zone=zone, worktype=worktype)
        filtered_tickets = []

        for item in all_tickets:
            if self.is_target_technician(item):
                filtered_tickets.append(item)

        print(f"🎯 จากทั้งหมด {len(all_tickets)} รายการ -> คัดเหลือเฉพาะช่างในทีม {len(filtered_tickets)} รายการ")
        return filtered_tickets

    def get_ticket_activity_log(self, ticket_id: str, zone: str = "2") -> str:
        self.ensure_authenticated_session()
        url = f"{self.base_url}/get_activity_detail"
        payload = {
            "ticketID": ticket_id,
            "zone": "2" if zone == "WW BMA East" or not zone else str(zone),
        }

        try:
            res = self.session.post(url, data=payload, headers=self.headers, timeout=15)
            if res.status_code == 200:
                return res.text
        except Exception as e:
            print(f"❌ Error fetching activity log for {ticket_id}: {e}")
        return ""

    def get_ticket_detail(
        self,
        ticket_item,
        zone: str = "2",
        worktype: str = "Corporate Service",
        retry: bool = True
    ) -> dict:
        self.ensure_authenticated_session()
        ticket_id = self.extract_ticket_id(ticket_item)
        target_zone = "2" if zone == "WW BMA East" or not zone else str(zone)

        url = f"{self.base_url}/get_ticketDeatil"
        payload = {
            "ticketID": ticket_id,
            "zone": target_zone,
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

                result_dict = data if isinstance(data, dict) else {"data": data}

                # 1. ดึง Activity Log
                activity_log_text = self.get_ticket_activity_log(ticket_id, zone=target_zone)
                
                # 2. แกะเวลา HOLD SLA จาก Log
                hold_info = self.parse_hold_sla(activity_log_text, raw_data=result_dict)
                result_dict["hold_info"] = hold_info

                # 3. Override ฟิลด์เวลาทั้งหมดเพื่อความแน่นอนในการส่งข้อความ
                if hold_info.get("reschedule_time"):
                    real_time = hold_info["reschedule_time"]
                    result_dict["ExpectDate"] = real_time
                    result_dict["appointmentDate"] = real_time
                    result_dict["appointment_date"] = real_time
                    result_dict["appointDate"] = real_time
                    result_dict["appoint_date"] = real_time

                return result_dict
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
        result = {"is_hold": False, "reschedule_time": None, "reason": None}
        if not log_text:
            return result

        # ล้าง HTML Tags และจัดรูปแบบข้อความ
        clean_text = re.sub(r'<[^>]+>', ' ', log_text)
        clean_text = re.sub(r'\s+', ' ', clean_text)

        if "HOLD" in clean_text.upper():
            result["is_hold"] = True

        # 🎯 Regex เจาะจงแพทเทิร์น: HOLD SLA (... to DD/MM/YY HH:MM)
        # ตัวอย่าง: Narong Songnimit HOLD SLA (05/09/26 22:15 to 06/09/26 09:00)
        pattern = r'HOLD\s+SLA\s*\([^)]*?\bto\s+(\d{1,2}/\d{1,2}/\d{2,4}\s+\d{1,2}:\d{2})\)'
        match = re.search(pattern, clean_text, re.IGNORECASE)

        if match:
            raw_dt = match.group(1).strip() # จะได้ เช่น "06/09/26 09:00" หรือ "07/09/26 13:00"
            parts = raw_dt.split()
            if len(parts) == 2:
                d_p = parts[0].split('/')
                if len(d_p) == 3:
                    dd, mm, yy = d_p[0].zfill(2), d_p[1].zfill(2), d_p[2]
                    yyyy = f"20{yy}" if len(yy) == 2 else yy
                    result["reschedule_time"] = f"{dd}/{mm}/{yyyy} เวลา {parts[1]} น."
                else:
                    result["reschedule_time"] = raw_dt
            else:
                result["reschedule_time"] = raw_dt

        # 🎯 ดึงสาเหตุที่ HOLD
        reason_match = re.search(r'เนื่องจาก\s*([^\s<]+(?:\s+[^\s<]+)*)', clean_text)
        if reason_match:
            result["reason"] = reason_match.group(0).strip()

        return result