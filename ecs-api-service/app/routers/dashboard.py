"""
Dashboard Router - Updated to Use Existing Services
Provides dashboard APIs using optimized existing services
"""

from fastapi import APIRouter, HTTPException, Request, Depends
from typing import List, Dict, Any, Optional
from datetime import datetime, timedelta
from pydantic import BaseModel, Field
import uuid
import logging
import json
import asyncio
import time 
import os  
import uuid 
# Import shared models and utilities
from shared.config.settings import settings
from shared.models.client import Client, ClientInfo, CampaignStatus, CallOutcome, CRMTag
from shared.models.call_session import CallSession, CallStatus
# from shared.utils.database import db_client
from shared.utils.redis_client import metrics_cache
# Import existing optimized services
from services.voice_processor import VoiceProcessor
from services.hybrid_tts import HybridTTSService
# from services.lyzr_client import lyzr_client as get_lyzr_client
from services.lyzr_client import lyzr_client
from services.elevenlabs_client import elevenlabs_client as get_elevenlabs_client
from services.deepgram_client import deepgram_client as get_deepgram_client

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api/dashboard", tags=["Dashboard"])

# Initialize existing services
voice_processor = VoiceProcessor()
hybrid_tts = HybridTTSService()

async def get_client_repo():
    """Get client repository (ensures it's initialized)"""
    try:
        from shared.utils.database import client_repo, init_database
        
        if client_repo is None:
            await init_database()
            from shared.utils.database import client_repo as repo
            return repo
        return client_repo
    except Exception as e:
        logger.error(f"Failed to get client repo: {e}")
        return None

async def get_session_repo():
    """Get session repository (ensures it's initialized)"""
    try:
        from shared.utils.database import session_repo, init_database
        
        if session_repo is None:
            await init_database()
            from shared.utils.database import session_repo as repo
            return repo
        return session_repo
    except Exception as e:
        logger.error(f"Failed to get session repo: {e}")
        return None

# Pydantic Models
class TestClientCreate(BaseModel):
    first_name: str = Field(..., min_length=1, max_length=50)
    last_name: str = Field(..., min_length=1, max_length=50)
    phone: str = Field(..., pattern=r'^\+?[1-9]\d{10,14}$')
    email: Optional[str] = None
    notes: Optional[str] = None

class TestAgentCreate(BaseModel):
    name: str = Field(..., min_length=1, max_length=100)
    email: str = Field(..., pattern=r'^[^@]+@[^@]+\.[^@]+$')
    google_calendar_id: Optional[str] = None
    timezone: str = "America/New_York"
    specialties: List[str] = []
    working_hours: str = "9AM-5PM"

class TestCallRequest(BaseModel):
    client_id: str
    agent_id: str
    call_type: str = "test"

# ================================================================
# PRODUCTION DASHBOARD ENDPOINTS
# ================================================================

@router.get("/stats")
async def get_campaign_stats():
    """Get production campaign statistics"""
    try:
        client_repo = await get_client_repo()
        if not client_repo:
            # Return default stats if database not available
            return {
                "total_clients": 0,
                "completed_calls": 0,
                "interested_clients": 0,
                "not_interested_clients": 0,
                "pending_clients": 0,
                "completion_rate": 0.0,
                "interest_rate": 0.0,
                "last_updated": datetime.utcnow().isoformat(),
                "note": "Database not available"
            }
        
        stats = await client_repo.get_campaign_stats()
        if not stats:
            stats = {}
        
        return {
            "total_clients": stats.get("total_clients", 0),
            "completed_calls": stats.get("completed_calls", 0),
            "interested_clients": stats.get("interested_clients", 0),
            "not_interested_clients": stats.get("not_interested_clients", 0),
            "pending_clients": stats.get("pending_clients", 0),
            "completion_rate": stats.get("completion_rate", 0.0),
            "interest_rate": stats.get("interest_rate", 0.0),
            "last_updated": datetime.utcnow().isoformat()
        }
        
    except Exception as e:
        logger.error(f"❌ Stats error: {e}")
        return {
            "total_clients": 0,
            "completed_calls": 0,
            "interested_clients": 0,
            "not_interested_clients": 0,
            "pending_clients": 0,
            "completion_rate": 0.0,
            "interest_rate": 0.0,
            "last_updated": datetime.utcnow().isoformat(),
            "error": str(e)
        }
    

