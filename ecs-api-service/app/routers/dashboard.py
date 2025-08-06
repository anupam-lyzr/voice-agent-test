"""
Production Dashboard Router
Provides comprehensive dashboard APIs with call summaries and transcripts
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

# Import shared models and utilities
from shared.config.settings import settings
from shared.models.client import Client, ClientInfo, CampaignStatus, CallOutcome, CRMTag
from shared.models.call_session import CallSession, CallStatus

# Import services
from services.voice_processor import VoiceProcessor
from services.hybrid_tts import HybridTTSService
from services.lyzr_client import lyzr_client
from services.elevenlabs_client import elevenlabs_client
from services.deepgram_client import deepgram_client

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api/dashboard", tags=["Dashboard"])

# Initialize services
voice_processor = VoiceProcessor()
hybrid_tts = HybridTTSService()

# Database repository getters
async def get_client_repo():
    """Get client repository (ensures it's initialized)"""
    try:
        from shared.utils.database import client_repo, init_database
        
        if client_repo is None:
            logger.info("Initializing database...")
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

# Helper Functions
def _build_transcript(session: CallSession) -> str:
    """Build conversation transcript from session turns"""
    if not session.conversation_turns:
        return ""
    
    transcript_lines = []
    for turn in session.conversation_turns:
        transcript_lines.append(f"Customer: {turn.customer_speech}")
        transcript_lines.append(f"Agent: {turn.agent_response}")
        transcript_lines.append("")  # Empty line between turns
    
    return "\n".join(transcript_lines).strip()

def _format_duration(seconds: int) -> str:
    """Format duration in human-readable format"""
    if seconds < 60:
        return f"{seconds}s"
    elif seconds < 3600:
        minutes = seconds // 60
        secs = seconds % 60
        return f"{minutes}m {secs}s"
    else:
        hours = seconds // 3600
        minutes = (seconds % 3600) // 60
        return f"{hours}h {minutes}m"

# ================================================================
# PRODUCTION DASHBOARD ENDPOINTS
# ================================================================

@router.get("/stats")
async def get_campaign_stats():
    """Get comprehensive campaign statistics"""
    try:
        client_repo = await get_client_repo()
        if not client_repo:
            return {
                "total_clients": 0,
                "completed_calls": 0,
                "interested_clients": 0,
                "not_interested_clients": 0,
                "dnc_requests": 0,
                "pending_clients": 0,
                "completion_rate": 0.0,
                "interest_rate": 0.0,
                "avg_call_duration": 0,
                "total_conversations": 0,
                "last_updated": datetime.utcnow().isoformat(),
                "note": "Database not available"
            }
        
        # Get comprehensive stats
        stats = await client_repo.get_campaign_stats()
        if not stats:
            stats = {}
        
        # Get session stats for call durations
        session_repo = await get_session_repo()
        call_stats = {"avg_duration": 0, "total_calls": 0}
        
        if session_repo:
            try:
                from shared.utils.database import db_client
                if db_client is not None and db_client.database is not None:
                    # Calculate average call duration
                    pipeline = [
                        {"$match": {"session_metrics.total_call_duration_seconds": {"$gt": 0}}},
                        {"$group": {
                            "_id": None,
                            "avg_duration": {"$avg": "$session_metrics.total_call_duration_seconds"},
                            "total_calls": {"$sum": 1}
                        }}
                    ]
                    async for doc in db_client.database.call_sessions.aggregate(pipeline):
                        call_stats = doc
            except Exception as e:
                logger.error(f"Error calculating call stats: {e}")
        
        # Calculate additional metrics
        total_clients = stats.get("total_clients", 0)
        completed_calls = stats.get("completed_calls", 0)
        interested_clients = stats.get("interested_clients", 0)
        
        completion_rate = (completed_calls / total_clients * 100) if total_clients > 0 else 0
        interest_rate = (interested_clients / completed_calls * 100) if completed_calls > 0 else 0
        
        return {
            "total_clients": total_clients,
            "completed_calls": completed_calls,
            "interested_clients": interested_clients,
            "not_interested_clients": stats.get("not_interested_clients", 0),
            "dnc_requests": stats.get("dnc_requests", 0),
            "pending_clients": stats.get("pending_clients", 0),
            "in_progress": stats.get("in_progress", 0),
            "completion_rate": round(completion_rate, 1),
            "interest_rate": round(interest_rate, 1),
            "avg_call_duration": round(call_stats.get("avg_duration", 0)),
            "total_conversations": call_stats.get("total_calls", 0),
            "calls_today": stats.get("calls_today", 0),
            "calls_this_week": stats.get("calls_this_week", 0),
            "last_updated": datetime.utcnow().isoformat()
        }
        
    except Exception as e:
        logger.error(f"❌ Stats error: {e}")
        return {
            "error": str(e),
            "last_updated": datetime.utcnow().isoformat()
        }

@router.get("/call-logs")
async def get_call_logs(
    limit: int = 50,
    offset: int = 0,
    outcome: Optional[str] = None,
    date_from: Optional[datetime] = None,
    date_to: Optional[datetime] = None
):
    """Get detailed call logs with transcripts and summaries"""
    try:
        session_repo = await get_session_repo()
        client_repo = await get_client_repo()
        
        if not session_repo:
            return {"logs": [], "total": 0, "error": "Database not available"}
        
        # Build query filter
        query = {}
        if outcome:
            query["final_outcome"] = outcome
        if date_from or date_to:
            query["started_at"] = {}
            if date_from:
                query["started_at"]["$gte"] = date_from
            if date_to:
                query["started_at"]["$lte"] = date_to
        
        # Get sessions with filter
        from shared.utils.database import db_client
        if db_client is None or db_client.database is None:
            return {"logs": [], "total": 0, "error": "Database not connected"}
        
        # Get total count
        total_count = await db_client.database.call_sessions.count_documents(query)
        
        # Get paginated results
        cursor = db_client.database.call_sessions.find(query).sort("started_at", -1).skip(offset).limit(limit)
        
        call_logs = []
        async for doc in cursor:
            session = CallSession(**doc)
            
            # Get client information
            client_name = "Unknown"
            client_phone = session.phone_number
            
            if session.client_data:
                client_name = session.client_data.get("client_name", "Unknown")
            elif session.client_id and session.client_id != "unknown" and client_repo:
                try:
                    client = await client_repo.get_client_by_id(session.client_id)
                    if client:
                        client_name = f"{client.client.first_name} {client.client.last_name}"
                except Exception:
                    pass
            
            # Build call log entry
            log_entry = {
                "call_id": session.session_id,
                "call_sid": session.twilio_call_sid,
                "client_name": client_name,
                "client_phone": client_phone,
                "status": session.call_status.value if session.call_status else "unknown",
                "outcome": session.final_outcome or "unknown",
                "duration": _format_duration(
                    session.session_metrics.total_call_duration_seconds 
                    if session.session_metrics and session.session_metrics.total_call_duration_seconds 
                    else 0
                ),
                "duration_seconds": session.session_metrics.total_call_duration_seconds if session.session_metrics else 0,
                "started_at": session.started_at.isoformat() if session.started_at else None,
                "completed_at": session.completed_at.isoformat() if session.completed_at else None,
                "conversation_turns": len(session.conversation_turns) if session.conversation_turns else 0,
                "conversation_stage": session.conversation_stage.value if session.conversation_stage else "unknown",
                "is_test_call": getattr(session, 'is_test_call', False)
            }
            
            # Add transcript if requested (for individual call view)
            if session.conversation_turns:
                log_entry["has_transcript"] = True
                log_entry["transcript_preview"] = session.conversation_turns[0].customer_speech[:100] + "..." if session.conversation_turns[0].customer_speech else ""
            else:
                log_entry["has_transcript"] = False
                log_entry["transcript_preview"] = ""
            
            # Add summary if available
            if hasattr(session, 'call_summary') and session.call_summary:
                log_entry["has_summary"] = True
                log_entry["summary_preview"] = {
                    "sentiment": session.call_summary.get("sentiment", "unknown"),
                    "key_points": session.call_summary.get("key_points", [])[:2],  # First 2 points
                    "urgency": session.call_summary.get("urgency", "unknown")
                }
            else:
                log_entry["has_summary"] = False
                log_entry["summary_preview"] = None
            
            call_logs.append(log_entry)
        
        return {
            "logs": call_logs,
            "total": total_count,
            "page": offset // limit + 1,
            "pages": (total_count + limit - 1) // limit,
            "limit": limit
        }
        
    except Exception as e:
        logger.error(f"❌ Call logs error: {e}")
        import traceback
        logger.error(traceback.format_exc())
        return {
            "logs": [],
            "total": 0,
            "error": str(e)
        }

@router.get("/call-details/{call_id}")
async def get_call_details(call_id: str):
    """Get complete call details including transcript and summary"""
    try:
        session_repo = await get_session_repo()
        if not session_repo:
            raise HTTPException(503, "Database not available")
        
        # Try to get session by session_id first
        from shared.utils.database import db_client
        if db_client is None or db_client.database is None:
            raise HTTPException(503, "Database not connected")
        
        # Search by session_id or twilio_call_sid
        doc = await db_client.database.call_sessions.find_one({
            "$or": [
                {"session_id": call_id},
                {"twilio_call_sid": call_id}
            ]
        })
        
        if not doc:
            raise HTTPException(404, "Call not found")
        
        session = CallSession(**doc)
        
        # Get client information
        client_info = None
        if session.client_id and session.client_id != "unknown":
            client_repo = await get_client_repo()
            if client_repo:
                try:
                    client = await client_repo.get_client_by_id(session.client_id)
                    if client:
                        client_info = {
                            "name": f"{client.client.first_name} {client.client.last_name}",
                            "phone": client.client.phone,
                            "email": client.client.email,
                            "last_agent": client.client.last_agent,
                            "total_attempts": client.total_attempts,
                            "crm_tags": [tag.value for tag in client.crm_tags] if client.crm_tags else []
                        }
                except Exception as e:
                    logger.warning(f"Could not get client info: {e}")
        
        # Build full transcript
        transcript = None
        if session.conversation_turns:
            transcript = _build_transcript(session)
        
        # Get call summary
        summary = None
        if hasattr(session, 'call_summary') and session.call_summary:
            summary = session.call_summary
        
        # Build response
        return {
            "call_id": session.session_id,
            "call_sid": session.twilio_call_sid,
            "client": client_info or {
                "name": session.client_data.get("client_name", "Unknown") if session.client_data else "Unknown",
                "phone": session.phone_number
            },
            "status": session.call_status.value if session.call_status else "unknown",
            "outcome": session.final_outcome or "unknown",
            "duration": _format_duration(
                session.session_metrics.total_call_duration_seconds 
                if session.session_metrics and session.session_metrics.total_call_duration_seconds 
                else 0
            ),
            "started_at": session.started_at.isoformat() if session.started_at else None,
            "completed_at": session.completed_at.isoformat() if session.completed_at else None,
            "conversation_turns": len(session.conversation_turns) if session.conversation_turns else 0,
            "conversation_stage": session.conversation_stage.value if session.conversation_stage else "unknown",
            "transcript": transcript,
            "summary": summary,
            "metrics": {
                "total_duration": session.session_metrics.total_call_duration_seconds if session.session_metrics else 0,
                "transcription_latency_avg": session.session_metrics.avg_transcription_latency_ms if session.session_metrics else 0,
                "tts_latency_avg": session.session_metrics.avg_tts_latency_ms if session.session_metrics else 0,
                "total_latency_avg": session.session_metrics.avg_total_latency_ms if session.session_metrics else 0
            },
            "is_test_call": getattr(session, 'is_test_call', False)
        }
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"❌ Call details error: {e}")
        raise HTTPException(500, f"Error retrieving call details: {str(e)}")

