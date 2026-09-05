FROM python:3.10-slim

# Set Environment Variables
ENV PYTHONUNBUFFERED=1 \
    TZ="Asia/Bangkok"

WORKDIR /app

# 1. ติดตั้งระบบ Timezone ไทย และ Libs สำหรับ curl_cffi / SSL
RUN apt-get update && apt-get install -y --no-install-recommends \
    tzdata \
    ca-certificates \
    libcurl4-openssl-dev \
    libssl-dev \
    && ln -fs /usr/share/zoneinfo/$TZ /etc/localtime \
    && dpkg-reconfigure -f noninteractive tzdata \
    && rm -rf /var/lib/apt/lists/*

# 2. ก๊อบปี้และลง Dependencies
COPY requirements.txt .
RUN pip install --no-cache-dir --upgrade pip \
    && pip install --no-cache-dir -r requirements.txt

# 3. ก๊อบปี้โค้ดทั้งหมด
COPY . .

# 4. สั่งรัน FastAPI
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "10000"]