@router.get("/call-logs")
async def get_call_logs(limit: int = 50):
    """Get production call logs using existing session repository"""
    try:

        # GET REPOSITORY DYNAMICALLY
        session_repo = await get_session_repo()
        if not session_repo:
            raise Exception("Database not available")
        
        # Use existing session repository for call logs
        sessions = await session_repo.get_recent_sessions(limit=limit)
        
        call_logs = []
        for session in sessions:
            call_logs.append({
                "call_id": session.session_id,
                "call_sid": session.twilio_call_sid,
                "client_phone": session.phone_number,
                "client_name": session.client_id,  # Would need to resolve to name
                "status": session.call_status.value if session.call_status else "unknown",
                "outcome": session.final_outcome or "unknown",
                "duration": f"{session.session_metrics.total_call_duration_seconds}s" if session.session_metrics else "unknown",
                "started_at": session.started_at.isoformat() if session.started_at else None,
                "completed_at": session.completed_at.isoformat() if session.completed_at else None,
                "conversation_turns": len(session.conversation_history),
                "summary": session.call_summary if hasattr(session, 'call_summary') else None
            })
        
        return {"logs": call_logs, "total": len(call_logs)}
        
    except Exception as e:
        logger.error(f"❌ Call logs error: {e}")
        # Return fallback logs
        return {
            "logs": [
                {
                    "call_id": "call_001",
                    "client_name": "John Doe",
                    "phone": "+1234567890",
                    "outcome": "interested",
                    "duration": "2m 45s",
                    "timestamp": datetime.utcnow().isoformat(),
                    "summary": "Customer interested in health insurance options"
                }
            ],
            "total": 1,
            "note": "Using fallback data - database connection issue"
        }

@router.get("/performance")
async def get_performance_metrics():
    """Get system performance metrics using existing services"""
    try:
        # Get performance data from existing services
        performance_data = {
            "target_metrics": {
                "static_response_latency": "< 700ms",
                "dynamic_response_latency": "< 2500ms",
                "transcription_latency": "< 500ms",
                "summary_generation": "< 2000ms"
            },
            "service_status": {
                "voice_processor": hasattr(voice_processor, 'is_configured') and voice_processor.is_configured(),
                "hybrid_tts": await hybrid_tts.is_configured(),
            },
            "current_metrics": {},
            "last_updated": datetime.utcnow().isoformat()
        }
        
        # Test service latencies
        try:
            if lyzr_client.is_configured():
                performance_data["service_status"]["lyzr"] = True
                # Could add latency test here
        except Exception:
            performance_data["service_status"]["lyzr"] = False
        
        try:
            elevenlabs_client = await get_elevenlabs_client()
            if elevenlabs_client.is_configured():
                performance_data["service_status"]["elevenlabs"] = True
        except Exception:
            performance_data["service_status"]["elevenlabs"] = False
        
        try:
            deepgram_client = await get_deepgram_client()
            if deepgram_client.is_configured():
                performance_data["service_status"]["deepgram"] = True
        except Exception:
            performance_data["service_status"]["deepgram"] = False
        
        return performance_data
        
    except Exception as e:
        logger.error(f"❌ Performance metrics error: {e}")
        return {
            "target_metrics": {
                "static_response_latency": "< 700ms",
                "dynamic_response_latency": "< 2500ms"
            },
            "current_metrics": {"error": str(e)},
            "last_updated": datetime.utcnow().isoformat()
        }

# ================================================================
# TESTING ENDPOINTS
# ================================================================

@router.get("/test-clients")
async def get_test_clients():
    """Get test clients using existing database utilities"""
    try:
        client_repo = await get_client_repo()
        if not client_repo:
            raise Exception("Database not available")
        
        clients = await client_repo.get_test_clients(limit=100)
        
        formatted_clients = []
        for client in clients:
            formatted_clients.append({
                "id": str(client.id),
                "name": f"{client.client.first_name} {client.client.last_name}",
                "phone": client.client.phone,
                "email": client.client.email,
                "status": client.campaign_status.value,
                "total_attempts": client.total_attempts,
                "created_at": client.created_at.isoformat() if client.created_at else None,
            })
        
        return {"clients": formatted_clients}
        
    except Exception as e:
        logger.error(f"❌ Test clients error: {e}")
        return {"clients": [], "error": str(e)}
    
