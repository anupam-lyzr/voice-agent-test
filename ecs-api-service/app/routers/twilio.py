"""
Production-Ready Twilio Router
Handles all customer responses with hybrid TTS and complete conversation flow
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

# Emergency fallback greeting
def create_emergency_greeting_twiml(client_name: str = "there") -> str:
    """Create emergency greeting TwiML when services fail"""
    return f'''<?xml version="1.0" encoding="UTF-8"?>
<Response>
    <Say voice="Polly.Joanna">Hello {client_name}, this is Alex from Altruis Advisor Group. We're experiencing technical difficulties. Please call us back later. Thank you.</Say>
    <Hangup/>
</Response>'''

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


async def cache_session(session: CallSession):
    """Cache session with proper twilio_call_sid setting"""
    try:
        # Ensure twilio_call_sid is set (was causing duplicate key errors)
        if not session.twilio_call_sid and hasattr(session, 'CallSid'):
            session.twilio_call_sid = session.CallSid
        
        # Additional validation to prevent null twilio_call_sid
        if not session.twilio_call_sid:
            logger.error(f"❌ Cannot cache session {session.session_id}: twilio_call_sid is None")
            return
        
        # Try Redis cache first
        from shared.utils.redis_client import session_cache
        if session_cache:
            await session_cache.save_session(session)
            logger.info(f"✅ Session cached in Redis: {session.session_id} (twilio_call_sid: {session.twilio_call_sid})")
        
        # Also save to database - but handle duplicate key errors
        session_repo = await get_session_repo()
        if session_repo:
            try:
                # Ensure twilio_call_sid is properly set
                if not session.twilio_call_sid:
                    logger.warning(f"⚠️ Session {session.session_id} has no twilio_call_sid")
                    return
                
                await session_repo.save_session(session)
                logger.info(f"✅ Session saved to database: {session.session_id}")
            except Exception as e:
                if "duplicate key" in str(e):
                    # Try to update instead
                    logger.warning(f"⚠️ Duplicate key, attempting update: {e}")
                    from shared.utils.database import db_client
                    if db_client is not None and db_client.database is not None:
                        # Try by session_id first, then by twilio_call_sid
                        try:
                            await db_client.database.call_sessions.replace_one(
                                {"session_id": session.session_id},
                                session.dict(by_alias=True),
                                upsert=True
                            )
                            logger.info(f"✅ Session updated via upsert: {session.session_id}")
                        except Exception as upsert_error:
                            logger.error(f"❌ Upsert failed: {upsert_error}")
                            # Try to delete and re-insert
                            try:
                                await db_client.database.call_sessions.delete_one({"twilio_call_sid": session.twilio_call_sid})
                                await session_repo.save_session(session)
                                logger.info(f"✅ Session re-saved after cleanup: {session.session_id}")
                            except Exception as cleanup_error:
                                logger.error(f"❌ Cleanup failed: {cleanup_error}")
                else:
                    logger.error(f"❌ Failed to save session to database: {e}")
    except Exception as e:
        logger.error(f"❌ Failed to cache session: {e}")

async def get_cached_session(call_sid: str) -> Optional[CallSession]:
    """Get cached session with fallback to database"""
    try:
        # Try cache first
        from shared.utils.redis_client import session_cache
        if session_cache:
            session = await session_cache.get_session(call_sid)
            if session:
                return session
        
        # Try active sessions
        if call_sid in active_sessions:
            return active_sessions[call_sid]
        
        # Try database
        session_repo = await get_session_repo()
        if session_repo:
            # Search by twilio_call_sid
            from shared.utils.database import db_client
            if db_client is not None and db_client.database is not None:
                doc = await db_client.database.call_sessions.find_one({"twilio_call_sid": call_sid})
                if doc:
                    return CallSession(**doc)
        
        return None
    except Exception as e:
        logger.error(f"Failed to get cached session: {e}")
        return None

async def create_hybrid_twiml_response(
    response_type: str, 
    text: Optional[str] = None,
    client_data: Optional[Dict[str, Any]] = None,
    gather_action: str = "/twilio/process-speech",
    should_hangup: bool = False,
    should_gather: bool = True
) -> Response:
    """Create TwiML response using hybrid TTS service for optimal performance"""
    
    try:
        logger.info(f"🎵 Creating hybrid TwiML for: {response_type}")
        
        # Get audio using hybrid TTS service
        tts_result = await hybrid_tts.get_response_audio(
            text=text or "",
            response_type=response_type,
            client_data=client_data
        )
        
        if tts_result.get("success") and tts_result.get("audio_url"):
            audio_url = tts_result["audio_url"]
            audio_type = tts_result.get("type", "unknown")
            generation_time = tts_result.get("generation_time_ms", 0)
            
            logger.info(f"✅ Hybrid audio ready: {audio_type} in {generation_time}ms")
            
            # Build TwiML based on requirements
            if should_hangup:
                twiml = f"""<?xml version="1.0" encoding="UTF-8"?>
