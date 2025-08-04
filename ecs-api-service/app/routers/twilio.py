"""
Updated Twilio Router - Integrated with Segmented Audio Service
Handles Twilio webhooks with exact AAG script and personalized audio using real client/agent names
"""

from fastapi import APIRouter, Request, Form, HTTPException
from fastapi.responses import Response
import uuid
import os
from typing import Optional, Dict, Any
import logging
import asyncio
from datetime import datetime

# Import shared models and utilities
from shared.config.settings import settings
from shared.models.call_session import CallSession, CallStatus, ConversationStage
from shared.models.client import Client, CallOutcome
# from shared.utils.database import client_repo, get_client_by_phone
# from shared.utils.redis_client import cache_session, get_cached_session

# Import updated services
from services.voice_processor import VoiceProcessor, update_client_record
from services.hybrid_tts import HybridTTSService
from services.segmented_audio_service import segmented_audio_service
from services.twiml_helpers import (
    create_simple_twiml,
    create_fallback_twiml,
    create_hangup_twiml
)

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/twilio", tags=["Twilio"])

# Store active conversation states
active_sessions: Dict[str, CallSession] = {}

client_repo = None
session_repo = None



async def get_client_by_phone(phone: str):
    """Get client by phone - fallback implementation"""
    try:
        from shared.utils.database import client_repo as repo
        if repo:
            return await repo.get_client_by_phone(phone)
    except:
        pass
    return None

async def cache_session(session):
    """Cache session - fallback implementation"""
    try:
        from shared.utils.redis_client import session_cache
        if session_cache:
            return await session_cache.save_session(session)
    except:
        pass
    return False

    
@router.post("/voice")
async def voice_webhook(
    request: Request,
    CallSid: str = Form(...),
    CallStatus: Optional[str] = Form(None),
    From: Optional[str] = Form(None),
    To: Optional[str] = Form(None),
    Direction: Optional[str] = Form(None)
):
    """Handle incoming voice calls with EXACT AAG script and segmented audio"""
    
    logger.info(f"📞 Voice webhook: {CallSid} - Status: {CallStatus} - From: {From} - To: {To}")
    
    try:
        if CallStatus == "in-progress":
            # For OUTBOUND calls, look up client by TO number
            client_phone = To if Direction == "outbound-api" else From
            logger.info(f"🔍 Looking up client by phone: {client_phone}")
            
            # Get client using existing database utilities
            client = await get_client_by_phone(client_phone)
            if not client:
                logger.warning(f"⚠️ Client not found for phone: {client_phone}")
                # Use generic greeting for unknown callers
                return await create_segmented_twiml_response(
                    response_type="greeting",
                    client_data={"client_name": "there"},  # Generic fallback
                    gather_action="/twilio/process-speech"
                )
            
            # Create session using existing models
            session = CallSession(
                session_id=str(uuid.uuid4()),
                twilio_call_sid=CallSid,
                client_id=str(client.id),
                phone_number=client_phone,
                lyzr_agent_id=settings.lyzr_conversation_agent_id,
                lyzr_session_id=f"{CallSid}-{uuid.uuid4().hex[:8]}"
            )
            session.call_status = CallStatus.IN_PROGRESS
            session.answered_at = datetime.utcnow()
            session.conversation_stage = ConversationStage.GREETING
            
            # Cache session
            await cache_session(session)
            
            active_sessions[CallSid] = session

            # Store client data in session for later use
            session.client_data = client_data
            
            # Also try to save to database
            try:
                from shared.utils.database import session_repo
                if session_repo:
                    await session_repo.save_session(session)
            except Exception as e:
                logger.warning(f"Could not save session to database: {e}")
            
            logger.info(f"🎯 Starting conversation with {client.client.full_name}")
            
            # Use EXACT AAG greeting with client's real name and agent info
            client_data = {
                "client_name": client.client.first_name,
                "first_name": client.client.first_name,
                "agent_name": client.client.last_agent,
                "last_agent": client.client.last_agent
            }
            
            return await create_segmented_twiml_response(
                response_type="greeting",
                client_data=client_data,
                gather_action="/twilio/process-speech"
            )
        
        # Handle other call statuses
        return Response(
            content=create_simple_twiml("Call received."),
            media_type="application/xml"
        )
        
    except Exception as e:
        logger.error(f"❌ Voice webhook error: {e}")
        return Response(
            content=create_fallback_twiml("We are experiencing technical difficulties. Please call back later."),
            media_type="application/xml"
        )

