"""
Twilio Router - Updated to Use Existing Services
Handles Twilio webhooks using optimized existing services
"""

from fastapi import APIRouter, Request, Form, WebSocket, WebSocketDisconnect
from fastapi.responses import Response
from typing import Optional, Dict, Any
import logging
import json
import uuid
from datetime import datetime

# Import shared models and utilities
from shared.config.settings import settings
from shared.models.call_session import CallSession, CallStatus, ConversationStage
from shared.models.client import Client, CallOutcome
from shared.utils.database import client_repo, get_client_by_phone
from shared.utils.redis_client import cache_session, get_cached_session

# Import existing optimized services
from ..services.voice_processor import VoiceProcessor, update_client_record
from ..services.hybrid_tts import HybridTTSService
from ..services.lyzr_client import get_lyzr_client
from ..services.elevenlabs_client import get_elevenlabs_client
from ..services.deepgram_client import get_deepgram_client
from ..services.twiml_helpers import (
    create_simple_twiml,
    create_voice_twiml,
    create_fallback_twiml,
    create_media_stream_twiml,
    create_hangup_twiml
)

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/twilio", tags=["Twilio"])

# Initialize services using existing optimized implementations
voice_processor = VoiceProcessor()
hybrid_tts = HybridTTSService()

# Store active conversation states (using existing pattern)
active_sessions: Dict[str, CallSession] = {}

@router.post("/voice")
async def voice_webhook(
    request: Request,
    CallSid: str = Form(...),
    CallStatus: Optional[str] = Form(None),
    From: Optional[str] = Form(None),
    To: Optional[str] = Form(None),
    Direction: Optional[str] = Form(None)
):
    """Handle incoming voice calls using existing voice processor"""
    
    logger.info(f"📞 Voice webhook: {CallSid} - Status: {CallStatus} - From: {From}")
    
    try:
        if CallStatus == "in-progress":
            # Get client using existing database utilities
            client = await get_client_by_phone(From)
            if not client:
                logger.warning(f"⚠️ Client not found for phone: {From}")
                return Response(
                    content=create_simple_twiml("Thank you for calling. Goodbye."),
                    media_type="application/xml"
                )
            
            # Create session using existing models
            session = CallSession(
                session_id=str(uuid.uuid4()),
                twilio_call_sid=CallSid,
                client_id=str(client.id),
                phone_number=From,
                lyzr_agent_id=settings.lyzr_conversation_agent_id,
                lyzr_session_id=f"{CallSid}-{uuid.uuid4().hex[:8]}"
            )
            session.call_status = CallStatus.IN_PROGRESS
            session.answered_at = datetime.utcnow()
            
            # Cache session using existing utilities
            await cache_session(session)
            active_sessions[CallSid] = session
            
            logger.info(f"🎯 Starting conversation with {client.client.full_name}")
            
            # Generate greeting using existing hybrid TTS
            greeting_text = f"Hello {client.client.first_name}, this is Alex from Altrius Advisor Group. It's been some time since you've been in touch with us. We'd love to improve our service for you during Open Enrollment. Can we help service you this year?"
            
            # Use existing TTS service for optimized greeting
            tts_response = await hybrid_tts.get_response_audio(
                text=greeting_text,
                response_type="greeting",
                context={"client_name": client.client.first_name}
            )
            
            if tts_response.get("success"):
                # Create TwiML with optimized audio
                return Response(
                    content=create_voice_twiml(
                        greeting_text,
                        gather_action="/twilio/process-speech",
                        audio_url=tts_response.get("audio_url")
                    ),
                    media_type="application/xml"
                )
            else:
                # Fallback to basic TwiML
                return Response(
                    content=create_voice_twiml(greeting_text, "/twilio/process-speech"),
                    media_type="application/xml"
                )
        
        # Handle other call statuses
        return Response(
            content=create_simple_twiml("Call received."),
            media_type="application/xml"
        )
        
    except Exception as e:
        logger.error(f"❌ Voice webhook error: {e}")
        return Response(
            content=create_fallback_twiml("We are experiencing technical difficulties."),
            media_type="application/xml"
        )

