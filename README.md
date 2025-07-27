# Voice Agent Production System

Production-ready AI Voice Agent for 14,000-client re-engagement campaign with sub-2 second latency, natural conversations, and automatic CRM integration.

## 🎯 Key Features

- **Hybrid TTS**: Pre-generated audio for static responses (<200ms) + Dynamic LYZR+ElevenLabs for complex conversations
- **Split Architecture**: ECS API Service (Twilio webhooks) + ECS Worker Service (campaign processing)
- **Business Hours**: Automatic enforcement (9 AM-5 PM ET, Mon-Fri)
- **CRM Integration**: Automatic Capsule CRM tagging and agent assignment
- **Call Summaries**: LYZR-powered summaries with structured data
- **Real-time Dashboard**: Live campaign progress and call details

## 🚀 Quick Start

### Local Development
```bash
# 1. Setup project
./setup-project.sh

# 2. Configure environment
cp .env.template .env
# Edit .env with your API keys

# 3. Start services
docker-compose up -d

# 4. Import client data
python scripts/setup/import-client-data.py

# 5. Generate static audio
python audio-generation/scripts/generate_static_audio.py
```

### Production Deployment
```bash
# Deploy AWS infrastructure
./scripts/deployment/deploy-infrastructure.sh

# Deploy application services
./scripts/deployment/deploy-api-service.sh
./scripts/deployment/deploy-worker-service.sh

# Deploy dashboard
./scripts/deployment/deploy-dashboard.sh
```

## 📊 Architecture

```
Campaign: EventBridge → Lambda → SQS → ECS Worker
Voice: Twilio ↔ ALB ↔ ECS API ↔ AI Services
Data: DocumentDB + Redis + S3
```

## 🔧 Configuration

See `.env.template` for all required environment variables.

## 📞 API Endpoints

- `POST /twilio/voice` - Twilio voice webhook
- `POST /twilio/status` - Call status updates
- `POST /twilio/media-stream` - Real-time audio processing
- `GET /health` - Health check
- `GET /metrics` - Performance metrics

## 🧪 Testing

```bash
# Unit tests
python -m pytest tests/unit/

# Integration tests  
python -m pytest tests/integration/

# End-to-end tests
python -m pytest tests/e2e/

# Load testing
python scripts/testing/test-concurrent-calls.py
```
