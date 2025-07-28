FROM python:3.11-slim

WORKDIR /app

# Copy requirements first
COPY requirements.txt .

# Install Python packages
RUN pip install --no-cache-dir -r requirements.txt

# Copy application code
COPY app/ .

# Set environment
ENV PYTHONPATH="/app"

# Simple health check
HEALTHCHECK --interval=30s --timeout=5s --start-period=10s --retries=2 \
    CMD python -c "print('Worker healthy')" || exit 1

# Run worker
CMD ["python", "-c", "print('Worker Service Starting...'); import time; time.sleep(1); exec(open('main.py').read())"]
