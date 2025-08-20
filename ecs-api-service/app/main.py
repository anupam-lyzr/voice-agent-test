"""
Enhanced Voice Agent API Service - Production Ready
Handles Twilio webhooks, dashboard APIs, and real-time voice processing with client type detection
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
from pathlib import Path

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# Enhanced router imports with fallbacks
twilio_router = None
dashboard_router = None
slot_selection_router = None

# Add current directory to Python path for imports
import sys
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

try:
    # Import the enhanced routers
    from routers.twilio import router as twilio_router
    from routers.dashboard import router as dashboard_router
    
    # Try to import slot selection router if it exists
    try:
        from routers.slot_selection import router as slot_selection_router
    except ImportError:
        # Create minimal slot selection router if missing
        from fastapi import APIRouter
        slot_selection_router = APIRouter(prefix="/api/slots", tags=["Slot Selection"])
        
        @slot_selection_router.get("/available")
        async def get_available_slots():
            return {"message": "Slot selection service not implemented yet"}
    
    # Try to import audio management router if it exists
    try:
        from routers.audio_management import router as audio_management_router
    except ImportError:
        # Create minimal audio management router if missing
        from fastapi import APIRouter
        audio_management_router = APIRouter(prefix="/audio", tags=["Audio Management"])
        
        @audio_management_router.get("/status")
        async def get_audio_status():
            return {"message": "Audio management service not implemented yet"}
    
    logger.info("✅ Enhanced routers imported successfully")
    
except ImportError as import_error:
    logger.error(f"❌ Router import failed: {import_error}")
    
    # Create emergency fallback routers
    from fastapi import APIRouter, Form
    from fastapi.responses import Response
    
    twilio_router = APIRouter(prefix="/twilio", tags=["Twilio"])
    dashboard_router = APIRouter(prefix="/api/dashboard", tags=["Dashboard"])
    slot_selection_router = APIRouter(prefix="/api/slots", tags=["Slot Selection"])
    
    # Emergency Twilio endpoints
    @twilio_router.post("/voice")
    async def emergency_voice_webhook(CallSid: str = Form(...)):
        return Response(
            content='''<?xml version="1.0" encoding="UTF-8"?>
<Response>
    <Say voice="Polly.Matthew">Hello, thank you for calling. We are experiencing technical difficulties. Please call back at 8-3-3, 2-2-7, 8-5-0-0. Goodbye.</Say>
    <Hangup/>
</Response>''',
            media_type="application/xml"
        )
    
    @twilio_router.post("/status")  
    async def emergency_status_webhook():
        return {"status": "ok"}
    
    @twilio_router.get("/test-connection")
    async def emergency_test_connection():
        return {"status": "emergency_mode", "message": "Emergency router active"}
    
    # Emergency Dashboard endpoints
    @dashboard_router.get("/stats")
    async def emergency_stats():
        return {
            "error": "System initializing", 
            "total_clients": 0,
            "status": "emergency_mode"
        }
    
    @dashboard_router.get("/health")
    async def emergency_health():
        return {
            "status": "emergency_mode",
            "message": "Dashboard in emergency mode"
        }
    
    @dashboard_router.get("/test-clients")
    async def emergency_test_clients():
        return {
            "clients": [], 
            "note": "System in emergency mode"
        }
    
    # Emergency Slot Selection
    @slot_selection_router.get("/available")
    async def emergency_slots():
        return {"error": "Slot selection service not available"}
    
    logger.warning("⚠️ Using emergency fallback routers")

# Try to import shared utilities with enhanced error handling
db_client = None
redis_client = None
settings = None

try:
    from shared.config.settings import settings
    logger.info("✅ Settings imported successfully")
except ImportError as e:
    logger.warning(f"⚠️ Settings not available: {e}")
    # Create minimal settings fallback
    class MinimalSettings:
        app_name = "Voice Agent API"
        environment = "development"
        debug = True
        max_concurrent_calls = 30
        base_url = "http://localhost:8000"
        
        def validate_required_settings(self):
            return {"api_keys": {"valid": False, "message": "Not configured"}}
        
        def get_webhook_url(self, endpoint):
            return f"{self.base_url}/twilio/{endpoint}"
    
    settings = MinimalSettings()

try:
    from shared.utils.database import init_database, close_database, db_client
    logger.info("✅ Database utilities imported")
except ImportError as e:
    logger.warning(f"⚠️ Database utilities not available: {e}")
    
    async def init_database():
        logger.warning("Database initialization skipped - not available")
        
    async def close_database():
        logger.warning("Database close skipped - not available")

try:
    from shared.utils.redis_client import init_redis, close_redis, redis_client
    logger.info("✅ Redis utilities imported")
except ImportError as e:
    logger.warning(f"⚠️ Redis utilities not available: {e}")
    
    async def init_redis():
        logger.warning("Redis initialization skipped - not available")
        
    async def close_redis():
        logger.warning("Redis close skipped - not available")

# Enhanced application lifespan manager
@asynccontextmanager
async def lifespan(app: FastAPI):
    """Enhanced application lifespan manager with better error handling"""
    
    logger.info(f"🚀 Starting {getattr(settings, 'app_name', 'Voice Agent API')}")
    logger.info(f"🎯 Environment: {getattr(settings, 'environment', 'development')}")
    logger.info(f"🔧 Debug mode: {getattr(settings, 'debug', True)}")
    
    # Initialize services with error handling
    initialization_results = {}
    
    # Database initialization
    try:
        await init_database()
        initialization_results["database"] = "✅ Initialized"
        logger.info("✅ Database initialized")
    except Exception as e:
        initialization_results["database"] = f"⚠️ Failed: {e}"
        logger.warning(f"⚠️ Database initialization failed: {e}")
    
    # Redis initialization  
    try:
        await init_redis()
        initialization_results["redis"] = "✅ Initialized"
        logger.info("✅ Redis initialized")
    except Exception as e:
        initialization_results["redis"] = f"⚠️ Failed: {e}"
        logger.warning(f"⚠️ Redis initialization failed: {e}")
    
    # Validate API keys and settings
    try:
        if hasattr(settings, 'validate_required_settings'):
            validation = settings.validate_required_settings()
            for key, result in validation.items():
                status = "✅" if result.get('valid', False) else "⚠️"
                logger.info(f"{status} {key}: {result.get('message', 'Unknown')}")
                initialization_results[key] = f"{status} {result.get('message', 'Unknown')}"
    except Exception as e:
        logger.warning(f"⚠️ Settings validation failed: {e}")
        initialization_results["settings"] = f"⚠️ Failed: {e}"
    
    # Create necessary directories
    try:
        directories_to_create = [
            "static/audio/temp",
            "audio-generation/segments", 
            "audio-generation/names/clients",
            "audio-generation/names/agents",
            "audio-generation/concatenated_cache"
        ]
        
        for directory in directories_to_create:
            Path(directory).mkdir(parents=True, exist_ok=True)
            
        initialization_results["directories"] = "✅ Created"
        logger.info("✅ Directory structure created")
        
    except Exception as e:
        initialization_results["directories"] = f"⚠️ Failed: {e}"
        logger.warning(f"⚠️ Directory creation failed: {e}")
    
    # Test external service configurations
    try:
        service_status = {}
        
        # Test ElevenLabs
        try:
            from services.elevenlabs_client import elevenlabs_client
            if elevenlabs_client.is_configured():
                service_status["elevenlabs"] = "✅ Configured"
            else:
                service_status["elevenlabs"] = "⚠️ Not configured"
        except Exception:
            service_status["elevenlabs"] = "❌ Import failed"
        
        # Test Deepgram
        try:
            from services.deepgram_client import deepgram_client
            if deepgram_client.is_configured():
                service_status["deepgram"] = "✅ Configured"
            else:
                service_status["deepgram"] = "⚠️ Not configured"
        except Exception:
            service_status["deepgram"] = "❌ Import failed"
        
        # Test LYZR
        try:
            from services.lyzr_client import lyzr_client
            if lyzr_client.is_configured():
                service_status["lyzr"] = "✅ Configured"
            else:
                service_status["lyzr"] = "⚠️ Not configured"
        except Exception:
            service_status["lyzr"] = "❌ Import failed"
        
        for service, status in service_status.items():
            logger.info(f"{status.split()[0]} {service}: {status.split(' ', 1)[1] if ' ' in status else status}")
            initialization_results[f"service_{service}"] = status
            
    except Exception as e:
        logger.warning(f"⚠️ Service status check failed: {e}")
        initialization_results["services"] = f"⚠️ Failed: {e}"
    
    # Log final initialization summary
    logger.info("🎯 Initialization Summary:")
    for component, status in initialization_results.items():
        logger.info(f"   {component}: {status}")
    
    # Application is ready
    logger.info("🎉 Voice Agent API is ready!")
    
    yield
    
    # Shutdown procedures
    logger.info("🛑 Shutting down Voice Agent API...")
    
    try:
        await close_database()
        logger.info("✅ Database connection closed")
    except Exception as e:
        logger.warning(f"⚠️ Database cleanup warning: {e}")
    
    try:
        await close_redis()
        logger.info("✅ Redis connection closed")
    except Exception as e:
        logger.warning(f"⚠️ Redis cleanup warning: {e}")
    
    logger.info("👋 Voice Agent API shutdown complete")

# Create FastAPI application
app = FastAPI(
    title="Enhanced Voice Agent Production System",
    description="Production-ready voice agent with client type detection, dashboard, and comprehensive testing capabilities",
    version="2.0.0",
    lifespan=lifespan
)

# Enhanced CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # Configure for your domain in production
    allow_credentials=True,
    allow_methods=["GET", "POST", "PUT", "DELETE", "OPTIONS"],
    allow_headers=["*"],
)

# Serve static files (for audio files and temp files)
static_dirs = [
    ("static", "static"),
    ("audio-generation", "audio-generation")
]

for mount_path, directory in static_dirs:
    if not os.path.exists(directory):
        os.makedirs(directory, exist_ok=True)
    
    try:
        app.mount(f"/{mount_path}", StaticFiles(directory=directory), name=mount_path)
        logger.info(f"📁 Mounted static directory: /{mount_path} -> {directory}")
    except Exception as e:
        logger.warning(f"⚠️ Failed to mount {directory}: {e}")

# Include routers with error handling
try:
    app.include_router(twilio_router)
    app.include_router(dashboard_router) 
    app.include_router(slot_selection_router)
    app.include_router(audio_management_router)
    logger.info("🔗 Enhanced routers included successfully")
except Exception as e:
    logger.error(f"❌ Router inclusion failed: {e}")

# Startup event to log all routes
@app.on_event("startup")
async def log_routes():
    """Log all available routes for debugging"""
    logger.info("🔗 All registered routes:")
    for route in app.routes:
        if hasattr(route, 'methods') and hasattr(route, 'path'):
            methods = list(route.methods)
            logger.info(f"   {methods} {route.path}")

# Enhanced root endpoint
@app.get("/")
async def root():
    """Enhanced root endpoint with comprehensive system information"""
    
    # Get all registered routes for the response
    routes = []
    for route in app.routes:
        if hasattr(route, 'methods') and hasattr(route, 'path'):
            routes.append({
                "path": route.path,
                "methods": list(route.methods)
            })
    
    # System status
    system_status = {
        "database": "unknown",
        "redis": "unknown", 
        "static_files": "mounted"
    }
    
    try:
        if db_client is not None:
            system_status["database"] = "connected"
    except:
        pass
    
    try:
        if redis_client is not None:
            system_status["redis"] = "connected"
    except:
        pass
    
    return {
        "service": "Enhanced Voice Agent Production System",
        "version": "2.0.0",
        "status": "running",
        "environment": getattr(settings, 'environment', 'development'),
        "debug": getattr(settings, 'debug', True),
        "features": {
            "client_type_detection": True,
            "medicare_non_medicare_support": True,
            "enhanced_voice_processing": True,
            "hybrid_tts": True,
            "segmented_audio": True,
            "voicemail_detection": True,
            "interruption_handling": True,
            "no_speech_fallbacks": True,
            "comprehensive_dashboard": True
        },
        "system_status": system_status,
        "timestamp": datetime.utcnow().isoformat(),
        "total_routes": len(routes),
        "key_endpoints": {
            "twilio_voice": "/twilio/voice",
            "twilio_status": "/twilio/status", 
            "dashboard_stats": "/api/dashboard/stats",
            "dashboard_health": "/api/dashboard/health",
            "test_clients": "/api/dashboard/test-clients",
            "active_calls": "/api/dashboard/active-calls"
        }
    }

# Enhanced health check endpoint
@app.get("/health")
async def health_check():
    """Enhanced health check with service status"""
    
    health_status = {
        "status": "healthy",
        "timestamp": datetime.utcnow().isoformat(),
        "version": "2.0.0",
        "services": {}
    }
    
    # Check database (non-blocking)
    try:
        if db_client is not None:
            # Use the is_connected method instead of boolean evaluation
            if db_client.is_connected():
                admin_db = db_client.client.admin
                await asyncio.wait_for(admin_db.command('ping'), timeout=5.0)
                health_status["services"]["database"] = "healthy"
            else:
                health_status["services"]["database"] = "error"
        else:
            health_status["services"]["database"] = "not_configured"
    except Exception as e:
        health_status["services"]["database"] = "error"
        # Don't mark as degraded for database issues during startup
        logger.warning(f"Database health check failed: {e}")
    
    # Check Redis (non-blocking)
    try:
        if redis_client is not None:
            await asyncio.wait_for(redis_client.ping(), timeout=5.0)
            health_status["services"]["redis"] = "healthy"
        else:
            health_status["services"]["redis"] = "not_configured"
    except Exception as e:
        health_status["services"]["redis"] = "error"
        # Don't mark as degraded for Redis issues during startup
        logger.warning(f"Redis health check failed: {e}")
    
    # Only mark as degraded if core services are failing
    if health_status["status"] == "healthy":
        logger.info("✅ Health check passed - API service is healthy")
    
    return health_status

# Enhanced debug endpoint
@app.get("/debug")
async def debug_info():
    """Debug endpoint with comprehensive system information"""
    
    try:
        debug_data = {
            "timestamp": datetime.utcnow().isoformat(),
            "python_path": sys.path[:3],  # First 3 entries
            "working_directory": os.getcwd(),
            "environment_variables": {
                "PYTHONPATH": os.environ.get("PYTHONPATH", "not_set"),
                "ENVIRONMENT": os.environ.get("ENVIRONMENT", "not_set")
            },
            "imported_modules": {
                "twilio_router": twilio_router is not None,
                "dashboard_router": dashboard_router is not None,
                "slot_selection_router": slot_selection_router is not None,
                "settings": settings is not None,
                "db_client": db_client is not None,
                "redis_client": redis_client is not None
            },
            "static_mounts": [
                {"path": "/static", "exists": os.path.exists("static")},
                {"path": "/audio-generation", "exists": os.path.exists("audio-generation")}
            ],
            "directory_structure": {
                "services": os.path.exists("services"),
                "routers": os.path.exists("routers"), 
                "shared": os.path.exists("shared"),
                "audio-generation": os.path.exists("audio-generation")
            }
        }
        
        return debug_data
        
    except Exception as e:
        return {
            "error": "Debug info generation failed",
            "message": str(e),
            "timestamp": datetime.utcnow().isoformat()
        }

# Error handlers
@app.exception_handler(404)
async def not_found_handler(request: Request, exc: HTTPException):
    """Enhanced 404 handler with helpful information"""
    from fastapi.responses import JSONResponse
    return JSONResponse(
        status_code=404,
        content={
            "error": "Not Found",
            "message": f"The requested path '{request.url.path}' was not found",
            "method": request.method,
            "suggestions": [
                "Check the API documentation",
                "Verify the HTTP method (GET, POST, etc.)",
                "Ensure the endpoint exists in the current version"
            ],
            "available_endpoints": {
                "twilio": ["/twilio/voice", "/twilio/status", "/twilio/test-connection"],
                "dashboard": ["/api/dashboard/stats", "/api/dashboard/health", "/api/dashboard/test-clients"],
                "system": ["/", "/health", "/debug"]
            },
            "timestamp": datetime.utcnow().isoformat()
        }
    )

@app.exception_handler(405)
async def method_not_allowed_handler(request: Request, exc: HTTPException):
    """Enhanced 405 handler for method not allowed errors"""
    from fastapi.responses import JSONResponse
    return JSONResponse(
        status_code=405,
        content={
            "error": "Method Not Allowed", 
            "message": f"The method '{request.method}' is not allowed for '{request.url.path}'",
            "path": request.url.path,
            "method": request.method,
            "suggestions": [
                "Check if you're using the correct HTTP method (GET, POST, PUT, DELETE)",
                "Verify the endpoint accepts your method",
                "Check the API documentation for allowed methods"
            ],
            "timestamp": datetime.utcnow().isoformat()
        }
    )

@app.exception_handler(500)
async def internal_server_error_handler(request: Request, exc: HTTPException):
    """Enhanced 500 handler with diagnostic information"""
    from fastapi.responses import JSONResponse
    return JSONResponse(
        status_code=500,
        content={
            "error": "Internal Server Error",
            "message": "An internal server error occurred",
            "path": request.url.path,
            "method": request.method,
            "suggestions": [
                "Check the server logs for more details",
                "Verify all required services are running",
                "Contact support if the issue persists"
            ],
            "timestamp": datetime.utcnow().isoformat(),
            "support_info": {
                "logs_location": "Check application logs",
                "health_check": "/health",
                "debug_info": "/debug"
            }
        }
    )

if __name__ == "__main__":
    import uvicorn
    
    # Enhanced development server configuration
    uvicorn_config = {
        "app": "main:app",
        "host": "0.0.0.0",
        "port": 8000,
        "reload": getattr(settings, 'debug', True),
        "log_level": "info",
        "access_log": True
    }
    
    logger.info("🚀 Starting Enhanced Voice Agent API Server...")
    logger.info(f"📡 Server will be available at: http://localhost:8000")
    logger.info(f"📖 API documentation: http://localhost:8000/docs")
    logger.info(f"🔍 Debug info: http://localhost:8000/debug")
    
    uvicorn.run(**uvicorn_config)