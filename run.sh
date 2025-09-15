#!/bin/bash

# Set default port if not provided by Cloud Run
PORT=${PORT:-8080}

echo "Starting Celery worker..."
celery -A celery_worker.celery_app worker --loglevel=info &

echo "Waiting for Celery to start..."
sleep 5

echo "Starting Gunicorn on port $PORT..."
exec gunicorn --bind 0.0.0.0:$PORT --workers 1 --threads 8 --timeout 0 app:app
