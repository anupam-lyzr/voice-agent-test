#!/bin/bash
# system-startup.sh
# Start the existing voice agent system and run initial tests

set -e

GREEN='\033[0;32m'
BLUE='\033[0;34m'
YELLOW='\033[1;33m'
RED='\033[0;31m'
NC='\033[0m'

echo -e "${BLUE}🚀 Starting Voice Agent Production System${NC}"

# Check prerequisites
echo -e "${YELLOW}📋 Checking prerequisites...${NC}"

if ! docker info > /dev/null 2>&1; then
    echo -e "${RED}❌ Docker is not running. Please start Docker Desktop.${NC}"
    exit 1
fi

if [ ! -f "docker-compose.yml" ]; then
    echo -e "${RED}❌ Please run from project root directory${NC}"
    exit 1
fi

# Create .env if it doesn't exist
if [ ! -f ".env" ]; then
    echo -e "${YELLOW}📄 Creating .env from template...${NC}"
    cp .env.template .env
    echo -e "${YELLOW}⚠️  Please edit .env with your actual API keys before continuing${NC}"
    echo -e "${YELLOW}⚠️  Press Enter when ready...${NC}"
    read
fi

# Create required directories
echo -e "${YELLOW}📁 Creating required directories...${NC}"
mkdir -p data
mkdir -p scripts/setup
mkdir -p ecs-api-service/app/static/audio
mkdir -p ecs-worker-service/app/static

# Update agents configuration with real emails
echo -e "${YELLOW}👥 Creating agents configuration with real emails...${NC}"
cat > data/agents.json << 'EOF'
{
  "agents": [
    {
      "id": "anthony_fracchia",
      "name": "Anthony Fracchia",
      "email": "anthony@altruisadvisor.com",
      "google_calendar_id": "anthony@altruisadvisor.com",
      "timezone": "America/New_York",
      "working_hours": "9AM-5PM",
      "specialties": ["health", "medicare"],
      "tag_identifier": "AB - Anthony Fracchia",
      "client_count": 1861
    },
    {
      "id": "lashawn_boyd",
      "name": "LaShawn Boyd",
      "email": "lashawn@altruisadvisor.com",
      "google_calendar_id": "lashawn@altruisadvisor.com",
      "timezone": "America/New_York",
      "working_hours": "9AM-5PM",
      "specialties": ["auto", "life"],
      "tag_identifier": "AB - LaShawn Boyd",
      "client_count": 822
    },
    {
      "id": "india_watson",
      "name": "India Watson",
      "email": "india@altruisadvisor.com",
      "google_calendar_id": "india@altruisadvisor.com",
      "timezone": "America/New_York",
      "working_hours": "9AM-5PM",
      "specialties": ["health", "dental"],
      "tag_identifier": "AB - India Watson",
      "client_count": 770
    },
    {
      "id": "hineth_pettway",
      "name": "Hineth Pettway",
      "email": "hineth@altruisadvisor.com",
      "google_calendar_id": "hineth@altruisadvisor.com",
      "timezone": "America/New_York",
      "working_hours": "9AM-5PM",
      "specialties": ["medicare", "supplements"],
      "tag_identifier": "AB - Hineth Pettway",
      "client_count": 649
    },
    {
      "id": "keith_braswell",
      "name": "Keith Braswell",
      "email": "keith@altruisadvisor.com",
      "google_calendar_id": "keith@altruisadvisor.com",
      "timezone": "America/New_York",
      "working_hours": "9AM-5PM",
      "specialties": ["vision", "dental"],
      "tag_identifier": "AB - Keith Braswell",
      "client_count": 907
    }
  ]
}
EOF

