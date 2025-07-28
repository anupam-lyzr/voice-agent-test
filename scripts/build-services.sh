#!/bin/bash
# Verbose build script with better error handling

set -e

GREEN='\033[0;32m'
BLUE='\033[0;34m'
YELLOW='\033[1;33m'
RED='\033[0;31m'
NC='\033[0m'

echo -e "${BLUE}📦 Building Voice Agent Services (Minimal Version)${NC}"

# Function to handle errors
handle_error() {
    echo -e "${RED}❌ Build failed at: $1${NC}"
    echo -e "${YELLOW}💡 Try: docker-compose logs api-service${NC}"
    echo -e "${YELLOW}💡 Try: docker-compose logs worker-service${NC}"
    exit 1
}

# Set error handler
trap 'handle_error $LINENO' ERR

# Check directory
if [ ! -f "docker-compose.yml" ]; then
    echo -e "${RED}❌ Please run from project root${NC}"
    exit 1
fi

# Stop existing containers
echo -e "${YELLOW}🛑 Stopping existing containers...${NC}"
docker-compose down --remove-orphans

# Sync shared code if it exists
if [ -d "shared-source" ]; then
    echo -e "${YELLOW}🔄 Syncing shared code...${NC}"
    
    # Sync to API Service
    echo "  → API Service"
    rm -rf ecs-api-service/app/shared
    cp -r shared-source ecs-api-service/app/shared
    find ecs-api-service/app/shared -type d -exec touch {}/__init__.py \;
    
    # Sync to Worker Service
    echo "  → Worker Service"
    rm -rf ecs-worker-service/app/shared
    cp -r shared-source ecs-worker-service/app/shared
    find ecs-worker-service/app/shared -type d -exec touch {}/__init__.py \;
    
    echo -e "${GREEN}✅ Shared code synced${NC}"
fi

# Build with verbose output
echo -e "${YELLOW}🏗️  Building API Service...${NC}"
cd ecs-api-service
docker build -t voice-agent-api . --progress=plain
cd ..

echo -e "${YELLOW}🏗️  Building Worker Service...${NC}"
cd ecs-worker-service  
docker build -t voice-agent-worker . --progress=plain
cd ..

echo -e "${GREEN}✅ Docker images built successfully${NC}"

# Start services
echo -e "${YELLOW}🚀 Starting services...${NC}"
docker-compose up -d

# Wait a moment for services to start
echo -e "${YELLOW}⏳ Waiting for services to start...${NC}"
sleep 5

# Check service status
echo -e "${BLUE}📊 Service Status:${NC}"
docker-compose ps

echo -e "${GREEN}✅ Build and start complete!${NC}"
echo
echo -e "${BLUE}🌐 Service URLs:${NC}"
echo "  API: http://localhost:8000"
echo "  Health: http://localhost:8000/health"
echo
echo -e "${YELLOW}💡 Check logs with:${NC}"
echo "  docker-compose logs -f api-service"
echo "  docker-compose logs -f worker-service"