@router.get("/performance")
async def get_performance_metrics():
    """Get system performance metrics"""
    try:
        # Get service performance stats
        performance_data = {
            "target_metrics": {
                "static_response_latency": "< 700ms",
                "dynamic_response_latency": "< 2500ms",
                "transcription_latency": "< 500ms",
                "tts_latency": "< 800ms",
                "lyzr_response_latency": "< 1200ms",
                "total_response_latency": "< 2000ms"
            },
            "service_status": {
                "voice_processor": voice_processor.is_configured(),
                "hybrid_tts": await hybrid_tts.is_configured(),
                "lyzr": lyzr_client.is_configured(),
                "elevenlabs": elevenlabs_client.is_configured(),
                "deepgram": deepgram_client.is_configured()
            },
            "current_metrics": {},
            "service_stats": {}
        }
        
        # Get actual performance stats from services
        try:
            performance_data["service_stats"]["hybrid_tts"] = hybrid_tts.get_performance_stats()
        except Exception as e:
            logger.warning(f"Could not get hybrid TTS stats: {e}")
        
        try:
            performance_data["service_stats"]["lyzr"] = lyzr_client.get_statistics()
        except Exception as e:
            logger.warning(f"Could not get LYZR stats: {e}")
        
        try:
            performance_data["service_stats"]["elevenlabs"] = elevenlabs_client.get_statistics()
        except Exception as e:
            logger.warning(f"Could not get ElevenLabs stats: {e}")
        
        try:
            performance_data["service_stats"]["deepgram"] = deepgram_client.get_statistics()
        except Exception as e:
            logger.warning(f"Could not get Deepgram stats: {e}")
        
        # Get average latencies from recent calls
        try:
            session_repo = await get_session_repo()
            if session_repo:
                from shared.utils.database import db_client
                if db_client is not None and db_client.database is not None:
                    pipeline = [
                        {"$match": {"session_metrics": {"$exists": True}}},
                        {"$group": {
                            "_id": None,
                            "avg_transcription_latency": {"$avg": "$session_metrics.avg_transcription_latency_ms"},
                            "avg_tts_latency": {"$avg": "$session_metrics.avg_tts_latency_ms"},
                            "avg_total_latency": {"$avg": "$session_metrics.avg_total_latency_ms"},
                            "total_calls": {"$sum": 1}
                        }}
                    ]
                    
                    async for doc in db_client.database.call_sessions.aggregate(pipeline):
                        performance_data["current_metrics"] = {
                            "avg_transcription_latency_ms": round(doc.get("avg_transcription_latency", 0)),
                            "avg_tts_latency_ms": round(doc.get("avg_tts_latency", 0)),
                            "avg_total_latency_ms": round(doc.get("avg_total_latency", 0)),
                            "calls_analyzed": doc.get("total_calls", 0)
                        }
        except Exception as e:
            logger.warning(f"Could not get performance metrics: {e}")
        
        performance_data["last_updated"] = datetime.utcnow().isoformat()
        
        return performance_data
        
    except Exception as e:
        logger.error(f"❌ Performance metrics error: {e}")
        return {
            "error": str(e),
            "last_updated": datetime.utcnow().isoformat()
        }

