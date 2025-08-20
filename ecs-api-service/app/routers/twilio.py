"""
Complete Working Twilio Router - Production Ready
Handles all voice webhooks with start delay, voicemail detection, and enhanced response handling
"""

from fastapi import APIRouter, Request, Form, HTTPException
from fastapi.responses import Response
import uuid
import os
from typing import Optional, Dict, Any, Tuple, List
import logging
import asyncio
from datetime import datetime
import time

# Import shared models and utilities
from shared.config.settings import settings
from shared.models.call_session import CallSession, ConversationStage, ConversationTurn, ResponseType, SessionMetrics
from shared.models.call_session import CallStatus as CallStatusEnum
from shared.models.client import Client, CallOutcome, CRMTag

# Import services
from services.voice_processor import VoiceProcessor
from services.client_data_service import ClientDataService

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/twilio", tags=["Twilio"])

# Store active conversation states
active_sessions: Dict[str, CallSession] = {}

# Initialize services
voice_processor = VoiceProcessor()
client_data_service = ClientDataService()

# FIXED: Use consistent male voice for all fallbacks
MALE_VOICE = "Polly.Matthew"

class EnhancedTwiMLManager:
    """Enhanced TwiML manager with start delay, voicemail detection, and client-type support"""
    
    @staticmethod
    async def create_greeting_with_delay(
        client_data: Optional[Dict[str, Any]] = None,
        gather_action: str = "/twilio/process-speech"
    ) -> Response:
        """Create greeting TwiML with 2-second delay for customer to say hello"""
        
        try:
            logger.info(f"🎵 Creating greeting with 2-second delay")
            
            # Import hybrid TTS here to avoid circular imports
            try:
                from services.hybrid_tts import HybridTTSService
                hybrid_tts = HybridTTSService()
                
                # Get greeting audio using hybrid TTS with client type detection
                tts_result = await hybrid_tts.get_response_audio(
                    text="",  # Will use template-based generation
                    response_type="greeting",
                    client_data=client_data
                )
                
                if tts_result.get("success") and tts_result.get("audio_url"):
                    audio_url = tts_result["audio_url"]
                    
                    # TwiML without delay for faster response
                    twiml = f"""<?xml version="1.0" encoding="UTF-8"?>
<Response>
    <Play>{audio_url}</Play>
    <Gather action="{gather_action}" method="POST" input="speech" actionOnEmptyResult="true" timeout="8" speechTimeout="auto" enhanced="true" interruptionAction="{gather_action.replace('process-speech', 'handle-interruption')}">
    </Gather>
    <Say voice="{MALE_VOICE}">I didn't catch that. Could you please repeat your response?</Say>
    <Pause length="1"/>
    <Say voice="{MALE_VOICE}">Thank you for calling. Please call us back at 8-3-3, 2-2-7, 8-5-0-0. Goodbye.</Say>
    <Hangup/>
</Response>"""
                    
                    return Response(content=twiml, media_type="application/xml")
                
            except Exception as hybrid_error:
                logger.warning(f"⚠️ Hybrid TTS failed: {hybrid_error}")
            
            # Fallback with delay if hybrid TTS fails
            logger.warning("⚠️ Using fallback greeting with delay")
            
            # Determine appropriate fallback script based on client type
            if client_data:
                enhanced_data = client_data_service.analyze_client_data(client_data)
                client_type = enhanced_data.get("client_type")
                scripts = client_data_service.get_scripts_for_client_type(client_type)
                greeting_script = scripts.get("greeting", "")
                
                if greeting_script:
                    greeting_text = client_data_service.format_script_with_data(greeting_script, enhanced_data)
                else:
                    # Ultimate fallback
                    client_name = client_data.get("first_name", "there")
                    if client_name and client_name.lower() != "there":
                        greeting_text = f"Hello {client_name}, Alex here from Altruis Advisor Group. We've helped you with your health insurance needs in the past and I just wanted to reach out to see if we can be of service to you this year during Open Enrollment?"
                    else:
                        greeting_text = "Hello there, Alex here from Altruis Advisor Group. We've helped you with your health insurance needs in the past and I just wanted to reach out to see if we can be of service to you this year during Open Enrollment?"
            else:
                # No client data fallback
                greeting_text = "Hello there, Alex here from Altruis Advisor Group. We've helped you with your health insurance needs in the past and I just wanted to reach out to see if we can be of service to you this year during Open Enrollment?"
            
            twiml = f"""<?xml version="1.0" encoding="UTF-8"?>
<Response>
    <Say voice="{MALE_VOICE}">{greeting_text}</Say>
    <Gather action="{gather_action}" method="POST" input="speech" actionOnEmptyResult="true" timeout="8" speechTimeout="auto" enhanced="true" interruptionAction="{gather_action.replace('process-speech', 'handle-interruption')}">
    </Gather>
    <Say voice="{MALE_VOICE}">I didn't catch that. Could you please repeat your response?</Say>
    <Pause length="1"/>
    <Say voice="{MALE_VOICE}">Thank you for calling. Please call us back at 8-3-3, 2-2-7, 8-5-0-0. Goodbye.</Say>
    <Hangup/>
</Response>"""
            
            return Response(content=twiml, media_type="application/xml")
        
        except Exception as e:
            logger.error(f"❌ Greeting generation error: {e}")
            
            # Emergency greeting fallback
            emergency_greeting = "Hello, this is Alex from Altruis Advisor Group. Thank you for calling."
            
            twiml = f"""<?xml version="1.0" encoding="UTF-8"?>
<Response>
    <Say voice="{MALE_VOICE}">{emergency_greeting}</Say>
    <Gather action="{gather_action}" method="POST" input="speech" timeout="5" speechTimeout="auto" interruptionAction="{gather_action.replace('process-speech', 'handle-interruption')}">
    </Gather>
    <Say voice="{MALE_VOICE}">Thank you for calling. Goodbye.</Say>
    <Hangup/>
</Response>"""
            
            return Response(content=twiml, media_type="application/xml")
    
    @staticmethod
    async def create_voicemail_response(
        client_data: Optional[Dict[str, Any]] = None
    ) -> Response:
        """Create voicemail TwiML response with client-type specific script"""
        
        try:
            logger.info(f"📱 Creating voicemail response")
            
            # Import hybrid TTS here to avoid circular imports
            try:
                from services.hybrid_tts import HybridTTSService
                hybrid_tts = HybridTTSService()
                
                # Import client data service
                from services.client_data_service import client_data_service
                
                # Analyze client data to determine appropriate voicemail script
                if client_data:
                    enhanced_data = client_data_service.analyze_client_data(client_data)
                else:
                    enhanced_data = client_data_service._get_fallback_client_data({})
                
                # Get voicemail using enhanced hybrid TTS
                tts_result = await hybrid_tts.get_response_audio(
                    text="",  # Will use template-based generation
                    response_type="voicemail",
                    client_data=enhanced_data
                )
                
                if tts_result.get("success") and tts_result.get("audio_url"):
                    audio_url = tts_result["audio_url"]
                    
                    twiml = f"""<?xml version="1.0" encoding="UTF-8"?>
<Response>
    <Play>{audio_url}</Play>
    <Hangup/>
</Response>"""
                    
                    return Response(content=twiml, media_type="application/xml")
                
            except Exception as hybrid_error:
                logger.warning(f"⚠️ Hybrid TTS failed for voicemail: {hybrid_error}")
            
            # Emergency fallback with client-type specific script
            logger.error(f"❌ Using emergency voicemail fallback")
            
            # Get formatted voicemail script based on client type
            if client_data:
                enhanced_data = client_data_service.analyze_client_data(client_data)
                scripts = client_data_service.get_formatted_scripts_for_client(enhanced_data)
                voicemail_script = scripts.get("voicemail", "")
                
                if not voicemail_script:
                    # Fallback voicemail
                    client_name = enhanced_data.get("first_name", "")
                    voicemail_script = f"Hello {client_name}, this is Alex from Altruis Advisor Group. Please call us back at 8-3-3, 2-2-7, 8-5-0-0. Thank you."
            else:
                voicemail_script = "Hello, this is Alex from Altruis Advisor Group. Please call us back at 8-3-3, 2-2-7, 8-5-0-0. Thank you."
            
            twiml = f"""<?xml version="1.0" encoding="UTF-8"?>
<Response>
    <Say voice="{MALE_VOICE}">{voicemail_script}</Say>
    <Hangup/>
</Response>"""
            
            return Response(content=twiml, media_type="application/xml")
        
        except Exception as e:
            logger.error(f"❌ Voicemail generation error: {e}")
            
            # Emergency voicemail fallback
            emergency_voicemail = "Hello, this is Alex from Altruis Advisor Group. Please call us back at 8-3-3, 2-2-7, 8-5-0-0. Thank you."
            
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
        """Create enhanced no-speech response using voice processor"""
        
        try:
            # Determine response type based on attempt
            if attempt_number == 1:
                response_type = "no_speech_first"
                should_hangup = False
            elif attempt_number == 2:
                response_type = "no_speech_second"
                should_hangup = False
            else:
                response_type = "no_speech_final"
                should_hangup = True
            
            # Try hybrid TTS first
            try:
                from services.hybrid_tts import HybridTTSService
                hybrid_tts = HybridTTSService()
                
                tts_result = await hybrid_tts.get_response_audio(
                    text="",
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
        <Pause length="2"/>
    </Gather>
    <Say voice="{MALE_VOICE}">Thank you for calling. Please call us back at 8-3-3, 2-2-7, 8-5-0-0. Goodbye.</Say>
    <Hangup/>
</Response>"""
                    
                    return Response(content=twiml, media_type="application/xml")
                
            except Exception as hybrid_error:
                logger.warning(f"⚠️ Hybrid TTS failed for no-speech: {hybrid_error}")
            
            # Fallback to TTS
            fallback_texts = {
                1: "I'm sorry, I can't seem to hear you clearly. If you said something, could you please speak a bit louder? I'm here to help.",
                2: "I'm still having trouble hearing you. If you're there, please try speaking directly into your phone. Are you interested in reviewing your health insurance options?",
                3: "I apologize, but I'm having difficulty hearing your response. If you'd like to speak with someone, please call us back at 8-3-3, 2-2-7, 8-5-0-0. Thank you and have a great day."
            }
            
            text = fallback_texts.get(attempt_number, fallback_texts[3])
            
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
    <Gather action="{gather_action}" method="POST" input="speech" actionOnEmptyResult="true" timeout="8" speechTimeout="auto" interruptionAction="{gather_action.replace('process-speech', 'handle-interruption')}">
        <Pause length="2"/>
    </Gather>
    <Say voice="{MALE_VOICE}">Thank you for calling. Goodbye.</Say>
    <Hangup/>
</Response>"""
            
            return Response(content=twiml, media_type="application/xml")
        
        except Exception as e:
            logger.error(f"❌ No speech response error: {e}")
            
            # Emergency no-speech fallback
            emergency_text = "I'm having trouble hearing you. Please call us back at 8-3-3, 2-2-7, 8-5-0-0."
            
            twiml = f"""<?xml version="1.0" encoding="UTF-8"?>
<Response>
    <Say voice="{MALE_VOICE}">{emergency_text}</Say>
    <Hangup/>
</Response>"""
            
            return Response(content=twiml, media_type="application/xml")
    
    @staticmethod
    async def create_hybrid_twiml_response(
        response_type: str,
        text: Optional[str] = None,
        client_data: Optional[Dict[str, Any]] = None,
        should_hangup: bool = False,
        gather_action: str = "/twilio/process-speech"
    ) -> Response:
        """Create TwiML response using hybrid TTS or fallback"""
        
        try:
            # Try hybrid TTS first
            try:
                from services.hybrid_tts import HybridTTSService
                hybrid_tts = HybridTTSService()
                
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
    <Hangup/>
</Response>"""
                    else:
                        twiml = f"""<?xml version="1.0" encoding="UTF-8"?>
<Response>
    <Play>{audio_url}</Play>
    <Gather action="{gather_action}" method="POST" input="speech" actionOnEmptyResult="true" timeout="8" speechTimeout="auto" enhanced="true" interruptionAction="{gather_action.replace('process-speech', 'handle-interruption')}">
        <Pause length="2"/>
    </Gather>
    <Say voice="{MALE_VOICE}">I didn't catch that. Could you please repeat your response?</Say>
    <Say voice="{MALE_VOICE}">Thank you for calling. Please call us back at 8-3-3, 2-2-7, 8-5-0-0. Goodbye.</Say>
    <Hangup/>
</Response>"""
                    
                    return Response(content=twiml, media_type="application/xml")
                
            except Exception as hybrid_error:
                logger.warning(f"⚠️ Hybrid TTS failed: {hybrid_error}")
            
            # Fallback to Say verb
            fallback_text = text or "Thank you for calling."
            
            if should_hangup:
                twiml = f"""<?xml version="1.0" encoding="UTF-8"?>
<Response>
    <Say voice="{MALE_VOICE}">{fallback_text}</Say>
    <Hangup/>
</Response>"""
            else:
                twiml = f"""<?xml version="1.0" encoding="UTF-8"?>
<Response>
    <Say voice="{MALE_VOICE}">{fallback_text}</Say>
    <Gather action="{gather_action}" method="POST" input="speech" timeout="5" speechTimeout="auto" interruptionAction="{gather_action.replace('process-speech', 'handle-interruption')}">
        <Pause length="2"/>
    </Gather>
    <Say voice="{MALE_VOICE}">Thank you for calling. Goodbye.</Say>
    <Hangup/>
</Response>"""
            
            return Response(content=twiml, media_type="application/xml")
        
        except Exception as e:
            logger.error(f"❌ Hybrid TwiML response error: {e}")
            return await EnhancedTwiMLManager.create_emergency_twiml()
    
    @staticmethod
    async def create_emergency_twiml() -> Response:
        """Create emergency TwiML fallback"""
        
        emergency_text = "Thank you for calling. We are experiencing technical difficulties. Please call us back at 8-3-3, 2-2-7, 8-5-0-0."
        
        twiml = f"""<?xml version="1.0" encoding="UTF-8"?>
<Response>
    <Say voice="{MALE_VOICE}">{emergency_text}</Say>
    <Hangup/>
</Response>"""
        
        return Response(content=twiml, media_type="application/xml")
    
    @staticmethod
    async def create_silence_response(
        attempt_number: int,
        client_data: Optional[Dict[str, Any]] = None,
        gather_action: str = "/twilio/process-speech"
    ) -> Response:
        """Create silence detection response using voice processor"""
        
        try:
            # Import voice processor for silence handling
            from services.voice_processor import voice_processor
            
            # Create a temporary session for silence processing
            from shared.models.call_session import CallSession, ConversationStage
            temp_session = CallSession(
                session_id="temp_silence",
                twilio_call_sid="temp",
                client_id="temp",
                phone_number="temp",
                lyzr_agent_id="temp",
                lyzr_session_id="temp",
                conversation_stage=ConversationStage.GREETING,
                client_data=client_data or {}
            )
            
            # Process silence with voice processor
            process_result = await voice_processor._handle_silence_detection(
                session=temp_session,
                silence_count=attempt_number,
                start_time=time.time()
            )
            
            response_text = process_result.get("response_text", "")
            should_hangup = process_result.get("end_conversation", False)
            
            # Determine response type for hybrid TTS
            if attempt_number == 1:
                response_type = "no_speech_first"
            elif attempt_number == 2:
                response_type = "no_speech_second"
            else:
                response_type = "no_speech_final"
            
            # Generate audio using hybrid TTS
            from services.hybrid_tts import hybrid_tts_service
            audio_result = await hybrid_tts_service.get_response_audio(
                text=response_text,
                response_type=response_type,
                client_data=client_data
            )
            
            if audio_result.get("success") and audio_result.get("audio_url"):
                audio_url = audio_result["audio_url"]
                
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
    <Gather action="{gather_action}" method="POST" input="speech" actionOnEmptyResult="true" timeout="8" speechTimeout="auto" enhanced="true" interruptionAction="{gather_action.replace('process-speech', 'handle-interruption')}">
        <Pause length="2"/>
    </Gather>
    <Say voice="{MALE_VOICE}">Thank you for calling. Please call us back at 8-3-3, 2-2-7, 8-5-0-0. Goodbye.</Say>
    <Hangup/>
</Response>"""
            else:
                # Fallback to text-to-speech if audio generation fails
                if should_hangup:
                    twiml = f"""<?xml version="1.0" encoding="UTF-8"?>
<Response>
    <Say voice="{MALE_VOICE}">{response_text}</Say>
    <Hangup/>
</Response>"""
                else:
                    twiml = f"""<?xml version="1.0" encoding="UTF-8"?>
<Response>
    <Say voice="{MALE_VOICE}">{response_text}</Say>
    <Gather action="{gather_action}" method="POST" input="speech" actionOnEmptyResult="true" timeout="8" speechTimeout="auto" enhanced="true">
        <Pause length="2"/>
    </Gather>
    <Say voice="{MALE_VOICE}">Thank you for calling. Please call us back at 8-3-3, 2-2-7, 8-5-0-0. Goodbye.</Say>
    <Hangup/>
</Response>"""
            
            return Response(content=twiml, media_type="application/xml")
            
        except Exception as e:
            logger.error(f"❌ Silence response error: {e}")
            
            # Fallback silence responses using hybrid TTS
            fallback_texts = {
                1: "I'm sorry, I didn't hear anything. Did you say something?",
                2: "I'm sorry, I didn't hear anything. Did you say something?",
                3: "You can call us back at 8-3-3, 2-2-7, 8-5-0-0. Have a great day."
            }
            
            text = fallback_texts.get(attempt_number, fallback_texts[3])
            should_hangup = attempt_number >= 3
            
            # Determine response type for hybrid TTS
            if attempt_number == 1:
                response_type = "no_speech_first"
            elif attempt_number == 2:
                response_type = "no_speech_second"
            else:
                response_type = "no_speech_final"
            
            # Generate audio using hybrid TTS
            from services.hybrid_tts import hybrid_tts_service
            audio_result = await hybrid_tts_service.get_response_audio(
                text=text,
                response_type=response_type,
                client_data=client_data
            )
            
            if audio_result.get("success") and audio_result.get("audio_url"):
                audio_url = audio_result["audio_url"]
                
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
        <Pause length="2"/>
    </Gather>
    <Say voice="{MALE_VOICE}">Thank you for calling. Please call us back at 8-3-3, 2-2-7, 8-5-0-0. Goodbye.</Say>
    <Hangup/>
</Response>"""
            else:
                # Fallback to text-to-speech if audio generation fails
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
        <Pause length="2"/>
    </Gather>
    <Say voice="{MALE_VOICE}">Thank you for calling. Please call us back at 8-3-3, 2-2-7, 8-5-0-0. Goodbye.</Say>
    <Hangup/>
</Response>"""
            
            return Response(content=twiml, media_type="application/xml")
    
    @staticmethod
    async def create_final_silence_response(client_data: Optional[Dict[str, Any]] = None) -> Response:
        """Create final silence response that ends the call"""
        
        try:
            # Generate audio using hybrid TTS
            from services.hybrid_tts import hybrid_tts_service
            audio_result = await hybrid_tts_service.get_response_audio(
                text="You can call us back at 8-3-3, 2-2-7, 8-5-0-0. Have a great day.",
                response_type="no_speech_final",
                client_data=client_data
            )
            
            if audio_result.get("success") and audio_result.get("audio_url"):
                audio_url = audio_result["audio_url"]
                twiml = f"""<?xml version="1.0" encoding="UTF-8"?>
<Response>
    <Play>{audio_url}</Play>
    <Hangup/>
</Response>"""
            else:
                # Fallback to text-to-speech
                twiml = f"""<?xml version="1.0" encoding="UTF-8"?>
<Response>
    <Say voice="{MALE_VOICE}">You can call us back at 8-3-3, 2-2-7, 8-5-0-0. Have a great day.</Say>
    <Hangup/>
</Response>"""
            
            return Response(content=twiml, media_type="application/xml")
            
        except Exception as e:
            logger.error(f"❌ Final silence response error: {e}")
            
            # Emergency fallback
            twiml = f"""<?xml version="1.0" encoding="UTF-8"?>
<Response>
    <Say voice="{MALE_VOICE}">You can call us back at 8-3-3, 2-2-7, 8-5-0-0. Have a great day.</Say>
    <Hangup/>
</Response>"""
            
            return Response(content=twiml, media_type="application/xml")

# Session management functions
async def get_cached_session(call_sid: str) -> Optional[CallSession]:
    """Get session from cache, active sessions, or database with better error handling"""
    try:
        logger.info(f"🔍 Looking for session: {call_sid}")
        logger.info(f"📊 Active sessions count: {len(active_sessions)}")
        logger.info(f"📋 Active session keys: {list(active_sessions.keys())}")
        
        # Try cache first
        try:
            from shared.utils.redis_client import redis_client
            if redis_client:
                # Simple Redis check - implement proper session caching if needed
                pass
        except Exception as redis_error:
            logger.warning(f"⚠️ Redis retrieval failed: {redis_error}")
        
        # Try active sessions
        if call_sid in active_sessions:
            logger.info(f"✅ Found session in active_sessions: {call_sid}")
            return active_sessions[call_sid]
        else:
            logger.warning(f"⚠️ Session not found in active_sessions: {call_sid}")
        
        # Try database
        try:
            from shared.utils.database import db_client
            if db_client is not None and db_client.database is not None:
                doc = await db_client.database.call_sessions.find_one({"twilioCallSid": call_sid})
                if doc:
                    logger.info(f"✅ Found session in database: {call_sid}")
                    # Remove _id field to avoid validation errors
                    if "_id" in doc:
                        del doc["_id"]
                    return CallSession(**doc)
                else:
                    logger.warning(f"⚠️ Session not found in database: {call_sid}")
        except Exception as db_error:
            logger.warning(f"⚠️ Database retrieval failed: {db_error}")
        
        logger.error(f"❌ Session not found anywhere: {call_sid}")
        return None
    except Exception as e:
        logger.error(f"❌ Get cached session failed: {e}")
        return None

async def enhanced_cache_session(session: CallSession):
    """Save session to multiple storage locations"""
    try:
        # CRITICAL: Save to active sessions first (in-memory)
        if session.twilio_call_sid:
            active_sessions[session.twilio_call_sid] = session
            logger.info(f"💾 Session saved to active_sessions: {session.twilio_call_sid}")
        else:
            logger.warning(f"⚠️ Cannot save session: twilio_call_sid is None")
            return
        
        # Try to save to Redis cache
        try:
            from shared.utils.redis_client import redis_client
            if redis_client:
                # Implement Redis caching if needed
                pass
        except Exception as redis_error:
            logger.warning(f"⚠️ Redis caching failed: {redis_error}")
        
        # Try to save to database
        try:
            from shared.utils.database import db_client
            if db_client is not None and db_client.database is not None:
                # Ensure twilio_call_sid is set before saving
                if not session.twilio_call_sid:
                    logger.warning(f"⚠️ twilio_call_sid is None, cannot save to database")
                    return
                
                # Use model_dump with by_alias=True to handle field aliases properly
                session_dict = session.model_dump(by_alias=True)
                # Don't set _id manually - let MongoDB generate it
                if "_id" in session_dict:
                    del session_dict["_id"]
                
                # Use session_id as the query key if twilio_call_sid is not available
                query_key = {"twilioCallSid": session.twilio_call_sid} if session.twilio_call_sid else {"session_id": session.session_id}
                
                await db_client.database.call_sessions.replace_one(
                    query_key,
                    session_dict,
                    upsert=True
                )
                logger.info(f"💾 Session saved to database: {session.twilio_call_sid}")
        except Exception as db_error:
            logger.warning(f"⚠️ Database caching failed: {db_error}")
    
    except Exception as e:
        logger.error(f"❌ Enhanced cache session failed: {e}")
        # Even if caching fails, ensure session is in active_sessions
        if session.twilio_call_sid:
            active_sessions[session.twilio_call_sid] = session
            logger.info(f"💾 Session saved to active_sessions as fallback: {session.twilio_call_sid}")

async def get_client_data_by_phone(phone_number: str) -> Optional[Dict[str, Any]]:
    """Get client data from database by phone number"""
    try:
        logger.info(f"🔍 Looking up client data for phone: {phone_number}")
        
        # Clean phone number - remove all non-digits
        clean_phone = ''.join(filter(str.isdigit, phone_number))
        logger.info(f"🔍 Cleaned phone number: {clean_phone}")
        
        # Try to get from database
        try:
            from shared.utils.database import db_client
            if db_client is not None and db_client.database is not None:
                logger.info(f"🔍 Database connection available, searching for client...")
                
                # Try multiple phone number formats
                search_variations = []
                
                # Original format
                search_variations.append(phone_number)
                
                # Clean digits only
                if len(clean_phone) >= 10:
                    search_variations.append(clean_phone)
                    search_variations.append(int(clean_phone))
                
                # International format variations
                if phone_number.startswith('+'):
                    # Remove + and try
                    without_plus = phone_number[1:]
                    search_variations.append(without_plus)
                    search_variations.append(int(without_plus))
                
                # Add +1 prefix if it's a 10-digit US number
                if len(clean_phone) == 10:
                    search_variations.append(f"+1{clean_phone}")
                
                # Try each variation
                for variation in search_variations:
                    logger.info(f"🔍 Trying phone variation: {variation}")
                    
                    # Try different field names that might contain phone
                    search_queries = [
                        {"client.phone": variation},
                        {"phone": variation},
                        {"phone_number": variation},
                        {"client.phone_number": variation}
                    ]
                    
                    for query in search_queries:
                        doc = await db_client.database.clients.find_one(query)
                        if doc:
                            client_info = doc.get("client", {})
                            first_name = client_info.get('firstName', client_info.get('first_name', ''))
                            last_name = client_info.get('lastName', client_info.get('last_name', ''))
                            logger.info(f"✅ Found client: {first_name} {last_name}")
                            
                            return {
                                "first_name": first_name,
                                "last_name": last_name,
                                "phone": client_info.get("phone", client_info.get("phone_number", "")),
                                "email": client_info.get("email", ""),
                                "tags": doc.get("tags", ""),
                                "last_agent": client_info.get("lastAgent", client_info.get("last_agent", ""))
                            }
                
                # If no client found, let's debug what's in the database
                logger.warning(f"⚠️ No client found in database for phone: {phone_number}")
                logger.warning(f"⚠️ Tried variations: {search_variations}")
                
                # Get sample clients for debugging
                try:
                    sample_clients = await db_client.database.clients.find().limit(5).to_list(length=5)
                    logger.info(f"🔍 Sample clients in database:")
                    for i, client in enumerate(sample_clients):
                        client_data = client.get('client', {})
                        phone = client_data.get('phone', client_data.get('phone_number', 'No phone'))
                        name = f"{client_data.get('firstName', client_data.get('first_name', ''))} {client_data.get('lastName', client_data.get('last_name', ''))}"
                        logger.info(f"   {i+1}. {name} - Phone: {phone}")
                except Exception as sample_error:
                    logger.warning(f"⚠️ Could not get sample clients: {sample_error}")
                    
            else:
                logger.warning(f"⚠️ Database not available for client lookup")
        except Exception as db_error:
            logger.warning(f"⚠️ Database client lookup failed: {db_error}")
        
        # If no client found in database, return None instead of fallback
        logger.warning(f"⚠️ No client data found in database for phone: {phone_number}")
        return None
        
    except Exception as e:
        logger.error(f"❌ Error getting client data: {e}")
        return None

async def create_or_get_session(
    call_sid: str, 
    from_number: str, 
    to_number: str,
    client_data: Optional[Dict[str, Any]] = None
) -> CallSession:
    """Create new session or get existing one"""
    try:
        # Check if session already exists
        existing_session = await get_cached_session(call_sid)
        if existing_session:
            return existing_session
        
        # Create new session
        session = CallSession(
            session_id=str(uuid.uuid4()),
            twilio_call_sid=call_sid,  # This should be the actual call_sid
            client_id=client_data.get("client_id", "unknown") if client_data else "unknown",
            phone_number=from_number,
            call_status=CallStatusEnum.INITIATED,
            conversation_stage=ConversationStage.GREETING,
            conversation_turns=[],
            client_data=client_data or {},
            started_at=datetime.utcnow(),
            no_speech_count=0,
            lyzr_agent_id=getattr(settings, 'lyzr_conversation_agent_id', 'default_agent'),
            lyzr_session_id=f"session_{uuid.uuid4().hex[:8]}"
        )
        
        # Ensure twilio_call_sid is set properly
        if not session.twilio_call_sid:
            logger.warning(f"⚠️ twilio_call_sid was not set properly, setting it manually: {call_sid}")
            session.twilio_call_sid = call_sid
        
        return session
        
    except Exception as e:
        logger.error(f"❌ Error creating session: {e}")
        # Return minimal session
        return CallSession(
            session_id=str(uuid.uuid4()),
            twilio_call_sid=call_sid,
            client_id="unknown",
            phone_number=from_number,
            call_status=CallStatusEnum.INITIATED,
            conversation_stage=ConversationStage.GREETING,
            conversation_turns=[],
            client_data={},
            started_at=datetime.utcnow(),
            no_speech_count=0,
            lyzr_agent_id=getattr(settings, 'lyzr_conversation_agent_id', 'default_agent'),
            lyzr_session_id=f"session_{uuid.uuid4().hex[:8]}"
        )

# Webhook endpoints

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
    """Enhanced voice webhook with voicemail detection, start delay, and client type support"""
    
    logger.info(f"📞 Voice webhook: {CallSid} - Status: {CallStatus} - From: {From} - To: {To} - AnsweredBy: {AnsweredBy}")
    logger.info(f"🔍 Machine detection debug - AnsweredBy: '{AnsweredBy}' (type: {type(AnsweredBy)})")
    
    try:
        # Handle answering machine detection
        logger.info(f"🔍 Checking machine detection - AnsweredBy: '{AnsweredBy}'")
        if AnsweredBy == "machine":
            logger.info(f"📱 Voicemail detected for {CallSid}")
            
            # Get client data for personalized voicemail
            client_data = await get_client_data_by_phone(To)
            
            return await EnhancedTwiMLManager.create_voicemail_response(client_data)
        
        # Handle live person answer
        elif AnsweredBy in ["human", None]:  # None means we couldn't detect
            logger.info(f"👤 Live person answered: {CallSid}")
            
            # Get client data to determine appropriate script
            client_data = await get_client_data_by_phone(To)
            
            # If no client data found, create a generic client data structure
            if not client_data:
                logger.warning(f"⚠️ No client data found for {To}, using generic greeting")
                client_data = {
                    "first_name": "there",
                    "last_name": "",
                    "phone": To,
                    "email": "",
                    "tags": "Unknown",
                    "last_agent": "our team"
                }
            
            # Create or update session
            session = await create_or_get_session(CallSid, From, To, client_data)
            
            # Initialize session state
            session.conversation_stage = ConversationStage.GREETING
            session.call_status = CallStatusEnum.IN_PROGRESS
            session.no_speech_count = 0
            
            # CRITICAL: Save session to active_sessions immediately
            active_sessions[CallSid] = session
            logger.info(f"💾 Session immediately saved to active_sessions: {CallSid}")
            
            # Save session to other storage
            await enhanced_cache_session(session)
            
            # Create greeting with 2-second delay and client-type appropriate script
            gather_action = f"{getattr(settings, 'base_url', 'http://localhost:8000')}/twilio/process-speech"
            return await EnhancedTwiMLManager.create_greeting_with_delay(
                client_data=session.client_data,
                gather_action=gather_action
            )
        
        else:
            # Fallback for unknown answer type - treat as human answer
            logger.warning(f"⚠️ Unknown answer type: {AnsweredBy}, treating as human answer")
            
            # Get client data to determine appropriate script
            client_data = await get_client_data_by_phone(To)
            
            # Create or update session
            session = await create_or_get_session(CallSid, From, To, client_data)
            
            # Initialize session state
            session.conversation_stage = ConversationStage.GREETING
            session.call_status = CallStatusEnum.IN_PROGRESS
            session.no_speech_count = 0
            
            # CRITICAL: Save session to active_sessions immediately
            active_sessions[CallSid] = session
            logger.info(f"💾 Session immediately saved to active_sessions: {CallSid}")
            
            # Save session to other storage
            await enhanced_cache_session(session)
            
            # Create greeting with 2-second delay and client-type appropriate script
            gather_action = f"{getattr(settings, 'base_url', 'http://localhost:8000')}/twilio/process-speech"
            return await EnhancedTwiMLManager.create_greeting_with_delay(
                client_data=session.client_data,
                gather_action=gather_action
            )
        
    except Exception as e:
        logger.error(f"❌ Voice webhook error: {e}")
        import traceback
        logger.error(traceback.format_exc())
        
        return await EnhancedTwiMLManager.create_emergency_twiml()

@router.post("/process-speech")
async def process_speech_webhook(
    request: Request,
    CallSid: str = Form(...),
    SpeechResult: Optional[str] = Form(None),
    Confidence: Optional[float] = Form(None),
    UnstableSpeechResult: Optional[str] = Form(None)
):
    """Process customer speech with enhanced voice processor and silence detection"""
    
    logger.info(f"🗣️ Processing speech: {CallSid} - '{SpeechResult}' - Confidence: {Confidence}")
    logger.info(f"🔍 Speech debug - SpeechResult: '{SpeechResult}' (type: {type(SpeechResult)}) - Unstable: '{UnstableSpeechResult}'")
    
    try:
        # Get session
        session = active_sessions.get(CallSid) or await get_cached_session(CallSid)
        
        if not session:
            logger.error(f"❌ Session not found for speech processing: {CallSid}")
            logger.info(f"🔄 Attempting to create emergency session for: {CallSid}")
            
            # Create emergency session to prevent complete failure
            try:
                emergency_session = CallSession(
                    session_id=str(uuid.uuid4()),
                    twilio_call_sid=CallSid,
                    client_id="emergency",
                    phone_number="unknown",
                    call_status=CallStatusEnum.IN_PROGRESS,
                    conversation_stage=ConversationStage.GREETING,
                    conversation_turns=[],
                    client_data={"first_name": "Customer"},
                    started_at=datetime.utcnow(),
                    no_speech_count=0,
                    lyzr_agent_id=getattr(settings, 'lyzr_conversation_agent_id', 'default_agent'),
                    lyzr_session_id=f"emergency_{uuid.uuid4().hex[:8]}"
                )
                
                # Save emergency session
                active_sessions[CallSid] = emergency_session
                logger.info(f"✅ Emergency session created: {CallSid}")
                session = emergency_session
                
            except Exception as emergency_error:
                logger.error(f"❌ Failed to create emergency session: {emergency_error}")
                return await EnhancedTwiMLManager.create_emergency_twiml()
        
        logger.info(f"✅ Session found for speech: {CallSid} - Stage: {session.conversation_stage}")
        
        # Handle silence (no speech detected)
        if not SpeechResult or SpeechResult.strip() == "":
            session.no_speech_count += 1
            logger.info(f"🔇 Silence detected (attempt {session.no_speech_count}) for {CallSid}")
            
            # Save updated session
            await enhanced_cache_session(session)
            
            # Handle silence with progressive responses
            if session.no_speech_count <= 3:
                return await EnhancedTwiMLManager.create_silence_response(
                    attempt_number=session.no_speech_count,
                    client_data=session.client_data
                )
            else:
                # End call after 3 silence attempts
                return await EnhancedTwiMLManager.create_final_silence_response()
        
        # Process customer input with enhanced voice processor
        process_result = await voice_processor.process_customer_input(
            customer_input=SpeechResult,
            session=session,
            confidence=Confidence or 0.0
        )
        
        logger.info(f"🔄 Speech processed - Response: '{process_result.get('response_text', '')}' - Category: {process_result.get('response_category', '')}")
        
        # Update conversation history
        turn = ConversationTurn(
            turn_number=len(session.conversation_turns) + 1,
            customer_speech=SpeechResult,
            customer_speech_confidence=Confidence,
            agent_response=process_result.get("response_text", ""),
            response_type=ResponseType.HYBRID,
            conversation_stage=session.conversation_stage
        )
        session.conversation_turns.append(turn)
        
        # Update session state
        session.conversation_stage = process_result.get("conversation_stage", session.conversation_stage)
        session.no_speech_count = 0  # Reset on successful speech
        
        # Save updated session
        await enhanced_cache_session(session)
        
        # Generate TwiML response
        gather_action = f"{getattr(settings, 'base_url', 'http://localhost:8000')}/twilio/process-speech"
        return await EnhancedTwiMLManager.create_hybrid_twiml_response(
            response_type=process_result.get("response_category", "dynamic"),
            text=process_result.get("response_text"),
            client_data=session.client_data,
            should_hangup=process_result.get("end_conversation", False),
            gather_action=gather_action
        )
        
    except Exception as e:
        logger.error(f"❌ Speech processing error: {e}")
        import traceback
        logger.error(traceback.format_exc())
        
        return await EnhancedTwiMLManager.create_emergency_twiml()

@router.post("/handle-interruption")
async def handle_interruption(
    request: Request,
    CallSid: str = Form(...),
    SpeechResult: Optional[str] = Form(None),
    Confidence: Optional[float] = Form(None)
):
    """Handle customer interruptions while agent is speaking"""
    
    logger.info(f"🛑 Interruption detected: {CallSid} - '{SpeechResult}' - Confidence: {Confidence}")
    logger.info(f"🔍 Interruption debug - SpeechResult: '{SpeechResult}' (type: {type(SpeechResult)})")
    
    try:
        session = active_sessions.get(CallSid) or await get_cached_session(CallSid)
        
        if not session:
            logger.error(f"❌ Session not found for interruption: {CallSid}")
            return await EnhancedTwiMLManager.create_emergency_twiml()
        
        logger.info(f"✅ Session found for interruption: {CallSid} - Stage: {session.conversation_stage}")
        
        # Process interruption with voice processor
        process_result = await voice_processor.process_customer_input(
            customer_input=SpeechResult or "",
            session=session,
            confidence=Confidence or 0.0,
            is_interruption=True
        )
        
        logger.info(f"🔄 Interruption processed - Response: '{process_result.get('response_text', '')}' - Category: {process_result.get('response_category', '')}")
        
        # Update conversation turn for interruption
        turn = ConversationTurn(
            turn_number=len(session.conversation_turns) + 1,
            customer_speech=SpeechResult or "[INTERRUPTION]",
            customer_speech_confidence=Confidence,
            agent_response=process_result.get("response_text", ""),
            response_type=ResponseType.HYBRID,
            conversation_stage=session.conversation_stage
        )
        session.conversation_turns.append(turn)
        
        # Save updated session
        await enhanced_cache_session(session)
        
        gather_action = f"{getattr(settings, 'base_url', 'http://localhost:8000')}/twilio/process-speech"
        return await EnhancedTwiMLManager.create_hybrid_twiml_response(
            response_type=process_result.get("response_category", "interruption_acknowledgment"),
            text=process_result.get("response_text"),
            client_data=session.client_data,
            should_hangup=process_result.get("end_conversation", False),
            gather_action=gather_action
        )
        
    except Exception as e:
        logger.error(f"❌ Interruption handling error: {e}")
        import traceback
        logger.error(traceback.format_exc())
        return await EnhancedTwiMLManager.create_emergency_twiml()

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
            session = active_sessions.get(CallSid) or await get_cached_session(CallSid)
            
            if session:
                # Update final status
                try:
                    session.call_status = CallStatusEnum(CallStatus)
                except ValueError:
                    session.call_status = CallStatusEnum.COMPLETED
                
                session.completed_at = datetime.utcnow()
                
                # Calculate duration
                if session.started_at and session.completed_at:
                    duration = (session.completed_at - session.started_at).total_seconds()
                    if not hasattr(session, 'session_metrics'):
                        session.session_metrics = SessionMetrics()
                    session.session_metrics.total_call_duration_seconds = duration
                
                # Determine final outcome based on conversation
                if hasattr(session, 'conversation_turns') and session.conversation_turns:
                    # Analyze the entire conversation to determine outcome
                    session.final_outcome = _analyze_conversation_outcome(session.conversation_turns)
                else:
                    session.final_outcome = CallStatus
                
                # Save final session state to database
                try:
                    from shared.utils.database import db_client
                    if db_client is not None and db_client.database is not None:
                        # Use model_dump with by_alias=True to handle field aliases properly
                        session_dict = session.model_dump(by_alias=True)
                        # Don't set _id manually - let MongoDB generate it
                        if "_id" in session_dict:
                            del session_dict["_id"]
                        
                        # Use session_id as the query key if twilio_call_sid is not available
                        query_key = {"twilioCallSid": CallSid} if CallSid else {"session_id": session.session_id}
                        
                        await db_client.database.call_sessions.replace_one(
                            query_key,
                            session_dict,
                            upsert=True
                        )
                        logger.info(f"💾 Final session saved to database: {CallSid}")
                except Exception as db_error:
                    logger.error(f"❌ Database save error: {db_error}")
                
                # Clean up active session
                if CallSid in active_sessions:
                    del active_sessions[CallSid]
                    logger.info(f"🧹 Cleaned up active session: {CallSid}")
        
        return {"status": "ok", "call_sid": CallSid, "processed": True}
        
    except Exception as e:
        logger.error(f"❌ Status webhook error: {e}")
        return {"status": "error", "message": str(e), "call_sid": CallSid}

def _analyze_conversation_outcome(conversation_turns: List[ConversationTurn]) -> str:
        """Analyze conversation turns to determine the final outcome based on AAG script"""
        if not conversation_turns:
            return "completed"
        
        # Look for specific keywords in customer speech across all turns
        customer_speech_combined = " ".join([
            turn.customer_speech.lower() for turn in conversation_turns 
            if turn.customer_speech
        ])
        
        # Check for DNC-related keywords (highest priority)
        dnc_keywords = [
            "remove", "delete", "don't call", "stop calling", "take me off",
            "unsubscribe", "never call", "no more calls", "do not contact"
        ]
        
        # Check for scheduling-related keywords
        scheduling_keywords = [
            "schedule", "appointment", "meeting", "tomorrow", "next week", 
            "available", "time", "when", "book", "reserve", "calendar", "yes"
        ]
        
        # Check for interest-related keywords (first "Yes")
        interested_keywords = [
            "interested", "yes", "sure", "okay", "alright", "good", "great",
            "definitely", "absolutely", "love to", "would like", "want to"
        ]
        
        # Check for disinterest-related keywords (first "No")
        not_interested_keywords = [
            "not interested", "no thanks", "no thank you", "not right now",
            "maybe later", "call back", "busy", "not now", "don't want", "no"
        ]
        
        # Check for voicemail indicators
        voicemail_indicators = [
            "voicemail", "leave a message", "beep", "recording", "after the tone"
        ]
        
        # Analyze the conversation based on AAG script flow
        if any(keyword in customer_speech_combined for keyword in dnc_keywords):
            return "dnc_requested"
        elif any(keyword in customer_speech_combined for keyword in voicemail_indicators):
            return "voicemail"
        elif any(keyword in customer_speech_combined for keyword in scheduling_keywords):
            # Check if it's morning or afternoon preference
            if any(word in customer_speech_combined for word in ["morning", "am", "9", "10", "11"]):
                return "send_email_invite"  # Will send calendar invite
            elif any(word in customer_speech_combined for word in ["afternoon", "pm", "2", "3", "4"]):
                return "send_email_invite"  # Will send calendar invite
            else:
                return "send_email_invite"  # Will send calendar invite
        elif any(keyword in customer_speech_combined for keyword in interested_keywords):
            return "interested"  # First "Yes" - agent will reach out
        elif any(keyword in customer_speech_combined for keyword in not_interested_keywords):
            return "not_interested"
        else:
            # If no specific outcome detected, check conversation length
            if len(conversation_turns) < 3:
                return "no_contact"  # Short conversation might indicate no answer
            else:
                return "completed"  # Default fallback

@router.get("/test-connection")
async def test_connection():
    """Test endpoint for connection verification"""
    return {
        "status": "ok",
        "message": "Enhanced Twilio router is active",
        "active_sessions": len(active_sessions),
        "timestamp": datetime.utcnow().isoformat(),
        "features": {
            "voicemail_detection": True,
            "start_delay": True,
            "client_type_detection": True,
            "interruption_handling": True,
            "no_speech_fallbacks": True,
            "enhanced_voice_processing": True
        }
    }

@router.get("/active-sessions")
async def get_active_sessions():
    """Get information about currently active sessions"""
    try:
        session_info = []
        for call_sid, session in active_sessions.items():
            session_info.append({
                "call_sid": call_sid,
                "session_id": session.session_id,
                "phone_number": session.phone_number,
                "call_status": session.call_status.value if session.call_status else "unknown",
                "conversation_stage": session.conversation_stage.value if session.conversation_stage and hasattr(session.conversation_stage, 'value') else (session.conversation_stage if session.conversation_stage else "unknown"),
                "turns": len(session.conversation_turns) if session.conversation_turns else 0,
                "started_at": session.started_at.isoformat() if session.started_at else None,
                "client_name": f"{session.client_data.get('first_name', '')} {session.client_data.get('last_name', '')}".strip() if session.client_data else "Unknown"
            })
        
        return {
            "active_sessions": session_info,
            "total_active": len(active_sessions),
            "timestamp": datetime.utcnow().isoformat()
        }
        
    except Exception as e:
        logger.error(f"❌ Active sessions error: {e}")
        return {
            "error": str(e),
            "active_sessions": [],
            "total_active": 0
        }

@router.post("/cleanup-session/{call_sid}")
async def cleanup_session(call_sid: str):
    """Manually cleanup a session (for testing/debugging)"""
    try:
        if call_sid in active_sessions:
            session = active_sessions[call_sid]
            
            # Save to database before cleanup
            try:
                from shared.utils.database import db_client
                if db_client is not None and db_client.database is not None:
                    session_dict = session.model_dump(by_alias=True)
                    # Don't set _id manually - let MongoDB generate it
                    if "_id" in session_dict:
                        del session_dict["_id"]
                    await db_client.database.call_sessions.replace_one(
                        {"twilioCallSid": call_sid},
                        session_dict,
                        upsert=True
                    )
            except Exception as db_error:
                logger.warning(f"⚠️ Database save during cleanup failed: {db_error}")
            
            # Remove from active sessions
            del active_sessions[call_sid]
            
            return {
                "success": True,
                "message": f"Session {call_sid} cleaned up successfully",
                "session_id": session.session_id
            }
        else:
            return {
                "success": False,
                "message": f"Session {call_sid} not found in active sessions"
            }
            
    except Exception as e:
        logger.error(f"❌ Session cleanup error: {e}")
        return {
            "success": False,
            "error": str(e)
        }

@router.get("/debug/{call_sid}")
async def debug_session(call_sid: str):
    """Debug endpoint to get detailed session information"""
    try:
        debug_info = {
            "call_sid": call_sid,
            "timestamp": datetime.utcnow().isoformat(),
            "active_session": None,
            "database_session": None,
            "found_in": []
        }
        
        # Check active sessions
        if call_sid in active_sessions:
            session = active_sessions[call_sid]
            debug_info["active_session"] = {
                "session_id": session.session_id,
                "phone_number": session.phone_number,
                "call_status": session.call_status.value if session.call_status else None,
                "conversation_stage": session.conversation_stage.value if session.conversation_stage and hasattr(session.conversation_stage, 'value') else (session.conversation_stage if session.conversation_stage else None),
                "turns": len(session.conversation_turns) if session.conversation_turns else 0,
                "started_at": session.started_at.isoformat() if session.started_at else None,
                "client_data": session.client_data,
                "no_speech_count": getattr(session, 'no_speech_count', 0)
            }
            debug_info["found_in"].append("active_sessions")
        
        # Check database
        try:
            from shared.utils.database import db_client
            if db_client is not None and db_client.database is not None:
                doc = await db_client.database.call_sessions.find_one({"twilioCallSid": call_sid})
                if doc:
                    debug_info["database_session"] = {
                        "session_id": doc.get("session_id"),
                        "call_status": doc.get("call_status"),
                        "final_outcome": doc.get("final_outcome"),
                        "turns": len(doc.get("conversation_turns", [])),
                        "started_at": doc.get("started_at").isoformat() if doc.get("started_at") else None,
                        "completed_at": doc.get("completed_at").isoformat() if doc.get("completed_at") else None
                    }
                    debug_info["found_in"].append("database")
        except Exception as db_error:
            debug_info["database_error"] = str(db_error)
        
        if not debug_info["found_in"]:
            debug_info["found_in"] = ["nowhere"]
            debug_info["message"] = "Session not found in any storage location"
        
        return debug_info
        
    except Exception as e:
        logger.error(f"❌ Debug session error: {e}")
        return {
            "call_sid": call_sid,
            "error": str(e),
            "timestamp": datetime.utcnow().isoformat()
        }

# Health check endpoint
@router.get("/health")
async def twilio_router_health():
    """Health check for Twilio router"""
    return {
        "status": "healthy",
        "service": "twilio-router",
        "active_sessions": len(active_sessions),
        "features": {
            "voicemail_detection": True,
            "start_delay": True,
            "client_type_detection": True,
            "interruption_handling": True,
            "no_speech_fallbacks": True
        },
        "timestamp": datetime.utcnow().isoformat()
    }