# ===============================
# Data Governance - Correction Service
# ===============================

FROM python:3.11-slim

# -------------------------------
# Environment
# -------------------------------
ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONUNBUFFERED=1

# -------------------------------
# Workdir
# -------------------------------
WORKDIR /app

# -------------------------------
# System dependencies (light)
# -------------------------------
RUN apt-get update && apt-get install -y --no-install-recommends \
    gcc \
    curl \
    && rm -rf /var/lib/apt/lists/*

# -------------------------------
# Python dependencies
# -------------------------------
COPY requirements.txt .

# Mise à jour de pip pour assurer le support du streaming réseau
RUN pip install --no-cache-dir --upgrade pip

# Installation de PyTorch CPU avec timeout étendu et gestion des essais
RUN pip install --no-cache-dir \
    --default-timeout=1000 \
    --retries 10 \
    torch>=2.0.0 \
    --index-url https://download.pytorch.org/whl/cpu

# Installation des autres dépendances
RUN pip install --no-cache-dir --default-timeout=1000 --retries 10 -r requirements.txt

# -------------------------------
# Application code
# -------------------------------
COPY . .

# -------------------------------
# Expose FastAPI port
# -------------------------------
EXPOSE 8006

# -------------------------------
# Run service
# -------------------------------
CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8006"]