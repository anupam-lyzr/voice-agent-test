FROM python:3.11-slim

WORKDIR /app

# Install minimal system dependencies
RUN apt-get update && apt-get install -y curl && rm -rf /var/lib/apt/lists/*

# Copy requirements first (for Docker layer caching)
COPY requirements.txt .

# Install Python packages
RUN pip install --no-cache-dir -r requirements.txt

# Copy application code
COPY app/ .

# Set environment
ENV PYTHONPATH="/app"

# Expose port
EXPOSE 8000

# Simple health check
HEALTHCHECK --interval=30s --timeout=5s --start-period=10s --retries=2 \
    CMD curl -f http://localhost:8000/health || exit 1

# Run with basic uvicorn
CMD ["python", "-c", "print('API Service Starting...'); import time; time.sleep(1); exec(open('main.py').read())"]
