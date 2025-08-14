"""
Enhanced Twilio Router with Start Delay, Voicemail Detection, and No-Speech Handling
"""

from fastapi import APIRouter, Request, Form, HTTPException
from fastapi.responses import Response
import uuid
import os
from typing import Optional, Dict, Any, Tuple
import logging
import asyncio
from datetime import datetime
import time

# Import shared models and utilities
from shared.config.settings import settings
from shared.models.call_session import CallSession, ConversationStage, ConversationTurn, ResponseType
from shared.models.call_session import CallStatus as CallStatusEnum
from shared.models.client import Client, CallOutcome, CRMTag

# Import services
from services.voice_processor import VoiceProcessor
from services.hybrid_tts import HybridTTSService
from services.lyzr_client import lyzr_client
from services.twiml_helpers import create_simple_twiml, create_hangup_twiml

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/twilio", tags=["Twilio"])

# Store active conversation states
active_sessions: Dict[str, CallSession] = {}

# Initialize services
voice_processor = VoiceProcessor()
hybrid_tts = HybridTTSService()

# FIXED: Use consistent male voice for all fallbacks
MALE_VOICE = "Polly.Matthew"

class EnhancedTwiMLManager:
    """Enhanced TwiML manager with start delay and better fallbacks"""
    
    @staticmethod
    async def create_greeting_with_delay(
        client_data: Optional[Dict[str, Any]] = None,
        gather_action: str = "/twilio/process-speech"
    ) -> Response:
        """Create greeting TwiML with 2-second delay for customer to say hello"""
        
        try:
            logger.info(f"🎵 Creating greeting with 2-second delay")
            
            # Get greeting audio using hybrid TTS
            tts_result = await hybrid_tts.get_response_audio(
                text="",  # Will use default greeting text
                response_type="greeting",
                client_data=client_data
            )
            
            if tts_result.get("success") and tts_result.get("audio_url"):
                audio_url = tts_result["audio_url"]
                
                # TwiML with 2-second pause before greeting
                twiml = f"""<?xml version="1.0" encoding="UTF-8"?>
<Response>
    <Pause length="1"/>
    <Play>{audio_url}</Play>
    <Gather action="{gather_action}" method="POST" input="speech" actionOnEmptyResult="true" timeout="8" speechTimeout="auto" enhanced="true">
        <Pause length="2"/>
    </Gather>
    <Say voice="{MALE_VOICE}">I didn't catch that. Could you please repeat your response?</Say>
    <Pause length="1"/>
    <Say voice="{MALE_VOICE}">Thank you for calling. Goodbye.</Say>
    <Hangup/>
</Response>"""
                
                return Response(content=twiml, media_type="application/xml")
            
            # Hybrid TTS failed - this should be rare with segmented audio
            else:
                logger.error(f"❌ CRITICAL: Hybrid TTS completely failed for greeting")
                return EnhancedTwiMLManager.create_emergency_twiml(
                    client_data.get("client_name", "there") if client_data else "there"
                )
        
        except Exception as e:
            logger.error(f"❌ Greeting generation error: {e}")
            return EnhancedTwiMLManager.create_emergency_twiml("there")
    
    @staticmethod
    async def create_voicemail_twiml(
        client_data: Optional[Dict[str, Any]] = None,
        voicemail_script: Optional[str] = None
    ) -> Response:
        """Create specialized voicemail TwiML with proper script"""
        
        try:
            logger.info(f"📱 Creating voicemail TwiML")
            
            client_name = client_data.get("first_name", "there") if client_data else "there"
            
            # Use provided voicemail script or default
            if not voicemail_script:
                voicemail_script = (
                    f"Hello {client_name}, this is Alex from Altruis Advisor Group. "
                    f"We've helped with your health insurance needs in the past and we wanted to "
                    f"reach out to see if we could be of assistance this year during Open Enrollment. "
                    f"There have been a number of important changes to the Affordable Care Act that "
                    f"may impact your situation - so it may make sense to do a quick policy review. "
                    f"As always, our services are completely free of charge - if you'd like to review "
                    f"your policy please call us at 8-3-3, 2-2-7, 8-5-0-0. We look forward to hearing "
                    f"from you - take care!"
                )
            
            # Try hybrid TTS for voicemail (should use segmented audio)
            tts_result = await hybrid_tts.get_response_audio(
                text=voicemail_script,
                response_type="voicemail",
                client_data=client_data
            )
            
            if tts_result.get("success") and tts_result.get("audio_url"):
                audio_url = tts_result["audio_url"]
                
                twiml = f"""<?xml version="1.0" encoding="UTF-8"?>
<Response>
    <Play>{audio_url}</Play>
    <Hangup/>
</Response>"""
                
                return Response(content=twiml, media_type="application/xml")
            
            # Emergency fallback ONLY if hybrid completely fails
            else:
                logger.error(f"❌ CRITICAL: Hybrid TTS failed for voicemail - using emergency fallback")
                
                twiml = f"""<?xml version="1.0" encoding="UTF-8"?>
<Response>
    <Say voice="{MALE_VOICE}">{voicemail_script}</Say>
    <Hangup/>
</Response>"""
                
                return Response(content=twiml, media_type="application/xml")
        
        except Exception as e:
            logger.error(f"❌ Voicemail generation error: {e}")
            
            # Emergency voicemail fallback
            emergency_voicemail = f"Hello, this is Alex from Altruis Advisor Group. Please call us back at 8-3-3, 2-2-7, 8-5-0-0. Thank you."
            
            twiml = f"""<?xml version="1.0" encoding="UTF-8"?>
<Response>
    <Say voice="{MALE_VOICE}">{emergency_voicemail}</Say>
    <Hangup/>
</Response>"""
            
            return Response(content=twiml, media_type="application/xml")
    
    @staticmethod
    async def create_no_speech_response(
        attempt_number: int,
        client_data: Optional[Dict[str, Any]] = None,
        gather_action: str = "/twilio/process-speech"
    ) -> Response:
        """Create enhanced no-speech response using hybrid TTS when possible"""
        
        try:
            if attempt_number == 1:
                text = "I'm sorry, I can't seem to hear you clearly. If you said something, could you please speak a bit louder? I'm here to help."
                response_type = "clarification"
                should_hangup = False
            elif attempt_number == 2:
                text = "I'm still having trouble hearing you. If you're there, please try speaking directly into your phone. Can you hear me okay?"
                response_type = "clarification"
                should_hangup = False
            else:
                text = "I apologize, but I'm having difficulty with our connection. If you'd like to speak with us, please call us back at 8-3-3, 2-2-7, 8-5-0-0. Thank you, and have a great day."
                response_type = "goodbye"
                should_hangup = True
            
            # Try hybrid TTS first
            tts_result = await hybrid_tts.get_response_audio(
                text=text,
                response_type=response_type,
                client_data=client_data
            )
            
            if tts_result.get("success") and tts_result.get("audio_url"):
                audio_url = tts_result["audio_url"]
                
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
    <Gather action="{gather_action}" method="POST" input="speech" actionOnEmptyResult="true" timeout="8" speechTimeout="auto" enhanced="true">
        <Pause length="3"/>
    </Gather>
    <Say voice="{MALE_VOICE}">I still can't hear you. I'll call you back later. Goodbye.</Say>
    <Hangup/>
