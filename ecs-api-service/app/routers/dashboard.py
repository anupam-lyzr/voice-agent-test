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

# Import shared models and utilities
from shared.config.settings import settings
from shared.models.client import Client, ClientInfo, CampaignStatus, CallOutcome, CRMTag
from shared.models.call_session import CallSession, CallStatus
from shared.utils.database import client_repo, session_repo
from shared.utils.redis_client import metrics_cache

# Import existing optimized services
from ..services.voice_processor import VoiceProcessor
from ..services.hybrid_tts import HybridTTSService
from ..services.lyzr_client import get_lyzr_client
from ..services.elevenlabs_client import get_elevenlabs_client
from ..services.deepgram_client import get_deepgram_client

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api/dashboard", tags=["Dashboard"])

# Initialize existing services
voice_processor = VoiceProcessor()
hybrid_tts = HybridTTSService()

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
    """Get production campaign statistics using existing database utilities"""
    try:
        # Use existing database repository
        stats = await client_repo.get_campaign_stats()
        
        # Get additional metrics from cache
        worker_metrics = await metrics_cache.get("worker_metrics")
        performance_metrics = await metrics_cache.get("performance_metrics")
        
        return {
            "total_clients": stats.get("total_clients", 0),
            "completed_calls": stats.get("completed_calls", 0),
            "interested_clients": stats.get("interested_clients", 0),
            "not_interested_clients": stats.get("not_interested_clients", 0),
            "pending_clients": stats.get("pending_clients", 0),
            "completion_rate": stats.get("completion_rate", 0),
            "interest_rate": stats.get("interest_rate", 0),
            "worker_stats": worker_metrics or {},
            "performance": performance_metrics or {},
            "last_updated": datetime.utcnow().isoformat()
        }
        
    except Exception as e:
        logger.error(f"❌ Stats error: {e}")
        # Return fallback stats
        return {
            "total_clients": 14000,
            "completed_calls": 3500,
            "interested_clients": 1400,
            "not_interested_clients": 2100,
            "pending_clients": 10500,
            "completion_rate": 25.0,
            "interest_rate": 40.0,
            "last_updated": datetime.utcnow().isoformat(),
            "note": "Using fallback data - database connection issue"
        }

@router.get("/call-logs")
async def get_call_logs(limit: int = 50):
    """Get production call logs using existing session repository"""
    try:
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
                "voice_processor": voice_processor.is_ready(),
                "hybrid_tts": await hybrid_tts.is_ready(),
            },
            "current_metrics": {},
            "last_updated": datetime.utcnow().isoformat()
        }
        
        # Test service latencies
        try:
            lyzr_client = await get_lyzr_client()
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
        # Use existing client repository for test clients
        clients = await client_repo.get_clients(is_test=True, limit=100)
        
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
                "last_call_outcome": client.get_latest_call_outcome()
            })
        
        return {"clients": formatted_clients}
        
    except Exception as e:
        logger.error(f"❌ Test clients error: {e}")
        # Return fallback test clients
        return {
            "clients": [
                {
                    "id": "test_client_1",
                    "name": "John Doe",
                    "phone": "+1234567890",
                    "email": "john@example.com",
                    "status": "pending",
                    "total_attempts": 0,
                    "created_at": datetime.utcnow().isoformat()
                }
            ],
            "note": "Using fallback data - database connection issue"
        }

@router.post("/test-clients")
async def create_test_client(client_data: TestClientCreate):
    """Create test client using existing database utilities"""
    try:
        # Create client using existing models and repository
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
            is_test_client=True,
            notes=client_data.notes
        )
        
        # Use existing client repository
        client_id = await client_repo.create_client(client)
        
        return {
            "success": True,
            "client_id": client_id,
            "message": "Test client created successfully"
        }
        
    except Exception as e:
        logger.error(f"❌ Create test client error: {e}")
        raise HTTPException(500, f"Failed to create test client: {str(e)}")

@router.get("/test-agents")
async def get_test_agents():
    """Get test agents from configuration"""
    try:
        # Load agents from existing configuration
        agents = []
        try:
            with open("data/agents.json", "r") as f:
                agents_data = json.load(f)
                if "agents" in agents_data:
                    agents = agents_data["agents"]
        except FileNotFoundError:
            # Default test agents
            agents = [
                {
                    "id": "agent_1",
                    "name": "Sarah Johnson",
                    "email": "sarah@altruisadvisor.com",
                    "specialties": ["health", "family"],
                    "timezone": "America/New_York",
                    "working_hours": "9AM-5PM"
                },
                {
                    "id": "agent_2",
                    "name": "Mike Chen",
                    "email": "mike@altruisadvisor.com",
                    "specialties": ["medicare", "business"],
                    "timezone": "America/New_York",
                    "working_hours": "9AM-5PM"
                }
            ]
        
        return {"agents": agents}
        
    except Exception as e:
        logger.error(f"❌ Test agents error: {e}")
        raise HTTPException(500, "Failed to get test agents")

