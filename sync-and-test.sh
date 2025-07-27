#!/bin/bash
# sync-and-test.sh
# Sync shared code to services and test the setup

set -e

GREEN='\033[0;32m'
BLUE='\033[0;34m'
YELLOW='\033[1;33m'
NC='\033[0m'

echo -e "${BLUE}🔄 Syncing shared code and testing setup${NC}"

# Check if we're in the right directory
if [ ! -f "docker-compose.yml" ]; then
    echo "❌ Please run from project root directory"
    exit 1
fi

echo -e "${YELLOW}📁 Copying shared code to services...${NC}"

# Copy shared-source to both services
echo "  → API Service"
rm -rf ecs-api-service/app/shared
cp -r shared-source ecs-api-service/app/shared
find ecs-api-service/app/shared -type d -exec touch {}/__init__.py \;

echo "  → Worker Service"
rm -rf ecs-worker-service/app/shared
cp -r shared-source ecs-worker-service/app/shared
find ecs-worker-service/app/shared -type d -exec touch {}/__init__.py \;

echo -e "${GREEN}✅ Shared code copied${NC}"

# Create simple test files to validate the shared code
echo -e "${YELLOW}📄 Creating test files...${NC}"

# API Service test
cat > ecs-api-service/app/test_shared.py << 'EOF'
#!/usr/bin/env python3
"""Test shared code imports"""

try:
    from shared.config.settings import settings
    from shared.models.client import Client, ClientInfo, CallOutcome
    from shared.models.call_session import CallSession, ConversationStage
    from shared.utils.database import DatabaseClient
    from shared.utils.redis_client import RedisClient
    
    print("✅ All shared imports successful in API service")
    print(f"   App name: {settings.app_name}")
    print(f"   Debug mode: {settings.debug}")
    print(f"   MongoDB URI: {settings.mongodb_uri}")
    
except Exception as e:
    print(f"❌ Import error in API service: {e}")
    exit(1)
EOF

# Worker Service test
cat > ecs-worker-service/app/test_shared.py << 'EOF'
#!/usr/bin/env python3
"""Test shared code imports"""

try:
    from shared.config.settings import settings
    from shared.models.client import Client, ClientInfo, CallOutcome, CRMTag
    from shared.models.call_session import CallSession, ConversationStage
    from shared.utils.database import DatabaseClient, init_database
    from shared.utils.redis_client import RedisClient, init_redis
    
    print("✅ All shared imports successful in Worker service")
    print(f"   App name: {settings.app_name}")
    print(f"   Business hours check: {settings.is_business_hours()}")
    print(f"   Max concurrent calls: {settings.max_concurrent_calls}")
    
except Exception as e:
    print(f"❌ Import error in Worker service: {e}")
    exit(1)
EOF

# Run the tests
echo -e "${YELLOW}🧪 Testing shared code imports...${NC}"

echo "Testing API Service imports:"
cd ecs-api-service/app
python test_shared.py
cd ../..

echo
echo "Testing Worker Service imports:"
cd ecs-worker-service/app  
python test_shared.py
cd ../..

echo
echo -e "${GREEN}✅ Shared code integration test passed!${NC}"

# Update requirements files with shared dependencies
echo -e "${YELLOW}📦 Updating requirements files...${NC}"

# API Service requirements
cat > ecs-api-service/requirements.txt << 'EOF'
# Core Framework
fastapi==0.104.1
uvicorn==0.24.0
pydantic==2.4.2
pydantic-settings==2.0.3

# Database & Cache
motor==3.3.2
pymongo==4.6.0
redis==5.0.1

# HTTP Client
httpx==0.25.2

# AWS
boto3==1.29.7

# Twilio
twilio==9.0.4

# Utilities
python-dotenv==1.0.0
python-multipart==0.0.6
aiofiles==23.2.0
orjson==3.9.10
pytz==2023.3

# WebSockets
websockets==12.0
EOF

# Worker Service requirements
cat > ecs-worker-service/requirements.txt << 'EOF'
# Core
pydantic==2.4.2
pydantic-settings==2.0.3
asyncio

# Database & Cache
motor==3.3.2
pymongo==4.6.0
redis==5.0.1

# HTTP Client
httpx==0.25.2

