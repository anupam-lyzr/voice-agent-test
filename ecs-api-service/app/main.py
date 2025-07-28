"""
Voice Agent API Service - Complete Implementation
Handles Twilio webhooks and real-time voice processing
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

# Import shared utilities
from shared.config.settings import settings
from shared.utils.database import init_database, close_database, db_client
from shared.utils.redis_client import init_redis, close_redis, redis_client

# Import routers
from routers.twilio import router as twilio_router

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
        # Continue startup even if connections fail for development
    
    # Validate API keys
    validation = settings.validate_required_settings()
    for key, result in validation.items():
        status = "✅" if result['valid'] else "⚠️"
        logger.info(f"{status} {key}: {result['message']}")
    
    # Log webhook URLs
    logger.info("🔗 Webhook URLs:")
    logger.info(f"   Voice: {settings.get_webhook_url('voice')}")
    logger.info(f"   Status: {settings.get_webhook_url('status')}")
    logger.info(f"   Media Stream: {settings.get_webhook_url('media-stream')}")
    
    logger.info("🌐 API Service ready for Twilio webhooks")
    
    yield
    
    logger.info("🛑 Shutting down API Service")
    try:
        await close_database()
        await close_redis()
    except Exception as e:
        logger.error(f"❌ Shutdown error: {e}")

app = FastAPI(
    title="Voice Agent API Service",
    description="Handles Twilio webhooks and real-time voice processing",
    version="1.0.0",
    lifespan=lifespan
)

# CORS middleware - FIXED FOR FRONTEND
app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "http://localhost:3000",  # React development server
        "http://localhost:5173",  # Vite development server  
        "http://localhost:8080",  # Alternative dev server
        "https://*.vercel.app",   # Vercel deployments
        "https://*.netlify.app",  # Netlify deployments
        "*"  # Allow all origins for development (remove in production)
    ],
    allow_credentials=True,
    allow_methods=["GET", "POST", "PUT", "DELETE", "OPTIONS"],
    allow_headers=["*"],
    expose_headers=["X-Process-Time"]
)

# Performance monitoring middleware
@app.middleware("http")
async def performance_monitor(request: Request, call_next):
    """Monitor request performance"""
    start_time = time.time()
    
    response = await call_next(request)
    
    process_time = (time.time() - start_time) * 1000  # Convert to ms
    response.headers["X-Process-Time"] = f"{process_time:.2f}ms"
    
    # Log slow requests
    if process_time > 2000:  # Log requests slower than 2 seconds
        logger.warning(f"⚠️ Slow request: {request.url.path} took {process_time:.2f}ms")
    
    return response

# Error handling middleware
@app.middleware("http")
async def error_handler(request: Request, call_next):
    """Global error handling"""
    try:
        return await call_next(request)
    except Exception as e:
        logger.error(f"❌ Request error on {request.url.path}: {e}")
        return Response(
            content=f'{{"error": "Internal server error", "detail": "{str(e)}"}}',
            status_code=500,
            media_type="application/json"
        )

# Static files for audio
static_dir = os.path.join(os.getcwd(), "static", "audio")
os.makedirs(static_dir, exist_ok=True)
app.mount("/static", StaticFiles(directory=os.path.dirname(static_dir)), name="static")

# Include routers - THIS WAS MISSING
app.include_router(twilio_router)

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
        ],
        "endpoints": {
            "twilio_voice": "/twilio/voice",
            "twilio_status": "/twilio/status",
            "twilio_media_stream": "/twilio/media-stream",
            "health": "/health",
            "config": "/config"
        }
    }

@app.get("/health")
async def health_check():
    """Health check endpoint with component status"""
    try:
        # Check database connection
        db_connected = False
        try:
            if db_client:
                db_connected = db_client.is_connected()
        except Exception:
            pass
        
        # Check Redis connection  
        redis_connected = False
        try:
            if redis_client:
                redis_connected = redis_client.is_connected()
        except Exception:
            pass
        
        # Check external API configurations
        components = {
            "database": "connected" if db_connected else "disconnected",
            "redis": "connected" if redis_connected else "disconnected",
            "twilio": "configured" if settings.twilio_account_sid and settings.twilio_auth_token else "not_configured",
            "deepgram": "configured" if settings.deepgram_api_key else "not_configured",
            "elevenlabs": "configured" if settings.elevenlabs_api_key else "not_configured",
            "lyzr": "configured" if settings.lyzr_api_key else "not_configured"
        }
        
        return {
            "status": "healthy",
            "service": "api",
            "timestamp": datetime.utcnow().isoformat(),
            "business_hours": settings.is_business_hours(),
            "max_concurrent_calls": settings.max_concurrent_calls,
            "components": components
        }
        
    except Exception as e:
        logger.error(f"Health check error: {e}")
        return {
            "status": "unhealthy", 
            "service": "api",
            "error": str(e),
            "timestamp": datetime.utcnow().isoformat()
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
        },
        "performance": {
            "target_latency_ms": 2000,
            "static_audio_latency_ms": 200,
            "dynamic_tts_latency_ms": 1500
        }
    }

# Additional endpoints for testing
@app.get("/test-cors")
async def test_cors():
    """Test CORS configuration"""
    return {
        "message": "CORS is working!",
        "timestamp": datetime.utcnow().isoformat(),
        "headers_received": "Check browser network tab"
    }

@app.post("/test-webhook")
async def test_webhook(request: Request):
    """Test webhook endpoint for debugging"""
    try:
        body = await request.body()
        form_data = await request.form()
        
        return {
            "success": True,
            "message": "Webhook test successful",
            "method": request.method,
            "headers": dict(request.headers),
            "form_data": dict(form_data),
            "body_length": len(body)
        }
    except Exception as e:
        return {
            "success": False,
            "error": str(e)
        }

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(
        app, 
        host="0.0.0.0", 
        port=8000, 
        reload=settings.debug,
        log_level="info" if settings.debug else "warning"
    )