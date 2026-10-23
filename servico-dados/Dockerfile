FROM python:3.12.12-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY . .

RUN useradd -m app
USER app

EXPOSE 8001

CMD ["sh", "-c", "python init_db.py && exec gunicorn -b 0.0.0.0:8001 -w 2 app:app"]
