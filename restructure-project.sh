#!/bin/bash
# restructure-project.sh
# Reorganizes project for self-contained services

set -e

GREEN='\033[0;32m'
BLUE='\033[0;34m'
YELLOW='\033[1;33m'
NC='\033[0m'

echo -e "${BLUE}🔧 Restructuring project for self-contained services${NC}"

# Move shared to shared-source
if [ -d "shared" ] && [ ! -d "shared-source" ]; then
    echo -e "${YELLOW}📁 Moving shared/ to shared-source/...${NC}"
    mv shared shared-source
fi

# Create the build scripts
mkdir -p scripts

# Create build script
cat > scripts/build-services.sh << 'EOF'
#!/bin/bash
# Build script that syncs shared code and builds services

set -e

GREEN='\033[0;32m'
BLUE='\033[0;34m'
YELLOW='\033[1;33m'
NC='\033[0m'

echo -e "${BLUE}📦 Building Voice Agent Services${NC}"

# Check directory
if [ ! -f "docker-compose.yml" ]; then
    echo -e "${YELLOW}⚠️  Please run from project root${NC}"
    exit 1
fi

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

# Build services
echo -e "${YELLOW}🏗️  Building services...${NC}"
docker-compose build

echo -e "${GREEN}✅ Build complete${NC}"
EOF

chmod +x scripts/build-services.sh

# Create sync script
cat > scripts/sync-shared.sh << 'EOF'
#!/bin/bash
# Quick sync without rebuild

set -e

GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m'

echo -e "${YELLOW}🔄 Syncing shared code...${NC}"

# Sync to both services
rm -rf ecs-api-service/app/shared ecs-worker-service/app/shared
cp -r shared-source ecs-api-service/app/shared
cp -r shared-source ecs-worker-service/app/shared
find ecs-api-service/app/shared -type d -exec touch {}/__init__.py \;
find ecs-worker-service/app/shared -type d -exec touch {}/__init__.py \;

echo -e "${GREEN}✅ Sync complete${NC}"

# Restart if running
if [ "$(docker-compose ps -q)" ]; then
    echo -e "${YELLOW}🔄 Restarting services...${NC}"
    docker-compose restart
fi
EOF

chmod +x scripts/sync-shared.sh

# Update Makefile
cat >> Makefile << 'EOF'

# Build services with shared code sync
build:
	./scripts/build-services.sh

# Quick sync shared code
sync-shared:
	./scripts/sync-shared.sh

# Development with sync
dev-build:
	./scripts/build-services.sh
	docker-compose up -d

# Updated development start
dev: sync-shared
	docker-compose up -d
EOF

# Update Dockerfiles to not copy shared externally
cat > ecs-api-service/Dockerfile << 'EOF'
FROM python:3.11-slim

WORKDIR /app

# Install system dependencies
RUN apt-get update && apt-get install -y \
    gcc \
    curl \
    && rm -rf /var/lib/apt/lists/*

# Copy requirements and install
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy application code (shared code is already copied by build script)
COPY app/ .

# Set Python path  
ENV PYTHONPATH="/app"

# Expose port
EXPOSE 8000

# Health check
HEALTHCHECK --interval=30s --timeout=10s --start-period=5s --retries=3 \
    CMD curl -f http://localhost:8000/health || exit 1

# Run application
CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8000", "--reload"]
EOF

cat > ecs-worker-service/Dockerfile << 'EOF'
FROM python:3.11-slim

WORKDIR /app

# Install system dependencies  
RUN apt-get update && apt-get install -y \
    gcc \
    && rm -rf /var/lib/apt/lists/*

# Copy requirements and install
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy application code (shared code is already copied by build script)
COPY app/ .

# Set Python path
ENV PYTHONPATH="/app"

# Health check
HEALTHCHECK --interval=30s --timeout=10s --start-period=5s --retries=3 \
    CMD python -c "import main; print('Worker healthy')" || exit 1

# Run worker
CMD ["python", "-m", "main"]
EOF

# Update docker-compose.yml for new structure
cat > docker-compose.yml << 'EOF'
version: '3.8'

services:
  # MongoDB (DocumentDB alternative for local development)
  mongodb:
    image: mongo:6.0
    container_name: voice-agent-mongodb
    ports:
      - "27017:27017"
    environment:
      - MONGO_INITDB_ROOT_USERNAME=admin
      - MONGO_INITDB_ROOT_PASSWORD=password123
      - MONGO_INITDB_DATABASE=voice_agent
    volumes:
      - mongodb_data:/data/db
    networks:
      - voice-agent-network

  # Redis for session caching
  redis:
    image: redis:7-alpine
    container_name: voice-agent-redis
    ports:
      - "6379:6379"
    command: redis-server --requirepass redis123
    volumes:
      - redis_data:/data
    networks:
      - voice-agent-network

  # ECS API Service (Twilio webhooks)
  api-service:
    build: ./ecs-api-service
    container_name: voice-agent-api
    ports:
      - "8000:8000"
    env_file:
      - .env
    environment:
      - DOCUMENTDB_HOST=mongodb
      - REDIS_URL=redis://:redis123@redis:6379
      - PYTHONPATH=/app
    depends_on:
      - mongodb
      - redis
    networks:
      - voice-agent-network
    restart: unless-stopped

  # ECS Worker Service (Campaign processing)
  worker-service:
    build: ./ecs-worker-service
    container_name: voice-agent-worker
    env_file:
      - .env
    environment:
      - DOCUMENTDB_HOST=mongodb
      - REDIS_URL=redis://:redis123@redis:6379
      - PYTHONPATH=/app
    depends_on:
      - mongodb
      - redis
    networks:
      - voice-agent-network
    restart: unless-stopped

volumes:
  mongodb_data:
  redis_data:

networks:
  voice-agent-network:
    driver: bridge
EOF

echo -e "${GREEN}✅ Project restructured for self-contained services${NC}"
echo
echo -e "${BLUE}📁 New Structure:${NC}"
echo "├── shared-source/           # Source of truth for shared code"
echo "├── ecs-api-service/         # Self-contained API service"
echo "├── ecs-worker-service/      # Self-contained worker service"
echo "└── scripts/                 # Build and sync scripts"
echo
echo -e "${YELLOW}🚀 Next Steps:${NC}"
echo "1. ./scripts/build-services.sh    # Build with shared code"
echo "2. docker-compose up -d           # Start services"
echo "3. make sync-shared               # Quick sync during development"