# ================================================================
# TESTING ENDPOINTS
# ================================================================
@router.get("/test-clients")
async def get_test_clients():
    """Get all test clients"""
    try:
        client_repo = await get_client_repo()
        if not client_repo:
            raise HTTPException(503, "Database not available")
        
        # Fix: Use proper database query
        from shared.utils.database import db_client
        if db_client is None or db_client.database is None:
            raise HTTPException(503, "Database not connected")
        
        # Query test clients directly
        cursor = db_client.database.clients.find({"is_test_client": True}).limit(100)
        
        formatted_clients = []
        async for doc in cursor:
            try:
                client = Client(**doc)
                formatted_clients.append({
                    "id": str(client.id),
                    "name": f"{client.client.first_name} {client.client.last_name}",
                    "phone": client.client.phone,
                    "email": client.client.email,
                    "status": client.campaign_status.value,
                    "total_attempts": client.total_attempts,
                    "last_outcome": client.get_latest_call_outcome() if hasattr(client, 'get_latest_call_outcome') else None,
                    "created_at": client.created_at.isoformat() if client.created_at else None,
                })
            except Exception as e:
                logger.warning(f"Error formatting client: {e}")
                continue
        
        return {"clients": formatted_clients, "total": len(formatted_clients)}
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"❌ Test clients error: {e}")
        return {"clients": [], "error": str(e)}

