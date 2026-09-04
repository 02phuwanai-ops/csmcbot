import os
import re
import logging
from curl_cffi import requests

BASE_URL = "https://csmcbot.truecorp.co.th/updatett/"
AUTH_USER = os.getenv("SYS_USERNAME", "VDWW2097")
AUTH_PASS = os.getenv("SYS_PASSWORD", "MaX@3063306330633063")

def get_authenticated_session():
    """
    สร้าง Session และทำ Auto-Login ผ่าน HTTP Request (API Pure)
    คืนค่า Session ที่ล็อกอินสำเร็จแล้วเพื่อนำไปใช้ยิง API ต่อ
    """
    session = requests.Session(impersonate="chrome120")
    
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
        "Referer": BASE_URL,
    }

    try:
        # 1. เปิดหน้าแรกเพื่อรับ Session Cookie ตั้งต้น
        print("🔑 กำลังเชื่อมต่อหน้า Login...")
        init_res = session.get(BASE_URL, headers=headers, timeout=15)
        
        # 2. เตรียม Payload สำหรับยิง Login
        login_data = {
            "username": AUTH_USER,
            "password": AUTH_PASS,
        }

        # 3. ยิง Request เข้าสู่ระบบ
        print(f"🔑 กำลังส่งข้อมูล Login สำหรับผู้ใช้: {AUTH_USER}")
        login_res = session.post(
            f"{BASE_URL}login", 
            data=login_data, 
            headers=headers, 
            timeout=15
        )

        if login_res.status_code in [200, 302]:
            print("✅ Login เข้าสู่ระบบสำเร็จ (API Pure)!")
            return session
        else:
            print(f"❌ Login ไม่สำเร็จ HTTP Status: {login_res.status_code}")
            return session

    except Exception as e:
        print(f"❌ เกิดข้อผิดพลาดขณะ Login: {e}")
        return session