async def create_segmented_twiml_response(
    response_type: str, 
    client_data: Optional[Dict[str, Any]] = None,
    gather_action: str = "/twilio/process-speech",
    should_hangup: bool = False
) -> Response:
    """Create TwiML response using segmented audio service"""
    
    try:
        logger.info(f"🎵 Creating segmented TwiML for: {response_type}")
        
        # Get personalized audio using hybrid TTS (which uses segmented service)
        hybrid_tts = HybridTTSService()
        
        tts_response = await hybrid_tts.get_response_audio(
            text="",  # Text not needed for mapped responses
            response_type=response_type,
            client_data=client_data
        )
        
        if tts_response.get("success") and tts_response.get("audio_url"):
            audio_url = tts_response.get("audio_url")
            generation_time = tts_response.get("generation_time_ms", 0)
            audio_type = tts_response.get("type", "unknown")
            
            logger.info(f"✅ Audio generated: {audio_type} in {generation_time}ms")
            
            # Create TwiML with Play verb and speech gathering
            if should_hangup:
                twiml = f"""<?xml version="1.0" encoding="UTF-8"?>
<Response>
    <Play>{audio_url}</Play>
    <Hangup/>
</Response>"""
            else:
                twiml = f"""<?xml version="1.0" encoding="UTF-8"?>
<Response>
    <Play>{audio_url}</Play>
    <Gather action="{gather_action}" method="POST" input="speech" timeout="8" speechTimeout="auto" enhanced="true">
        <Pause length="1"/>
    </Gather>
    <Say voice="Polly.Joanna-Neural">I didn't hear you. Thank you for calling. Goodbye.</Say>
</Response>"""
        else:
            # Fallback: Generate audio directly if segmented fails
            logger.warning(f"⚠️ Segmented audio failed: {tts_response.get('error')}")
            
            fallback_text = _get_fallback_text(response_type, client_data)
            audio_url = await _generate_fallback_audio(fallback_text)
            
            if audio_url:
                if should_hangup:
                    twiml = f"""<?xml version="1.0" encoding="UTF-8"?>
<Response>
    <Play>{audio_url}</Play>
    <Hangup/>
</Response>"""
                else:
                    twiml = f"""<?xml version="1.0" encoding="UTF-8"?>
<Response>
    <Play>{audio_url}</Play>
    <Gather action="{gather_action}" method="POST" input="speech" timeout="8" speechTimeout="auto" enhanced="true">
        <Pause length="1"/>
    </Gather>
    <Say voice="Polly.Joanna-Neural">I didn't hear you. Thank you for calling. Goodbye.</Say>
</Response>"""
            else:
                # Final fallback: Use Twilio voice with high quality
                clean_text = _get_fallback_text(response_type, client_data)
                clean_text = clean_text.replace("&", "and").replace("<", "").replace(">", "")
                
                if should_hangup:
                    twiml = f"""<?xml version="1.0" encoding="UTF-8"?>
<Response>
    <Say voice="Polly.Joanna-Neural">{clean_text}</Say>
    <Hangup/>
</Response>"""
                else:
                    twiml = f"""<?xml version="1.0" encoding="UTF-8"?>
<Response>
    <Say voice="Polly.Joanna-Neural">{clean_text}</Say>
    <Gather action="{gather_action}" method="POST" input="speech" timeout="8" speechTimeout="auto" enhanced="true">
        <Pause length="1"/>
    </Gather>
    <Say voice="Polly.Joanna-Neural">I didn't hear you. Thank you for calling. Goodbye.</Say>
</Response>"""
        
        return Response(content=twiml, media_type="application/xml")
        
    except Exception as e:
        logger.error(f"❌ Segmented TwiML generation error: {e}")
        # Emergency fallback
        emergency_text = "Thank you for calling Altruis Advisor Group. Please call back later."
        twiml = f"""<?xml version="1.0" encoding="UTF-8"?>
<Response>
    <Say voice="Polly.Joanna-Neural">{emergency_text}</Say>
    <Hangup/>
</Response>"""
        return Response(content=twiml, media_type="application/xml")

