FROM python:3.11-slim

WORKDIR /app

# 1. Install build dependencies for TenSEAL first (cached layer)
RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    cmake \
    && rm -rf /var/lib/apt/lists/*s

# 2. Copy and install Python requirements
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# 3. Copy application code
COPY . .

EXPOSE 8009

CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8009"]
# FROM python:3.11-slim

# WORKDIR /app

# COPY requirements.txt .

# # Install build dependencies for TenSEAL
# RUN apt-get update && apt-get install -y \
#     build-essential \
#     cmake \
#     && rm -rf /var/lib/apt/lists/*

# RUN pip install --no-cache-dir -r requirements.txt

# COPY . .

# EXPOSE 8009

# CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8009"]