</Response>"""
                
                return Response(content=twiml, media_type="application/xml")
            
            # Emergency fallback to Polly only if hybrid fails
            else:
                logger.error(f"❌ Hybrid TTS failed for no-speech response {attempt_number}")
                
                if should_hangup:
                    twiml = f"""<?xml version="1.0" encoding="UTF-8"?>
<Response>
    <Say voice="{MALE_VOICE}">{text}</Say>
    <Hangup/>
</Response>"""
                else:
                    twiml = f"""<?xml version="1.0" encoding="UTF-8"?>
<Response>
    <Say voice="{MALE_VOICE}">{text}</Say>
    <Gather action="{gather_action}" method="POST" input="speech" actionOnEmptyResult="true" timeout="8" speechTimeout="auto" enhanced="true">
        <Pause length="3"/>
    </Gather>
    <Say voice="{MALE_VOICE}">I still can't hear you. I'll call you back later. Goodbye.</Say>
    <Hangup/>
</Response>"""
                
                return Response(content=twiml, media_type="application/xml")
        
        except Exception as e:
            logger.error(f"❌ No-speech response error: {e}")
            return EnhancedTwiMLManager.create_emergency_twiml()
    
    @staticmethod
    async def create_hybrid_twiml_response(
        response_type: str, 
        text: Optional[str] = None,
        client_data: Optional[Dict[str, Any]] = None,
        gather_action: str = "/twilio/process-speech",
        should_hangup: bool = False,
        should_gather: bool = True
    ) -> Response:
        """Create TwiML response using hybrid TTS service"""
        
        try:
            logger.info(f"🎵 Creating hybrid TwiML for: {response_type}")
            
            # Get audio using hybrid TTS service (prioritizes segmented audio)
            tts_result = await hybrid_tts.get_response_audio(
                text=text or "",
                response_type=response_type,
                client_data=client_data
            )
            
            if tts_result.get("success") and tts_result.get("audio_url"):
                audio_url = tts_result["audio_url"]
                
                if should_hangup:
                    twiml = f"""<?xml version="1.0" encoding="UTF-8"?>
