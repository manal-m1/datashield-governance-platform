FROM python:3.11-slim

WORKDIR /app

RUN apt-get update && apt-get install -y --no-install-recommends \
    gcc \
    && rm -rf /var/lib/apt/lists/*

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY main.py .
COPY consumer/ ./consumer/
COPY producer/ ./producer/
COPY scripts/ ./scripts/
COPY detection/ ./detection/
COPY tests/ ./tests/
COPY backend/ ./backend/
COPY api/ ./api/
COPY data/ ./data/

RUN useradd --create-home streamshield
USER streamshield

CMD ["python", "main.py"]