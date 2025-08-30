# الخطوة 1: استخدم إصدار بايثون مستقر ومتوافق
FROM python:3.9-slim

# الخطوة 2: قم بتعيين متغيرات البيئة لتجنب المشاكل
ENV PYTHONUNBUFFERED=1
ENV PIP_NO_CACHE_DIR=off
ENV PIP_DISABLE_PIP_VERSION_CHECK=on

# الخطوة 3: تثبيت الأدوات الأساسية المطلوبة مثل ffmpeg
RUN apt-get update && \
    apt-get install -y --no-install-recommends ffmpeg && \
    apt-get clean && \
    rm -rf /var/lib/apt/lists/*

# الخطوة 4: إعداد مجلد العمل
WORKDIR /app

# الخطوة 5: نسخ ملف المكتبات وتثبيتها
# سنقوم بتثبيت torch بشكل منفصل لتحديد مصدره لضمان التوافق مع CPU
COPY requirements.txt .
RUN pip install --no-cache-dir torch torchaudio --index-url https://download.pytorch.org/whl/cpu
RUN pip install --no-cache-dir -r requirements.txt

# الخطوة 6: نسخ جميع ملفات التطبيق إلى الحاوية
COPY . .

# الخطوة 7: الأمر النهائي لتشغيل التطبيق باستخدام Gunicorn (خادم ويب احترافي)
# قمنا بزيادة الـ timeout إلى 600 ثانية (10 دقائق) لأن فصل الصوت عملية بطيئة
CMD ["gunicorn", "--bind", "0.0.0.0:8080", "--workers", "1", "--threads", "4", "--timeout", "600", "app:app"]
