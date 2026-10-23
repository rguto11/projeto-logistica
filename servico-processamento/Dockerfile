FROM python:3.12.12-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY . .

RUN useradd -m app
USER app

EXPOSE 8002

CMD ["gunicorn", "-b", "0.0.0.0:8002", "-w", "2", "--timeout", "60", "app:app"]
