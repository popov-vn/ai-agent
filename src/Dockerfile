FROM python:3.9-slim

WORKDIR /app

ARG OPEN_API_TOKEN
ARG TELEGRAM_BOT_TOKEN

COPY agent2.py .
COPY telebot.py .
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY . .

CMD ["python", "telebot.py"]