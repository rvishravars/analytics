FROM python:3.11-slim

WORKDIR /app

# Install system dependencies for building python packages and openssl
RUN apt-get update && apt-get install -y \
    build-essential \
    openssl \
    lsof \
    && rm -rf /var/lib/apt/lists/*

# Copy requirements
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy source code
COPY . .

# Generate certificates during build (or entrypoint)
# For simplicity, we generate them here so they exist in the image
WORKDIR /app/scripts
RUN bash generate_certs.sh

WORKDIR /app/src

# Expose ports
EXPOSE 8000 8001 8002 8003

# Default command (can be overridden)
CMD ["python3", "server.py"]