@router.post("/process-speech")
async def process_speech_webhook(
    request: Request,
    CallSid: str = Form(...),
    SpeechResult: Optional[str] = Form(None),
    Confidence: Optional[float] = Form(None)
):
    """Process customer speech using existing voice processor"""
    
    logger.info(f"🎤 Processing speech: {CallSid} - Result: {SpeechResult} - Confidence: {Confidence}")
    
    try:
        # Get session
        session = active_sessions.get(CallSid)
        if not session:
            # Try to get from cache
            session = await get_cached_session(CallSid)
            if session:
                active_sessions[CallSid] = session
        
        if not session:
            logger.error(f"❌ Session not found: {CallSid}")
            return Response(
                content=create_simple_twiml("Session expired. Please call back."),
                media_type="application/xml"
            )
        
        # Process speech using existing voice processor
        customer_input = SpeechResult or "no response"
        
        # Use existing voice processor for AI response
        ai_response = await voice_processor.process_customer_input(
            customer_input=customer_input,
            session=session,
            confidence=Confidence or 0.0
        )
        
        if not ai_response.get("success"):
            logger.error(f"❌ Voice processing failed: {ai_response.get('error')}")
            return Response(
                content=create_simple_twiml("Thank you for your time. Have a great day!"),
                media_type="application/xml"
            )
        
        response_text = ai_response.get("response_text", "Thank you for your call.")
        call_outcome = ai_response.get("outcome", "unknown")
        
        # Update session with conversation turn
        session.add_conversation_turn(
            customer_input=customer_input,
            agent_response=response_text,
            confidence=Confidence or 0.0
        )
        
        # Use hybrid TTS for optimized response
        response_type = "interested" if call_outcome == "interested" else "general"
        tts_response = await hybrid_tts.get_response_audio(
            text=response_text,
            response_type=response_type,
            context={"outcome": call_outcome}
        )
        
        # Determine if call should end
        should_end_call = call_outcome in ["interested", "not_interested", "dnc_requested"]
        
        if should_end_call:
            # End call with final message
            session.complete_call(call_outcome)
            await cache_session(session)
            
            # Update client record using existing utilities
            await update_client_record(session, call_outcome)
            
            # Clean up session
            if CallSid in active_sessions:
                del active_sessions[CallSid]
            
            return Response(
                content=create_hangup_twiml(response_text, tts_response.get("audio_url")),
                media_type="application/xml"
            )
        else:
            # Continue conversation
            await cache_session(session)
            
            return Response(
                content=create_voice_twiml(
                    response_text,
                    "/twilio/process-speech",
                    tts_response.get("audio_url")
                ),
                media_type="application/xml"
            )
        
    except Exception as e:
        logger.error(f"❌ Speech processing error: {e}")
        return Response(
            content=create_simple_twiml("Thank you for your call. Our team will contact you soon."),
            media_type="application/xml"
        )

@router.post("/status")
async def status_webhook(
    request: Request,
    CallSid: str = Form(...),
    CallStatus: str = Form(...),
    CallDuration: Optional[str] = Form(None),
    RecordingUrl: Optional[str] = Form(None)
):
    """Handle call status updates using existing session management"""
    
    logger.info(f"📊 Status update: {CallSid} - Status: {CallStatus} - Duration: {CallDuration}")
    
    try:
        # Get session from cache or active sessions
        session = active_sessions.get(CallSid)
        if not session:
            session = await get_cached_session(CallSid)
        
        if session and CallStatus in ["completed", "failed", "busy", "no-answer"]:
            # Update session with final status
            if not session.completed_at:  # Only update if not already completed
                session.call_status = CallStatus(CallStatus.lower().replace("-", "_"))
                session.complete_call(CallStatus)
                
                if CallDuration:
                    session.session_metrics.total_call_duration_seconds = int(CallDuration)
                
                if RecordingUrl:
                    session.recording_url = RecordingUrl
                
                # Save final session state
                await cache_session(session)
                
                # Generate call summary using existing services
                if session.conversation_history:
                    try:
                        # Use existing LYZR client for summary
                        lyzr_client = await get_lyzr_client()
                        summary = await lyzr_client.generate_call_summary(
                            session.get_conversation_transcript(),
                            session.get_context_for_summary()
                        )
                        
                        if summary.get("success"):
                            logger.info(f"✅ Call summary generated: {CallSid}")
                        
                    except Exception as e:
                        logger.error(f"❌ Summary generation failed: {e}")
                
                # Clean up active session
                if CallSid in active_sessions:
                    del active_sessions[CallSid]
                
                logger.info(f"✅ Call completed: {CallSid} - Duration: {CallDuration}s")
        
        return {"status": "ok", "call_sid": CallSid}
        
    except Exception as e:
        logger.error(f"❌ Status webhook error: {e}")
        return {"status": "error", "message": str(e)}

