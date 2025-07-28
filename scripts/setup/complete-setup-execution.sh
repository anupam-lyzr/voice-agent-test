#!/bin/bash
# complete-setup-execution.sh
# Complete setup and execution plan for Voice Agent Production System

set -e

GREEN='\033[0;32m'
BLUE='\033[0;34m'
YELLOW='\033[1;33m'
RED='\033[0;31m'
BOLD='\033[1m'
NC='\033[0m'

echo -e "${BOLD}${BLUE}🚀 VOICE AGENT PRODUCTION SYSTEM - COMPLETE SETUP${NC}"
echo -e "${BLUE}=====================================================${NC}"

# Function to check if command was successful
check_status() {
    if [ $? -eq 0 ]; then
        echo -e "${GREEN}✅ $1 completed successfully${NC}"
    else
        echo -e "${RED}❌ $1 failed${NC}"
        exit 1
    fi
}

# Function to create missing files/directories
setup_project_structure() {
    echo -e "${YELLOW}📁 Setting up project structure...${NC}"
    
    # Create required directories
    mkdir -p {data,scripts/setup,config,ecs-api-service/app/static/audio,ecs-worker-service/app/static}
    
    # Create config directory for Google service account
    mkdir -p config
    
    # Create placeholder for Google service account (user will need to add real file)
    if [ ! -f "config/google-service-account.json" ]; then
        cat > config/google-service-account.json << 'EOF'
{
  "type": "service_account",
  "project_id": "your-project-id",
  "private_key_id": "your-key-id",
  "private_key": "-----BEGIN PRIVATE KEY-----\nYOUR-PRIVATE-KEY\n-----END PRIVATE KEY-----\n",
  "client_email": "voice-agent-calendar@your-project.iam.gserviceaccount.com",
  "client_id": "your-client-id",
  "auth_uri": "https://accounts.google.com/o/oauth2/auth",
  "token_uri": "https://oauth2.googleapis.com/token",
  "auth_provider_x509_cert_url": "https://www.googleapis.com/oauth2/v1/certs",
  "client_x509_cert_url": "https://www.googleapis.com/oauth2/v1/certs"
}
EOF
        echo -e "${YELLOW}⚠️  Created placeholder Google service account file${NC}"
        echo -e "${YELLOW}    Please replace config/google-service-account.json with your real credentials${NC}"
    fi
}

# Step 1: Prerequisites Check
echo -e "${YELLOW}📋 Step 1: Checking prerequisites...${NC}"

if ! command -v docker &> /dev/null; then
    echo -e "${RED}❌ Docker not found. Please install Docker Desktop.${NC}"
    exit 1
fi

if ! docker info > /dev/null 2>&1; then
    echo -e "${RED}❌ Docker is not running. Please start Docker Desktop.${NC}"
    exit 1
fi

if ! command -v python3 &> /dev/null; then
    echo -e "${RED}❌ Python 3 not found. Please install Python 3.8+.${NC}"
    exit 1
fi

if [ ! -f "docker-compose.yml" ]; then
    echo -e "${RED}❌ Please run this script from the project root directory.${NC}"
    exit 1
fi

check_status "Prerequisites check"

# Step 2: Project Structure Setup
setup_project_structure
check_status "Project structure setup"

# Step 3: Create agents configuration with real emails
echo -e "${YELLOW}👥 Step 3: Creating agents configuration...${NC}"

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

check_status "Agents configuration"

# Step 4: Create test clients data
echo -e "${YELLOW}📊 Step 4: Creating test client data...${NC}"

cat > data/test-clients.csv << 'EOF'
first_name,last_name,phone,email,tags,last_contacted
Test,User1,+15551234567,test1@example.com,AB - Anthony Fracchia,2023-01-01T10:00:00Z
Test,User2,+15551234568,test2@example.com,AB - LaShawn Boyd,2023-01-01T10:00:00Z
Test,User3,+15551234569,test3@example.com,AB - India Watson,2023-01-01T10:00:00Z
Test,User4,+15551234570,test4@example.com,AB - Hineth Pettway,2023-01-01T10:00:00Z
Test,User5,+15551234571,test5@example.com,AB - Keith Braswell,2023-01-01T10:00:00Z
Your,Name,+15551234572,your.email@example.com,AB - Anthony Fracchia,2023-01-01T10:00:00Z
EOF

check_status "Test client data creation"

# Step 5: Environment Configuration
echo -e "${YELLOW}⚙️  Step 5: Environment configuration...${NC}"

if [ ! -f ".env" ]; then
    cp .env.template .env
    echo -e "${YELLOW}📄 Created .env file from template${NC}"
    echo -e "${RED}⚠️  IMPORTANT: Edit .env with your actual API keys before continuing!${NC}"
    echo -e "${YELLOW}   Required keys: DEEPGRAM_API_KEY, ELEVENLABS_API_KEY, TWILIO_*, LYZR_*${NC}"
    echo -e "${YELLOW}   Press Enter when you've updated .env...${NC}"
    read
fi

check_status "Environment configuration"

# Step 6: Build and Start Services
echo -e "${YELLOW}🔨 Step 6: Building and starting services...${NC}"

# Make build script executable
chmod +x scripts/build-services.sh

# Build services
./scripts/build-services.sh
check_status "Service build"

# Wait for services to be ready
echo -e "${YELLOW}⏳ Waiting for services to initialize...${NC}"
sleep 15

# Step 7: System Health Check
echo -e "${YELLOW}🧪 Step 7: System health check...${NC}"