<Response>
    <Pause length="2"/>
    <Play>{audio_url}</Play>
    <Pause length="1"/>
    <Hangup/>
</Response>"""
            elif should_gather:
                twiml = f"""<?xml version="1.0" encoding="UTF-8"?>
<Response>
    <Play>{audio_url}</Play>
    <Gather action="{gather_action}" actionOnEmptyResult="true" method="POST" input="speech" timeout="8" speechTimeout="auto" enhanced="true">
        <Pause length="1"/>
    </Gather>
    <Say voice="Polly.Joanna">I didn't catch that. Could you please repeat your response?</Say>
    <Pause length="2"/>
    <Say voice="Polly.Joanna">Thank you for calling. Goodbye.</Say>
    <Hangup/>
</Response>"""
            else:
                # No gather, just play and continue
                twiml = f"""<?xml version="1.0" encoding="UTF-8"?>
<Response>
    <Play>{audio_url}</Play>
</Response>"""
            
            return Response(content=twiml, media_type="application/xml")
        
        # Fallback if hybrid TTS fails
        logger.warning(f"⚠️ Hybrid TTS failed for {response_type}, using fallback")
        client_name = client_data.get("client_name", "there") if client_data else "there"
        
        if should_hangup:
            fallback_twiml = f"""<?xml version="1.0" encoding="UTF-8"?>
<Response>
    <Say voice="Polly.Joanna">Thank you for your time, {client_name}. Have a wonderful day!</Say>
    <Hangup/>
