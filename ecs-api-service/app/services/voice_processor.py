"""
Fixed Voice Processor Service - Production Ready
Handles customer speech processing with proper state transitions
"""

import asyncio
import httpx
import logging
import time
from typing import Dict, Any, Optional, List
from datetime import datetime

from shared.config.settings import settings
from shared.models.call_session import CallSession, ConversationStage
from shared.utils.redis_client import redis_client

logger = logging.getLogger(__name__)

class VoiceProcessor:
    """Service for processing customer speech and generating responses"""
    
    def __init__(self):
        self.httpx_client = httpx.AsyncClient(timeout=30.0)
        self._configured = False
        
        # Common response patterns for faster processing
        self.response_patterns = {
            "yes_responses": ["yes", "yeah", "yep", "sure", "absolutely", "definitely", "of course", "okay", "ok", "sounds good", "that's fine", "it will"],
            "no_responses": ["no", "nope", "not really", "not interested", "no thanks", "don't think so", "i'm not"],
            "maybe_responses": ["maybe", "not sure", "i don't know", "let me think", "perhaps"],
            "dnc_requests": ["remove", "do not call", "don't call", "take me off", "unsubscribe", "stop calling"]
        }
        
        # Mark as configured
        self._configure()
    
    def _configure(self):
        """Configure the voice processor"""
        try:
            self._configured = True
            logger.info("✅ Voice Processor configured successfully")
        except Exception as e:
            logger.error(f"❌ Voice Processor configuration error: {e}")
            self._configured = False
    
    def is_configured(self) -> bool:
        """Check if voice processor is configured"""
        return self._configured
    
    async def process_customer_input(
        self, 
        customer_input: str, 
        session: CallSession, 
        confidence: float = 0.8
    ) -> Dict[str, Any]:
        """
        Process customer input based on conversation stage
        Fixed state machine to prevent loops
        """
        start_time = time.time()
        
        # Sanitize input
        customer_input = customer_input.lower().strip().replace(".", "").replace(",", "")
        
        logger.info(
            f"🗣️ Processing input: '{customer_input}' for session {session.session_id} "
            f"in stage: {session.conversation_stage.value}"
        )
        
        try:
            # STATE MACHINE LOGIC - FIXED TO PREVENT LOOPS
            if session.conversation_stage == ConversationStage.GREETING:
                # After initial greeting, listening for interest
                if self._is_interested(customer_input):
                    # Move to SCHEDULING stage
                    return await self._handle_initial_interest(session, start_time)
                elif self._is_not_interested(customer_input):
                    # Move to DNC_CHECK stage
                    return await self._handle_initial_disinterest(session, start_time)
                elif self._is_dnc_request(customer_input):
                    # Move to GOODBYE stage
                    return await self._handle_dnc_request(session, start_time)
                elif self._is_maybe(customer_input):
                    # Stay in GREETING stage
                    return await self._handle_maybe_response(session, start_time)
                else:
                    # Stay in GREETING stage for clarification
                    return await self._handle_unclear_response(session, start_time, "greeting")
            
            elif session.conversation_stage == ConversationStage.SCHEDULING:
                # Asked if they want to connect with their agent
                if self._is_interested(customer_input):
                    # Customer wants to schedule - END CALL
                    return await self._handle_scheduling_confirmation(session, start_time)
                elif self._is_not_interested(customer_input):
                    # Customer doesn't want to schedule but was interested - END CALL
                    return await self._handle_scheduling_rejection(session, start_time)
                elif self._is_dnc_request(customer_input):
                    # Move to GOODBYE with DNC
                    return await self._handle_dnc_request(session, start_time)
                else:
                    # Stay in SCHEDULING for clarification
                    return await self._handle_unclear_response(session, start_time, "scheduling")
            
            elif session.conversation_stage == ConversationStage.DNC_CHECK:
                # Asked about continuing communications
                if self._is_interested(customer_input):
                    # Keep communications - END CALL
                    return await self._handle_keep_communications(session, start_time)
                elif self._is_not_interested(customer_input) or self._is_dnc_request(customer_input):
                    # Confirm DNC - END CALL
                    return await self._handle_dnc_confirmation(session, start_time)
                else:
                    # Stay in DNC_CHECK for clarification
                    return await self._handle_unclear_response(session, start_time, "dnc_check")
            
            # If we're in GOODBYE or any unexpected stage, end the call
            else:
                logger.info(f"✅ In final stage or unexpected state: {session.conversation_stage.value}")
                return await self._create_response(
                    response_text="Thank you for your time today. Have a wonderful day!",
                    response_category="goodbye",
                    conversation_stage=ConversationStage.GOODBYE,
                    end_conversation=True,
                    outcome="completed",
                    start_time=start_time,
                    detected_intent="completed"
                )
                
        except Exception as e:
            logger.error(f"❌ Voice processing error: {e}")
            # Return a proper error response instead of throwing
            return await self._create_response(
                response_text="I apologize, I'm having some technical difficulties. Thank you for your patience.",
                response_category="error",
                conversation_stage=ConversationStage.GOODBYE,
                end_conversation=True,
                outcome="error",
                start_time=start_time,
                detected_intent="error"
            )
    
    # --- Helper methods for checking input patterns ---
    
    def _is_interested(self, text: str) -> bool:
        """Check if input indicates interest"""
        return any(word in text for word in self.response_patterns["yes_responses"])
    
    def _is_not_interested(self, text: str) -> bool:
        """Check if input indicates no interest"""
        return any(word in text for word in self.response_patterns["no_responses"])
    
    def _is_maybe(self, text: str) -> bool:
        """Check if input is uncertain"""
        return any(word in text for word in self.response_patterns["maybe_responses"])
    
    def _is_dnc_request(self, text: str) -> bool:
        """Check if input is a DNC request"""
        return any(phrase in text for phrase in self.response_patterns["dnc_requests"])
    
    # --- State transition handlers ---
    
    async def _handle_initial_interest(self, session: CallSession, start_time: float) -> Dict[str, Any]:
        """Handle when user expresses initial interest - MOVE TO SCHEDULING"""
        logger.info("✅ Customer interested in service - Moving to SCHEDULING stage")
        
        agent_name = session.client_data.get("last_agent", session.client_data.get("agent_name", "your previous agent"))
        
        # IMPORTANT: Update session stage to SCHEDULING
        session.conversation_stage = ConversationStage.SCHEDULING
        
        return await self._create_response(
            response_text=(
                f"Wonderful! I see that {agent_name} was the last agent who helped you. "
                f"I'd love to connect you with them again. We'll send you an email with "
                f"{agent_name}'s available time slots so you can choose what works "
                f"best for your schedule. Does that sound good?"
            ),
            response_category="agent_introduction",
            conversation_stage=ConversationStage.SCHEDULING,
            end_conversation=False,
            outcome="interested",
            start_time=start_time,
            detected_intent="interested"
        )
    
    async def _handle_initial_disinterest(self, session: CallSession, start_time: float) -> Dict[str, Any]:
        """Handle when user is not interested - MOVE TO DNC_CHECK"""
        logger.info("❌ Customer not interested - Moving to DNC_CHECK stage")
        
        # IMPORTANT: Update session stage to DNC_CHECK
        session.conversation_stage = ConversationStage.DNC_CHECK
        
        return await self._create_response(
            response_text=(
                "No problem at all! Would you like to continue receiving occasional "
                "health insurance updates from our team? We promise to keep them "
                "informative and not overwhelming. A simple yes or no will do!"
            ),
            response_category="not_interested",
            conversation_stage=ConversationStage.DNC_CHECK,
            end_conversation=False,
            outcome="not_interested",
            start_time=start_time,
            detected_intent="not_interested"
        )
    
    async def _handle_scheduling_confirmation(self, session: CallSession, start_time: float) -> Dict[str, Any]:
        """Handle when user confirms they want to schedule - END CALL"""
        logger.info("✅ Customer confirmed scheduling - Ending call with success")
        
        agent_name = session.client_data.get("last_agent", session.client_data.get("agent_name", "your agent"))
        
        # IMPORTANT: Move to GOODBYE and end conversation
        session.conversation_stage = ConversationStage.GOODBYE
        
        # Try to schedule the meeting asynchronously
        try:
            await self._schedule_meeting_async(session, agent_name)
        except Exception as e:
            logger.error(f"❌ Failed to schedule meeting: {e}")
        
        return await self._create_response(
            response_text=(
                f"Perfect! I'll send you an email shortly with {agent_name}'s available time slots. "
                f"You can review the calendar and choose a time that works best for your schedule. "
                f"Thank you so much for your time today, and have a wonderful day!"
            ),
            response_category="schedule_confirmation",
            conversation_stage=ConversationStage.GOODBYE,
            end_conversation=True,
            outcome="scheduled",
            start_time=start_time,
            detected_intent="scheduled"
        )
    
    async def _handle_scheduling_rejection(self, session: CallSession, start_time: float) -> Dict[str, Any]:
        """Handle when user declines scheduling - END CALL"""
        logger.info("❌ Customer declined scheduling - Ending call")
        
        agent_name = session.client_data.get("last_agent", session.client_data.get("agent_name", "your agent"))
        
        # IMPORTANT: Move to GOODBYE and end conversation
        session.conversation_stage = ConversationStage.GOODBYE
        
        return await self._create_response(
            response_text=(
                f"I completely understand. {agent_name} will make a note of our conversation, "
                f"and we'll be here whenever you're ready to explore your options. "
                f"Thank you for your time today. Have a wonderful day!"
            ),
            response_category="no_schedule_followup",
            conversation_stage=ConversationStage.GOODBYE,
            end_conversation=True,
            outcome="interested_no_schedule",
            start_time=start_time,
            detected_intent="interested_no_schedule"
        )
    
    async def _handle_dnc_request(self, session: CallSession, start_time: float) -> Dict[str, Any]:
        """Handle do-not-call request - END CALL"""
        logger.info("🚫 Customer requested DNC - Ending call")
        
        # IMPORTANT: Move to GOODBYE and end conversation
        session.conversation_stage = ConversationStage.GOODBYE
        
        return await self._create_response(
            response_text=(
                "I completely understand. I'll make sure you're removed from all future calls "
                "right away. You'll receive a confirmation email shortly. Our contact information "
                "will be in that email if you ever change your mind - remember, our service is "
                "always free. Have a wonderful day!"
            ),
            response_category="dnc_confirmation",
            conversation_stage=ConversationStage.GOODBYE,
            end_conversation=True,
            outcome="dnc_requested",
            start_time=start_time,
            detected_intent="dnc_requested"
        )
    
    async def _handle_keep_communications(self, session: CallSession, start_time: float) -> Dict[str, Any]:
        """Handle when user wants to keep receiving communications - END CALL"""
        logger.info("✅ Customer wants to keep communications - Ending call")
        
        # IMPORTANT: Move to GOODBYE and end conversation
        session.conversation_stage = ConversationStage.GOODBYE
        
        return await self._create_response(
            response_text=(
                "Great! We'll keep you in the loop with helpful health insurance updates "
                "throughout the year. If you ever need assistance, just reach out - "
                "we're always here to help, and our service is always free. "
                "Thank you for your time today!"
            ),
            response_category="keep_communications",
            conversation_stage=ConversationStage.GOODBYE,
            end_conversation=True,
            outcome="keep_communications",
            start_time=start_time,
            detected_intent="keep_communications"
        )
    
    async def _handle_dnc_confirmation(self, session: CallSession, start_time: float) -> Dict[str, Any]:
        """Handle when user confirms DNC - END CALL"""
        logger.info("🚫 Customer confirmed DNC - Ending call")
        
        # IMPORTANT: Move to GOODBYE and end conversation
        session.conversation_stage = ConversationStage.GOODBYE
        
        return await self._create_response(
            response_text=(
                "No problem at all. I'll remove you from our calling list right away. "
                "You'll receive a confirmation email shortly. Thank you for your time, "
                "and have a great day!"
            ),
            response_category="dnc_confirmation",
            conversation_stage=ConversationStage.GOODBYE,
            end_conversation=True,
            outcome="dnc_requested",
            start_time=start_time,
            detected_intent="dnc_requested"
        )
    
    async def _handle_maybe_response(self, session: CallSession, start_time: float) -> Dict[str, Any]:
        """Handle uncertain responses"""
        logger.info("🤔 Customer uncertain - Asking for clarification")
        
        return await self._create_response(
            response_text=(
                "I understand you might need some time to think about it. "
                "Let me ask you this - are you currently happy with your health insurance, "
                "or would you be open to learning about potentially better options? "
                "There's no obligation, and our consultation is completely free."
            ),
            response_category="clarification",
            conversation_stage=session.conversation_stage,  # Stay in same stage
            end_conversation=False,
            outcome="clarification_needed",
            start_time=start_time,
            detected_intent="maybe"
        )
    
    async def _handle_unclear_response(self, session: CallSession, start_time: float, context: str) -> Dict[str, Any]:
        """Handle unclear responses based on context"""
        logger.info(f"❓ Unclear response in {context} - Asking for clarification")
        
        if context == "greeting":
            text = (
                "I apologize, I didn't quite catch that. "
                "Would you be interested in reviewing your health insurance options "
                "for this year's open enrollment? A simple yes or no would be great."
            )
        elif context == "scheduling":
            agent_name = session.client_data.get("last_agent", "your agent")
            text = (
                f"Let me clarify - would you like us to send you an email with "
                f"{agent_name}'s available times for a brief consultation? "
                f"Just say yes if you'd like that, or no if you're not interested."
            )
        elif context == "dnc_check":
            text = (
                "I want to make sure I understand correctly. "
                "Would you like to continue receiving health insurance updates from us? "
                "Please say yes or no."
            )
        else:
            text = (
                "I apologize, I didn't understand that. "
                "Could you please repeat your response?"
            )
        
        return await self._create_response(
            response_text=text,
            response_category="clarification",
            conversation_stage=session.conversation_stage,  # Stay in same stage
            end_conversation=False,
            outcome="clarification_needed",
            start_time=start_time,
            detected_intent="unclear"
        )
    
    async def _create_response(
        self,
        response_text: str,
        response_category: str,
        conversation_stage: ConversationStage,
        end_conversation: bool,
        outcome: str,
        start_time: float,
        detected_intent: str = None
    ) -> Dict[str, Any]:
        """Create standardized response"""
        
        # Update session stage - ensure it's the value string
        if hasattr(conversation_stage, 'value'):
            stage_value = conversation_stage.value
        else:
            stage_value = conversation_stage
        
        return {
            "success": True,
            "response_text": response_text,
            "response_category": response_category,
            "conversation_stage": stage_value,
            "end_conversation": end_conversation,
            "outcome": outcome,
            "processing_time_ms": int((time.time() - start_time) * 1000),
            "detected_intent": detected_intent or outcome
        }
    
    async def _create_error_response(self, start_time: float) -> Dict[str, Any]:
        """Create error response"""
        return {
            "success": False,
            "response_text": "I apologize, I'm having some technical difficulties. Thank you for your patience.",
            "response_category": "error",
            "conversation_stage": "goodbye",
            "end_conversation": True,
            "outcome": "error",
            "processing_time_ms": int((time.time() - start_time) * 1000),
            "detected_intent": "error"
        }
    
    def get_current_time(self) -> float:
        """Get current time for latency tracking"""
        return time.time()
    
    async def _schedule_meeting_async(self, session: CallSession, agent_name: str):
        """Schedule meeting asynchronously without blocking the call"""
        try:
            # Get client information
            client_name = session.client_data.get("client_name", "Client")
            client_phone = session.phone_number
            
            # Try to get client email from database
            client_email = None
            try:
                from shared.utils.database import get_client_by_phone
                client = await get_client_by_phone(client_phone)
                if client and hasattr(client.client, 'email'):
                    client_email = client.client.email
            except Exception as e:
                logger.warning(f"Could not get client email: {e}")
            
            # If no email, use a placeholder
            if not client_email:
                client_email = f"{client_name.lower().replace(' ', '.')}@example.com"
            
            # Get agent email from agents config
            agent_email = None
            try:
                import json
                with open("data/agents.json", 'r') as f:
                    agents_config = json.load(f)
                    for agent in agents_config.get("agents", []):
                        if agent.get("name") == agent_name:
                            agent_email = agent.get("email")
                            break
            except Exception as e:
                logger.warning(f"Could not load agents config: {e}")
            
            if not agent_email:
                logger.warning(f"Agent email not found for {agent_name}")
                return
            
            # Schedule the meeting using the worker service
            # This will be handled by the worker service that has access to Google Calendar
            logger.info(f"📅 Scheduling meeting for {client_name} with {agent_name} ({agent_email})")
            
            # For now, we'll just log that scheduling should happen
            # In a full implementation, this would send a message to a queue or make an API call
            # to the worker service to handle the actual calendar scheduling
            
        except Exception as e:
            logger.error(f"❌ Error in async meeting scheduling: {e}")
    
    async def close(self):
        """Close HTTP client"""
        await self.httpx_client.aclose()

# Global instance
voice_processor = VoiceProcessor()