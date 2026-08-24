# Fixation sur Debian Bookworm (Stable) pour éviter les erreurs 404/timeouts
FROM python:3.11-slim-bookworm

WORKDIR /app

# Configuration des retries apt + installation des dépendances système
RUN echo "Acquire::Retries \"5\";" > /etc/apt/apt.conf.d/80retries && \
    apt-get update --fix-missing && \
    apt-get install -y --no-install-recommends \
        gcc \
        build-essential \
        python3-dev \
    && rm -rf /var/lib/apt/lists/*

COPY requirements.txt .

# Mise à jour des outils et installation des packages Python
RUN pip install --no-cache-dir --upgrade pip setuptools wheel && \
    pip install --no-cache-dir -r requirements.txt

# Copie du code source
COPY main.py .
COPY consumer/ ./consumer/
COPY producer/ ./producer/
COPY scripts/ ./scripts/
COPY detection/ ./detection/
COPY tests/ ./tests/
COPY backend/ ./backend/
COPY api/ ./api/
COPY data/ ./data/

# Création et attribution des permissions à l'utilisateur non-root
RUN useradd --create-home streamshield && \
    chown -R streamshield:streamshield /app

USER streamshield

CMD ["python", "main.py"]
# FROM python:3.11-slim

# WORKDIR /app

# # Installation des dépendances de compilation système
# RUN apt-get update && apt-get install -y --no-install-recommends \
#     gcc \
#     build-essential \
#     python3-dev \
#     && rm -rf /var/lib/apt/lists/*

# COPY requirements.txt .

# # Mise à jour des outils de packaging puis installation des dépendances
# RUN pip install --no-cache-dir --upgrade pip setuptools wheel && \
#     pip install --no-cache-dir -r requirements.txt

# # Copie du code source
# COPY main.py .
# COPY consumer/ ./consumer/
# COPY producer/ ./producer/
# COPY scripts/ ./scripts/
# COPY detection/ ./detection/
# COPY tests/ ./tests/
# COPY backend/ ./backend/
# COPY api/ ./api/
# COPY data/ ./data/

# # Création de l'utilisateur non-root
# RUN useradd --create-home streamshield
# USER streamshield

# CMD ["python", "main.py"]