@router.post("/test-clients")
async def create_test_client(client_data: TestClientCreate):
    """Create a test client"""
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
            is_test_client=True,
            notes=client_data.notes
        )

        client_repo = await get_client_repo()
        if not client_repo:
            raise HTTPException(503, "Database not available")
        
        client_id = await client_repo.create_client(client)
        
        return {
            "success": True,
            "client_id": client_id,
            "message": "Test client created successfully"
        }
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"❌ Create test client error: {e}")
        raise HTTPException(500, f"Failed to create test client: {str(e)}")

@router.get("/test-agents")
async def get_test_agents():
    """Get all test agents"""
    try:
        test_agent_repo = await get_test_agent_repo()
        if not test_agent_repo:
            raise HTTPException(503, "Database not available")
        
        agents = await test_agent_repo.get_all_test_agents()
        
        formatted_agents = []
        for agent in agents:
            formatted_agents.append({
                "id": str(agent.id),
                "name": agent.name,
                "email": agent.email,
                "google_calendar_id": agent.google_calendar_id,
                "timezone": agent.timezone,
                "specialties": agent.specialties,
                "working_hours": agent.working_hours
            })
        
        return {"agents": formatted_agents, "total": len(formatted_agents)}
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"❌ Test agents error: {e}")
        return {"agents": [], "error": str(e)}

@router.post("/test-agents")
async def create_test_agent(agent_data: TestAgentCreate):
    """Create a test agent"""
    try:
        test_agent_repo = await get_test_agent_repo()
        if not test_agent_repo:
            raise HTTPException(503, "Database not available")
        
        from shared.utils.database import TestAgent
        
        agent = TestAgent(
            name=agent_data.name,
            email=agent_data.email,
            google_calendar_id=agent_data.google_calendar_id,
            timezone=agent_data.timezone,
            specialties=agent_data.specialties,
            working_hours=agent_data.working_hours
        )
        
        agent_id = await test_agent_repo.create_test_agent(agent)
        
        return {
            "success": True,
            "agent_id": agent_id,
            "message": "Test agent created successfully"
        }
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"❌ Create test agent error: {e}")
        raise HTTPException(500, f"Failed to create test agent: {str(e)}")

@router.post("/test-call")
async def initiate_test_call(call_request: TestCallRequest):
    """Initiate a test call using Twilio"""
    try:
        client_repo = await get_client_repo()
        test_agent_repo = await get_test_agent_repo()
        
        if not client_repo or not test_agent_repo:
            raise HTTPException(503, "Database not available")
        
        # Get client
        client = await client_repo.get_client_by_id(call_request.client_id)
        if not client:
            raise HTTPException(404, "Test client not found")
        
        # Get agent
        agent = await test_agent_repo.get_test_agent_by_id(call_request.agent_id)
        if not agent:
            raise HTTPException(404, "Test agent not found")
        
        # Update client with agent assignment for the test
        await client_repo.update_client(
            call_request.client_id,
            {"client.last_agent": agent.name}
        )
        
        # Import Twilio client
        from twilio.rest import Client as TwilioClient
        
        # Check Twilio configuration
        if not settings.twilio_account_sid or not settings.twilio_auth_token:
            raise HTTPException(500, "Twilio credentials not configured")
        
        if not settings.twilio_phone_number:
            raise HTTPException(500, "Twilio phone number not configured")
        
        # Create Twilio client
        twilio_client = TwilioClient(settings.twilio_account_sid, settings.twilio_auth_token)
        
        # Make the call
        try:
            logger.info(f"🔥 Making test call to {client.client.phone} from {settings.twilio_phone_number}")
            
            call = twilio_client.calls.create(
                to=client.client.phone,
                from_=settings.twilio_phone_number,
                url=f"{settings.base_url}/twilio/voice",
                status_callback=f"{settings.base_url}/twilio/status",
                status_callback_event=['initiated', 'ringing', 'answered', 'completed'],
                status_callback_method='POST'
            )
            
            logger.info(f"✅ Test call initiated: {call.sid}")
            
            # Create initial session for tracking
            from shared.models.call_session import CallSession
            session = CallSession(
                session_id=str(uuid.uuid4()),
                twilio_call_sid=call.sid,
                client_id=call_request.client_id,
                phone_number=client.client.phone,
                lyzr_agent_id=settings.lyzr_conversation_agent_id,
                lyzr_session_id=f"test_{uuid.uuid4().hex[:8]}",
                is_test_call=True,
                client_data={
                    "client_name": client.client.first_name,
                    "first_name": client.client.first_name,
                    "agent_name": agent.name,
                    "last_agent": agent.name
                }
            )
            
            # Cache session
            from shared.utils.redis_client import session_cache
            if session_cache:
                await session_cache.save_session(session)
            
            return {
                "success": True,
                "call_id": session.session_id,
                "call_sid": call.sid,
                "status": call.status,
                "client_name": f"{client.client.first_name} {client.client.last_name}",
                "client_phone": client.client.phone,
                "agent_name": agent.name,
                "message": "Test call initiated successfully!",
                "webhook_url": f"{settings.base_url}/twilio/voice"
            }
            
        except Exception as e:
            logger.error(f"❌ Twilio API error: {e}")
            raise HTTPException(500, f"Failed to initiate call: {str(e)}")
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"❌ Test call error: {e}")
        raise HTTPException(500, f"Test call failed: {str(e)}")

