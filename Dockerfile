FROM python:3.11-slim

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY backend/ ./backend/
COPY frontend/ ./frontend/
COPY dados/ ./dados/

RUN adduser --disabled-password --gecos "" appuser && \
	chown -R appuser:appuser /app

USER appuser

WORKDIR /app

CMD ["uvicorn", "backend.main:app", "--host", "0.0.0.0", "--port", "8000"]