<Response>
    <Play>{audio_url}</Play>
    <Pause length="1"/>
    <Hangup/>
</Response>"""
                elif should_gather:
                    twiml = f"""<?xml version="1.0" encoding="UTF-8"?>
<Response>
    <Play>{audio_url}</Play>
    <Gather action="{gather_action}" method="POST" input="speech" actionOnEmptyResult="true" timeout="8" speechTimeout="auto" enhanced="true">
        <Pause length="2"/>
    </Gather>
    <Say voice="{MALE_VOICE}">I didn't catch that. Could you please repeat your response?</Say>
    <Pause length="1"/>
    <Say voice="{MALE_VOICE}">Thank you for calling. Goodbye.</Say>
    <Hangup/>
</Response>"""
                else:
                    twiml = f"""<?xml version="1.0" encoding="UTF-8"?>
<Response>
    <Play>{audio_url}</Play>
</Response>"""
                
                return Response(content=twiml, media_type="application/xml")
            
            # Emergency fallback to Polly ONLY if hybrid completely fails
            else:
                logger.error(f"❌ CRITICAL: Hybrid TTS completely failed for {response_type}")
                
                if should_hangup:
                    fallback_twiml = f"""<?xml version="1.0" encoding="UTF-8"?>
<Response>
    <Say voice="{MALE_VOICE}">{text or 'Thank you for your time. Have a wonderful day!'}</Say>
    <Hangup/>
</Response>"""
                else:
                    fallback_twiml = f"""<?xml version="1.0" encoding="UTF-8"?>
<Response>
    <Say voice="{MALE_VOICE}">{text or 'How can I help you?'}</Say>
    <Gather action="{gather_action}" method="POST" input="speech" actionOnEmptyResult="true" timeout="8" speechTimeout="auto" enhanced="true">
        <Pause length="2"/>
    </Gather>
    <Say voice="{MALE_VOICE}">Thank you for calling. Goodbye.</Say>
    <Hangup/>
</Response>"""
                
                return Response(content=fallback_twiml, media_type="application/xml")
        
        except Exception as e:
            logger.error(f"❌ Hybrid TwiML generation error: {e}")
            return EnhancedTwiMLManager.create_emergency_twiml()
    
    @staticmethod
    def create_emergency_twiml(client_name: str = "there") -> Response:
        """Create emergency TwiML when all systems fail"""
        
        emergency_text = f"Hello {client_name}, this is Alex from Altruis Advisor Group. We're experiencing technical difficulties. Please call us back at 8-3-3, 2-2-7, 8-5-0-0. Thank you."
        
        twiml = f"""<?xml version="1.0" encoding="UTF-8"?>
<Response>
    <Say voice="{MALE_VOICE}">{emergency_text}</Say>
    <Hangup/>
