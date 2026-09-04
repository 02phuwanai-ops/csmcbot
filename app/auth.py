# app/auth.py
import re
import time
from playwright.sync_api import sync_playwright

BASE_URL = "https://csmcbot.truecorp.co.th/updatett/"
AUTH_USER = "VDWW2097"
AUTH_PASS = "MaX@3063306330633063"


def login_page(page):
    """ฟังก์ชัน Login เข้าสู่ระบบ"""
    try:
        user_input = page.locator(
            "input[type='text'], input[name='username'], #username"
        ).first
        pass_input = page.locator(
            "input[type='password'], input[name='password'], #password"
        ).first

        if user_input.is_visible(timeout=3000):
            print("🔑 กำลังกรอก Login...")
            user_input.fill(AUTH_USER)
            pass_input.fill(AUTH_PASS)

            login_btn = page.locator(
                "button[type='submit'], input[type='submit'], #login"
            ).first
            if login_btn.is_visible():
                login_btn.click()
            else:
                pass_input.press("Enter")

            page.wait_for_load_state("domcontentloaded")
            time.sleep(3)
    except Exception as e:
        print(f"ℹ️ Skip Login: {e}")


def scrape_all_region_tickets(
    region_name: str = "WW BMA East", headless: bool = False
) -> list[dict]:
    """เลือก Region -> อ่าน Ticket ทั้งหมดใน Dropdown -> ดึงข้อมูล HTML ทุก Ticket อัตโนมัติ (พร้อมระบบป้องกัน Server Overload)"""
    results = []

    with sync_playwright() as p:
        browser = p.chromium.launch(
            headless=headless,
            args=["--disable-blink-features=AutomationControlled"],
        )
        context = browser.new_context(
            user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) Chrome/122.0.0.0 Safari/537.36"
        )
        page = context.new_page()

        try:
            print(f"⏳ กำลังเปิด Browser เพื่อดึงข้อมูล Region: {region_name}...")
            page.goto(BASE_URL, wait_until="domcontentloaded", timeout=30000)
            login_page(page)

            # -------------------------------------------------------------
            # 1. เลือก Region (เช่น WW BMA East)
            # -------------------------------------------------------------
            print(f"🌐 กำลังเลือก Region: {region_name}")
            region_select = page.locator("#select2-regionID-container")
            if region_select.is_visible(timeout=3000):
                region_select.click()
                time.sleep(1)

                region_option = page.locator(
                    ".select2-results__option", has_text=region_name
                ).first
                if region_option.is_visible():
                    region_option.click()
                    time.sleep(2)

            # -------------------------------------------------------------
            # 2. ดึงรายชื่อ Ticket ทั้งหมดที่อยู่ใน Dropdown Ticket
            # -------------------------------------------------------------
            print("🖱️ กำลังเปิดอ่านรายชื่อ Ticket ทั้งหมด...")
            ticket_select = page.locator("#select2-ticketID-container")
            ticket_select.click()
            time.sleep(1.5)

            # อ่านข้อความใน Option ทั้งหมดที่ขึ้นใน Dropdown
            options = page.locator(".select2-results__option").all_text_contents()
            
            # กรองเอาเฉพาะรายการที่เป็นเลข Ticket (เช่น TT2026xxxx)
            ticket_list = []
            for opt in options:
                m = re.search(r"(TT\d{10,14})", opt)
                if m:
                    ticket_list.append(m.group(1))

            # ปิด Dropdown ก่อนเริ่ม Loop
            page.keyboard.press("Escape")
            time.sleep(1)

            total_found = len(ticket_list)
            print(f"🎯 พบทั้งหมด {total_found} Ticket ใน Region นี้")

            if total_found == 0:
                browser.close()
                return []

            # -------------------------------------------------------------
            # 3. วน Loop เลือกทีละ Ticket เพื่อดึง HTML หน้าจอ (เพิ่ม Delay)
            # -------------------------------------------------------------
            for idx, t_no in enumerate(ticket_list, 1):
                print(f"[{idx}/{total_found}] 🔍 กำลังดึง Ticket: {t_no}")

                ticket_select.click()
                time.sleep(1.2)  # หน่วงเวลารอ Dropdown แสดงผล

                search_input = page.locator(".select2-search__field").first
                if search_input.is_visible():
                    search_input.fill(t_no)
                    time.sleep(1.2)  # หน่วงเวลารอผลการค้นหา

                    matching_item = page.locator(
                        ".select2-results__option", has_text=t_no
                    ).first
                    if matching_item.is_visible():
                        matching_item.click()
                    else:
                        search_input.press("Enter")

                time.sleep(3.5)  # เว้นช่วงให้ Server โหลดข้อมูล AJAX คืนมาเต็มที่

                # เก็บ HTML
                html_content = page.content()
                results.append({
                    "ticket_detail": html_content,
                    "circuit_detail": html_content,
                })

                # พักสายการดึงข้อมูลทุกๆ 5 รายการ เป็นเวลา 5 วินาที เพื่อลดภาระ Server
                if idx % 5 == 0 and idx != total_found:
                    print("⏸️ พักการส่ง Request 5 วินาที เพื่อป้องกัน Server ล่ม...")
                    time.sleep(5)

            browser.close()
            print("\n✅ ดึงข้อมูลครบทุก Ticket ใน Region เรียบร้อยแล้ว!")
            return results

        except Exception as e:
            print(f"❌ เกิดข้อผิดพลาด: {e}")
            browser.close()
            return results