# AWS
boto3==1.29.7

# Twilio
twilio==9.0.4

# Utilities
python-dotenv==1.0.0
orjson==3.9.10
pytz==2023.3

# Email
email-validator==2.1.0
EOF

echo -e "${GREEN}✅ Requirements updated${NC}"

# Create updated main.py files that use shared code
echo -e "${YELLOW}📄 Creating updated main.py files...${NC}"

# API Service main.py with shared code
cat > ecs-api-service/app/main.py << 'EOF'
"""
Voice Agent API Service
Handles Twilio webhooks and real-time voice processing
"""

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
import logging
import asyncio
from contextlib import asynccontextmanager

# Import shared utilities
from shared.config.settings import settings
from shared.utils.database import init_database, close_database
from shared.utils.redis_client import init_redis, close_redis

# Configure logging
logging.basicConfig(
    level=logging.INFO if settings.debug else logging.WARNING,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

@asynccontextmanager
async def lifespan(app: FastAPI):
    """Application lifespan manager"""
    logger.info(f"🚀 Starting {settings.app_name} API Service")
    logger.info(f"🎯 Environment: {settings.environment}")
    logger.info(f"🔧 Debug mode: {settings.debug}")
    
    # Initialize database and cache
    try:
        await init_database()
        await init_redis()
        logger.info("✅ Database and cache initialized")
    except Exception as e:
        logger.error(f"❌ Initialization failed: {e}")
    
    # Validate API keys
    validation = settings.validate_required_settings()
    for key, result in validation.items():
        status = "✅" if result['valid'] else "⚠️"
        logger.info(f"{status} {key}: {result['message']}")
    
    logger.info("🌐 API Service ready for Twilio webhooks")
    
    yield
    
    logger.info("🛑 Shutting down API Service")
    await close_database()
    await close_redis()

app = FastAPI(
    title="Voice Agent API Service",
    description="Handles Twilio webhooks and real-time voice processing",
    version="1.0.0",
    lifespan=lifespan
)

# CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

@app.get("/")
async def root():
    """Root endpoint"""
    return {
        "service": "Voice Agent API Service",
        "version": "1.0.0",
        "status": "running",
        "environment": settings.environment,
        "features": [
            "Twilio webhook handling",
            "Real-time voice processing", 
            "Hybrid TTS (static + dynamic)",
            "Session management",
            "Performance monitoring"
        ]
    }

@app.get("/health")
async def health_check():
    """Health check endpoint"""
    # Import here to avoid circular imports
    from shared.utils.database import db_client
    from shared.utils.redis_client import redis_client
    
    return {
        "status": "healthy",
        "service": "api",
        "database_connected": db_client.is_connected(),
        "redis_connected": redis_client.is_connected(),
        "business_hours": settings.is_business_hours(),
        "max_concurrent_calls": settings.max_concurrent_calls
    }

@app.get("/config")
async def get_config():
    """Get service configuration"""
    return {
        "service": "api",
        "webhook_urls": {
            "voice": settings.get_webhook_url("voice"),
            "status": settings.get_webhook_url("status"),
            "media_stream": settings.get_webhook_url("media-stream")
        },
        "voice_settings": settings.elevenlabs_voice_settings,
        "business_hours": {
            "timezone": settings.business_timezone,
            "start": settings.business_start_hour,
            "end": settings.business_end_hour,
            "days": settings.business_days_list,
            "current_status": settings.is_business_hours()
        }
    }

# TODO: Add Twilio webhook routes
# @app.post("/twilio/voice")
# @app.post("/twilio/status") 
# @app.post("/twilio/media-stream")

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000, reload=settings.debug)
EOF

# Worker Service main.py with shared code
cat > ecs-worker-service/app/main.py << 'EOF'
"""
Voice Agent Worker Service
Processes campaign queue and handles outbound calls
"""

import asyncio
import logging
import signal
import sys
from datetime import datetime

# Import shared utilities
from shared.config.settings import settings
from shared.utils.database import init_database, close_database, get_client_by_phone
from shared.utils.redis_client import init_redis, close_redis
from shared.models.client import Client, CampaignStatus

