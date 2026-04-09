FROM python:3.11-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1

WORKDIR /app

COPY requirements.txt /app/requirements.txt
RUN pip install --no-cache-dir -r /app/requirements.txt

COPY backend /app/backend
COPY config /app/config
COPY runner.py /app/runner.py

EXPOSE 8000

CMD ["uvicorn", "backend.api.routes:app", "--host", "0.0.0.0", "--port", "8000"]
