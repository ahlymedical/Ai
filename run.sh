#!/bin/bash
# الخروج فوراً في حال حدوث أي خطأ
set -e

# هذا السكربت يقوم ببدء تشغيل عامل Celery في الخلفية ثم خادم Gunicorn في المقدمة.
# Cloud Run يراقب العملية التي تعمل في المقدمة (Foreground).

# 1. بدء تشغيل عامل Celery في الخلفية
echo "Starting Celery worker in the background..."
celery -A celery_worker.celery_app worker --loglevel=info &

# 2. بدء تشغيل خادم الويب Gunicorn في المقدمة
# سيستمع الخادم للمنفذ (PORT) الذي يحدده Cloud Run تلقائياً.
echo "Starting Gunicorn web server..."
exec gunicorn --bind "0.0.0.0:${PORT}" --workers 1 --threads 8 --timeout 0 app:app
