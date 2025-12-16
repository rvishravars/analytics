FROM python:3.11-slim

WORKDIR /app

# Install system dependencies if needed (e.g., for compilation)
RUN apt-get update && apt-get install -y \
    build-essential \
    && rm -rf /var/lib/apt/lists/*

# Copy requirements first to leverage cache
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy source code
COPY . .

# Set PYTHONPATH to ensure imports work correctly
ENV PYTHONPATH=/app

# Run the application
CMD ["python", "main.py"]