# Configure logging
logging.basicConfig(
    level=logging.INFO if settings.debug else logging.WARNING,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

class WorkerService:
    """Main worker service class"""
    
    def __init__(self):
        self.running = False
        self.processed_count = 0
    
    async def start(self):
        """Start the worker service"""
        logger.info(f"🚀 Starting {settings.app_name} Worker Service")
        logger.info(f"🎯 Environment: {settings.environment}")
        
        # Initialize database and cache
        try:
            await init_database()
            await init_redis()
            logger.info("✅ Database and cache initialized")
        except Exception as e:
            logger.error(f"❌ Initialization failed: {e}")
            return
        
        # Validate business hours
        if settings.is_business_hours():
            logger.info("✅ Within business hours - worker active")
        else:
            logger.info("⏰ Outside business hours - worker will wait")
        
        self.running = True
        
        # Setup signal handlers
        signal.signal(signal.SIGINT, self._signal_handler)
        signal.signal(signal.SIGTERM, self._signal_handler)
        
        logger.info("🔄 Worker service started - monitoring for tasks")
        
        # Main worker loop
        await self._worker_loop()
    
    async def _worker_loop(self):
        """Main worker processing loop"""
        while self.running:
            try:
                # Check business hours
                if not settings.is_business_hours():
                    logger.info("⏰ Outside business hours - sleeping")
                    await asyncio.sleep(300)  # Sleep 5 minutes
                    continue
                
                # Process campaign tasks
                await self._process_campaign_tasks()
                
                # Sleep between iterations
                await asyncio.sleep(30)  # Check every 30 seconds
                
            except Exception as e:
                logger.error(f"❌ Worker loop error: {e}")
                await asyncio.sleep(60)  # Wait 1 minute on error
    
    async def _process_campaign_tasks(self):
        """Process campaign tasks"""
        # TODO: Implement actual campaign processing
        # This would:
        # 1. Get clients ready for calling from database
        # 2. Initiate Twilio calls
        # 3. Update client records
        # 4. Handle CRM integration
        
        logger.info(f"🔍 Checking for campaign tasks... (processed: {self.processed_count})")
        
        # For now, just increment counter to show it's working
        self.processed_count += 1
        
        # Example: Get a client by phone (testing database connection)
        try:
            test_client = await get_client_by_phone("+1234567890")
            if test_client:
                logger.info(f"📋 Found test client: {test_client.client.full_name}")
            else:
                logger.info("📋 No test client found (this is expected)")
        except Exception as e:
            logger.error(f"Database test error: {e}")
    
    def _signal_handler(self, signum, frame):
        """Handle shutdown signals"""
        logger.info(f"📡 Received signal {signum} - shutting down gracefully")
        self.running = False
    
    async def stop(self):
        """Stop the worker service"""
        logger.info("🛑 Stopping worker service")
        self.running = False
        
        await close_database()
        await close_redis()
        
        logger.info(f"✅ Worker service stopped (processed {self.processed_count} tasks)")

async def main():
    """Main entry point"""
    worker = WorkerService()
    
    try:
        await worker.start()
    except KeyboardInterrupt:
        logger.info("🛑 Keyboard interrupt received")
    except Exception as e:
        logger.error(f"❌ Worker service error: {e}")
    finally:
        await worker.stop()

if __name__ == "__main__":
    asyncio.run(main())
EOF

echo -e "${GREEN}✅ Updated main.py files created${NC}"

# Clean up test files
rm -f ecs-api-service/app/test_shared.py
rm -f ecs-worker-service/app/test_shared.py

echo
echo -e "${BLUE}🎉 Shared code sync and test completed!${NC}"
echo
echo -e "${YELLOW}📋 What's Ready:${NC}"
echo "✅ Shared configuration, models, and utilities"
echo "✅ Database and Redis connection managers"
echo "✅ Self-contained API and Worker services"
echo "✅ Updated requirements and main.py files"
echo
echo -e "${YELLOW}🚀 Next Steps:${NC}"
echo "1. ./scripts/build-services.sh    # Build Docker images"
echo "2. docker-compose up -d           # Start services"
echo "3. curl http://localhost:8000     # Test API service"
echo
echo -e "${GREEN}Ready to implement Twilio webhooks and campaign processing!${NC}"