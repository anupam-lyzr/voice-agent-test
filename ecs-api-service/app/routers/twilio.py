"""
Twilio Webhook Router
Handles all Twilio webhook endpoints for voice processing
"""

from fastapi import APIRouter, Request, Form, WebSocket, WebSocketDisconnect
from fastapi.responses import Response
from typing import Optional, Dict, Any
import logging
import json
import uuid
from datetime import datetime

from shared.config.settings import settings
from shared.models.call_session import CallSession, CallStatus, ConversationStage, ConversationTurn, ResponseType
from shared.models.client import Client, CallOutcome
from shared.utils.database import client_repo, get_client_by_phone
from shared.utils.redis_client import cache_session, get_cached_session

from services.hybrid_tts import HybridTTSService
from services.voice_processor import VoiceProcessor

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/twilio", tags=["Twilio Webhooks"])

# Global services
hybrid_tts = HybridTTSService()
voice_processor = VoiceProcessor()

@router.post("/voice")
async def voice_webhook(
    request: Request,
    CallSid: str = Form(...),
    CallStatus: Optional[str] = Form(None),
    From: Optional[str] = Form(None),
    To: Optional[str] = Form(None),
    Direction: Optional[str] = Form(None)
):
    """Handle incoming voice calls and initiate conversation"""
    
    logger.info(f"📞 Voice webhook: {CallSid} - Status: {CallStatus}")
    
    try:
        if CallStatus == "in-progress":
            # Call answered - start conversation
            
            # Get client by phone number
            client = await get_client_by_phone(From)
            if not client:
                logger.warning(f"⚠️ Client not found for phone: {From}")
                return Response(
                    content=create_simple_twiml("Thank you for calling. Goodbye."),
                    media_type="application/xml"
                )
            
            # Create call session
            session = CallSession(
                session_id=str(uuid.uuid4()),
                twilio_call_sid=CallSid,
                client_id=client.id,
                phone_number=From,
                lyzr_agent_id=settings.lyzr_conversation_agent_id,
                lyzr_session_id=f"{CallSid}-{uuid.uuid4().hex[:8]}"
            )
            session.call_status = CallStatus.IN_PROGRESS
            session.answered_at = datetime.utcnow()
            
            # Cache session
            await cache_session(session)
            
            logger.info(f"🎯 Starting conversation with {client.client.full_name}")
            
            # Generate greeting with client's name
            greeting_text = f"Hello {client.client.first_name}, this is Alex from Altrius Advisor Group. It's been some time since you've been in touch with us. We'd love to improve our service for you during Open Enrollment. Can we help service you this year?"
            
            # Get greeting audio (static or dynamic)
            audio_result = await hybrid_tts.get_response_audio(
                text=greeting_text,
                response_type="greeting",
                client_data=client.client.model_dump_for_greeting()
            )
            
            # Create TwiML response
            if audio_result["success"]:
                twiml = create_voice_twiml(
                    audio_url=audio_result["audio_url"],
                    gather_action=settings.get_webhook_url("speech"),
                    session_id=session.session_id
                )
                
                # Log first turn
                turn = ConversationTurn(
                    turn_number=1,
                    agent_response=greeting_text,
                    response_type=ResponseType.STATIC_AUDIO if audio_result["type"] == "static" else ResponseType.DYNAMIC_TTS,
                    audio_url=audio_result["audio_url"],
                    conversation_stage=ConversationStage.GREETING,
                    response_generation_time_ms=audio_result.get("generation_time_ms", 0)
                )
                session.add_conversation_turn(turn)
                session.update_conversation_stage(ConversationStage.INTEREST_CHECK)
                
                # Update cache
                await cache_session(session)
                
            else:
                # Fallback to Twilio TTS
                twiml = create_fallback_twiml(greeting_text, settings.get_webhook_url("speech"))
            
            return Response(content=twiml, media_type="application/xml")
        
        else:
            # Other call statuses
            return Response(content="<Response></Response>", media_type="application/xml")
            
    except Exception as e:
        logger.error(f"❌ Voice webhook error: {e}")
        return Response(
            content=create_simple_twiml("Sorry, there was an error. Please call back later."),
            media_type="application/xml"
        )