@router.get("/active-calls")
async def get_active_calls():
    """Get currently active calls"""
    try:
        active_calls = []
        
        # Get from Twilio router's active sessions
        try:
            from routers.twilio import active_sessions
            for call_sid, session in active_sessions.items():
                active_calls.append({
                    "call_sid": call_sid,
                    "session_id": session.session_id,
                    "client_phone": session.phone_number,
                    "client_name": session.client_data.get("client_name", "Unknown") if session.client_data else "Unknown",
                    "status": session.call_status.value if session.call_status else "in_progress",
                    "stage": session.conversation_stage.value if session.conversation_stage else "unknown",
                    "turns": len(session.conversation_turns) if session.conversation_turns else 0,
                    "started_at": session.started_at.isoformat() if session.started_at else None,
                    "duration": int((datetime.utcnow() - session.started_at).total_seconds()) if session.started_at else 0
                })
        except ImportError:
            logger.warning("Could not import active_sessions from twilio router")
        
        # Also check Redis cache for active sessions
        try:
            from shared.utils.redis_client import session_cache
            if session_cache:
                cached_active = await session_cache.get_active_sessions()
                for session_data in cached_active:
                    if not any(c["call_sid"] == session_data.get("twilio_call_sid") for c in active_calls):
                        active_calls.append({
                            "call_sid": session_data.get("twilio_call_sid", "unknown"),
                            "session_id": "cached",
                            "client_phone": session_data.get("phone_number", "unknown"),
                            "status": session_data.get("status", "unknown"),
                            "started_at": session_data.get("started_at"),
                            "source": "cache"
                        })
        except Exception as e:
            logger.warning(f"Could not get cached active sessions: {e}")
        
        return {
            "active_calls": active_calls, 
            "total_active": len(active_calls),
            "timestamp": datetime.utcnow().isoformat()
        }
        
    except Exception as e:
        logger.error(f"Active calls error: {e}")
        return {"active_calls": [], "total_active": 0, "error": str(e)}

@router.get("/call-status/{call_sid}")
async def get_call_status(call_sid: str):
    """Get real-time status of a specific call"""
    try:
        # Check active sessions first
        from routers.twilio import active_sessions
        session = active_sessions.get(call_sid)
        
        if session:
            return {
                "call_sid": call_sid,
                "session_id": session.session_id,
                "status": "active",
                "call_status": session.call_status.value if session.call_status else "in_progress",
                "client_phone": session.phone_number,
                "client_name": session.client_data.get("client_name", "Unknown") if session.client_data else "Unknown",
                "conversation_stage": session.conversation_stage.value if session.conversation_stage else "unknown",
                "turns": len(session.conversation_turns) if session.conversation_turns else 0,
                "current_turn": session.current_turn_number if hasattr(session, 'current_turn_number') else 0,
                "started_at": session.started_at.isoformat() if session.started_at else None,
                "duration": int((datetime.utcnow() - session.started_at).total_seconds()) if session.started_at else 0,
                "found_in": "active_sessions"
            }
        
        # Try Redis cache
        try:
            from shared.utils.redis_client import session_cache
            if session_cache:
                cached_session = await session_cache.get_session(call_sid)
                if cached_session:
                    return {
                        "call_sid": call_sid,
                        "session_id": cached_session.session_id,
                        "status": "cached",
                        "call_status": cached_session.call_status.value if cached_session.call_status else "unknown",
                        "client_phone": cached_session.phone_number,
                        "client_name": cached_session.client_data.get("client_name", "Unknown") if cached_session.client_data else "Unknown",
                        "conversation_stage": cached_session.conversation_stage.value if cached_session.conversation_stage else "unknown",
                        "turns": len(cached_session.conversation_turns) if cached_session.conversation_turns else 0,
                        "found_in": "redis_cache"
                    }
        except Exception as e:
            logger.warning(f"Cache lookup failed: {e}")
