"""
Voice Agent API Service - Complete Implementation
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

# Import routers with fallback
try:
    from routers.twilio import router as twilio_router
    from routers.dashboard import router as dashboard_router
    logger.info("✅ Routers imported successfully")
except ImportError as e:
    logger.warning(f"⚠️ Router import failed: {e}")
    # Create fallback routers
    from fastapi import APIRouter
    twilio_router = APIRouter(prefix="/twilio", tags=["Twilio"])
    dashboard_router = APIRouter(prefix="/api/dashboard", tags=["Dashboard"])
    
    @dashboard_router.get("/test-clients")
    async def get_test_clients():
        return {"clients": [], "note": "Router needs to be properly configured"}
    
    @dashboard_router.get("/test-agents") 
    async def get_test_agents():
        return {"agents": [], "note": "Router needs to be properly configured"}
    
    @twilio_router.post("/voice")
    async def voice_webhook():
        return Response(
            content='<?xml version="1.0" encoding="UTF-8"?><Response><Say>Hello, thank you for calling.</Say></Response>',
            media_type="application/xml"
        )

# Try to import shared utilities (fall back if not available)
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
    
    # Log available routes
    logger.info("🔗 Available endpoints:")
    logger.info("   GET  /                    - API information")
    logger.info("   GET  /health              - Health check")
    logger.info("   GET  /config              - System configuration")
    logger.info("   POST /twilio/voice        - Twilio voice webhook")
    logger.info("   POST /twilio/status       - Twilio status webhook")
    logger.info("   GET  /api/dashboard/stats - Production stats")
    logger.info("   GET  /api/dashboard/test-clients - Test clients")
    logger.info("   POST /api/dashboard/test-call - Initiate test call")
    
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

# Performance monitoring middleware
@app.middleware("http")
async def performance_monitor(request: Request, call_next):
    """Monitor request performance"""
    start_time = time.time()
    
    try:
        response = await call_next(request)
        process_time = (time.time() - start_time) * 1000  # Convert to ms
        response.headers["X-Process-Time"] = f"{process_time:.2f}ms"
        
        # Log slow requests
        if process_time > 1000:  # 1 second threshold
            logger.warning(f"⚠️ Slow request: {request.url.path} took {process_time:.2f}ms")
        
        return response
    except Exception as e:
        process_time = (time.time() - start_time) * 1000
        logger.error(f"❌ Request error on {request.url.path} after {process_time:.2f}ms: {e}")
        raise

# Error handling middleware
@app.middleware("http")
async def error_handler(request: Request, call_next):
    """Global error handling"""
    try:
        return await call_next(request)
    except Exception as e:
        logger.error(f"❌ Unhandled error on {request.url.path}: {e}")
        return Response(
            content=f'{{"error": "Internal server error", "detail": "{str(e)}", "path": "{request.url.path}"}}',
            status_code=500,
            media_type="application/json"
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

# Include routers
app.include_router(twilio_router)
app.include_router(dashboard_router)

logger.info("📍 Routers included successfully")

@app.get("/")
async def root():
    """Root endpoint with system information"""
    return {
        "service": "Voice Agent Production System",
        "version": "1.0.0", 
        "status": "running",
        "environment": getattr(settings, 'environment', 'development'),
        "features": [
            "Twilio voice webhook handling",
            "Dashboard API endpoints",
            "Real-time call processing",
            "Production statistics",
            "Testing capabilities",
            "Performance monitoring"
        ],
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
            "routers": ["twilio", "dashboard"]
        }
        
        # Overall health
        health_status = "healthy"
        if not any(external_apis.values()):
            health_status = "degraded"
        
        return {
            "status": health_status,
            "timestamp": datetime.utcnow().isoformat(),
            "version": "1.0.0",
            "components": components,
            "uptime": time.time(),
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

@app.get("/config")
async def get_config():
    """Get system configuration (non-sensitive)"""
    try:
        config = {
            "version": "1.0.0",
            "environment": getattr(settings, 'environment', 'development'),
            "max_concurrent_calls": getattr(settings, 'max_concurrent_calls', 30),
            "base_url": os.getenv("BASE_URL", "http://localhost:8000"),
            "features": {
                "voice_processing": True,
                "dashboard": True,
                "testing": True,
                "production_stats": True
            },
            "api_endpoints": {
                "voice_webhook": "/twilio/voice",
                "status_webhook": "/twilio/status",
                "dashboard_api": "/api/dashboard/",
                "health_check": "/health"
            }
        }
        
        # Add webhook URLs if available
        if hasattr(settings, 'get_webhook_url'):
            config["webhook_urls"] = {
                "voice": settings.get_webhook_url("voice"),
                "status": settings.get_webhook_url("status")
            }
        else:
            config["webhook_urls"] = {
                "voice": f"{os.getenv('BASE_URL', 'http://localhost:8000')}/twilio/voice",
                "status": f"{os.getenv('BASE_URL', 'http://localhost:8000')}/twilio/status"
            }
        
        return config
        
    except Exception as e:
        logger.error(f"Config endpoint error: {e}")
        return {"error": str(e)}

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000, reload=True)