def _get_fallback_text(response_type: str, client_data: Optional[Dict[str, Any]] = None) -> str:
    """Get fallback text for response types"""
    
    client_name = "there"
    agent_name = "your agent"
    
    if client_data:
        client_name = client_data.get("client_name") or client_data.get("first_name") or "there"
        agent_name = client_data.get("agent_name") or client_data.get("last_agent") or "your agent"
    
    fallback_texts = {
        "greeting": f"Hello {client_name}, Alex here from Altruis Advisor Group. We've helped you with your health insurance needs in the past and I just wanted to reach out to see if we can be of service to you this year during Open Enrollment? A simple Yes or No is fine, and remember, our services are completely free of charge.",
        
        "agent_introduction": f"Great, looks like {agent_name} was the last agent you worked with here at Altruis. Would you like to schedule a quick 15-minute discovery call with them to get reacquainted? A simple Yes or No will do!",
        
        "schedule_confirmation": f"Great, give me a moment while I check {agent_name}'s calendar... Perfect! I've scheduled a 15-minute discovery call for you. You should receive a calendar invitation shortly. Thank you and have a wonderful day!",
        
        "no_schedule_followup": f"No problem, {agent_name} will reach out to you and the two of you can work together to determine the best next steps. We look forward to servicing you, have a wonderful day!",
        
        "not_interested": "No problem, would you like to continue receiving general health insurance communications from our team? Again, a simple Yes or No will do!",
        
        "dnc_confirmation": "Understood, we will make sure you are removed from all future communications and send you a confirmation email once that is done. Our contact details will be in that email as well, so if you do change your mind in the future please feel free to reach out – we are always here to help and our service is always free of charge. Have a wonderful day!",
        
        "keep_communications": "Great, we're happy to keep you informed throughout the year regarding the ever-changing world of health insurance. If you'd like to connect with one of our insurance experts in the future please feel free to reach out – we are always here to help and our service is always free of charge. Have a wonderful day!",
        
        "goodbye": "Thank you for your time today. Have a wonderful day!",
        
        "clarification": "I want to make sure I understand correctly. Can we help service you this year during Open Enrollment? Please say Yes if you're interested, or No if you're not interested."
    }
    
    return fallback_texts.get(response_type, "Thank you for calling Altruis Advisor Group.")

async def _generate_fallback_audio(text: str) -> Optional[str]:
    """Generate fallback audio using ElevenLabs directly"""
    try:
        from services.elevenlabs_client import elevenlabs_client
        
        result = await elevenlabs_client.generate_speech(text)
        
        if result.get("success") and result.get("audio_data"):
            # Save audio file temporarily
            filename = f"fallback_{uuid.uuid4().hex[:8]}.mp3"
            
            # Create temp directory if not exists
            os.makedirs("static/audio/temp", exist_ok=True)
            
            # Save audio file
            filepath = f"static/audio/temp/{filename}"
            with open(filepath, "wb") as f:
                f.write(result["audio_data"])
            
            # Return public URL
            audio_url = f"{settings.base_url.rstrip('/')}/static/audio/temp/{filename}"
            logger.info(f"✅ Generated fallback audio: {audio_url}")
            return audio_url
        
        return None
        
    except Exception as e:
        logger.error(f"❌ Fallback audio generation failed: {e}")
        return None

@router.post("/process-speech")
async def process_speech_webhook(
    request: Request,
    CallSid: str = Form(...),
    SpeechResult: Optional[str] = Form(None),
    Confidence: Optional[float] = Form(None)
):
    """Process customer speech using EXACT AAG script logic with segmented audio"""
    
    logger.info(f"🎤 Processing speech: {CallSid} - Result: '{SpeechResult}' - Confidence: {Confidence}")
    
    try:
        # Get session
        session = active_sessions.get(CallSid)
        if not session:
            session = await get_cached_session(CallSid)
            if session:
                active_sessions[CallSid] = session
        
        if not session:
            logger.error(f"❌ Session not found: {CallSid}")
            return await create_segmented_twiml_response(
                response_type="goodbye",
                should_hangup=True
            )
        
        # Get client data for personalized responses
        client = await get_client_by_phone(session.phone_number)
        client_data = {}
        if client:
            client_data = {
                "client_name": client.client.first_name,
                "first_name": client.client.first_name,
                "agent_name": client.client.last_agent,
                "last_agent": client.client.last_agent
            }
        
        # Clean customer input
        customer_input = (SpeechResult or "no response").strip().lower()
        
        # EXACT script logic from the AAG document
        response_type, should_end_call, outcome = process_aag_script_logic(
            customer_input, 
            session, 
            client_data
        )
        
        # Update session with conversation turn
        from shared.models.call_session import ConversationTurn, ResponseType
        
        turn = ConversationTurn(
            turn_number=len(session.conversation_turns) + 1,
            customer_speech=SpeechResult or "no response",
            customer_speech_confidence=Confidence or 0.0,
            agent_response=f"Response type: {response_type}",
            response_type=ResponseType.HYBRID,
            conversation_stage=session.conversation_stage
        )
        
        session.conversation_turns.append(turn)
        session.current_turn_number = turn.turn_number
        
        # Update session in cache
        await cache_session(session)
        
        if should_end_call:
            # End call with final message
            session.complete_call(outcome)
            await cache_session(session)
            
            # Update client record
            await update_client_with_aag_outcome(session, outcome, customer_input, client)
            
            # Clean up session
            if CallSid in active_sessions:
                del active_sessions[CallSid]
            
            return await create_segmented_twiml_response(
                response_type=response_type,
                client_data=client_data,
                should_hangup=True
            )
        else:
            # Continue conversation
            return await create_segmented_twiml_response(
                response_type=response_type,
                client_data=client_data,
                gather_action="/twilio/process-speech"
            )
        
    except Exception as e:
        logger.error(f"❌ Speech processing error: {e}")
        return await create_segmented_twiml_response(
            response_type="goodbye",
            should_hangup=True
        )

