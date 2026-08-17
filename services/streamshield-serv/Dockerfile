FROM python:3.12-slim

WORKDIR /app

# Dépendances système minimales (compilation de certains clients Kafka)
RUN apt-get update && apt-get install -y --no-install-recommends \
    gcc \
    && rm -rf /var/lib/apt/lists/*

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY consumer/ ./consumer/
COPY producer/ ./producer/
COPY scripts/ ./scripts/

# Utilisateur non-root -- cohérent avec les principes de sécurité du Projet Fédérateur
RUN useradd --create-home streamshield
USER streamshield

ENTRYPOINT ["python"]
CMD ["consumer/main.py", "--domain", "clients"]