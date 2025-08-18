#!/bin/bash

# Build script that generates audio files before Docker build

echo "🎵 Generating audio files in the correct location..."
cd app
python -m app.scripts.generate_segmented_audio

echo "🐳 Building Docker image..."
cd ..
docker build -t voice-agent-api .

echo "✅ Build complete!"
echo "📁 Audio files generated in: app/audio-generation/"
