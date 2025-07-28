"""
Twilio Webhook Router - Updated with TwiML Helpers
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
from services.voice_processor import VoiceProcessor, update_client_record
from services.twiml_helpers import (
    create_simple_twiml,
    create_voice_twiml,
    create_fallback_twiml,
    create_media_stream_twiml,
    create_hangup_twiml
)

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
    
    logger.info(f"📞 Voice webhook: {CallSid} - Status: {CallStatus} - From: {From}")
    
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
                client_data={
                    "client_name": client.client.full_name,
                    "first_name": client.client.first_name
                }
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
        
        elif CallStatus == "ringing":
            # Call is ringing, return empty response
            return Response(content="<Response></Response>", media_type="application/xml")
        
        else:
            # Other call statuses (completed, failed, etc.)
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
    From: Optional[str] = Form(None),
    Digits: Optional[str] = Form(None)
):
    """Process customer speech and generate response"""
    
    logger.info(f"🗣️ Speech webhook: {CallSid} - Speech: '{SpeechResult}' - Digits: '{Digits}'")
    
    try:
        # Get session from cache
        session = await get_cached_session(CallSid)
        if not session:
            logger.error(f"❌ Session not found: {CallSid}")
            return Response(
                content=create_simple_twiml("Thank you for calling. Goodbye."),
                media_type="application/xml"
            )
        
        # Use speech result or digits
        customer_input = SpeechResult or Digits or ""
        
        if not customer_input.strip():
            # No input received
            return Response(
                content=create_simple_twiml("I didn't hear you. Thank you for your time. Goodbye."),
                media_type="application/xml"
            )
        
        # Process speech with voice processor
        response_result = await voice_processor.process_customer_speech(
            session=session,
            customer_speech=customer_input,
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
            turn_number=len(session.conversation_turns) + 1,
            agent_response=response_result["response_text"],
            customer_speech=customer_input,
            response_type=ResponseType.STATIC_AUDIO if audio_result.get("type") == "static" else ResponseType.DYNAMIC_TTS,
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
            content=create_simple_twiml("Thank you for your time."),
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
                    
                    if RecordingUrl:
                        session.recording_url = RecordingUrl
                    
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
            data = await websocket.receive_text()
            
            try:
                message = json.loads(data)
                event = message.get("event")
                
                if event == "connected":
                    logger.info(f"📡 Media stream connected for {session_id}")
                    await websocket.send_text(json.dumps({
                        "event": "connected",
                        "session_id": session_id
                    }))
                
                elif event == "start":
                    logger.info(f"🎙️ Media stream started for {session_id}")
                    
                elif event == "media":
                    # Handle incoming audio data
                    media_data = message.get("media", {})
                    payload = media_data.get("payload")
                    
                    if payload:
                        # Process audio payload (base64 encoded audio)
                        # This would integrate with real-time STT
                        pass
                
                elif event == "stop":
                    logger.info(f"🛑 Media stream stopped for {session_id}")
                    break
                    
            except json.JSONDecodeError:
                logger.error(f"Invalid JSON in media stream: {data[:100]}...")
                
    except WebSocketDisconnect:
        logger.info(f"🔌 Media stream disconnected: {session_id}")
    
    except Exception as e:
        logger.error(f"❌ Media stream error: {e}")
        await websocket.close()

# Additional testing endpoints
@router.post("/test")
async def test_webhook(request: Request):
    """Test webhook endpoint for development"""
    
    try:
        form_data = await request.form()
        
        logger.info(f"🧪 Test webhook called with: {dict(form_data)}")
        
        return Response(
            content=create_simple_twiml("Test webhook received successfully!"),
            media_type="application/xml"
        )
        
    except Exception as e:
        logger.error(f"❌ Test webhook error: {e}")
        return Response(
            content=create_simple_twiml("Test webhook failed."),
            media_type="application/xml"
        )

@router.get("/test-tts")
async def test_tts(text: str = "Hello, this is a test of our voice system."):
    """Test TTS generation"""
    
    try:
        audio_result = await hybrid_tts.get_response_audio(
            text=text,
            response_type="test",
            client_data={"client_name": "Test User"}
        )
        
        return {
            "success": audio_result["success"],
            "audio_url": audio_result.get("audio_url"),
            "type": audio_result.get("type"),
            "generation_time_ms": audio_result.get("generation_time_ms"),
            "text": text
        }
        
    except Exception as e:
        logger.error(f"❌ TTS test error: {e}")
        return {
            "success": False,
            "error": str(e)
        }