@router.post("/speech")
async def speech_webhook(
    request: Request,
    CallSid: str = Form(...),
    SpeechResult: Optional[str] = Form(None),
    From: Optional[str] = Form(None)
):
    """Process customer speech and generate response"""
    
    logger.info(f"🗣️ Speech webhook: {CallSid} - Speech: '{SpeechResult}'")
    
    try:
        # Get session from cache
        session = await get_cached_session(CallSid)
        if not session:
            logger.error(f"❌ Session not found: {CallSid}")
            return Response(
                content=create_simple_twiml("Thank you for calling. Goodbye."),
                media_type="application/xml"
            )
        
        # Process speech with voice processor
        response_result = await voice_processor.process_customer_speech(
            session=session,
            customer_speech=SpeechResult or "",
            client_phone=From
        )
        
        if not response_result["success"]:
            # Error in processing - end call gracefully
            return Response(
                content=create_simple_twiml(response_result.get("message", "Thank you for your time.")),
                media_type="application/xml"
            )
        
        # Get audio for response
        audio_result = await hybrid_tts.get_response_audio(
            text=response_result["response_text"],
            response_type=response_result["response_category"],
            conversation_context=session.conversation_context
        )
        
        # Create conversation turn
        turn = ConversationTurn(
            agent_response=response_result["response_text"],
            customer_speech=SpeechResult,
            response_type=ResponseType.STATIC_AUDIO if audio_result["type"] == "static" else ResponseType.DYNAMIC_TTS,
            audio_url=audio_result["audio_url"] if audio_result["success"] else None,
            conversation_stage=session.conversation_stage,
            customer_intent=response_result.get("detected_intent"),
            response_generation_time_ms=response_result.get("generation_time_ms", 0),
            tts_generation_time_ms=audio_result.get("generation_time_ms", 0)
        )
        
        session.add_conversation_turn(turn)
        
        # Update session based on response
        if response_result.get("end_conversation"):
            session.complete_call(response_result.get("final_outcome", "completed"))
            
            # Create final TwiML (no gather)
            if audio_result["success"]:
                twiml = f"""<?xml version="1.0" encoding="UTF-8"?>
<Response>
    <Play>{audio_result["audio_url"]}</Play>
</Response>"""
            else:
                twiml = create_simple_twiml(response_result["response_text"])
        
        else:
            # Continue conversation
            if response_result.get("conversation_stage"):
                session.update_conversation_stage(
                    ConversationStage(response_result["conversation_stage"])
                )
            
            # Create continuing TwiML
            if audio_result["success"]:
                twiml = create_voice_twiml(
                    audio_url=audio_result["audio_url"],
                    gather_action=settings.get_webhook_url("speech"),
                    session_id=session.session_id
                )
            else:
                twiml = create_fallback_twiml(
                    response_result["response_text"],
                    settings.get_webhook_url("speech")
                )
        
        # Update session cache
        await cache_session(session)
        
        # Update client record if conversation completed
        if response_result.get("end_conversation"):
            await update_client_record(session, response_result)
        
        return Response(content=twiml, media_type="application/xml")
        
    except Exception as e:
        logger.error(f"❌ Speech processing error: {e}")
        return Response(
            content=create_simple_twiml("Thank you for your time. Have a great day!"),
            media_type="application/xml"
        )

@router.post("/status")
async def status_webhook(
    request: Request,
    CallSid: str = Form(...),
    CallStatus: str = Form(...),
    CallDuration: Optional[str] = Form(None)
):
    """Handle call status updates from Twilio"""
    
    logger.info(f"📊 Status webhook: {CallSid} - Status: {CallStatus} - Duration: {CallDuration}")
    
    try:
        session = await get_cached_session(CallSid)
        if session:
            if CallStatus in ["completed", "failed", "busy", "no-answer"]:
                # Update session with final status
                if not session.completed_at:  # Only update if not already completed
                    session.call_status = CallStatus(CallStatus.lower().replace("-", "_"))
                    session.complete_call(CallStatus)
                    
                    if CallDuration:
                        session.session_metrics.total_call_duration_seconds = int(CallDuration)
                    
                    await cache_session(session)
                    
                    logger.info(f"✅ Call completed: {CallSid} - Duration: {CallDuration}s")
        
        return {"status": "ok", "call_sid": CallSid}
        
    except Exception as e:
        logger.error(f"❌ Status webhook error: {e}")
        return {"status": "error", "message": str(e)}

