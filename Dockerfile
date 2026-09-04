FROM python:3.10-slim

# ติดตั้ง System Dependencies ที่ Playwright และ Chromium จำเป็นต้องใช้
RUN apt-get update && apt-get install -y \
    wget \
    gnupg \
    curl \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

# ก๊อบปี้ไฟล์ requirements.txt และติดตั้ง Python packages
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# ติดตั้ง Chromium Browser สำหรับ Playwright
RUN playwright install chromium --with-deps

# ก๊อบปี้โค้ดทั้งหมดในโปรเจกต์
COPY . .

# สั่งรัน FastAPI บน Port 10000 (Port มาตรฐานของ Render)
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "10000"]