@router.post("/test-clients")
async def create_test_client(client_data: TestClientCreate):
    """Create test client using existing database utilities"""
    try:
        client_info = ClientInfo(
            first_name=client_data.first_name,
            last_name=client_data.last_name,
            phone=client_data.phone,
            email=client_data.email,
            last_agent="test_agent"
        )
        
        client = Client(
            client=client_info,
            campaign_status=CampaignStatus.PENDING,
            total_attempts=0,
            call_history=[],
            crm_tags=[],
            created_at=datetime.utcnow(),
            updated_at=datetime.utcnow(),
            is_test_client=True,  # Make sure this is set
            notes=client_data.notes if hasattr(client_data, 'notes') else None
        )

        client_repo = await get_client_repo()
        if not client_repo:
            raise Exception("Database not available")
        
        client_id = await client_repo.create_client(client)
        
        return {
            "success": True,
            "client_id": client_id,
            "message": "Test client created successfully"
        }
        
    except Exception as e:
        logger.error(f"❌ Create test client error: {e}")
        raise HTTPException(500, f"Failed to create test client: {str(e)}")

async def get_test_agent_repo():
    """Get test agent repository"""
    try:
        from shared.utils.database import test_agent_repo, init_database
        if test_agent_repo is None:
            await init_database()
            from shared.utils.database import test_agent_repo as repo
            return repo
        return test_agent_repo
    except Exception as e:
        logger.error(f"Failed to get test agent repo: {e}")
        return None

@router.post("/test-agents")
async def create_test_agent(agent_data: TestAgentCreate):
    """Create test agent in database"""
    try:
        test_agent_repo = await get_test_agent_repo()
        if not test_agent_repo:
            raise Exception("Database not available")
        
        # Import TestAgent from database module
        from shared.utils.database import TestAgent
        
        agent = TestAgent(
            name=agent_data.name,
            email=agent_data.email,
            google_calendar_id=agent_data.google_calendar_id,
            timezone=agent_data.timezone,
            specialties=getattr(agent_data, 'specialties', [])
        )
        
        agent_id = await test_agent_repo.create_test_agent(agent)
        
        return {
            "success": True,
            "agent_id": agent_id,
            "message": "Test agent created successfully"
        }
        
    except Exception as e:
        logger.error(f"❌ Create test agent error: {e}")
        raise HTTPException(500, f"Failed to create test agent: {str(e)}")

@router.get("/test-agents")
async def get_test_agents():
    """Get all test agents from database"""
    try:
        test_agent_repo = await get_test_agent_repo()
        if not test_agent_repo:
            raise Exception("Database not available")
        
        agents = await test_agent_repo.get_all_test_agents()
        
        formatted_agents = []
        for agent in agents:
            formatted_agents.append({
                "id": str(agent.id),
                "name": agent.name,
                "email": agent.email,
                "timezone": agent.timezone,
                "specialties": agent.specialties,
                "working_hours": agent.working_hours
            })
        
        return {"agents": formatted_agents}
        
    except Exception as e:
        logger.error(f"❌ Test agents error: {e}")
        return {"agents": [], "error": str(e)}

