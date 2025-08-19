# Use Alpine base image to save disk space
FROM python:3.11-alpine

WORKDIR /app

# Install dependencies
RUN apk update && \
    apk add --no-cache \
        curl \
        ffmpeg \
        gcc \
        musl-dev \
        python3-dev \
        libffi-dev \
        openssl-dev

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy application code
COPY app/ .

# Copy your audio-generation directory with all audio files
COPY app/audio-generation /app/audio-generation

# Ensure directories exist
RUN mkdir -p static/audio/temp \
    audio-generation/segments \
    audio-generation/names/clients \
    audio-generation/names/agents \
    audio-generation/concatenated_cache

ENV PYTHONPATH=/app

EXPOSE 8000

CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8000"]