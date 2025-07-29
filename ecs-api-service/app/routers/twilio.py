"""
Twilio Router - Complete Real-time Audio Processing Implementation
Handles Twilio webhooks and WebSocket media streams with full audio pipeline
"""

from fastapi import APIRouter, Request, Form, WebSocket, WebSocketDisconnect
from fastapi.responses import Response
from typing import Optional, Dict, Any
import logging
import json
import uuid
import asyncio
import base64
import io
from datetime import datetime

# Import shared models and utilities
from shared.config.settings import settings
from shared.models.call_session import CallSession, CallStatus, ConversationStage
from shared.models.client import Client, CallOutcome
from shared.utils.database import client_repo, get_client_by_phone
from shared.utils.redis_client import cache_session, get_cached_session

# Import services
from services.voice_processor import VoiceProcessor, update_client_record
from services.hybrid_tts import HybridTTSService
from services.deepgram_client import deepgram_client
from services.elevenlabs_client import elevenlabs_client
from services.twiml_helpers import (
    create_simple_twiml,
    create_voice_twiml,
    create_fallback_twiml,
    create_media_stream_twiml,
    create_hangup_twiml
)

# Audio processing imports
try:
    from pydub import AudioSegment
    from pydub.utils import which
    import audioop
    AUDIO_PROCESSING_AVAILABLE = True
except ImportError:
    AUDIO_PROCESSING_AVAILABLE = False
    logger = logging.getLogger(__name__)
    logger.warning("⚠️ Audio processing libraries not available - install pydub and audioop-lts")

# AWS S3 for audio storage
try:
    import boto3
    from botocore.exceptions import ClientError
    S3_AVAILABLE = True
except ImportError:
    S3_AVAILABLE = False

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/twilio", tags=["Twilio"])

# Store active conversation states
active_sessions: Dict[str, CallSession] = {}

# Audio processing buffer for real-time streams
audio_buffers: Dict[str, bytes] = {}

