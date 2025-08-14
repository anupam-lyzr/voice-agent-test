"""
Voice Agent API Service - Fixed Import Paths
Handles Twilio webhooks, dashboard APIs, and real-time voice processing
"""

from fastapi import FastAPI, Request, Response, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from contextlib import asynccontextmanager
import logging
import asyncio
import os
import time
from datetime import datetime
from typing import Dict, Any

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# Import routers with better error handling
twilio_router = None
dashboard_router = None

# Try multiple import strategies
import sys
import os

# Add current directory to Python path for imports
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

try:
    from routers.twilio import router as twilio_router
    from routers.dashboard import router as dashboard_router
    from routers.slot_selection import router as slot_selection_router
    logger.info("✅ Routers imported successfully")
except ImportError as import_error:
    logger.error(f"❌ Router import failed: {import_error}")
    
    # Create minimal emergency routers
    from fastapi import APIRouter, Form
    from fastapi.responses import Response
    
    twilio_router = APIRouter(prefix="/twilio", tags=["Twilio"])
    dashboard_router = APIRouter(prefix="/api/dashboard", tags=["Dashboard"])
    slot_selection_router = APIRouter(prefix="/api", tags=["Slot Selection"])
    
    @twilio_router.post("/voice")
    async def emergency_voice_webhook(CallSid: str = Form(...)):
        return Response(
            content='''<?xml version="1.0" encoding="UTF-8"?>
<Response>
    <Say voice="Polly.Joanna">Hello, thank you for calling. We are experiencing technical difficulties. Please call back later.</Say>
    <Hangup/>
</Response>''',
            media_type="application/xml"
        )
    
    @twilio_router.post("/status")  
    async def emergency_status_webhook():
        return {"status": "ok"}
    
    @dashboard_router.get("/stats")
    async def emergency_stats():
        return {"error": "System initializing", "total_clients": 0}
        
    # Add basic endpoints to fallback routers
    @twilio_router.post("/voice")
    async def voice_webhook():
        return Response(
            content='<?xml version="1.0" encoding="UTF-8"?><Response><Say>Hello, thank you for calling.</Say></Response>',
            media_type="application/xml"
        )
    
    @twilio_router.post("/status")
    async def status_webhook():
        return {"status": "ok"}
        
    @twilio_router.get("/test-connection")
    async def test_connection():
        return {"status": "ok", "message": "Fallback router active"}
    
    @dashboard_router.get("/stats")
    async def get_stats():
        return {"message": "Router fallback - needs proper configuration"}
    
    @dashboard_router.get("/test-clients")
    async def get_test_clients():
        return {"clients": [], "note": "Router needs to be properly configured"}
    
    @dashboard_router.get("/test-agents") 
    async def get_test_agents():
        return {"agents": [], "note": "Router needs to be properly configured"}
    
    @slot_selection_router.get("/slot-selection")
    async def emergency_slot_selection():
        return {"error": "Slot selection service not available"}

# Try to import shared utilities with fallback
try:
    from shared.config.settings import settings
    from shared.utils.database import init_database, close_database, db_client
    from shared.utils.redis_client import init_redis, close_redis, redis_client
    logger.info("✅ Shared utilities imported successfully")
except ImportError as e:
    logger.warning(f"⚠️ Shared utilities not available: {e}")
    # Create minimal settings fallback
    class MinimalSettings:
        app_name = "Voice Agent API"
        environment = "development"
        debug = True
        max_concurrent_calls = 30
        
        def validate_required_settings(self):
            return {"api_keys": {"valid": False, "message": "Not configured"}}
        
        def get_webhook_url(self, endpoint):
            return f"http://localhost:8000/twilio/{endpoint}"
    
    settings = MinimalSettings()
    db_client = None
    redis_client = None

@asynccontextmanager
async def lifespan(app: FastAPI):
    """Application lifespan manager"""
    logger.info(f"🚀 Starting {getattr(settings, 'app_name', 'Voice Agent API')}")
    logger.info(f"🎯 Environment: {getattr(settings, 'environment', 'development')}")
    logger.info(f"🔧 Debug mode: {getattr(settings, 'debug', True)}")
    
    # Initialize database and cache if available
    if hasattr(settings, 'validate_required_settings'):
        try:
            if 'init_database' in globals():
                await init_database()
                logger.info("✅ Database initialized")
        except Exception as e:
            logger.warning(f"⚠️ Database initialization failed: {e}")
        
        try:
            if 'init_redis' in globals():
                await init_redis()
                logger.info("✅ Redis initialized")
        except Exception as e:
            logger.warning(f"⚠️ Redis initialization failed: {e}")
        
        # Validate API keys
        try:
            validation = settings.validate_required_settings()
            for key, result in validation.items():
                status = "✅" if result['valid'] else "⚠️"
                logger.info(f"{status} {key}: {result['message']}")
        except Exception as e:
            logger.warning(f"⚠️ Settings validation failed: {e}")
    
    # Log all available routes after app creation
    yield
    
    logger.info("🛑 Shutting down Voice Agent System...")
    try:
        if 'close_database' in globals():
            await close_database()
        if 'close_redis' in globals():
            await close_redis()
    except Exception as e:
        logger.warning(f"⚠️ Cleanup warning: {e}")