# Create test clients data
echo -e "${YELLOW}📊 Creating test client data...${NC}"
cat > data/test-clients.csv << 'EOF'
first_name,last_name,phone,email,tags,last_contacted
Test,User1,+15551234567,test1@example.com,AB - Anthony Fracchia,2023-01-01T10:00:00Z
Test,User2,+15551234568,test2@example.com,AB - LaShawn Boyd,2023-01-01T10:00:00Z
Test,User3,+15551234569,test3@example.com,AB - India Watson,2023-01-01T10:00:00Z
Test,User4,+15551234570,test4@example.com,AB - Hineth Pettway,2023-01-01T10:00:00Z
Test,User5,+15551234571,test5@example.com,AB - Keith Braswell,2023-01-01T10:00:00Z
EOF

# Sync shared code and build services
echo -e "${YELLOW}🔄 Syncing shared code and building services...${NC}"
if [ -f "scripts/build-services.sh" ]; then
    chmod +x scripts/build-services.sh
    ./scripts/build-services.sh
else
    echo -e "${RED}❌ build-services.sh not found. Running docker-compose build directly...${NC}"
    docker-compose build
fi

# Start services
echo -e "${YELLOW}🚀 Starting services...${NC}"
docker-compose up -d

# Wait for services to be ready
echo -e "${YELLOW}⏳ Waiting for services to start...${NC}"
sleep 15

# Test the system
echo -e "${YELLOW}🧪 Testing system health...${NC}"

# Test API health
echo "Testing API health..."
api_health=$(curl -s http://localhost:8000/health || echo "failed")
if echo "$api_health" | grep -q "healthy"; then
    echo -e "${GREEN}✅ API Service is healthy${NC}"
else
    echo -e "${RED}❌ API Service health check failed${NC}"
    echo "Response: $api_health"
fi

# Test root endpoint
echo "Testing root endpoint..."
root_response=$(curl -s http://localhost:8000/ || echo "failed")
if echo "$root_response" | grep -q "Voice Agent API"; then
    echo -e "${GREEN}✅ Root endpoint is working${NC}"
else
    echo -e "${RED}❌ Root endpoint test failed${NC}"
fi

# Test Twilio voice webhook
echo "Testing Twilio voice webhook..."
webhook_response=$(curl -s -X POST http://localhost:8000/twilio/voice \
    -H "Content-Type: application/x-www-form-urlencoded" \
    -d "CallSid=test123&CallStatus=in-progress&From=%2B15551234567&To=%2B15551234567" || echo "failed")

if echo "$webhook_response" | grep -q "Response"; then
    echo -e "${GREEN}✅ Twilio voice webhook is working${NC}"
else
    echo -e "${RED}❌ Twilio voice webhook test failed${NC}"
    echo "Response: $webhook_response"
fi

# Check service logs
echo -e "${YELLOW}📋 Recent service logs:${NC}"
echo "API Service logs (last 10 lines):"
docker-compose logs --tail=10 api-service

echo "Worker Service logs (last 10 lines):"
docker-compose logs --tail=10 worker-service

# Service status
echo -e "${BLUE}📊 Service Status:${NC}"
docker-compose ps

echo
echo -e "${GREEN}✅ System startup complete!${NC}"
echo
echo -e "${BLUE}🌐 Service URLs:${NC}"
echo "  API Service: http://localhost:8000"
echo "  API Health: http://localhost:8000/health"
echo "  Voice Webhook: http://localhost:8000/twilio/voice"
echo "  MongoDB: mongodb://admin:password123@localhost:27017"
echo "  Redis: redis://localhost:6379"
echo
echo -e "${YELLOW}📝 Next Steps:${NC}"
echo "1. Verify your .env file has correct API keys"
echo "2. Test voice webhook: curl -X POST http://localhost:8000/twilio/voice"
echo "3. Import client data: python scripts/setup/import-client-data.py"
echo "4. Check logs: docker-compose logs -f"
echo
echo -e "${BLUE}🔧 Useful Commands:${NC}"
echo "  docker-compose logs -f          # View live logs"
echo "  docker-compose restart          # Restart services"
echo "  docker-compose down             # Stop services"
echo "  docker-compose up -d            # Start services"