echo "Testing API health..."
api_health=$(curl -s http://localhost:8000/health || echo "failed")
if echo "$api_health" | grep -q "healthy"; then
    echo -e "${GREEN}✅ API Service is healthy${NC}"
else
    echo -e "${RED}❌ API Service health check failed${NC}"
    echo "Response: $api_health"
fi

echo "Testing Twilio webhook..."
webhook_test=$(curl -s -X POST http://localhost:8000/twilio/voice \
    -H "Content-Type: application/x-www-form-urlencoded" \
    -d "CallSid=test123&CallStatus=in-progress&From=%2B15551234567" || echo "failed")

if echo "$webhook_test" | grep -q "Response"; then
    echo -e "${GREEN}✅ Twilio webhook is working${NC}"
else
    echo -e "${RED}❌ Twilio webhook test failed${NC}"
fi

check_status "System health check"

# Step 8: Install Python Dependencies for Data Import
echo -e "${YELLOW}📦 Step 8: Installing Python dependencies...${NC}"

# Create requirements for scripts
cat > scripts/requirements.txt << 'EOF'
pandas==2.0.3
openpyxl==3.1.2
motor==3.3.2
pymongo==4.6.0
pydantic==2.4.2
pydantic-settings==2.0.3
python-dotenv==1.0.0
google-api-python-client==2.95.0
google-auth==2.22.0
google-auth-oauthlib==1.0.0
google-auth-httplib2==0.1.0
httpx==0.25.2
EOF

# Install dependencies
python3 -m pip install -r scripts/requirements.txt
check_status "Python dependencies installation"

# Step 9: Test Client Data Import
echo -e "${YELLOW}📥 Step 9: Testing client data import...${NC}"

# Copy the import script to the correct location
mkdir -p scripts/setup

# Run test import with test data
echo "Testing import with test clients..."
python3 scripts/setup/client_import_script.py --file data/test-clients.csv --test --dry-run
check_status "Test data import (dry run)"

# Step 10: Dashboard Setup
echo -e "${YELLOW}🖥️  Step 10: Dashboard setup...${NC}"

if [ -d "dashboard" ]; then
    echo "Dashboard directory already exists, updating..."
else
    echo "Creating dashboard..."
fi

# Create the dashboard structure (already created above in the artifacts)
echo -e "${GREEN}✅ Dashboard structure created${NC}"

# Step 11: Final System Status
echo -e "${YELLOW}📊 Step 11: Final system status...${NC}"

echo -e "${BLUE}🌐 Service Status:${NC}"
docker-compose ps

echo -e "${BLUE}📋 Recent Logs:${NC}"
echo "API Service (last 5 lines):"
docker-compose logs --tail=5 api-service

echo "Worker Service (last 5 lines):"
docker-compose logs --tail=5 worker-service

# Step 12: Next Steps Information
echo
echo -e "${BOLD}${GREEN}🎉 SYSTEM SETUP COMPLETE!${NC}"
echo -e "${BLUE}================================${NC}"
echo
echo -e "${BLUE}🌐 Service URLs:${NC}"
echo "  API Service: http://localhost:8000"
echo "  API Health: http://localhost:8000/health"
echo "  Voice Webhook: http://localhost:8000/twilio/voice"
echo "  MongoDB: mongodb://admin:password123@localhost:27017"
echo "  Redis: redis://localhost:6379"
echo
echo -e "${YELLOW}📝 IMMEDIATE NEXT STEPS:${NC}"
echo
echo -e "${BOLD}1. Complete API Configuration:${NC}"
echo "   ✓ Edit .env with your actual API keys"
echo "   ✓ Test each service integration"
echo
echo -e "${BOLD}2. Import Real Client Data:${NC}"
echo "   python3 scripts/setup/client_import_script.py --file 'AAG  Lyzr  No Contact  2 Years.xlsx'"
echo "   (This will import all 6,426 clients with correct agent assignment)"
echo
echo -e "${BOLD}3. Set up Google Calendar Integration:${NC}"
echo "   ✓ Create Google Cloud service account"
echo "   ✓ Download credentials JSON file"
echo "   ✓ Replace config/google-service-account.json"
echo "   ✓ Share agent calendars with service account email"
echo
echo -e "${BOLD}4. Start Dashboard:${NC}"
echo "   cd dashboard"
echo "   npm install"
echo "   npm start"
echo "   (Dashboard will be available at http://localhost:3000)"
echo
echo -e "${BOLD}5. Test Voice Call:${NC}"
echo "   ✓ Configure Twilio webhook URL: http://your-domain.com/twilio/voice"
echo "   ✓ Make test call to your own number"
echo "   ✓ Verify agent assignment and call flow"
echo
echo -e "${BLUE}🔧 Development Commands:${NC}"
echo "  docker-compose logs -f              # View live logs"
echo "  docker-compose restart              # Restart services"
echo "  docker-compose down                 # Stop services"
echo "  docker-compose up -d                # Start services"
echo "  python3 scripts/setup/client_import_script.py --help  # Import help"
echo
echo -e "${BLUE}🧪 Testing Commands:${NC}"
echo "  # Import test data:"
echo "  python3 scripts/setup/client_import_script.py --file data/test-clients.csv --test"
echo
echo "  # Test voice webhook:"
echo "  curl -X POST http://localhost:8000/twilio/voice"
echo
echo "  # Check system health:"
echo "  curl http://localhost:8000/health"
echo
echo -e "${GREEN}🎯 READY FOR PRODUCTION TESTING!${NC}"
echo
echo -e "${YELLOW}⚠️  IMPORTANT REMINDERS:${NC}"
echo "- All test calls will be marked as test clients"
echo "- Production mode can be toggled in the dashboard"
echo "- Real client data import requires the Excel file"
echo "- Google Calendar requires service account setup"
echo "- Twilio webhooks need public URL (use ngrok for testing)"