# Try database
        try:
            session_repo = await get_session_repo()
            if session_repo:
                from shared.utils.database import db_client
                if db_client is not None and db_client.database is not None:
                    doc = await db_client.database.call_sessions.find_one({"twilio_call_sid": call_sid})
                    if doc:
                        db_session = CallSession(**doc)
                        return {
                            "call_sid": call_sid,
                            "session_id": db_session.session_id,
                            "status": "completed",
                            "call_status": db_session.call_status.value if db_session.call_status else "completed",
                            "client_phone": db_session.phone_number,
                            "client_name": db_session.client_data.get("client_name", "Unknown") if db_session.client_data else "Unknown",
                            "conversation_stage": db_session.conversation_stage.value if db_session.conversation_stage else "completed",
                            "turns": len(db_session.conversation_turns) if db_session.conversation_turns else 0,
                            "final_outcome": db_session.final_outcome,
                            "duration": db_session.session_metrics.total_call_duration_seconds if db_session.session_metrics else 0,
                            "found_in": "database"
                        }
        except Exception as e:
            logger.warning(f"Database lookup failed: {e}")
        
        # Not found
        return {
            "call_sid": call_sid,
            "session_id": "unknown",
            "status": "not_found",
            "call_status": "not_found",
            "client_phone": "unknown",
            "client_name": "Unknown",
            "found_in": "none",
            "message": "Call session not found",
            "suggestions": [
                "Call may have completed and been cleaned up",
                "Call SID may be incorrect",
                "Session may have expired from cache"
            ]
        }
        
    except Exception as e:
        logger.error(f"❌ Call status error: {e}")
        return {
            "call_sid": call_sid,
            "status": "error",
            "error": str(e)
        }

@router.delete("/test-clients/{client_id}")
async def delete_test_client(client_id: str):
    """Delete a test client"""
    try:
        client_repo = await get_client_repo()
        if not client_repo:
            raise HTTPException(503, "Database not available")
        
        # Verify it's a test client before deleting
        client = await client_repo.get_client_by_id(client_id)
        if not client:
            raise HTTPException(404, "Client not found")
        
        if not getattr(client, 'is_test_client', False):
            raise HTTPException(403, "Can only delete test clients")
        
        success = await client_repo.delete_client(client_id)
        if not success:
            raise HTTPException(500, "Failed to delete client")
        
        return {
            "success": True,
            "message": "Test client deleted successfully"
        }
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"❌ Delete test client error: {e}")
        raise HTTPException(500, f"Failed to delete test client: {str(e)}")

@router.delete("/test-agents/{agent_id}")
async def delete_test_agent(agent_id: str):
    """Delete a test agent"""
    try:
        test_agent_repo = await get_test_agent_repo()
        if not test_agent_repo:
            raise HTTPException(503, "Database not available")
        
        # Delete from database
        from shared.utils.database import db_client
        if db_client is not None and db_client.database is not None:
            from bson import ObjectId
            result = await db_client.database.test_agents.delete_one({"_id": ObjectId(agent_id)})
            
            if result.deleted_count > 0:
                return {
                    "success": True,
                    "message": "Test agent deleted successfully"
                }
            else:
                raise HTTPException(404, "Test agent not found")
        else:
            raise HTTPException(503, "Database not connected")
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"❌ Delete test agent error: {e}")
        raise HTTPException(500, f"Failed to delete test agent: {str(e)}")

# ================================================================
# SERVICE TESTING ENDPOINTS
# ================================================================

@router.post("/test-voice-processing")
async def test_voice_processing(request: Request):
    """Test voice processing pipeline"""
    try:
        body = await request.json()
        test_text = body.get("text", "Yes, I'm interested in learning more about health insurance.")
        session_stage = body.get("stage", "greeting")
        
        # Create test session
        test_session = CallSession(
            session_id="test_session",
            twilio_call_sid="test_call",
            client_id="test_client",
            phone_number="+1234567890",
            lyzr_agent_id=settings.lyzr_conversation_agent_id,
            lyzr_session_id="test_lyzr_session",
            client_data={
                "client_name": "Test Client",
                "first_name": "Test",
                "agent_name": "Test Agent",
                "last_agent": "Test Agent"
            },
            conversation_stage=ConversationStage(session_stage)
        )
        
        # Process input
        start_time = time.time()
        result = await voice_processor.process_customer_input(
            customer_input=test_text,
            session=test_session,
            confidence=0.95
        )
        end_time = time.time()
        
        return {
            "success": result.get("success", False),
            "input_text": test_text,
            "input_stage": session_stage,
            "response_text": result.get("response_text", ""),
            "response_category": result.get("response_category", "unknown"),
            "detected_intent": result.get("detected_intent", "unknown"),
            "outcome": result.get("outcome", "unknown"),
            "end_conversation": result.get("end_conversation", False),
            "processing_time_ms": result.get("processing_time_ms", 0),
            "total_time_ms": int((end_time - start_time) * 1000),
            "services_used": {
                "voice_processor": True,
                "lyzr": result.get("lyzr_used", False),
                "pattern_matching": not result.get("lyzr_used", False)
            }
        }
        
    except Exception as e:
        logger.error(f"❌ Voice processing test error: {e}")
        return {
            "success": False,
            "error": str(e),
            "input_text": body.get("text", "") if 'body' in locals() else ""
        }

