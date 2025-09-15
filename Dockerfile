FROM python:3.9-slim

ENV PYTHONUNBUFFERED=1
ENV PIP_NO_CACHE_DIR=off
ENV APP_HOME=/app
WORKDIR $APP_HOME

RUN apt-get update && \
    apt-get install -y --no-install-recommends ffmpeg git && \
    apt-get clean && \
    rm -rf /var/lib/apt/lists/*

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY . .

COPY run.sh .
RUN chmod +x ./run.sh

CMD ["./run.sh"]
