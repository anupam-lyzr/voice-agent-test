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
