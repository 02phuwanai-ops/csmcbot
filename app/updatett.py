import re
from concurrent.futures import ThreadPoolExecutor, as_completed
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

        # 2. รายชื่อ 6 เขต/แขวงที่อนุญาต
        self.allowed_districts = [
            # 1. บางจาก / พระโขนง
            "บางจาก", "พระโขนง",
            # 2. คลองเตย
            "คลองเตย", "คลองตัน",
            # 3. บางกะปิ / ห้วยขวาง
            "บางกะปิ", "ห้วยขวาง", "สามเสนนอก",
            # 4. คลองตันเหนือ / วัฒนา
            "คลองตันเหนือ", "วัฒนา", "สุขุมวิท",
            # 5. จรเข้บัว / ลาดพร้าว
            "จรเข้บัว", "ลาดพร้าว", "ลาดพร้าววังหิน",
            # 6. พลับพลา / วังทองหลาง
            "พลับพลา", "วังทองหลาง",
        ]

        # 🚫 Blacklist เขตที่ไม่ต้องการดึง (เช่น ดินแดง)
        self.excluded_districts = [
            "ดินแดง",
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
                item.get("ticketID")
                or item.get("ticketNo")
                or item.get("SUBJECT")
                or item.get("text")
                or item.get("val")
                or item.get("label")
                or item.get("value")
                or str(item)
            )
            return str(val).strip()
        return str(item).strip()

    def extract_ticket_id(self, item) -> str:
        """🎯 ปรับแก้ให้รองรับทั้ง TT และ INC จากทุก Field"""
        text = self.get_full_ticket_text(item)
        match = re.search(r'((?:TT|INC)\d+)', text, re.IGNORECASE)
        if match:
            return match.group(1).upper()
        return text.split()[0] if text else ""

    def is_target_technician(self, ticket_input) -> bool:
        """🎯 เช็กชื่อช่างในทีมจากข้อมูลตั๋วโดยตรง (ใช้เงื่อนไขเดิมกับทั้ง TT และ INC)"""
        # ดึงข้อความตั๋วและตรวจสอบทั้งหมดในรูป string
        raw_str = str(ticket_input) if isinstance(ticket_input, dict) else self.get_full_ticket_text(ticket_input)
        raw_str_lower = raw_str.lower()

        # 1. ตรวจสอบชื่อช่างทั้ง 7 คน หรือ ชื่อหน้าช่าง ในสตริงข้อความตั๋ว
        for target in self.target_technicians:
            first_name = target.split()[0].strip().lower()  # ดึงเฉพาะชื่อหน้า เช่น "Chakares", "Naruenat"
            if target.lower() in raw_str_lower or first_name in raw_str_lower:
                return True

        # 2. ป้องกันตั๋ว HOLD SLA / BMAE4 หลุด
        keywords_bypass = ["HOLD", "SLAHOLD", "WW-BMAE4-CORP", "BMAE4"]
        for kw in keywords_bypass:
            if kw.lower() in raw_str_lower:
                return True

        return False

    def fetch_all_tickets_from_web(
        self, zone: str = "2", worktype: str = "Corporate Service", retry: bool = True
    ) -> list:
        self.ensure_authenticated_session()
        url = f"{self.base_url}/get_ticket"
        
        target_zone = "2" if zone == "WW BMA East" or not zone else str(zone)

        # 🎯 ดึงตั๋วแบบครอบคลุมทั้ง Corporate Service, Incident และค่าว่าง
        payloads_to_try = [
            {"zone": target_zone, "workType": worktype, "includeClosedWithin24Hours": "No"},
            {"zone": target_zone, "workType": "Incident", "includeClosedWithin24Hours": "No"},
            {"zone": target_zone, "workType": "", "includeClosedWithin24Hours": "No"},
            {"zone": target_zone, "workType": worktype, "includeClosedWithin24Hours": "Yes"},
        ]

        all_collected_tickets = []
        seen_ticket_ids = set()

        for payload in payloads_to_try:
            try:
                res = self.session.post(url, data=payload, headers=self.headers, timeout=30)
                if res.status_code == 200:
                    try:
                        data = res.json()
                    except Exception:
                        continue

                    raw_ticket_list = data.get("ticket_list", {}) if isinstance(data, dict) else data

                    if isinstance(raw_ticket_list, dict):
                        for t_id, t_info in raw_ticket_list.items():
                            extracted_id = self.extract_ticket_id(t_id) or self.extract_ticket_id(t_info)
                            if extracted_id and extracted_id not in seen_ticket_ids:
                                seen_ticket_ids.add(extracted_id)
                                if isinstance(t_info, dict):
                                    t_info["ticketID"] = extracted_id
                                    all_collected_tickets.append(t_info)
                                else:
                                    all_collected_tickets.append({"ticketID": extracted_id, "SUBJECT": str(t_info)})
                    elif isinstance(raw_ticket_list, list):
                        for t_item in raw_ticket_list:
                            t_id = self.extract_ticket_id(t_item)
                            if t_id and t_id not in seen_ticket_ids:
                                seen_ticket_ids.add(t_id)
                                all_collected_tickets.append(t_item)

            except Exception as e:
                print(f"❌ Error fetching ticket list: {e}")

        if all_collected_tickets:
            print(f"✅ ดึงตั๋วสำเร็จ! เจอทั้งหมด {len(all_collected_tickets)} ใบ (รวม TT และ INC)")
            return all_collected_tickets

        if retry:
            print("🔄 ไม่พบตั๋วในรอบแรก กำลังลอง Re-login ขอ Cookie ใหม่และยิงซ้ำอัตโนมัติ...")
            self.ensure_authenticated_session(force_refresh=True)
            return self.fetch_all_tickets_from_web(zone=zone, worktype=worktype, retry=False)

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

        print(f"🎯 จากทั้งหมด {len(all_tickets)} รายการ -> คัดเหลือเฉพาะช่างในทีมและตั๋ว INC {len(filtered_tickets)} รายการ")
        return filtered_tickets

    def fetch_details_in_parallel(
        self,
        tickets: list,
        zone: str = "2",
        worktype: str = "Corporate Service",
        max_workers: int = 8
    ) -> list:
        """🚀 ดึงรายละเอียดตั๋วแบบขนานด้วย Multi-threading เพื่อเพิ่มความเร็ว"""
        results = []
        if not tickets:
            return results

        print(f"⚡ เริ่มดึงรายละเอียดตั๋วขนานกัน ({max_workers} Workers)...")

        with ThreadPoolExecutor(max_workers=max_workers) as executor:
            # Map แต่ละตั๋วเข้ากับการดึง Detail
            future_to_ticket = {
                executor.submit(self.get_ticket_detail, item, zone, worktype): item
                for item in tickets
            }

            for future in as_completed(future_to_ticket):
                ticket_item = future_to_ticket[future]
                ticket_id = self.extract_ticket_id(ticket_item)
                try:
                    detail = future.result()
                    if detail:
                        results.append(detail)
                    else:
                        print(f"   ❌ ตั๋ว {ticket_id} ถูกข้าม (อาจติด Blacklist เขต หรือไม่มีข้อมูล)")
                except Exception as e:
                    print(f"❌ Error processing ticket {ticket_id}: {e}")

        return results

    def get_ticket_activity_log(self, ticket_id: str, zone: str = "2", activity_id: str = "") -> str:
        self.ensure_authenticated_session()
        url = f"{self.base_url}/get_activity_detail"
        
        payload = {
            "ticketID": ticket_id,
            "zone": "2" if zone == "WW BMA East" or not zone else str(zone),
            "activity": activity_id
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

        # 🎯 ตั๋ว INC จะพยายามดึงหลายๆ WorkType เพื่อป้องกันไม่ให้ข้อมูลหลุด
        worktypes_to_try = [worktype, "Incident", ""] if "INC" in ticket_id.upper() else [worktype, ""]

        for wt in worktypes_to_try:
            payload = {
                "ticketID": ticket_id,
                "zone": target_zone,
                "worktype": wt,
            }

            try:
                res = self.session.post(
                    url, data=payload, headers=self.headers, timeout=30
                )

                if res.status_code == 200:
                    try:
                        data = res.json()
                    except Exception:
                        continue

                    if not data:
                        continue

                    address_info = str(data)

                    # 🚫 1. เช็ก Blacklist เขตห้าม (ดินแดง)
                    if any(ex_dist in address_info for ex_dist in self.excluded_districts):
                        print(f"⛔ ตั๋ว {ticket_id} ติด Blacklist ดินแดง -> ข้าม")
                        return {}

                    # 🎯 2. กรองเขต: สำหรับตั๋ว TT ให้เช็กเขตที่อนุญาต / สำหรับตั๋ว INC ให้ปล่อยผ่านได้เลยถ้าไม่ติด Blacklist
                    is_inc = "INC" in ticket_id.upper()
                    if not is_inc:
                        if not any(dist in address_info for dist in self.allowed_districts):
                            return {}

                    result_dict = data if isinstance(data, dict) else {"data": data}

                    # ดึง Activity Log และเวลา HOLD SLA
                    activity_log_text = self.get_ticket_activity_log(ticket_id, zone=target_zone)
                    hold_info = self.parse_hold_sla(activity_log_text, raw_data=result_dict)
                    result_dict["hold_info"] = hold_info

                    if hold_info.get("reschedule_time"):
                        real_time = hold_info["reschedule_time"]
                        result_dict["ExpectDate"] = real_time
                        result_dict["appointmentDate"] = real_time
                        result_dict["appointment_date"] = real_time
                        result_dict["appointDate"] = real_time
                        result_dict["appoint_date"] = real_time

                    return result_dict
            except Exception as e:
                print(f"Error fetching detail for Ticket {ticket_id}: {e}")

        if retry:
            self.ensure_authenticated_session(force_refresh=True)
            return self.get_ticket_detail(ticket_item, zone=zone, worktype=worktype, retry=False)

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

        clean_text = re.sub(r'<[^>]+>', ' ', log_text)
        clean_text = re.sub(r'\s+', ' ', clean_text)

        if "HOLD" in clean_text.upper():
            result["is_hold"] = True

        pattern = r'HOLD\s+SLA\s*\([^)]*?\bto\s+(\d{1,2}/\d{1,2}/\d{2,4}\s+\d{1,2}:\d{2})\)'
        match = re.search(pattern, clean_text, re.IGNORECASE)

        if match:
            raw_dt = match.group(1).strip()
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

        reason_match = re.search(r'เนื่องจาก\s*([^\s<]+(?:\s+[^\s<]+)*)', clean_text)
        if reason_match:
            result["reason"] = reason_match.group(0).strip()

        return result