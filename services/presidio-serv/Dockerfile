FROM python:3.11-slim

WORKDIR /app

# Installation des dépendances système de compilation
RUN apt-get update && apt-get install -y --no-install-recommends \
    gcc \
    python3-dev \
    && rm -rf /var/lib/apt/lists/*

COPY requirements.txt .

# 1. Mise à jour des outils fondamentaux et blocage de setuptools
RUN pip install --no-cache-dir --upgrade pip "setuptools<70.0.0" wheel

# 2. Pré-installation des dépendances de compilation nécessaires à thinc/spacy
RUN pip install --no-cache-dir "Cython<3.0" "numpy>=1.25.0"

# 3. Installation des requirements sans isolement de build
RUN pip install --no-cache-dir --no-build-isolation -r requirements.txt

# Téléchargement des modèles spaCy
RUN python -m spacy download en_core_web_sm
RUN python -m spacy download fr_core_news_sm

# Copie des fichiers d'application
COPY . .

EXPOSE 8003

CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8003", "--workers", "4"]
