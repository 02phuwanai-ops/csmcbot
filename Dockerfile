FROM python:3.10-slim

WORKDIR /app

# ก๊อบปี้ไฟล์ requirements.txt และติดตั้ง Python packages
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# ก๊อบปี้โค้ดทั้งหมดในโปรเจกต์
COPY . .

# สั่งรัน FastAPI บน Port 10000
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "10000"]