@router.post("/test-tts")
async def test_text_to_speech(request: Request):
    """Test TTS generation with hybrid service"""
    try:
        body = await request.json()
        text = body.get("text", "Hello, this is a test of our text-to-speech service.")
        response_type = body.get("response_type", "dynamic")
        client_name = body.get("client_name", "John")
        agent_name = body.get("agent_name", "Sarah")
        
        client_data = {
            "client_name": client_name,
            "first_name": client_name,
            "agent_name": agent_name,
            "last_agent": agent_name
        }
        
        # Test hybrid TTS
        start_time = time.time()
        tts_result = await hybrid_tts.get_response_audio(
            text=text,
            response_type=response_type,
            client_data=client_data
        )
        end_time = time.time()
        
        return {
            "success": tts_result.get("success", False),
            "text": text,
            "response_type": response_type,
            "audio_url": tts_result.get("audio_url"),
            "audio_type": tts_result.get("type", "unknown"),
            "is_static": tts_result.get("type") in ["static", "segmented"],
            "generation_time_ms": tts_result.get("generation_time_ms", 0),
            "total_time_ms": int((end_time - start_time) * 1000),
            "service_used": tts_result.get("type", "unknown"),
            "client_data": client_data
        }
        
    except Exception as e:
        logger.error(f"❌ TTS test error: {e}")
        return {
            "success": False,
            "error": str(e),
            "text": body.get("text", "") if 'body' in locals() else ""
        }

@router.post("/test-lyzr")
async def test_lyzr_agent(request: Request):
    """Test LYZR agent response"""
    try:
        body = await request.json()
        message = body.get("message", "I'm interested but I have questions about the coverage.")
        client_name = body.get("client_name", "Test Client")
        
        if not lyzr_client.is_configured():
            return {
                "success": False,
                "error": "LYZR not configured",
                "message": "Please configure LYZR API credentials"
            }
        
        # Start conversation
        session_id = f"test_{uuid.uuid4().hex[:8]}"
        await lyzr_client.start_conversation(client_name, "+1234567890")
        
        # Get response
        start_time = time.time()
        result = await lyzr_client.get_agent_response(
            session_id=session_id,
            customer_message=message,
            context={
                "conversation_stage": "greeting",
                "client_name": client_name
            }
        )
        end_time = time.time()
        
        # End session
        lyzr_client.end_session(session_id)
        
        return {
            "success": result.get("success", False),
            "input_message": message,
            "agent_response": result.get("response", ""),
            "session_ended": result.get("session_ended", False),
            "latency_ms": result.get("latency_ms", 0),
            "total_time_ms": int((end_time - start_time) * 1000),
            "turn_count": result.get("turn_count", 1)
        }
        
    except Exception as e:
        logger.error(f"❌ LYZR test error: {e}")
        return {
            "success": False,
            "error": str(e)
        }

