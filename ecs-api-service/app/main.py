"""
Voice Agent API Service
Handles Twilio webhooks and real-time voice processing
"""

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
import logging
import asyncio
import os
from contextlib import asynccontextmanager

# Import shared utilities
from shared.config.settings import settings
from shared.utils.database import init_database, close_database
from shared.utils.redis_client import init_redis, close_redis

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
    
    # Create static directory for audio files
    os.makedirs("static/audio", exist_ok=True)
    
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
    
    # Log webhook URLs
    logger.info("🔗 Twilio Webhook URLs:")
    logger.info(f"   Voice: {settings.get_webhook_url('voice')}")
    logger.info(f"   Speech: {settings.get_webhook_url('speech')}")
    logger.info(f"   Status: {settings.get_webhook_url('status')}")
    
    logger.info("🌐 API Service ready for Twilio webhooks")
    
    yield
    
    logger.info("🛑 Shutting down API Service")
    await close_database()
    await close_redis()

app = FastAPI(
    title="Voice Agent API Service",
    description="Handles Twilio webhooks and real-time voice processing with hybrid TTS",
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

# Static files for audio serving
app.mount("/static", StaticFiles(directory="static"), name="static")

# Include routers
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
        "webhook_urls": {
            "voice": settings.get_webhook_url("voice"),
            "speech": settings.get_webhook_url("speech"),
            "status": settings.get_webhook_url("status"),
            "media_stream": f"{settings.base_url}/twilio/media-stream/{{session_id}}"
        }
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
        "max_concurrent_calls": settings.max_concurrent_calls,
        "voice_settings": settings.elevenlabs_voice_settings
    }

@app.get("/metrics")
async def get_performance_metrics():
    """Get performance metrics"""
    from routers.twilio import hybrid_tts, voice_processor
    
    return {
        "service": "api",
        "hybrid_tts_stats": hybrid_tts.get_performance_stats(),
        "voice_processor_stats": voice_processor.get_performance_stats(),
        "target_performance": {
            "static_response_time": "< 200ms",
            "dynamic_response_time": "< 2000ms",
            "total_turn_time": "< 2500ms"
        }
    }

@app.get("/config")
async def get_config():
    """Get service configuration"""
    return {
        "service": "api",
        "webhook_urls": {
            "voice": settings.get_webhook_url("voice"),
            "speech": settings.get_webhook_url("speech"),
            "status": settings.get_webhook_url("status"),
            "media_stream": f"{settings.base_url}/twilio/media-stream/{{session_id}}"
        },
        "voice_settings": {
            "voice_id": settings.default_voice_id,
            "stability": settings.voice_stability,
            "similarity_boost": settings.voice_similarity_boost,
            "style": settings.voice_style,
            "model": settings.tts_model
        },
        "business_hours": {
            "timezone": settings.business_timezone,
            "start": settings.business_start_hour,
            "end": settings.business_end_hour,
            "days": settings.business_days_list,
            "current_status": settings.is_business_hours()
        },
        "performance_targets": {
            "static_audio": "< 200ms",
            "dynamic_tts": "< 2000ms",
            "total_conversation_turn": "< 2500ms"
        }
    }

@app.post("/test-tts")
async def test_tts(text: str = "Hello, this is a test of the voice system."):
    """Test TTS functionality"""
    from routers.twilio import hybrid_tts
    
    try:
        result = await hybrid_tts.get_response_audio(
            text=text,
            response_type="test"
        )
        
        return {
            "success": result["success"],
            "audio_url": result.get("audio_url"),
            "type": result.get("type"),
            "generation_time_ms": result.get("generation_time_ms"),
            "text": text
        }
    except Exception as e:
        return {
            "success": False,
            "error": str(e),
            "text": text
        }

@app.get("/static-audio-manifest")
async def get_static_audio_manifest():
    """Get list of available static audio files"""
    static_audio_dir = "audio-generation/generated_audio"
    
    if os.path.exists(static_audio_dir):
        audio_files = [f for f in os.listdir(static_audio_dir) if f.endswith('.mp3')]
        return {
            "static_audio_available": True,
            "files": audio_files,
            "base_url": f"{settings.base_url}/static/audio/"
        }
    else:
        return {
            "static_audio_available": False,
            "message": "Run 'python audio-generation/scripts/generate_static_audio.py' to create static audio files"
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