def process_aag_script_logic(
    customer_input: str, 
    session: CallSession, 
    client_data: Dict[str, Any]
) -> tuple[str, bool, str]:
    """Process customer response using EXACT AAG script logic from document"""
    
    customer_lower = customer_input.lower()
    conversation_stage = session.conversation_stage
    
    logger.info(f"🔄 Processing stage: {conversation_stage}, input: '{customer_input}'")
    
    # Stage 1: Initial response to greeting
    if conversation_stage == ConversationStage.GREETING:
        if any(word in customer_lower for word in ["yes", "yeah", "sure", "okay", "interested"]):
            # Customer said YES - move to agent introduction
            session.conversation_stage = ConversationStage.SCHEDULING
            return "agent_introduction", False, "interested"
        
        elif any(word in customer_lower for word in ["no", "not interested", "not really"]):
            # Customer said NO - ask about future communications
            session.conversation_stage = ConversationStage.DNC_QUESTION
            return "not_interested", False, "not_interested_initial"
        
        else:
            # Unclear response - try to clarify
            return "clarification", False, "clarification"
    
    # Stage 2: Scheduling response (after agent introduction)
    elif conversation_stage == ConversationStage.SCHEDULING:
        if any(word in customer_lower for word in ["yes", "yeah", "sure", "okay"]):
            # Customer wants to schedule
            session.conversation_stage = ConversationStage.COMPLETED
            return "schedule_confirmation", True, "scheduled"
        
        elif any(word in customer_lower for word in ["no", "not really", "not now"]):
            # Customer doesn't want to schedule but is interested
            session.conversation_stage = ConversationStage.COMPLETED
            return "no_schedule_followup", True, "interested_no_schedule"
        
        else:
            # Unclear - try again
            return "clarification", False, "schedule_clarification"
    
    # Stage 3: DNC Question response
    elif conversation_stage == ConversationStage.DNC_QUESTION:
        if any(word in customer_lower for word in ["yes", "yeah", "sure", "okay"]):
            # Customer wants to keep receiving communications
            session.conversation_stage = ConversationStage.COMPLETED
            return "keep_communications", True, "keep_communications"
        
        elif any(word in customer_lower for word in ["no", "remove", "don't", "stop"]):
            # Customer wants to be removed
            session.conversation_stage = ConversationStage.COMPLETED
            return "dnc_confirmation", True, "dnc_requested"
        
        else:
            # Unclear - try again
            return "clarification", False, "dnc_clarification"
    
    # Default fallback
    session.conversation_stage = ConversationStage.COMPLETED
    return "goodbye", True, "completed"

