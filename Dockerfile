FROM python:3.12-alpine

WORKDIR /app

ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONUNBUFFERED=1

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY bot.py darexsh-bot.py apps_data.py sync_projects.py telegram_health_server.py ./

CMD ["python", "bot.py"]
