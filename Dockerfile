FROM python:3.11-slim

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY . .

ENV TG_BOT_TOKEN=your_bot_token
ENV TG_USER_ID=your_chat_id
ENV TG_ADMIN_ID=your_admin_id

CMD ["python", "main.py"]