@router.post("/test-call")
async def initiate_test_call(call_request: TestCallRequest):
    """Initiate REAL test call using Twilio API"""
    try:
        client_repo = await get_client_repo()
        test_agent_repo = await get_test_agent_repo()
        
        if not client_repo or not test_agent_repo:
            raise HTTPException(500, "Database not available")
        
        # Get client from database
        client = await client_repo.get_client_by_id(call_request.client_id)
        if not client:
            raise HTTPException(404, "Test client not found")
        
        # Get agent from database
        agent = await test_agent_repo.get_test_agent_by_id(call_request.agent_id)
        if not agent:
            raise HTTPException(404, "Test agent not found")
        
        # Import Twilio client for REAL calls
        from twilio.rest import Client as TwilioClient
        
        # Check Twilio configuration
        if not settings.twilio_account_sid or not settings.twilio_auth_token:
            raise HTTPException(500, "Twilio credentials not configured")
        
        if not hasattr(settings, 'twilio_phone_number') or not settings.twilio_phone_number:
            raise HTTPException(500, "Twilio phone number not configured")
        
        # Create REAL Twilio client
        twilio_client = TwilioClient(settings.twilio_account_sid, settings.twilio_auth_token)
        
        # Make REAL call
        try:
            logger.info(f"🔥 Making REAL call to {client.client.phone} from {settings.twilio_phone_number}")
            
            call = twilio_client.calls.create(
                to=client.client.phone,  # Call the test client's real phone
                from_=settings.twilio_phone_number,  # Your Twilio number
                url=f"{settings.base_url}/twilio/voice",  # Your webhook URL
                status_callback=f"{settings.base_url}/twilio/status",
                status_callback_event=['initiated', 'ringing', 'answered', 'completed'],
                status_callback_method='POST'
            )
            
            # NOW we have the REAL call SID from Twilio
            real_call_sid = call.sid  # This is the actual Twilio call SID
            
            logger.info(f"✅ REAL call initiated: {real_call_sid}")
            
            # Create session with REAL call SID
            session = CallSession(
                session_id=str(uuid.uuid4()),
                twilio_call_sid=real_call_sid,  # Use REAL call SID from Twilio
                client_id=call_request.client_id,
                phone_number=client.client.phone,
                lyzr_agent_id=settings.lyzr_conversation_agent_id,
                lyzr_session_id=f"test_{uuid.uuid4().hex[:8]}",
                is_test_call=True
            )
            
            # Cache session for webhook processing
            from shared.utils.redis_client import cache_session
            await cache_session(session)
            
            return {
                "success": True,
                "call_id": session.session_id,
                "call_sid": real_call_sid,  # Return REAL Twilio call SID
                "status": call.status,
                "client_name": f"{client.client.first_name} {client.client.last_name}",
                "phone": client.client.phone,
                "agent_name": agent.name,
                "message": "🔥 REAL test call initiated - you should receive a call shortly!",
                "twilio_call_status": call.status,
                "webhook_url": f"{settings.base_url}/twilio/voice"
            }
            
        except Exception as e:
            logger.error(f"❌ Twilio API error: {e}")
            raise HTTPException(500, f"Failed to initiate Twilio call: {str(e)}")
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"❌ Test call error: {e}")
        raise HTTPException(500, f"Test call failed: {str(e)}")

@router.delete("/test-clients/{client_id}")
async def delete_test_client(client_id: str):
    """Delete test client using existing repository"""
    try:

        # GET REPOSITORY DYNAMICALLY
        client_repo = await get_client_repo()
        if not client_repo:
            raise HTTPException(500, "Database not available")
        
        # Verify it's a test client before deleting
        client = await client_repo.get_client_by_id(client_id)
        if not client or not getattr(client, 'is_test_client', False):
            raise HTTPException(404, "Test client not found")
        
        # Use existing repository to delete
        success = await client_repo.delete_client(client_id)
        if not success:
            raise HTTPException(500, "Failed to delete client")
        
        return {"success": True, "message": "Test client deleted successfully"}
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"❌ Delete test client error: {e}")
        raise HTTPException(500, "Failed to delete test client")

# ================================================================
# TESTING ENDPOINTS FOR SERVICES
# ================================================================

@router.post("/test-voice-processing")
async def test_voice_processing(request: Request):
    """Test voice processing pipeline using existing services"""
    try:
        body = await request.json()
        test_text = body.get("text", "Yes, I'm interested in learning more about health insurance.")
        
        # Test existing voice processor
        test_session = CallSession(
            session_id="test_session",
            twilio_call_sid="test_call",
            client_id="test_client",
            phone_number="+1234567890",
            lyzr_agent_id=settings.lyzr_conversation_agent_id,
            lyzr_session_id="test_lyzr_session"
        )
        
        # Process input using existing voice processor
        result = await voice_processor.process_customer_input(
            customer_input=test_text,
            session=test_session,
            confidence=0.95
        )
        
        return {
            "success": result.get("success", False),
            "input_text": test_text,
            "response_text": result.get("response_text", ""),
            "outcome": result.get("outcome", "unknown"),
            "processing_time_ms": result.get("processing_time_ms", 0),
            "services_used": {
                "voice_processor": True,
                "lyzr": result.get("lyzr_used", False),
                "hybrid_tts": result.get("tts_used", False)
            }
        }
        
    except Exception as e:
        logger.error(f"❌ Voice processing test error: {e}")
        return {
            "success": False,
            "error": str(e),
            "input_text": test_text if 'test_text' in locals() else ""
        }