app = FastAPI(
    title="Voice Agent Production System",
    description="Production-ready voice agent with dashboard and testing capabilities",
    version="1.0.0",
    lifespan=lifespan
)

# CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # Configure for your domain in production
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Serve static files (for audio files)
static_dir = os.path.join(os.getcwd(), "static")
os.makedirs(static_dir, exist_ok=True)
app.mount("/static", StaticFiles(directory=static_dir), name="static")

# Include routers - CRITICAL: This must happen AFTER app creation
app.include_router(twilio_router)
app.include_router(dashboard_router)
app.include_router(slot_selection_router)

logger.info("📍 Routers included successfully")

# Log all routes after including routers
@app.on_event("startup")
async def log_routes():
    """Log all available routes for debugging"""
    logger.info("🔗 All registered routes:")
    for route in app.routes:
        if hasattr(route, 'methods') and hasattr(route, 'path'):
            methods = list(route.methods)
            logger.info(f"   {methods} {route.path}")

@app.get("/")
async def root():
    """Root endpoint with system information"""
    # Get all registered routes for the response
    routes = []
    for route in app.routes:
        if hasattr(route, 'methods') and hasattr(route, 'path'):
            routes.append({
                "path": route.path,
                "methods": list(route.methods)
            })
    
    return {
        "service": "Voice Agent Production System",
        "version": "1.0.0", 
        "status": "running",
        "environment": getattr(settings, 'environment', 'development'),
        "total_routes": len(routes),
        "routes": routes,
        "endpoints": {
            "health": "/health",
            "config": "/config",
            "docs": "/docs",
            "twilio_voice": "/twilio/voice",
            "twilio_status": "/twilio/status",
            "twilio_test": "/twilio/test-connection",
            "dashboard_stats": "/api/dashboard/stats",
            "dashboard_clients": "/api/dashboard/test-clients",
            "dashboard_agents": "/api/dashboard/test-agents",
            "dashboard_call_logs": "/api/dashboard/call-logs",
            "dashboard_test_call": "/api/dashboard/test-call"
        },
        "timestamp": datetime.utcnow().isoformat()
    }

@app.get("/health")
async def health_check():
    """Health check endpoint with component status"""
    try:
        # Count registered routes
        route_count = len([r for r in app.routes if hasattr(r, 'methods')])
        
        # Check database connection if available
        db_connected = False
        if db_client:
            try:
                if hasattr(db_client, 'admin'):
                    await db_client.admin.command('ping')
                    db_connected = True
                elif hasattr(db_client, 'is_connected'):
                    db_connected = db_client.is_connected()
            except Exception:
                pass
        
        # Check Redis connection if available
        redis_connected = False
        if redis_client:
            try:
                if hasattr(redis_client, 'ping'):
                    await redis_client.ping()
                    redis_connected = True
                elif hasattr(redis_client, 'is_connected'):
                    redis_connected = redis_client.is_connected()
            except Exception:
                pass
        
        # Check external API configurations
        external_apis = {
            "twilio": bool(os.getenv("TWILIO_ACCOUNT_SID") and os.getenv("TWILIO_AUTH_TOKEN")),
            "lyzr": bool(os.getenv("LYZR_USER_API_KEY")),
            "deepgram": bool(os.getenv("DEEPGRAM_API_KEY")),
            "elevenlabs": bool(os.getenv("ELEVENLABS_API_KEY"))
        }
        
        # Component status
        components = {
            "database": "connected" if db_connected else "not_configured",
            "redis": "connected" if redis_connected else "not_configured",
            "external_apis": external_apis,
            "environment": getattr(settings, 'environment', 'development'),
            "registered_routes": route_count,
            "routers": ["twilio", "dashboard"]
        }
        
        # Overall health
        health_status = "healthy"
        if route_count < 5:  # Should have at least 5 routes
            health_status = "degraded"
        
        return {
            "status": health_status,
            "timestamp": datetime.utcnow().isoformat(),
            "version": "1.0.0",
            "components": components,
            "message": "Voice Agent API is running"
        }
        
    except Exception as e:
        logger.error(f"Health check error: {e}")
        return {
            "status": "error",
            "timestamp": datetime.utcnow().isoformat(),
            "error": str(e),
            "message": "Health check failed"
        }

@app.get("/debug/routes")
async def debug_routes():
    """Debug endpoint to see all registered routes"""
    routes = []
    for route in app.routes:
        route_info = {"path": str(route.path)}
        if hasattr(route, 'methods'):
            route_info["methods"] = list(route.methods)
        if hasattr(route, 'name'):
            route_info["name"] = route.name
        routes.append(route_info)
    
    return {
        "total_routes": len(routes),
        "routes": routes,
        "timestamp": datetime.utcnow().isoformat()
    }

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000, reload=True)