</Response>"""
        
        return Response(content=twiml, media_type="application/xml")

# Enhanced session management functions
async def get_client_repo():
    """Get client repository with initialization"""
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
    """Get session repository with initialization"""
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

async def get_client_by_phone(phone: str) -> Optional[Client]:
    """Get client by phone with error handling"""
    try:
        client_repo = await get_client_repo()
        if client_repo:
            return await client_repo.get_client_by_phone(phone)
        return None
    except Exception as e:
        logger.error(f"Failed to get client by phone {phone}: {e}")
        return None

async def enhanced_cache_session(session: CallSession):
    """Enhanced session caching with better error handling"""
    try:
        if not session.twilio_call_sid:
            logger.error(f"❌ Cannot cache session {session.session_id}: twilio_call_sid is None")
            return False
        
        # Try Redis cache first
        from shared.utils.redis_client import session_cache
        if session_cache:
            try:
                await session_cache.save_session(session)
                logger.debug(f"✅ Session cached in Redis: {session.session_id}")
            except Exception as redis_error:
                logger.warning(f"⚠️ Redis cache failed: {redis_error}")
        
        # Save to database with proper error handling
        session_repo = await get_session_repo()
        if session_repo:
            try:
                success = await session_repo.save_session(session)
                if success:
                    logger.debug(f"✅ Session saved to database: {session.session_id}")
                    return True
                else:
                    logger.error(f"❌ Database save returned false: {session.session_id}")
                    return False
            except Exception as db_error:
                logger.error(f"❌ Database save failed: {db_error}")
                # Try direct database operation as fallback
                try:
                    from shared.utils.database import db_client
                    if db_client is not None and db_client.database is not None:
                        session_dict = session.model_dump(by_alias=True)
                        if "_id" in session_dict:
                            del session_dict["_id"]
                        
                        await db_client.database.call_sessions.replace_one(
                            {"twilioCallSid": session.twilio_call_sid},
                            session_dict,
                            upsert=True
                        )
                        logger.info(f"✅ Fallback save successful: {session.session_id}")
                        return True
                except Exception as fallback_error:
                    logger.error(f"❌ Fallback save failed: {fallback_error}")
                    return False
        
        return False
    except Exception as e:
        logger.error(f"❌ Enhanced cache session failed: {e}")
        return False

async def get_cached_session(call_sid: str) -> Optional[CallSession]:
    """Enhanced session retrieval with better error handling"""
    try:
        # Try cache first
        from shared.utils.redis_client import session_cache
        if session_cache:
            try:
                session = await session_cache.get_session(call_sid)
                if session:
                    return session
            except Exception as redis_error:
                logger.warning(f"⚠️ Redis retrieval failed: {redis_error}")
        
        # Try active sessions
        if call_sid in active_sessions:
            return active_sessions[call_sid]
        
        # Try database
        session_repo = await get_session_repo()
        if session_repo:
            try:
                from shared.utils.database import db_client
                if db_client is not None and db_client.database is not None:
                    doc = await db_client.database.call_sessions.find_one({"twilioCallSid": call_sid})
                    if doc:
                        return CallSession(**doc)
            except Exception as db_error:
                logger.warning(f"⚠️ Database retrieval failed: {db_error}")
        
        return None
    except Exception as e:
        logger.error(f"❌ Get cached session failed: {e}")
        return None

# Enhanced webhook handlers

@router.post("/voice")
async def voice_webhook(
    request: Request,
    CallSid: str = Form(...),
    CallStatus: Optional[str] = Form(None),
    From: Optional[str] = Form(None),
    To: Optional[str] = Form(None),
    Direction: Optional[str] = Form(None),
    is_test_call: Optional[str] = Form(None),
    AnsweredBy: Optional[str] = Form(None)
):
    """Enhanced voice webhook with voicemail detection and start delay"""
    
    logger.info(f"📞 Voice webhook: {CallSid} - Status: {CallStatus} - From: {From} - AnsweredBy: {AnsweredBy}")
    
    try:
        # Handle answering machine detection
        if AnsweredBy == "machine":
            logger.info(f"📱 Voicemail detected for {CallSid}")
            
            # Get client data for personalized voicemail
            client_phone = To if Direction == "outbound-api" else From
            client = await get_client_by_phone(client_phone)
            
            client_data = {
                "client_name": "there",
                "first_name": "there"
            }
            
            if client:
                client_data = {
                    "client_name": client.client.first_name,
                    "first_name": client.client.first_name
                }
            
            return await EnhancedTwiMLManager.create_voicemail_twiml(client_data)
        
        if CallStatus == "in-progress":
            # Determine client phone based on call direction
            client_phone = To if Direction == "outbound-api" else From
            logger.info(f"🔍 Looking up client by phone: {client_phone}")
            
            # Initialize client data with defaults
            client_data = {
                "client_name": "there",
                "first_name": "there",
                "agent_name": "your agent",
                "last_agent": "your agent"
            }
            
            # Try to get client from database
            client = await get_client_by_phone(client_phone)
            if client:
                client_data = {
                    "client_name": client.client.first_name,
                    "first_name": client.client.first_name,
                    "agent_name": client.client.last_agent or "your agent",
                    "last_agent": client.client.last_agent or "your agent"
                }
                logger.info(f"✅ Found client: {client.client.first_name}")
            else:
                logger.warning(f"⚠️ Client not found for phone: {client_phone}")
            
            # Check for cached session or create new one
            cached_session = await get_cached_session(CallSid)
            
            if cached_session:
                session = cached_session
                session.call_status = CallStatusEnum.IN_PROGRESS
                session.answered_at = datetime.utcnow()
                session.conversation_stage = ConversationStage.GREETING
                logger.info(f"✅ Using cached session for {CallSid}")
            else:
                # Create new session
                session = CallSession(
                    session_id=str(uuid.uuid4()),
                    twilio_call_sid=CallSid,
                    client_id=str(client.id) if client else "unknown",
                    phone_number=client_phone,
                    lyzr_agent_id=settings.lyzr_conversation_agent_id,
                    lyzr_session_id=f"voice-{CallSid}-{uuid.uuid4().hex[:8]}",
                    client_data=client_data,
                    is_test_call=(is_test_call == "true") or (client_phone.startswith("+1555") if client_phone else False)
                )
                
                # Set initial session state
                session.no_speech_count = 0
                session.call_status = CallStatusEnum.IN_PROGRESS
                session.answered_at = datetime.utcnow()
                session.conversation_stage = ConversationStage.GREETING
            
            # Store session
            active_sessions[CallSid] = session
            await enhanced_cache_session(session)
            
            # Start LYZR conversation session if configured
            if lyzr_client.is_configured():
                try:
                    await lyzr_client.start_conversation(
                        client_name=client_data["first_name"],
                        phone_number=client_phone
                    )
                    logger.info(f"🤖 LYZR session started for {CallSid}")
                except Exception as e:
                    logger.warning(f"⚠️ LYZR session start failed: {e}")
            
            # Return greeting with 2-second delay
            return await EnhancedTwiMLManager.create_greeting_with_delay(
                client_data=client_data,
                gather_action="/twilio/process-speech"
            )
        
        # For other statuses, just acknowledge
        return Response(
            content=create_simple_twiml("Call received."),
            media_type="application/xml"
        )
        
    except Exception as e:
        logger.error(f"❌ Voice webhook error: {e}")
        import traceback
        logger.error(traceback.format_exc())
        
        # Use emergency fallback
        return EnhancedTwiMLManager.create_emergency_twiml("there")

@router.post("/process-speech")
async def process_speech_webhook(
    request: Request,
    CallSid: str = Form(...),
    SpeechResult: Optional[str] = Form(None),
    Confidence: Optional[float] = Form(None),
    UnstableSpeechResult: Optional[str] = Form(None)
):
    """Enhanced speech processing with better no-speech handling"""
    
    # Use UnstableSpeechResult if SpeechResult is empty for better responsiveness
    if not SpeechResult and UnstableSpeechResult:
        SpeechResult = UnstableSpeechResult
        logger.info(f"🎤 Using unstable speech result: '{SpeechResult}'")
    
    logger.info(f"🎤 Processing speech: {CallSid} - Result: '{SpeechResult}' - Confidence: {Confidence}")
    
    try:
        # Get session with enhanced retrieval
        session = active_sessions.get(CallSid)
        if not session:
            session = await get_cached_session(CallSid)
            if session:
                active_sessions[CallSid] = session
                logger.info(f"✅ Restored session from cache: {CallSid}")
        
        if not session:
            logger.error(f"❌ CRITICAL: Session not found for CallSid: {CallSid}")
            return Response(
                content=create_hangup_twiml("I'm sorry, there was a problem with the call. Please call us back."),
                media_type="application/xml"
            )
        
        # Ensure session integrity
        if not session.twilio_call_sid:
            session.twilio_call_sid = CallSid
        
        if not hasattr(session, 'no_speech_count'):
            session.no_speech_count = 0
        
        # Enhanced no speech handling
        if not SpeechResult:
            logger.warning(f"⚠️ No speech detected for {CallSid} (attempt {session.no_speech_count + 1})")
            session.no_speech_count += 1
            
            if session.no_speech_count >= 3:
                logger.warning(f"⚠️ Too many no-speech attempts. Ending call {CallSid}.")
                session.final_outcome = "no_answer"
                session.conversation_stage = ConversationStage.GOODBYE
                await enhanced_cache_session(session)
                
                return await EnhancedTwiMLManager.create_no_speech_response(
                    attempt_number=3,
                    client_data=session.client_data
                )
            else:
                return await EnhancedTwiMLManager.create_no_speech_response(
                    attempt_number=session.no_speech_count,
                    client_data=session.client_data
                )
        
        session.no_speech_count = 0
        
        # Process speech with enhanced voice processor
        process_result = await voice_processor.process_customer_input(
            customer_input=SpeechResult,
            session=session,
            confidence=Confidence or 0.0
        )
        
        logger.info(f"🔄 Processing result: {process_result}")
        
        # Update session conversation stage
        new_stage_value = process_result.get("conversation_stage")
        if new_stage_value:
            try:
                session.conversation_stage = ConversationStage(new_stage_value)
                logger.info(f"📍 Updated session stage to: {session.conversation_stage.value}")
            except ValueError:
                logger.warning(f"⚠️ Invalid stage value: {new_stage_value}")
        
        # Create conversation turn
        response_type_enum = ResponseType.HYBRID if process_result.get("lyzr_used") else ResponseType.STATIC
        
        turn = ConversationTurn(
            turn_number=len(session.conversation_turns) + 1 if session.conversation_turns else 1,
            customer_speech=SpeechResult,
            customer_speech_confidence=Confidence or 0.0,
            agent_response=process_result.get("response_text", ""),
            response_type=response_type_enum,
            conversation_stage=session.conversation_stage,
            processing_time_ms=process_result.get("processing_time_ms", 0)
        )
        
        if not session.conversation_turns:
            session.conversation_turns = []
        session.conversation_turns.append(turn)
        session.current_turn_number = turn.turn_number
        
        # Update final outcome if provided
        if process_result.get("outcome"):
            session.final_outcome = process_result["outcome"]
        
        # Save updated session
        await enhanced_cache_session(session)
        
        # Check if conversation should end
        if process_result.get("end_conversation", False):
            logger.info(f"🎬 Conversation ending for {CallSid}. Outcome: {session.final_outcome}")
            
            session.call_status = CallStatusEnum.COMPLETED
            session.complete_call(session.final_outcome)
            await enhanced_cache_session(session)
            
            return await EnhancedTwiMLManager.create_hybrid_twiml_response(
                response_type=process_result.get("response_category", "goodbye"),
                text=process_result.get("response_text"),
                client_data=session.client_data,
                should_hangup=True
            )
        else:
            # Continue conversation
            return await EnhancedTwiMLManager.create_hybrid_twiml_response(
                response_type=process_result.get("response_category", "dynamic"),
                text=process_result.get("response_text"),
                client_data=session.client_data
            )
            
    except Exception as e:
        logger.error(f"❌ Unrecoverable error in speech processing for {CallSid}: {e}", exc_info=True)
        return await EnhancedTwiMLManager.create_hybrid_twiml_response(
            response_type="error",
            text="I apologize, we have encountered a system error. Please call back at 8-3-3, 2-2-7, 8-5-0-0. Goodbye.",
            should_hangup=True
        )

# Add interruption handling endpoint
@router.post("/handle-interruption")
async def handle_interruption(
    request: Request,
    CallSid: str = Form(...),
    SpeechResult: Optional[str] = Form(None),
    Confidence: Optional[float] = Form(None)
):
    """Handle customer interruptions while agent is speaking"""
    
    logger.info(f"🛑 Interruption detected: {CallSid} - '{SpeechResult}'")
    
    try:
        session = active_sessions.get(CallSid) or await get_cached_session(CallSid)
        
        if not session:
            logger.error(f"❌ Session not found for interruption: {CallSid}")
            return EnhancedTwiMLManager.create_emergency_twiml()
        
        # Process interruption with voice processor
        process_result = await voice_processor.process_customer_input(
            customer_input=SpeechResult or "",
            session=session,
            confidence=Confidence or 0.0,
            is_interruption=True
        )
        
        # Save updated session
        await enhanced_cache_session(session)
        
        return await EnhancedTwiMLManager.create_hybrid_twiml_response(
            response_type=process_result.get("response_category", "interruption_acknowledgment"),
            text=process_result.get("response_text"),
            client_data=session.client_data,
            should_hangup=process_result.get("end_conversation", False)
        )
        
    except Exception as e:
        logger.error(f"❌ Interruption handling error: {e}")
        return EnhancedTwiMLManager.create_emergency_twiml()

# Keep existing status webhook and other endpoints...
@router.post("/status")
async def status_webhook(
    request: Request,
    CallSid: str = Form(...),
    CallStatus: str = Form(...),
    CallDuration: Optional[str] = Form(None),
    RecordingUrl: Optional[str] = Form(None)
):
    """Handle call status updates with proper cleanup"""
    
    logger.info(f"📊 Status update: {CallSid} - Status: {CallStatus} - Duration: {CallDuration}")
    
    try:
        # Handle call completion
        if CallStatus in ["completed", "failed", "busy", "no-answer"]:
            # Get session from active or cache
            session = active_sessions.get(CallSid)
            if not session:
                session = await get_cached_session(CallSid)
            
            if session:
                # Update call status
                if CallStatus == "completed":
                    session.call_status = CallStatusEnum.COMPLETED
                elif CallStatus == "failed":
                    session.call_status = CallStatusEnum.FAILED
                elif CallStatus == "busy":
                    session.call_status = CallStatusEnum.BUSY
                elif CallStatus == "no-answer":
                    session.call_status = CallStatusEnum.NO_ANSWER
                
                # Update duration
                if CallDuration:
                    try:
                        duration = int(CallDuration)
                        if not session.session_metrics:
                            from shared.models.call_session import SessionMetrics
                            session.session_metrics = SessionMetrics()
                        session.session_metrics.total_call_duration_seconds = duration
                    except ValueError:
                        logger.warning(f"Invalid call duration: {CallDuration}")
                
                # Set appropriate outcome based on status if not already set
                if not session.final_outcome:
                    if CallStatus == "completed":
                        if session.conversation_stage == ConversationStage.GOODBYE:
                            session.final_outcome = "completed"
                        else:
                            session.final_outcome = "incomplete"
                    elif CallStatus == "no-answer":
                        session.final_outcome = "no_answer"
                    elif CallStatus in ["busy", "failed"]:
                        session.final_outcome = "failed"
                
                # Complete the call
                session.complete_call(session.final_outcome)
                session.completed_at = datetime.utcnow()
                
                # Get client for summary and update
                client = await get_client_by_phone(session.phone_number)
                
                # Generate call summary if there were conversation turns
                if session.conversation_turns and len(session.conversation_turns) > 0:
                    await generate_and_save_call_summary(session, client)
                
                # Update client record if we have one
                if client and session.final_outcome:
                    await update_client_record(session, session.final_outcome, client)
                
                # Final save to database
                session_repo = await get_session_repo()
                if session_repo:
                    try:
                        if not session.twilio_call_sid:
                            session.twilio_call_sid = CallSid
                        
                        success = await session_repo.save_session(session)
                        if success:
                            logger.info(f"✅ Final session saved: {CallSid}")
                        else:
                            logger.error(f"❌ Failed to save session: {CallSid}")
                    except Exception as e:
                        logger.error(f"❌ Database save error: {e}")
                
                # Clean up
                from shared.utils.redis_client import session_cache
                if session_cache:
                    try:
                        await session_cache.delete_session(CallSid)
                        logger.info(f"🗑️ Removed from Redis: {CallSid}")
                    except Exception as e:
                        logger.warning(f"Redis cleanup failed: {e}")
                
                if CallSid in active_sessions:
                    del active_sessions[CallSid]
                    logger.info(f"🗑️ Removed from active sessions: {CallSid}")
                
                logger.info(f"✅ Call completed: {CallSid} - Outcome: {session.final_outcome}")
            else:
                logger.warning(f"⚠️ No session found for completed call: {CallSid}")
        
        # Handle other status updates
        else:
            session = active_sessions.get(CallSid) or await get_cached_session(CallSid)
            
            if session:
                if CallStatus == "initiated":
                    session.call_status = CallStatusEnum.INITIATED
                elif CallStatus == "ringing":
                    session.call_status = CallStatusEnum.RINGING
                elif CallStatus == "in-progress":
                    session.call_status = CallStatusEnum.IN_PROGRESS
                
                await enhanced_cache_session(session)
                logger.info(f"📞 Call status updated: {CallSid} -> {CallStatus}")
        
        return {"status": "ok", "call_sid": CallSid, "call_status": CallStatus}
        
    except Exception as e:
        logger.error(f"❌ Status webhook error: {e}")
        return {"status": "error", "message": str(e)}

# Helper functions for client record updates and call summaries
async def update_client_record(session: CallSession, outcome: str, client: Client):
    """Update client record with call outcome and details"""
    try:
        client_repo = await get_client_repo()
        if not client_repo:
            logger.warning("⚠️ Cannot update client - repo not available")
            return
        
        client_id = str(client.id)
        
        # Apply CRM tags based on outcome
        if outcome in ["scheduled", "interested", "interested_no_schedule"]:
            await client_repo.add_crm_tag(client_id, CRMTag.INTERESTED)
            await client_repo.update_call_outcome(client_id, CallOutcome.INTERESTED)
            logger.info(f"✅ Client {client_id} marked as INTERESTED")
            
        elif outcome in ["not_interested", "keep_communications"]:
            await client_repo.add_crm_tag(client_id, CRMTag.NOT_INTERESTED)
            await client_repo.update_call_outcome(client_id, CallOutcome.NOT_INTERESTED)
            logger.info(f"✅ Client {client_id} marked as NOT_INTERESTED")
            
        elif outcome == "dnc_requested":
            await client_repo.add_crm_tag(client_id, CRMTag.DNC_REQUESTED)
            await client_repo.update_call_outcome(client_id, CallOutcome.DNC_REQUESTED)
            logger.info(f"✅ Client {client_id} marked as DNC_REQUESTED")
            
        elif outcome == "no_answer":
            await client_repo.update_call_outcome(client_id, CallOutcome.NO_ANSWER)
            logger.info(f"✅ Client {client_id} marked as NO_ANSWER")
        
        # Build call summary
        call_summary = {
            "attempt_number": client.total_attempts + 1,
            "timestamp": datetime.utcnow(),
            "outcome": outcome,
            "duration_seconds": int(session.session_metrics.total_call_duration_seconds) if session.session_metrics else 0,
            "twilio_call_sid": session.twilio_call_sid,
            "conversation_turns": len(session.conversation_turns) if session.conversation_turns else 0,
            "final_stage": session.conversation_stage.value if session.conversation_stage else "unknown"
        }
        
        # Add transcript if available
        if session.conversation_turns:
            transcript = build_conversation_transcript(session)
            call_summary["transcript"] = transcript
        
        # Add AI summary if available
        if hasattr(session, 'call_summary') and session.call_summary:
            call_summary["ai_summary"] = session.call_summary
        
        # Add call attempt to history
        await client_repo.add_call_attempt(client_id, call_summary)
        
        # Update campaign status if needed
        if outcome in ["interested", "not_interested", "dnc_requested", "scheduled"]:
            await client_repo.update_client(client_id, {"campaignStatus": "completed"})
        
    except Exception as e:
        logger.error(f"❌ Failed to update client record: {e}")

async def generate_and_save_call_summary(session: CallSession, client: Optional[Client] = None):
    """Generate and save call summary using LYZR"""
    try:
        if not session.conversation_turns:
            logger.warning(f"⚠️ No conversation turns to summarize for {session.session_id}")
            return
        
        # Build conversation transcript
        transcript = build_conversation_transcript(session)
        
        # Get client name
        client_name = "Unknown"
        if client:
            client_name = f"{client.client.first_name} {client.client.last_name}"
        elif session.client_data:
            client_name = session.client_data.get("client_name", "Unknown")
        
        # Generate summary using LYZR if configured
        if lyzr_client.is_configured():
            summary_result = await lyzr_client.generate_call_summary(
                conversation_transcript=transcript,
                client_name=client_name,
                call_outcome=session.final_outcome or "completed"
            )
            
            if summary_result["success"]:
                session.call_summary = summary_result["summary"]
                logger.info(f"📝 AI summary generated for {session.session_id}")
        else:
            # Create basic summary without LYZR
            session.call_summary = {
                "outcome": session.final_outcome or "completed",
                "sentiment": "neutral",
                "key_points": [f"Call completed with {len(session.conversation_turns)} turns"],
                "customer_concerns": [],
                "recommended_actions": [],
                "agent_notes": f"Call duration: {session.session_metrics.total_call_duration_seconds}s",
                "generated_by": "system"
            }
        
        # Save session with summary
        await enhanced_cache_session(session)
        
        # Save to database
        session_repo = await get_session_repo()
        if session_repo:
            await session_repo.save_session(session)
        
    except Exception as e:
        logger.error(f"❌ Summary generation failed: {e}")

def build_conversation_transcript(session: CallSession) -> str:
    """Build formatted conversation transcript"""
    transcript_lines = []
    
    for turn in session.conversation_turns:
        transcript_lines.append(f"Customer: {turn.customer_speech}")
        transcript_lines.append(f"Agent: {turn.agent_response}")
        transcript_lines.append("")  # Empty line between turns
    
    return "\n".join(transcript_lines).strip()

@router.get("/test-connection")
async def test_twilio_connection():
    """Test enhanced Twilio connection and system readiness"""
    
    try:
        # Check service configurations
        services_status = {
            "twilio": {
                "configured": bool(settings.twilio_account_sid and settings.twilio_auth_token),
                "phone_number": settings.twilio_phone_number if settings.twilio_phone_number else "Not configured"
            },
            "hybrid_tts": {
                "configured": await hybrid_tts.is_configured(),
                "stats": hybrid_tts.get_performance_stats()
            },
            "voice_processor": {
                "configured": voice_processor.is_configured(),
                "enhanced_features": True
            },
            "lyzr": {
                "configured": lyzr_client.is_configured(),
                "conversation_agent": settings.lyzr_conversation_agent_id,
                "summary_agent": settings.lyzr_summary_agent_id
            }
        }
        
        # Test database connection
        try:
            client_repo = await get_client_repo()
            services_status["database"] = {"connected": client_repo is not None}
        except Exception as e:
            services_status["database"] = {"connected": False, "error": str(e)}
        
        # Check active sessions
        services_status["active_sessions"] = {
            "count": len(active_sessions),
            "sessions": list(active_sessions.keys())
        }
        
        # Overall system status
        all_configured = all([
            services_status["twilio"]["configured"],
            services_status["hybrid_tts"]["configured"],
            services_status["voice_processor"]["configured"]
        ])
        
        return {
            "status": "ready" if all_configured else "not_ready",
            "services": services_status,
            "webhook_urls": {
                "voice": f"{settings.base_url}/twilio/voice",
                "status": f"{settings.base_url}/twilio/status",
                "interruption": f"{settings.base_url}/twilio/handle-interruption"
            },
            "enhanced_features": {
                "start_delay": "2 seconds",
                "voicemail_detection": "enabled",
                "clarifying_questions": "enabled",
                "interruption_handling": "enabled",
                "no_speech_enhancement": "3 attempts with callbacks"
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