@router.get("/test-services")
async def test_all_services():
    """Test all service connectivity and configuration"""
    try:
        services_test = {
            "overall_status": "checking",
            "services": {},
            "timestamp": datetime.utcnow().isoformat()
        }
        
        # Test Voice Processor
        services_test["services"]["voice_processor"] = {
            "configured": voice_processor.is_configured(),
            "status": "ready" if voice_processor.is_configured() else "not_configured"
        }
        
        # Test Hybrid TTS
        try:
            tts_configured = await hybrid_tts.is_configured()
            tts_stats = hybrid_tts.get_performance_stats()
            services_test["services"]["hybrid_tts"] = {
                "configured": tts_configured,
                "status": "ready" if tts_configured else "not_configured",
                "stats": tts_stats
            }
        except Exception as e:
            services_test["services"]["hybrid_tts"] = {
                "configured": False,
                "status": "error",
                "error": str(e)
            }
        
        # Test LYZR
        try:
            lyzr_configured = lyzr_client.is_configured()
            if lyzr_configured:
                lyzr_test = await lyzr_client.test_connection()
                services_test["services"]["lyzr"] = {
                    "configured": True,
                    "status": "ready" if lyzr_test.get("success") else "failed",
                    "conversation_agent": settings.lyzr_conversation_agent_id,
                    "summary_agent": settings.lyzr_summary_agent_id,
                    "test_latency_ms": lyzr_test.get("latency_ms", 0)
                }
            else:
                services_test["services"]["lyzr"] = {
                    "configured": False,
                    "status": "not_configured"
                }
        except Exception as e:
            services_test["services"]["lyzr"] = {
                "configured": False,
                "status": "error",
                "error": str(e)
            }
        
        # Test ElevenLabs
        try:
            elevenlabs_configured = elevenlabs_client.is_configured()
            if elevenlabs_configured:
                elevenlabs_test = await elevenlabs_client.test_connection()
                services_test["services"]["elevenlabs"] = {
                    "configured": True,
                    "status": "ready" if elevenlabs_test.get("success") else "failed",
                    "test_latency_ms": elevenlabs_test.get("latency_ms", 0),
                    "default_voice": settings.default_voice_id
                }
            else:
                services_test["services"]["elevenlabs"] = {
                    "configured": False,
                    "status": "not_configured"
                }
        except Exception as e:
            services_test["services"]["elevenlabs"] = {
                "configured": False,
                "status": "error",
                "error": str(e)
            }
        
        # Test Deepgram
        try:
            deepgram_configured = deepgram_client.is_configured()
            if deepgram_configured:
                deepgram_test = await deepgram_client.test_connection()
                services_test["services"]["deepgram"] = {
                    "configured": True,
                    "status": "ready" if deepgram_test.get("success") else "failed",
                    "test_latency_ms": deepgram_test.get("latency_ms", 0),
                    "model": settings.stt_model
                }
            else:
                services_test["services"]["deepgram"] = {
                    "configured": False,
                    "status": "not_configured"
                }
        except Exception as e:
            services_test["services"]["deepgram"] = {
                "configured": False,
                "status": "error",
                "error": str(e)
            }
        
        # Test Database
        try:
            client_repo = await get_client_repo()
            services_test["services"]["database"] = {
                "connected": client_repo is not None,
                "status": "ready" if client_repo else "disconnected"
            }
        except Exception as e:
            services_test["services"]["database"] = {
                "connected": False,
                "status": "error",
                "error": str(e)
            }
        
        # Test Redis
        try:
            from shared.utils.redis_client import redis_client
            redis_connected = redis_client.is_connected() if redis_client else False
            services_test["services"]["redis"] = {
                "connected": redis_connected,
                "status": "ready" if redis_connected else "disconnected"
            }
        except Exception as e:
            services_test["services"]["redis"] = {
                "connected": False,
                "status": "error",
                "error": str(e)
            }
        
        # Test Twilio
        services_test["services"]["twilio"] = {
            "configured": bool(settings.twilio_account_sid and settings.twilio_auth_token),
            "phone_number": settings.twilio_phone_number if settings.twilio_phone_number else "Not configured",
            "status": "ready" if settings.twilio_account_sid and settings.twilio_auth_token else "not_configured"
        }
        
        # Determine overall status
        critical_services = [
            services_test["services"]["voice_processor"]["status"] == "ready",
            services_test["services"]["hybrid_tts"]["status"] == "ready",
            services_test["services"]["database"]["status"] == "ready",
            services_test["services"]["twilio"]["status"] == "ready"
        ]
        
        if all(critical_services):
            services_test["overall_status"] = "all_systems_operational"
        elif any(critical_services):
            services_test["overall_status"] = "partial_functionality"
        else:
            services_test["overall_status"] = "critical_services_down"
        
        return services_test
        
    except Exception as e:
        logger.error(f"❌ Service test error: {e}")
        return {
            "overall_status": "error",
            "error": str(e),
            "timestamp": datetime.utcnow().isoformat()
        }

@router.get("/system-health")
async def get_system_health():
    """Get comprehensive system health status"""
    try:
        health_data = {
            "status": "checking",
            "timestamp": datetime.utcnow().isoformat(),
            "components": {},
            "metrics": {},
            "alerts": []
        }
        
        # Check all components
        service_test = await test_all_services()
        health_data["components"] = service_test["services"]
        
        # Get performance metrics
        try:
            perf_metrics = await get_performance_metrics()
            health_data["metrics"] = perf_metrics.get("current_metrics", {})
        except Exception as e:
            logger.warning(f"Could not get performance metrics: {e}")
        
        # Get campaign stats
        try:
            campaign_stats = await get_campaign_stats()
            health_data["campaign"] = {
                "total_clients": campaign_stats.get("total_clients", 0),
                "completed_calls": campaign_stats.get("completed_calls", 0),
                "completion_rate": campaign_stats.get("completion_rate", 0)
            }
        except Exception as e:
            logger.warning(f"Could not get campaign stats: {e}")
        
        # Check for alerts
        alerts = []
        
        # Check service status
        for service, status in health_data["components"].items():
            if status.get("status") not in ["ready", "operational"]:
                alerts.append({
                    "level": "warning" if service in ["lyzr", "redis"] else "critical",
                    "service": service,
                    "message": f"{service} is not operational: {status.get('status')}"
                })
        
        # Check performance
        if health_data.get("metrics", {}).get("avg_total_latency_ms", 0) > 2500:
            alerts.append({
                "level": "warning",
                "service": "performance",
                "message": "Average response latency exceeds target (>2500ms)"
            })
        
        health_data["alerts"] = alerts
        
        # Determine overall health
        if not alerts:
            health_data["status"] = "healthy"
        elif any(alert["level"] == "critical" for alert in alerts):
            health_data["status"] = "unhealthy"
        else:
            health_data["status"] = "degraded"
        
        return health_data
        
    except Exception as e:
        logger.error(f"❌ System health check error: {e}")
        return {
            "status": "error",
            "error": str(e),
            "timestamp": datetime.utcnow().isoformat()
        }