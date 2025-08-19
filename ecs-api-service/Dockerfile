# Multi-stage build to optimize space usage
FROM python:3.11-alpine AS builder

WORKDIR /app

# Install build dependencies
RUN apk update && \
    apk add --no-cache \
        gcc \
        musl-dev \
        python3-dev \
        libffi-dev \
        openssl-dev

# Copy and install Python dependencies
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Final stage
FROM python:3.11-alpine

WORKDIR /app

# Install runtime dependencies only
RUN apk update && \
    apk add --no-cache \
        curl \
        ffmpeg

# Copy Python packages from builder stage
COPY --from=builder /usr/local/lib/python3.11/site-packages /usr/local/lib/python3.11/site-packages
COPY --from=builder /usr/local/bin /usr/local/bin

# Copy application code
COPY app/ .

# Create necessary directories
RUN mkdir -p static/audio/temp \
    audio-generation/segments \
    audio-generation/names/clients \
    audio-generation/names/agents \
    audio-generation/concatenated_cache

ENV PYTHONPATH=/app

EXPOSE 8000

CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8000"]