@router.post("/test-call")
async def initiate_test_call(call_request: TestCallRequest):
    """Initiate real test call using existing voice processor"""
    try:
        # Get client using existing repository
        client = await client_repo.get_client_by_id(call_request.client_id)
        if not client:
            raise HTTPException(404, "Test client not found")
        
        # Get agent details
        agents_data = []
        try:
            with open("data/agents.json", "r") as f:
                agents_data = json.load(f).get("agents", [])
        except FileNotFoundError:
            pass
        
        agent = next((a for a in agents_data if a["id"] == call_request.agent_id), None)
        if not agent:
            raise HTTPException(404, "Agent not found")
        
        # Create test call session using existing models
        session = CallSession(
            session_id=str(uuid.uuid4()),
            twilio_call_sid=f"test_call_{uuid.uuid4().hex[:8]}",
            client_id=call_request.client_id,
            phone_number=client.client.phone,
            lyzr_agent_id=settings.lyzr_conversation_agent_id,
            lyzr_session_id=f"test_{uuid.uuid4().hex[:8]}",
            is_test_call=True
        )
        
        # Initiate real call using existing voice processor
        call_result = await voice_processor.initiate_outbound_call(
            client=client,
            session=session,
            agent_context=agent
        )
        
        if not call_result.get("success"):
            raise HTTPException(500, f"Test call failed: {call_result.get('error')}")
        
        # Track call flow steps
        call_steps = [
            {
                "step": "call_initiated",
                "status": "completed",
                "timestamp": datetime.utcnow().isoformat(),
                "details": {"call_sid": call_result.get("call_sid")}
            },
            {
                "step": "twilio_connection",
                "status": "completed",
                "timestamp": datetime.utcnow().isoformat(),
                "details": {"status": call_result.get("status")}
            },
            {
                "step": "voice_processing",
                "status": "in_progress",
                "timestamp": datetime.utcnow().isoformat()
            }
        ]
        
        return {
            "success": True,
            "call_id": session.session_id,
            "call_sid": call_result.get("call_sid"),
            "status": "initiated",
            "client_name": f"{client.client.first_name} {client.client.last_name}",
            "phone": client.client.phone,
            "agent_name": agent["name"],
            "steps": call_steps,
            "message": "Real test call initiated successfully using existing services"
        }
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"❌ Test call error: {e}")
        raise HTTPException(500, f"Test call failed: {str(e)}")

@router.delete("/test-clients/{client_id}")
async def delete_test_client(client_id: str):
    """Delete test client using existing repository"""
    try:
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
        service_tests = {}
        
        # Test Voice Processor
        try:
            service_tests["voice_processor"] = {
                "ready": voice_processor.is_ready(),
                "configured": True
            }
        except Exception as e:
            service_tests["voice_processor"] = {
                "ready": False,
                "error": str(e)
            }
        
        # Test Hybrid TTS
        try:
            service_tests["hybrid_tts"] = {
                "ready": await hybrid_tts.is_ready(),
                "static_audio_available": await hybrid_tts.check_static_audio_availability()
            }
        except Exception as e:
            service_tests["hybrid_tts"] = {
                "ready": False,
                "error": str(e)
            }
        
        # Test LYZR Client
        try:
            lyzr_client = await get_lyzr_client()
            service_tests["lyzr"] = {
                "configured": lyzr_client.is_configured(),
                "conversation_agent_id": settings.lyzr_conversation_agent_id,
                "summary_agent_id": settings.lyzr_summary_agent_id
            }
        except Exception as e:
            service_tests["lyzr"] = {
                "configured": False,
                "error": str(e)
            }
        
        # Test ElevenLabs Client
        try:
            elevenlabs_client = await get_elevenlabs_client()
            service_tests["elevenlabs"] = {
                "configured": elevenlabs_client.is_configured(),
                "voice_id": settings.default_voice_id
            }
        except Exception as e:
            service_tests["elevenlabs"] = {
                "configured": False,
                "error": str(e)
            }
        
        # Test Deepgram Client
        try:
            deepgram_client = await get_deepgram_client()
            service_tests["deepgram"] = {
                "configured": deepgram_client.is_configured(),
                "model": settings.stt_model
            }
        except Exception as e:
            service_tests["deepgram"] = {
                "configured": False,
                "error": str(e)
            }
        
        # Test Database Connection
        try:
            test_stats = await client_repo.get_campaign_stats()
            service_tests["database"] = {
                "connected": True,
                "test_query_success": bool(test_stats)
            }
        except Exception as e:
            service_tests["database"] = {
                "connected": False,
                "error": str(e)
            }
        
        # Test Redis Cache
        try:
            test_cache = await metrics_cache.get("test_key")
            await metrics_cache.set("test_key", {"test": True}, expire_seconds=60)
            service_tests["redis"] = {
                "connected": True,
                "cache_working": True
            }
        except Exception as e:
            service_tests["redis"] = {
                "connected": False,
                "error": str(e)
            }
        
        # Overall system health
        all_critical_services_ready = all([
            service_tests.get("voice_processor", {}).get("ready", False),
            service_tests.get("hybrid_tts", {}).get("ready", False),
            service_tests.get("database", {}).get("connected", False)
        ])
        
        return {
            "overall_status": "ready" if all_critical_services_ready else "degraded",
            "services": service_tests,
            "critical_services_ready": all_critical_services_ready,
            "timestamp": datetime.utcnow().isoformat(),
            "environment": settings.environment if hasattr(settings, 'environment') else "unknown"
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
        health_data["components"]["voice_processor"] = voice_processor.is_ready()
        health_data["components"]["hybrid_tts"] = await hybrid_tts.is_ready()
        
        # Check external service configurations
        health_data["configuration"]["lyzr"] = bool(settings.lyzr_user_api_key)
        health_data["configuration"]["elevenlabs"] = bool(settings.elevenlabs_api_key)
        health_data["configuration"]["deepgram"] = bool(settings.deepgram_api_key)
        health_data["configuration"]["twilio"] = bool(settings.twilio_account_sid)
        
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