@router.post("/voice")
async def voice_webhook(
    request: Request,
    CallSid: str = Form(...),
    CallStatus: Optional[str] = Form(None),
    From: Optional[str] = Form(None),
    To: Optional[str] = Form(None),
    Direction: Optional[str] = Form(None)
):
    """Handle incoming voice calls with enhanced audio processing"""
    
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
            
            # Cache session
            await cache_session(session)
            active_sessions[CallSid] = session
            
            logger.info(f"🎯 Starting conversation with {client.client.full_name}")
            
            # Check if real-time audio processing is enabled
            if settings.enable_realtime_audio and AUDIO_PROCESSING_AVAILABLE:
                # Use WebSocket media streaming for real-time processing
                websocket_url = f"wss://{settings.base_url.replace('http://', '').replace('https://', '')}/twilio/media-stream/{CallSid}"
                
                return Response(
                    content=create_media_stream_twiml(websocket_url),
                    media_type="application/xml"
                )
            else:
                # Use traditional webhook approach with pre-generated audio
                hybrid_tts = HybridTTSService()
                
                # Generate greeting using existing hybrid TTS
                greeting_text = f"Hello {client.client.first_name}, this is Alex from Altrius Advisor Group. It's been some time since you've been in touch with us. We'd love to improve our service for you during Open Enrollment. Can we help service you this year?"
                
                tts_response = await hybrid_tts.get_response_audio(
                    text=greeting_text,
                    response_type="greeting",
                    client_data={"client_name": client.client.first_name}
                )
                
                if tts_response.get("success"):
                    return Response(
                        content=create_voice_twiml(
                            tts_response.get("audio_url"),
                            "/twilio/process-speech"
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
    """Process customer speech using traditional webhook approach"""
    
    logger.info(f"🎤 Processing speech: {CallSid} - Result: {SpeechResult} - Confidence: {Confidence}")
    
    try:
        # Get session
        session = active_sessions.get(CallSid)
        if not session:
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
        voice_processor = VoiceProcessor()
        customer_input = SpeechResult or "no response"
        
        ai_response = await voice_processor.process_customer_speech(
            session=session,
            customer_speech=customer_input,
            client_phone=session.phone_number
        )
        
        if not ai_response.get("success"):
            logger.error(f"❌ Voice processing failed: {ai_response.get('error')}")
            return Response(
                content=create_simple_twiml("Thank you for your time. Have a great day!"),
                media_type="application/xml"
            )
        
        response_text = ai_response.get("response_text", "Thank you for your call.")
        call_outcome = ai_response.get("final_outcome")
        
        # Update session with conversation turn
        session.add_conversation_turn(
            customer_input=customer_input,
            agent_response=response_text,
            confidence=Confidence or 0.0
        )
        
        # Use hybrid TTS for optimized response
        hybrid_tts = HybridTTSService()
        response_type = ai_response.get("response_category", "dynamic")
        
        tts_response = await hybrid_tts.get_response_audio(
            text=response_text,
            response_type=response_type,
            client_data={"client_name": session.client_id}
        )
        
        # Determine if call should end
        should_end_call = ai_response.get("end_conversation", False)
        
        if should_end_call:
            # End call with final message
            session.complete_call(call_outcome)
            await cache_session(session)
            
            # Update client record
            await update_client_record(session, ai_response)
            
            # Clean up session
            if CallSid in active_sessions:
                del active_sessions[CallSid]
            
            return Response(
                content=create_hangup_twiml(response_text),
                media_type="application/xml"
            )
        else:
            # Continue conversation
            await cache_session(session)
            
            if tts_response.get("success"):
                return Response(
                    content=create_voice_twiml(
                        tts_response.get("audio_url"),
                        "/twilio/process-speech"
                    ),
                    media_type="application/xml"
                )
            else:
                return Response(
                    content=create_voice_twiml(
                        response_text,
                        "/twilio/process-speech"
                    ),
                    media_type="application/xml"
                )
        
    except Exception as e:
        logger.error(f"❌ Speech processing error: {e}")
        return Response(
            content=create_simple_twiml("Thank you for your call. Our team will contact you soon."),
            media_type="application/xml"
        )

@router.websocket("/media-stream/{session_id}")
async def media_stream_websocket(websocket: WebSocket, session_id: str):
    """Handle Twilio Media Streams with complete real-time audio processing pipeline"""
    
    await websocket.accept()
    logger.info(f"🔌 Media stream connected: {session_id}")
    
    # Initialize audio buffer for this session
    audio_buffers[session_id] = b""
    
    try:
        # Initialize services
        voice_processor = VoiceProcessor()
        hybrid_tts = HybridTTSService()
        
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
                    # Process real-time audio
                    await process_media_chunk(
                        websocket, session_id, message,
                        voice_processor, hybrid_tts
                    )
                
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
    finally:
        # Clean up
        await voice_processor.close()
        if session_id in audio_buffers:
            del audio_buffers[session_id]

async def process_media_chunk(
    websocket: WebSocket, 
    session_id: str, 
    message: Dict[str, Any],
    voice_processor: VoiceProcessor,
    hybrid_tts: HybridTTSService
):
    """Process audio chunk through the complete real-time pipeline"""
    
    try:
        # 1. Decode audio from base64
        media_data = message.get("media", {})
        audio_payload = media_data.get("payload", "")
        
        if not audio_payload:
            return
        
        # Decode base64 audio (Twilio sends μ-law encoded audio at 8kHz)
        audio_chunk = base64.b64decode(audio_payload)
        
        # Add to buffer
        audio_buffers[session_id] += audio_chunk
        
        # Process when we have enough audio (approximately 2 seconds worth)
        # μ-law is 8kHz, 8-bit, so 2 seconds = ~16000 bytes
        buffer_size = 16000
        
        if len(audio_buffers[session_id]) >= buffer_size:
            audio_to_process = audio_buffers[session_id][:buffer_size]
            audio_buffers[session_id] = audio_buffers[session_id][buffer_size:]
            
            # Process the audio chunk
            await process_complete_audio_pipeline(
                websocket, session_id, audio_to_process,
                voice_processor, hybrid_tts
            )
        
    except Exception as e:
        logger.error(f"❌ Media chunk processing error: {e}")

async def process_complete_audio_pipeline(
    websocket: WebSocket,
    session_id: str,
    audio_data: bytes,
    voice_processor: VoiceProcessor,
    hybrid_tts: HybridTTSService
):
    """Complete audio processing pipeline: STT → Voice Processing → TTS → Response"""
    
    try:
        # Get session
        session = active_sessions.get(session_id)
        if not session:
            logger.warning(f"⚠️ No session found for {session_id}")
            return
        
        # 2. Send to Deepgram for real-time STT
        # Convert μ-law to WAV format for Deepgram
        wav_audio = convert_mulaw_to_wav(audio_data)
        
        transcription_result = await deepgram_client.transcribe_audio(
            audio_data=wav_audio,
            audio_format="wav",
            language="en-US"
        )
        
        if not transcription_result["success"]:
            logger.debug(f"🔇 Transcription failed: {transcription_result['error']}")
            return
        
        transcript = transcription_result["transcript"]
        confidence = transcription_result["confidence"]
        
        # Only process meaningful speech
        if not deepgram_client.is_meaningful_speech(transcript, confidence):
            logger.debug(f"🔇 Skipping low-quality speech: '{transcript}' (confidence: {confidence})")
            return
        
        logger.info(f"🎤 Real-time transcribed: '{transcript}' (confidence: {confidence:.2f})")
        
        # 3. Process with voice processor
        voice_result = await voice_processor.process_customer_speech(
            session=session,
            customer_speech=transcript,
            client_phone=session.phone_number
        )
        
        if not voice_result["success"]:
            logger.error(f"❌ Voice processing failed: {voice_result.get('error')}")
            return
        
        response_text = voice_result["response_text"]
        response_category = voice_result.get("response_category", "dynamic")
        
        # Update session with conversation turn
        session.add_conversation_turn(
            customer_input=transcript,
            agent_response=response_text,
            confidence=confidence
        )
        
        # 4. Generate TTS response using hybrid approach
        tts_result = await hybrid_tts.get_response_audio(
            text=response_text,
            response_type=response_category,
            client_data={
                "client_name": session.client_id,
                "phone": session.phone_number
            }
        )
        
        if not tts_result["success"]:
            logger.error(f"❌ TTS generation failed: {tts_result.get('error')}")
            return
        
        # 5. Send audio back to Twilio
        await send_audio_response_to_twilio(websocket, tts_result)
        
        logger.info(f"✅ Real-time audio pipeline completed in {tts_result.get('generation_time_ms', 0):.0f}ms")
        
        # Check if conversation should end
        if voice_result.get("end_conversation"):
            outcome = voice_result.get("final_outcome", "completed")
            session.complete_call(outcome)
            
            # Update client record
            await update_client_record(session, voice_result)
            
            # Send final message and close
            await websocket.send_text(json.dumps({
                "event": "end_call",
                "reason": outcome
            }))
            
            # Clean up session
            if session_id in active_sessions:
                del active_sessions[session_id]
        
    except Exception as e:
        logger.error(f"❌ Complete audio pipeline error: {e}")

async def send_audio_response_to_twilio(websocket: WebSocket, tts_result: Dict[str, Any]):
    """Send audio response back to Twilio WebSocket"""
    
    try:
        if "audio_url" in tts_result:
            # For static/cached audio, fetch from S3/URL and stream
            audio_url = tts_result["audio_url"]
            
            if audio_url.startswith("http"):
                # Fetch audio from URL (S3 or local server)
                import httpx
                async with httpx.AsyncClient() as client:
                    response = await client.get(audio_url)
                    if response.status_code == 200:
                        audio_data = response.content
                        await stream_audio_to_twilio(websocket, audio_data)
                    else:
                        logger.error(f"❌ Failed to fetch audio from URL: {audio_url}")
            
        elif "audio_data" in tts_result:
            # For dynamic audio, stream directly
            audio_data = tts_result["audio_data"]
            await stream_audio_to_twilio(websocket, audio_data)
        
        logger.info(f"🔊 Audio streamed to Twilio successfully")
        
    except Exception as e:
        logger.error(f"❌ Error sending audio to Twilio: {e}")

async def stream_audio_to_twilio(websocket: WebSocket, audio_data: bytes):
    """Stream audio data to Twilio in μ-law format"""
    
    try:
        # Convert MP3/WAV to μ-law format for Twilio
        mulaw_audio = convert_to_mulaw(audio_data)
        
        # Encode to base64
        audio_b64 = base64.b64encode(mulaw_audio).decode('utf-8')
        
        # Send in chunks (Twilio has payload limits)
        chunk_size = 1024
        for i in range(0, len(audio_b64), chunk_size):
            chunk = audio_b64[i:i + chunk_size]
            
            await websocket.send_text(json.dumps({
                "event": "media",
                "media": {
                    "payload": chunk
                }
            }))
            
            # Small delay between chunks for proper streaming
            await asyncio.sleep(0.02)
        
    except Exception as e:
        logger.error(f"❌ Audio streaming error: {e}")

def convert_mulaw_to_wav(mulaw_data: bytes) -> bytes:
    """Convert μ-law audio to WAV format for STT processing"""
    
    if not AUDIO_PROCESSING_AVAILABLE:
        logger.warning("⚠️ Audio processing not available, returning raw data")
        return mulaw_data
    
    try:
        # Convert μ-law to linear PCM
        linear_data = audioop.ulaw2lin(mulaw_data, 2)  # 2 bytes per sample (16-bit)
        
        # Create WAV file in memory
        wav_buffer = io.BytesIO()
        
        # Create AudioSegment from raw PCM data
        audio_segment = AudioSegment(
            data=linear_data,
            sample_width=2,  # 16-bit
            frame_rate=8000,  # 8kHz (Twilio's sample rate)
            channels=1  # Mono
        )
        
        # Export as WAV
        audio_segment.export(wav_buffer, format="wav")
        wav_buffer.seek(0)
        
        return wav_buffer.read()
        
    except Exception as e:
        logger.error(f"❌ μ-law to WAV conversion error: {e}")
        return mulaw_data

def convert_to_mulaw(audio_data: bytes) -> bytes:
    """Convert audio (MP3/WAV) to μ-law format for Twilio"""
    
    if not AUDIO_PROCESSING_AVAILABLE:
        logger.warning("⚠️ Audio processing not available, returning raw data")
        return audio_data
    
    try:
        # Load audio using pydub (supports MP3, WAV, etc.)
        audio_segment = AudioSegment.from_file(io.BytesIO(audio_data))
        
        # Convert to Twilio's required format: 8kHz, mono, 16-bit PCM
        audio_segment = audio_segment.set_frame_rate(8000).set_channels(1).set_sample_width(2)
        
        # Get raw PCM data
        pcm_data = audio_segment.raw_data
        
        # Convert PCM to μ-law
        mulaw_data = audioop.lin2ulaw(pcm_data, 2)  # 2 bytes per sample
        
        return mulaw_data
        
    except Exception as e:
        logger.error(f"❌ Audio to μ-law conversion error: {e}")
        # Fallback: return original data
        return audio_data

async def upload_audio_to_s3(audio_data: bytes, filename: str) -> Optional[str]:
    """Upload audio file to S3 and return public URL"""
    
    if not S3_AVAILABLE:
        logger.warning("⚠️ S3 not available, saving locally")
        return await save_audio_locally(audio_data, filename)
    
    try:
        s3_client = boto3.client(
            's3',
            region_name=settings.aws_region,
            aws_access_key_id=settings.aws_access_key_id,
            aws_secret_access_key=settings.aws_secret_access_key
        )
        
        # Upload to S3
        s3_client.put_object(
            Bucket=settings.s3_bucket_audio,
            Key=f"dynamic/{filename}",
            Body=audio_data,
            ContentType="audio/mpeg",
            ACL="public-read"  # Make publicly accessible
        )
        
        # Return public URL
        s3_url = f"https://{settings.s3_bucket_audio}.s3.{settings.aws_region}.amazonaws.com/dynamic/{filename}"
        
        logger.info(f"✅ Audio uploaded to S3: {s3_url}")
        return s3_url
        
    except ClientError as e:
        logger.error(f"❌ S3 upload error: {e}")
        return await save_audio_locally(audio_data, filename)
    except Exception as e:
        logger.error(f"❌ S3 upload error: {e}")
        return await save_audio_locally(audio_data, filename)

async def save_audio_locally(audio_data: bytes, filename: str) -> str:
    """Save audio locally and return URL (fallback for S3)"""
    
    try:
        import os
        
        # Create directory if it doesn't exist
        os.makedirs("static/audio/dynamic", exist_ok=True)
        
        # Save file
        filepath = f"static/audio/dynamic/{filename}"
        with open(filepath, "wb") as f:
            f.write(audio_data)
        
        # Return local URL
        local_url = f"{settings.base_url.rstrip('/')}/static/audio/dynamic/{filename}"
        
        logger.info(f"✅ Audio saved locally: {local_url}")
        return local_url
        
    except Exception as e:
        logger.error(f"❌ Local audio save error: {e}")
        return ""

@router.post("/status")
async def status_webhook(
    request: Request,
    CallSid: str = Form(...),
    CallStatus: str = Form(...),
    CallDuration: Optional[str] = Form(None),
    RecordingUrl: Optional[str] = Form(None)
):
    """Handle call status updates with enhanced logging"""
    
    logger.info(f"📊 Status update: {CallSid} - Status: {CallStatus} - Duration: {CallDuration}")
    
    try:
        # Get session from cache or active sessions
        session = active_sessions.get(CallSid)
        if not session:
            session = await get_cached_session(CallSid)
        
        if session and CallStatus in ["completed", "failed", "busy", "no-answer"]:
            # Update session with final status
            if not session.completed_at:
                session.call_status = CallStatus(CallStatus.lower().replace("-", "_"))
                session.complete_call(CallStatus)
                
                if CallDuration:
                    session.session_metrics.total_call_duration_seconds = int(CallDuration)
                
                if RecordingUrl:
                    session.recording_url = RecordingUrl
                
                # Save final session state
                await cache_session(session)
                
                # Clean up active session
                if CallSid in active_sessions:
                    del active_sessions[CallSid]
                
                # Clean up audio buffer
                if CallSid in audio_buffers:
                    del audio_buffers[CallSid]
                
                logger.info(f"✅ Call completed: {CallSid} - Duration: {CallDuration}s")
        
        return {"status": "ok", "call_sid": CallSid}
        
    except Exception as e:
        logger.error(f"❌ Status webhook error: {e}")
        return {"status": "error", "message": str(e)}

@router.get("/test-connection")
async def test_twilio_connection():
    """Test Twilio connection and all integrated services"""
    
    try:
        # Test service configurations
        services_status = {
            "twilio_configured": bool(settings.twilio_account_sid and settings.twilio_auth_token),
            "audio_processing_available": AUDIO_PROCESSING_AVAILABLE,
            "s3_available": S3_AVAILABLE,
            "realtime_audio_enabled": getattr(settings, 'enable_realtime_audio', False)
        }
        
        # Test individual services
        service_tests = {}
        
        # Test Deepgram
        try:
            deepgram_test = await deepgram_client.test_connection()
            service_tests["deepgram"] = deepgram_test
        except Exception as e:
            service_tests["deepgram"] = {"success": False, "error": str(e)}
        
        # Test ElevenLabs
        try:
            elevenlabs_test = await elevenlabs_client.test_connection()
            service_tests["elevenlabs"] = elevenlabs_test
        except Exception as e:
            service_tests["elevenlabs"] = {"success": False, "error": str(e)}
        
        # Test Voice Processor
        voice_processor = VoiceProcessor()
        service_tests["voice_processor"] = {"ready": True}
        await voice_processor.close()
        
        # Test Hybrid TTS
        hybrid_tts = HybridTTSService()
        service_tests["hybrid_tts"] = {"ready": True}
        
        return {
            "status": "ok",
            "configuration": services_status,
            "service_tests": service_tests,
            "active_sessions": len(active_sessions),
            "audio_buffers": len(audio_buffers),
            "webhook_urls": {
                "voice": f"{settings.base_url}/twilio/voice",
                "status": f"{settings.base_url}/twilio/status",
                "media_stream": f"{settings.base_url}/twilio/media-stream"
            },
            "capabilities": {
                "real_time_audio": AUDIO_PROCESSING_AVAILABLE,
                "s3_storage": S3_AVAILABLE,
                "webhook_processing": True,
                "hybrid_tts": True
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