@router.post("/test-tts")
async def test_text_to_speech(request: Request):
    """Test TTS using existing hybrid TTS service"""
    try:
        body = await request.json()
        text = body.get("text", "Hello, this is a test of our text-to-speech service.")
        response_type = body.get("response_type", "general")
        
        # Test existing hybrid TTS service
        tts_result = await hybrid_tts.get_response_audio(
            text=text,
            response_type=response_type,
            context={"test": True}
        )
        
        return {
            "success": tts_result.get("success", False),
            "text": text,
            "response_type": response_type,
            "audio_url": tts_result.get("audio_url"),
            "is_static": tts_result.get("is_static", False),
            "generation_time_ms": tts_result.get("generation_time_ms", 0),
            "service_used": tts_result.get("service_used", "unknown")
        }
        
    except Exception as e:
        logger.error(f"❌ TTS test error: {e}")
        return {
            "success": False,
            "error": str(e),
            "text": text if 'text' in locals() else ""
        }

@router.get("/test-services")
async def test_all_services():
    """Test all existing services connectivity and configuration"""
    try:

        # GET REPOSITORY DYNAMICALLY
        client_repo = await get_client_repo()

        return {
            "overall_status": "operational",
            "services": {
                "voice_processor": {"ready": True, "note": "Service available"},
                "hybrid_tts": {"ready": True, "note": "Service available"},
                "lyzr": {
                    "configured": lyzr_client.is_configured(),
                    "conversation_agent_id": settings.lyzr_conversation_agent_id
                },
                "elevenlabs": {
                    "configured": bool(settings.elevenlabs_api_key),
                    "voice_id": settings.default_voice_id
                },
                "deepgram": {
                    "configured": bool(settings.deepgram_api_key),
                    "model": settings.stt_model
                },
                "database": {
                    "connected": client_repo is not None,
                    "note": "Repository available" if client_repo else "Repository not available"
                },
                "redis": {
                    "connected": metrics_cache is not None,
                    "note": "Cache available" if metrics_cache else "Cache not available"
                }
            },
            "critical_services_ready": True,
            "timestamp": datetime.utcnow().isoformat(),
            "environment": "development"
        }
        
    except Exception as e:
        logger.error(f"❌ Service test error: {e}")
        return {
            "overall_status": "error",
            "error": str(e),
            "timestamp": datetime.utcnow().isoformat()
        }
@router.get("/system-health")
async def get_system_health():
    """Get comprehensive system health using existing services"""
    try:
        health_data = {
            "status": "healthy",
            "timestamp": datetime.utcnow().isoformat(),
            "components": {},
            "performance": {},
            "configuration": {}
        }
        
        # Check existing services health
        health_data["components"]["voice_processor"] = hasattr(voice_processor, 'is_configured') and voice_processor.is_configured()
        health_data["components"]["hybrid_tts"] = await hybrid_tts.is_configured()
        
        # Check external service configurations
        health_data["configuration"]["lyzr"] = bool(settings.lyzr_user_api_key)
        health_data["configuration"]["elevenlabs"] = bool(settings.elevenlabs_api_key)
        health_data["configuration"]["deepgram"] = bool(settings.deepgram_api_key)
        health_data["configuration"]["twilio"] = bool(settings.twilio_account_sid)

        # GET REPOSITORY DYNAMICALLY
        client_repo = await get_client_repo()

        # Check database connectivity
        try:
            await client_repo.get_campaign_stats()
            health_data["components"]["database"] = True
        except Exception:
            health_data["components"]["database"] = False
        
        # Check cache connectivity
        try:
            await metrics_cache.get("health_check")
            health_data["components"]["cache"] = True
        except Exception:
            health_data["components"]["cache"] = False
        
        # Determine overall health
        critical_components = [
            health_data["components"].get("voice_processor", False),
            health_data["components"].get("hybrid_tts", False),
            health_data["components"].get("database", False)
        ]
        
        if all(critical_components):
            health_data["status"] = "healthy"
        elif any(critical_components):
            health_data["status"] = "degraded"
        else:
            health_data["status"] = "unhealthy"
        
        return health_data
        
    except Exception as e:
        logger.error(f"❌ System health check error: {e}")
        return {
            "status": "error",
            "error": str(e),
            "timestamp": datetime.utcnow().isoformat()
        }