@router.websocket("/media-stream/{session_id}")
async def media_stream_websocket(websocket: WebSocket, session_id: str):
    """Handle Twilio Media Streams for real-time audio processing"""
    
    await websocket.accept()
    logger.info(f"🔌 Media stream connected: {session_id}")
    
    try:
        while True:
            # Receive audio data from Twilio
            data = await websocket.receive_text()
            message = json.loads(data)
            
            if message["event"] == "media":
                # Process real-time audio
                audio_data = message["media"]["payload"]
                
                # TODO: Implement real-time STT and response
                # This would integrate Deepgram for real-time transcription
                # and provide even faster response times
                
                logger.debug(f"📡 Received audio chunk: {len(audio_data)} bytes")
            
            elif message["event"] == "start":
                logger.info(f"🎤 Media stream started: {message}")
            
            elif message["event"] == "stop":
                logger.info(f"🛑 Media stream stopped: {message}")
                break
                
    except WebSocketDisconnect:
        logger.info(f"🔌 Media stream disconnected: {session_id}")
    except Exception as e:
        logger.error(f"❌ Media stream error: {e}")

# Helper functions

def create_voice_twiml(audio_url: str, gather_action: str, session_id: str) -> str:
    """Create TwiML for voice response with gather"""
    return f"""<?xml version="1.0" encoding="UTF-8"?>
<Response>
    <Play>{audio_url}</Play>
    <Gather 
        input="speech" 
        action="{gather_action}" 
        method="POST" 
        speechTimeout="3"
        timeout="8"
        language="en-US"
        enhanced="true">
    </Gather>
    <Say voice="alice">I'm here to help with any questions you have.</Say>
</Response>"""

def create_fallback_twiml(text: str, gather_action: str) -> str:
    """Create TwiML with Twilio's built-in TTS as fallback"""
    clean_text = text.replace("&", "and").replace("<", "").replace(">", "")[:500]
    
    return f"""<?xml version="1.0" encoding="UTF-8"?>
<Response>
    <Say voice="alice" language="en-US">{clean_text}</Say>
    <Gather 
        input="speech" 
        action="{gather_action}" 
        method="POST" 
        speechTimeout="3"
        timeout="8"
        language="en-US"
        enhanced="true">
    </Gather>
    <Say voice="alice">Please let me know how I can help.</Say>
</Response>"""

def create_simple_twiml(text: str) -> str:
    """Create simple TwiML for ending calls"""
    clean_text = text.replace("&", "and").replace("<", "").replace(">", "")[:500]
    
    return f"""<?xml version="1.0" encoding="UTF-8"?>
<Response>
    <Say voice="alice" language="en-US">{clean_text}</Say>
</Response>"""

async def update_client_record(session: CallSession, response_result: Dict[str, Any]):
    """Update client record with call results"""
    try:
        if not client_repo:
            return
        
        # Determine call outcome
        outcome = CallOutcome.COMPLETED
        if response_result.get("customer_interested"):
            outcome = CallOutcome.INTERESTED
        elif response_result.get("customer_not_interested"):
            outcome = CallOutcome.NOT_INTERESTED
        elif response_result.get("dnc_requested"):
            outcome = CallOutcome.DNC_REQUESTED
        
        # Create call attempt record
        call_attempt = {
            "attempt_number": len(session.conversation_turns),
            "timestamp": session.started_at,
            "outcome": outcome.value,
            "duration_seconds": session.session_metrics.total_call_duration_seconds,
            "twilio_call_sid": session.twilio_call_sid,
            "transcript": session.get_transcript(),
            "conversation_turns": len(session.conversation_turns),
            "static_responses_used": session.session_metrics.static_responses_used,
            "dynamic_responses_used": session.session_metrics.dynamic_responses_used,
            "avg_response_time_ms": session.session_metrics.avg_response_time_ms
        }
        
        # Add to client record
        await client_repo.add_call_attempt(session.client_id, call_attempt)
        
        # Add CRM tags based on outcome
        if outcome == CallOutcome.INTERESTED:
            from shared.models.client import CRMTag
            await client_repo.add_crm_tag(session.client_id, CRMTag.INTERESTED)
            
            # TODO: Trigger agent assignment
            
        elif outcome == CallOutcome.DNC_REQUESTED:
            from shared.models.client import CRMTag
            await client_repo.add_crm_tag(session.client_id, CRMTag.DNC_REQUESTED)
        
        logger.info(f"✅ Updated client record: {session.client_id} - Outcome: {outcome.value}")
        
    except Exception as e:
        logger.error(f"❌ Failed to update client record: {e}")