@router.websocket("/media-stream/{session_id}")
async def media_stream_websocket(websocket: WebSocket, session_id: str):
    """Handle Twilio Media Streams using existing audio processor"""
    
    await websocket.accept()
    logger.info(f"🔌 Media stream connected: {session_id}")
    
    try:
        # Import existing audio processor
        from ..core.audio_processor import AudioProcessor
        audio_processor = AudioProcessor()
        
        while True:
            data = await websocket.receive_text()
            
            try:
                message = json.loads(data)
                event = message.get("event")
                
                if event == "connected":
                    logger.info(f"📡 Media stream started: {session_id}")
                    await websocket.send_text(json.dumps({
                        "event": "connected",
                        "session_id": session_id
                    }))
                
                elif event == "start":
                    logger.info(f"🎙️ Audio capture started: {session_id}")
                    
                elif event == "media":
                    # Process audio using existing audio processor
                    media_data = message.get("media", {})
                    audio_data = media_data.get("payload", "")
                    
                    if audio_data:
                        # Use existing optimized audio processing
                        result = await audio_processor.process_audio(
                            session_id=session_id,
                            audio_data=audio_data,
                            audio_format="mulaw"
                        )
                        
                        if result.get("response_audio"):
                            # Send audio response back to Twilio
                            await websocket.send_text(json.dumps({
                                "event": "media",
                                "media": {
                                    "payload": result["response_audio"]
                                }
                            }))
                
                elif event == "stop":
                    logger.info(f"🛑 Media stream stopped: {session_id}")
                    break
                    
            except json.JSONDecodeError:
                logger.error(f"❌ Invalid JSON in media stream: {session_id}")
            except Exception as e:
                logger.error(f"❌ Media stream processing error: {e}")
                
    except WebSocketDisconnect:
        logger.info(f"🔌 Media stream disconnected: {session_id}")
    except Exception as e:
        logger.error(f"❌ Media stream error: {e}")

@router.get("/test-connection")
async def test_twilio_connection():
    """Test Twilio connection and existing services"""
    
    try:
        # Test existing service configurations
        services_status = {
            "twilio_configured": bool(settings.twilio_account_sid and settings.twilio_auth_token),
            "lyzr_configured": bool(settings.lyzr_user_api_key),
            "elevenlabs_configured": bool(settings.elevenlabs_api_key),
            "deepgram_configured": bool(settings.deepgram_api_key),
            "hybrid_tts_ready": await hybrid_tts.is_ready(),
            "voice_processor_ready": voice_processor.is_ready()
        }
        
        # Test service connections
        service_tests = {}
        
        try:
            lyzr_client = await get_lyzr_client()
            service_tests["lyzr"] = lyzr_client.is_configured()
        except Exception as e:
            service_tests["lyzr"] = f"Error: {str(e)}"
        
        try:
            elevenlabs_client = await get_elevenlabs_client()
            service_tests["elevenlabs"] = elevenlabs_client.is_configured()
        except Exception as e:
            service_tests["elevenlabs"] = f"Error: {str(e)}"
        
        try:
            deepgram_client = await get_deepgram_client()
            service_tests["deepgram"] = deepgram_client.is_configured()
        except Exception as e:
            service_tests["deepgram"] = f"Error: {str(e)}"
        
        return {
            "status": "ok",
            "configuration": services_status,
            "service_tests": service_tests,
            "active_sessions": len(active_sessions),
            "webhook_urls": {
                "voice": f"{settings.base_url}/twilio/voice",
                "status": f"{settings.base_url}/twilio/status",
                "media_stream": f"{settings.base_url}/twilio/media-stream"
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