</Response>"""
        else:
            fallback_twiml = create_emergency_greeting_twiml(client_name)
        
        return Response(content=fallback_twiml, media_type="application/xml")
        
    except Exception as e:
        logger.error(f"❌ Hybrid TwiML generation error: {e}")
        import traceback
        logger.error(traceback.format_exc())
        
        # Emergency fallback
        client_name = client_data.get("client_name", "there") if client_data else "there"
        return Response(content=create_emergency_greeting_twiml(client_name), media_type="application/xml")

@router.post("/voice")
async def voice_webhook(
    request: Request,
    CallSid: str = Form(...),
    CallStatus: Optional[str] = Form(None),
    From: Optional[str] = Form(None),
    To: Optional[str] = Form(None),
    Direction: Optional[str] = Form(None),
    is_test_call: Optional[str] = Form(None)
):
    """Handle incoming voice calls with complete AAG conversation flow"""
    
    logger.info(f"📞 Voice webhook: {CallSid} - Status: {CallStatus} - From: {From} - To: {To} - Direction: {Direction} - is_test_call: {is_test_call}")
    
    try:
        if CallStatus == "in-progress":
            # Determine client phone based on call direction
            client_phone = To if Direction == "outbound-api" else From
            logger.info(f"🔍 Looking up client by phone: {client_phone}")
            form_data = await request.form()
            logger.info(f"All form data: {dict(form_data)}")
            
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
                logger.info(f"✅ Found client: {client.client.first_name} (Agent: {client.client.last_agent})")
            else:
                logger.warning(f"⚠️ Client not found for phone: {client_phone}")
            
            # Check if there's already a cached session for this call (e.g., from test call creation)
            cached_session = await get_cached_session(CallSid)
            
            if cached_session:
                # Use the cached session and update it
                session = cached_session
                session.call_status = CallStatusEnum.IN_PROGRESS
                session.answered_at = datetime.utcnow()
                session.conversation_stage = ConversationStage.GREETING
                logger.info(f"✅ Using cached session for {CallSid}, is_test_call: {session.is_test_call}")
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
            await cache_session(session)
            
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
            
            # Return greeting using hybrid TTS
            return await create_hybrid_twiml_response(
                response_type="greeting",
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
        
        # Return emergency fallback
        return Response(
            content=create_emergency_greeting_twiml(),
            media_type="application/xml"
        )


@router.post("/process-speech")
async def process_speech_webhook(
    request: Request,
    CallSid: str = Form(...),
    SpeechResult: Optional[str] = Form(None),
    Confidence: Optional[float] = Form(None),
    UnstableSpeechResult: Optional[str] = Form(None)
):
    """Process customer speech with complete conversation handling"""
    
    # Use UnstableSpeechResult if SpeechResult is empty for better responsiveness
    if not SpeechResult and UnstableSpeechResult:
        SpeechResult = UnstableSpeechResult
        logger.info(f"🎤 Using unstable speech result: '{SpeechResult}'")
    
    logger.info(f"🎤 Processing speech: {CallSid} - Result: '{SpeechResult}' - Confidence: {Confidence}")
    
    try:
        # Get the session from active memory or fall back to cache
        session = active_sessions.get(CallSid)
        if not session:
            session = await get_cached_session(CallSid)
            if session:
                active_sessions[CallSid] = session
                logger.info(f"✅ Restored session from cache: {CallSid}")
        
        if not session:
            logger.error(f"❌ CRITICAL: Session not found for CallSid: {CallSid}. Cannot continue.")
            return Response(
                content=create_hangup_twiml("I'm sorry, there was a problem with the call. Please call us back."),
                media_type="application/xml"
            )
        
        # Initialize no_speech_count if not present
        if not hasattr(session, 'no_speech_count'):
            session.no_speech_count = 0
        
        # Handle no speech detected
        if not SpeechResult:
            logger.warning(f"⚠️ No speech detected for {CallSid}")
            session.no_speech_count += 1
            
            if session.no_speech_count >= 2:
                logger.warning(f"⚠️ Too many no-speech attempts. Ending call {CallSid}.")
                session.final_outcome = "no_answer"
                session.conversation_stage = ConversationStage.GOODBYE
                await cache_session(session)
                
                return await create_hybrid_twiml_response(
                    response_type="goodbye",
                    text="We seem to be having trouble hearing you. We will try reaching out later. Goodbye.",
                    client_data=session.client_data,
                    should_hangup=True
                )
            else:
                return await create_hybrid_twiml_response(
                    response_type="clarification",
                    text="I'm sorry, I didn't catch that. Could you please say that again?",
                    client_data=session.client_data
                )
        
        session.no_speech_count = 0
        
        # Process the speech using the fixed voice processor
        process_result = await voice_processor.process_customer_input(
            customer_input=SpeechResult,
            session=session,
            confidence=Confidence or 0.0
        )
        
        logger.info(f"🔄 Processing result: {process_result}")
        
        # IMPORTANT: Update session's conversation stage from the result
        new_stage_value = process_result.get("conversation_stage")
        if new_stage_value:
            try:
                session.conversation_stage = ConversationStage(new_stage_value)
                logger.info(f"📍 Updated session stage to: {session.conversation_stage.value}")
            except ValueError:
                logger.warning(f"⚠️ Invalid stage value: {new_stage_value}")
        
        # Create conversation turn with proper enum handling
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
        
        # Save the updated session state to cache BEFORE creating response
        await cache_session(session)
        
        # Check if the conversation should end
        if process_result.get("end_conversation", False):
            logger.info(f"🎬 Conversation ending for {CallSid}. Outcome: {session.final_outcome}")
            
            # Mark session as completed
            session.call_status = CallStatusEnum.COMPLETED
            session.complete_call(session.final_outcome)
            
            # Save final state
            await cache_session(session)
            
            # Remove from active sessions (will be cleaned up in status webhook)
            # But keep it for now to track completion
            
            return await create_hybrid_twiml_response(
                response_type=process_result.get("response_category", "goodbye"),
                text=process_result.get("response_text"),
                client_data=session.client_data,
                should_hangup=True
            )
        else:
            # Continue the conversation
            return await create_hybrid_twiml_response(
                response_type=process_result.get("response_category", "dynamic"),
                text=process_result.get("response_text"),
                client_data=session.client_data
            )
            
    except Exception as e:
        logger.error(f"❌ Unrecoverable error in speech processing for {CallSid}: {e}", exc_info=True)
        # Fallback to a generic error message and hang up
        return await create_hybrid_twiml_response(
            response_type="error",
            text="I apologize, we have encountered a system error. Please call back later. Goodbye.",
            should_hangup=True
        )

# @router.post("/process-speech")
# async def process_speech_webhook(
#     request: Request,
#     CallSid: str = Form(...),
#     SpeechResult: Optional[str] = Form(None),
#     Confidence: Optional[float] = Form(None),
#     UnstableSpeechResult: Optional[str] = Form(None)
# ):
#     """Process customer speech with complete conversation handling"""
    
#     # Use UnstableSpeechResult if SpeechResult is empty for better responsiveness
#     if not SpeechResult and UnstableSpeechResult:
#         SpeechResult = UnstableSpeechResult
#         logger.info(f"🎤 Using unstable speech result: '{SpeechResult}'")
    
#     logger.info(f"🎤 Processing speech: {CallSid} - Result: '{SpeechResult}' - Confidence: {Confidence}")
    
#     try:
#         # Get the session from active memory or fall back to cache
#         session = active_sessions.get(CallSid)
#         if not session:
#             session = await get_cached_session(CallSid)
#             if session:
#                 active_sessions[CallSid] = session
#                 logger.info(f"✅ Restored session from cache: {CallSid}")
        
#         if not session:
#             logger.error(f"❌ CRITICAL: Session not found for CallSid: {CallSid}. Cannot continue.")
#             return Response(
#                 content=create_hangup_twiml("I'm sorry, there was a problem with the call. Please call us back."),
#                 media_type="application/xml"
#             )
        
#         # Handle no speech detected
#         if not SpeechResult:
#             logger.warning(f"⚠️ No speech detected for {CallSid}")
#             session.no_speech_count += 1
            
#             if session.no_speech_count >= 2:
#                 logger.warning(f"⚠️ Too many no-speech attempts. Ending call {CallSid}.")
#                 return await create_hybrid_twiml_response(
#                     response_type="goodbye",
#                     text="We seem to be having trouble hearing you. We will try reaching out later. Goodbye.",
#                     client_data=session.client_data,
#                     should_hangup=True
#                 )
#             else:
#                 return await create_hybrid_twiml_response(
#                     response_type="clarification",
#                     text="I'm sorry, I didn't catch that. Could you please say that again?",
#                     client_data=session.client_data
#                 )
        
#         session.no_speech_count = 0
        
#         # Process the speech using your voice processor service
#         process_result = await voice_processor.process_customer_input(
#             customer_input=SpeechResult,
#             session=session,
#             confidence=Confidence or 0.0
#         )
        
#         logger.info(f"🔄 Processing result: {process_result}")
        
#         # FIXED: Correctly determine the enum member before creating the turn
#         response_type_enum = ResponseType.HYBRID if process_result.get("lyzr_used") else ResponseType.STATIC
        
#         turn = ConversationTurn(
#             turn_number=len(session.conversation_turns) + 1,
#             customer_speech=SpeechResult,
#             customer_speech_confidence=Confidence or 0.0,
#             agent_response=process_result.get("response_text", ""),
#             response_type=response_type_enum, # Use the corrected enum object
#             conversation_stage=session.conversation_stage,
#             processing_time_ms=process_result.get("processing_time_ms", 0)
#         )
        
#         session.conversation_turns.append(turn)
        
#         # Save the updated session state to cache
#         await cache_session(session)
        
#         # Check if the conversation should end
#         if process_result.get("end_conversation", False):
#             session.final_outcome = process_result.get("outcome", "completed")
#             logger.info(f"🎬 Conversation marked to end for {CallSid}. Outcome: {session.final_outcome}")
#             return await create_hybrid_twiml_response(
#                 response_type=process_result.get("response_category", "goodbye"),
#                 text=process_result.get("response_text"),
#                 client_data=session.client_data,
#                 should_hangup=True
#             )
#         else:
#             # Continue the conversation
#             return await create_hybrid_twiml_response(
#                 response_type=process_result.get("response_category", "dynamic"),
#                 text=process_result.get("response_text"),
#                 client_data=session.client_data
#             )
            
#     except Exception as e:
#         logger.error(f"❌ Unrecoverable error in speech processing for {CallSid}: {e}", exc_info=True)
#         # Fallback to a generic error message and hang up
#         return await create_hybrid_twiml_response(
#             response_type="error",
#             text="I apologize, we have encountered a system error. Please call back later. Goodbye.",
#             should_hangup=True
#         )


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
        await cache_session(session)
        
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
                        # If completed but no outcome, check conversation stage
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
                
                # Final save to database with all updates
                session_repo = await get_session_repo()
                if session_repo:
                    try:
                        # Ensure twilio_call_sid is not None
                        if not session.twilio_call_sid:
                            session.twilio_call_sid = CallSid
                        
                        # Use the session repository's save method which handles the document properly
                        success = await session_repo.save_session(session)
                        if success:
                            logger.info(f"✅ Final session saved to database: {CallSid}")
                        else:
                            logger.error(f"❌ Failed to save session to database: {CallSid}")
                    except Exception as e:
                        logger.error(f"❌ Database save error for {CallSid}: {e}")
                        # Fallback: try direct database operation with proper document structure
                        try:
                            from shared.utils.database import db_client
                            if db_client is not None and db_client.database is not None:
                                # Create document dict without _id field to avoid immutable field error
                                session_dict = session.model_dump()
                                # Remove _id if it exists to prevent immutable field error
                                if "_id" in session_dict:
                                    del session_dict["_id"]
                                
                                # Use upsert to handle both insert and update
                                await db_client.database.call_sessions.replace_one(
                                    {"twilio_call_sid": CallSid},
                                    session_dict,
                                    upsert=True
                                )
                                logger.info(f"✅ Fallback session save successful: {CallSid}")
                        except Exception as fallback_error:
                            logger.error(f"❌ Fallback save also failed for {CallSid}: {fallback_error}")
                
                # Clean up from Redis cache
                from shared.utils.redis_client import session_cache
                if session_cache:
                    try:
                        # Remove from Redis by call SID
                        await session_cache.delete_session(CallSid)
                        logger.info(f"🗑️ Removed session from Redis cache: {CallSid}")
                    except Exception as e:
                        logger.warning(f"Could not remove from Redis: {e}")
                
                # Clean up active session
                if CallSid in active_sessions:
                    del active_sessions[CallSid]
                    logger.info(f"🗑️ Removed from active sessions: {CallSid}")
                
                logger.info(f"✅ Call completed: {CallSid} - Outcome: {session.final_outcome} - Duration: {CallDuration}s")
            else:
                logger.warning(f"⚠️ No session found for completed call: {CallSid}")
        
        # Handle other status updates (initiated, ringing, in-progress)
        else:
            # Update session status if it exists
            session = active_sessions.get(CallSid)
            if not session:
                session = await get_cached_session(CallSid)
            
            if session:
                if CallStatus == "initiated":
                    session.call_status = CallStatusEnum.INITIATED
                elif CallStatus == "ringing":
                    session.call_status = CallStatusEnum.RINGING
                elif CallStatus == "in-progress":
                    session.call_status = CallStatusEnum.IN_PROGRESS
                
                # Save updated status
                await cache_session(session)
                logger.info(f"📞 Call status updated: {CallSid} -> {CallStatus}")
        
        return {"status": "ok", "call_sid": CallSid, "call_status": CallStatus}
        
    except Exception as e:
        logger.error(f"❌ Status webhook error: {e}")
        import traceback
        logger.error(traceback.format_exc())
        return {"status": "error", "message": str(e)}

@router.get("/test-connection")
async def test_twilio_connection():
    """Test Twilio connection and system readiness"""
    
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
                "configured": voice_processor.is_configured()
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
                "status": f"{settings.base_url}/twilio/status"
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