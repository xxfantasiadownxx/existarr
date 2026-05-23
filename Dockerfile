FROM python:3.12-slim

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY . .

RUN mkdir -p /data /media

EXPOSE 5100

CMD ["gunicorn", "--bind", "0.0.0.0:5100", "--workers", "2", "--timeout", "60", "app:app"]