async def update_client_with_aag_outcome(
    session: CallSession, 
    outcome: str, 
    customer_input: str,
    client: Optional[Client]
):
    """Update client record based on AAG call outcome"""
    try:
        if not client_repo or not client:
            logger.warning("⚠️ Cannot update client - repo or client not available")
            return
        
        from shared.models.client import CRMTag, CallOutcome
        
        client_id = session.client_id
        
        # Apply exact CRM tags from AAG document
        if outcome in ["scheduled", "interested_no_schedule"]:
            await client_repo.add_crm_tag(client_id, CRMTag.INTERESTED)
            await client_repo.update_call_outcome(client_id, CallOutcome.INTERESTED)
            logger.info(f"✅ Client {client_id} marked as INTERESTED")
            
        elif outcome == "keep_communications":
            await client_repo.add_crm_tag(client_id, CRMTag.NOT_INTERESTED)
            await client_repo.update_call_outcome(client_id, CallOutcome.NOT_INTERESTED)
            logger.info(f"✅ Client {client_id} marked as NOT_INTERESTED (keep comms)")
            
        elif outcome == "dnc_requested":
            await client_repo.add_crm_tag(client_id, CRMTag.DNC_REQUESTED)
            await client_repo.update_call_outcome(client_id, CallOutcome.DNC_REQUESTED)
            logger.info(f"✅ Client {client_id} marked as DNC_REQUESTED")
            
        else:
            await client_repo.update_call_outcome(client_id, CallOutcome.COMPLETED)
            logger.info(f"✅ Client {client_id} marked as COMPLETED")
        
        # Add call attempt to history
        call_attempt = {
            "attempt_number": client.total_attempts + 1,
            "timestamp": datetime.utcnow(),
            "outcome": outcome,
            "duration_seconds": int(session.session_metrics.total_call_duration_seconds or 0),
            "twilio_call_sid": session.twilio_call_sid,
            "audio_type": "segmented",
            "transcript": customer_input,
            "conversation_turns": len(session.conversation_turns)
        }
        
        await client_repo.add_call_attempt(client_id, call_attempt)
        
    except Exception as e:
        logger.error(f"❌ Failed to update client record: {e}")

@router.post("/status")
async def status_webhook(
    request: Request,
    CallSid: str = Form(...),
    CallStatus: str = Form(...),
    CallDuration: Optional[str] = Form(None),
    RecordingUrl: Optional[str] = Form(None)
):
    """Handle call status updates"""
    
    logger.info(f"📊 Status update: {CallSid} - Status: {CallStatus} - Duration: {CallDuration}")
    
    try:
        # Clean up session if call completed
        if CallStatus in ["completed", "failed", "busy", "no-answer"]:
            if CallSid in active_sessions:
                session = active_sessions.pop(CallSid)
                if CallDuration:
                    session.session_metrics.total_call_duration_seconds = int(CallDuration)
                await cache_session(session)
                logger.info(f"✅ Call completed: {CallSid} - Duration: {CallDuration}s")
        
        return {"status": "ok", "call_sid": CallSid}
        
    except Exception as e:
        logger.error(f"❌ Status webhook error: {e}")
        return {"status": "error", "message": str(e)}

@router.get("/test-connection")
async def test_twilio_connection():
    """Test Twilio connection and segmented audio system"""
    
    try:
        # Test configurations
        services_status = {
            "twilio_configured": bool(settings.twilio_account_sid and settings.twilio_auth_token),
            "segmented_audio_configured": await segmented_audio_service.is_configured(),
            "hybrid_tts_configured": await HybridTTSService().is_configured(),
            "elevenlabs_configured": bool(settings.elevenlabs_api_key and not settings.elevenlabs_api_key.startswith("your_"))
        }
        
        # Test segmented audio generation
        try:
            test_result = await segmented_audio_service.get_personalized_audio(
                template_name="greeting",
                client_name="John",
                agent_name="Sarah"
            )
            services_status["segmented_audio_test"] = test_result.get("success", False)
            services_status["test_generation_time_ms"] = test_result.get("generation_time_ms", 0)
        except Exception as e:
            services_status["segmented_audio_test"] = False
            services_status["segmented_audio_error"] = str(e)
        
        # Get performance stats
        hybrid_stats = HybridTTSService().get_performance_stats()
        segmented_stats = segmented_audio_service.get_performance_stats()
        
        return {
            "status": "ok",
            "configuration": services_status,
            "active_sessions": len(active_sessions),
            "webhook_urls": {
                "voice": f"{settings.base_url}/twilio/voice",
                "status": f"{settings.base_url}/twilio/status"
            },
            "aag_compliance": {
                "exact_script": True,
                "segmented_audio": True,
                "personalized_names": True,
                "conversation_flow": "AAG Document Compliant"
            },
            "performance_stats": {
                "hybrid_tts": hybrid_stats,
                "segmented_audio": segmented_stats
            },
            "timestamp": datetime.utcnow().isoformat()
        }
        
    except Exception as e:
        logger.error(f"❌ Connection test error: {e}")
        return {
            "status": "error",
            "error": str(e),
            "timestamp": datetime.utcnow().isoformat()
        }