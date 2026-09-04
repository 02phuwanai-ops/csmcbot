from curl_cffi import requests


class UpdateTTClient:

    def __init__(self, cookies_str: str = None):
        # ตั้ง Base URL ให้ตรงกับโฟลเดอร์หลักของเว็บ
        self.base_url = "https://csmcbot.truecorp.co.th/updatett"
        self.session = requests.Session(impersonate="chrome120")

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

    def set_cookies_from_string(self, cookie_header: str):
        """แปลง Cookie String ใส่ Session"""
        cookies_dict = {}
        for item in cookie_header.split(";"):
            if "=" in item:
                k, v = item.strip().split("=", 1)
                cookies_dict[k] = v
        self.session.cookies.update(cookies_dict)

    def fetch_all_tickets_from_web(
        self, zone: str = "WW BMA East", worktype: str = "Corporate Service"
    ) -> list:
        """ดึงรายการ Ticket ทั้งหมดใน Dropdown ของ Zone"""
        url = f"{self.base_url}/get_ticket"
        payload = {"zone": zone, "worktype": worktype}

        try:
            res = self.session.post(
                url, data=payload, headers=self.headers, timeout=30
            )
            if res.status_code == 200:
                data = res.json()
                return data if isinstance(data, list) else data.get("tickets", [])
        except Exception as e:
            print(f"Error fetching ticket list: {e}")

        return []

    def get_ticket_detail(
        self,
        ticket_id: str,
        zone: str = "WW BMA East",
        worktype: str = "Corporate Service",
    ) -> dict:
        """ดึงรายละเอียด Ticket โดยแปลงเลข TT เป็น Full String อัตโนมัติ"""
        
        # 1. ถ้าส่งมาแค่เลข TT202... ให้ดึงรายการมาจับคู่หา Full String ใน Dropdown ก่อน
        full_ticket_val = ticket_id
        if not (" " in ticket_id or "|" in ticket_id):
            all_tickets = self.fetch_all_tickets_from_web(zone=zone, worktype=worktype)
            for item in all_tickets:
                val_str = str(item.get("ticketID") or item.get("val") or item.get("text") or item)
                if ticket_id in val_str:
                    full_ticket_val = val_str
                    break

        # 2. ยิงเรียกรายละเอียด Ticket
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
            
            # หากติด 404 ให้ลองยิง fallback endpoint แบบไม่มี /updatett ซ้ำ
            if res.status_code == 404:
                alt_url = "https://csmcbot.truecorp.co.th/updatett/get_ticketDeatil"
                res = self.session.post(alt_url, data=payload, headers=self.headers, timeout=30)

            if res.status_code == 200:
                return res.json()
            else:
                print(
                    f"Failed to fetch detail for {ticket_id} - Status:"
                    f" {res.status_code}"
                )
                return {}
        except Exception as e:
            print(f"Error fetching detail for Ticket {ticket_id}: {e}")
            return {}