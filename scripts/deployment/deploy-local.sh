#!/bin/bash

# Local deployment script
set -e

echo "🚀 Deploying Voice Agent locally..."

# Check environment
if [ ! -f ".env" ]; then
    echo "❌ .env file not found. Copy from .env.template and configure."
    exit 1
fi

# Build and start services
echo "📦 Building services..."
docker-compose build

echo "🏃 Starting services..."
docker-compose up -d

echo "⏳ Waiting for services to start..."
sleep 10

# Check service health
echo "🔍 Checking service health..."
docker-compose ps

# Import data if needed
if [ "$1" = "--import-data" ]; then
    echo "📥 Importing client data..."
    make import-data
fi

# Generate audio if needed
if [ "$1" = "--generate-audio" ] || [ "$2" = "--generate-audio" ]; then
    echo "🎵 Generating static audio..."
    make audio
fi

echo "✅ Local deployment complete!"
echo "🌐 API Service: http://localhost:8000"
echo "📊 MongoDB: mongodb://admin:password123@localhost:27017"
echo "🔄 Redis: redis://localhost:6379"
