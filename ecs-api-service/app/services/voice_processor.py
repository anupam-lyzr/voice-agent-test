"""
Enhanced Voice Processor Service - Production Ready
Handles all customer responses including clarifying questions and interruptions
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
    """Enhanced service for processing customer speech and generating responses"""
    
    def __init__(self):
        self.httpx_client = httpx.AsyncClient(timeout=30.0)
        self._configured = False
        
        # Enhanced response patterns for all scenarios
        self.response_patterns = {
            "yes_responses": ["yes", "yeah", "yep", "sure", "absolutely", "definitely", "of course", "okay", "ok", "sounds good", "that's fine", "it will"],
            "no_responses": ["no", "nope", "not really", "not interested", "no thanks", "don't think so", "i'm not"],
            "maybe_responses": ["maybe", "not sure", "i don't know", "let me think", "perhaps"],
            "dnc_requests": ["remove", "do not call", "don't call", "take me off", "unsubscribe", "stop calling"],
            
            # NEW: Clarifying question patterns
            "identity_questions": [
                "who is this", "where are you calling from", "what company", "who are you",
                "where are you from", "what's your name", "who am i speaking with",
                "what organization", "what business"
            ],
            "ai_questions": [
                "are you a robot", "are you ai", "are you artificial", "are you real",
                "is this automated", "are you human", "is this a recording"
            ],
            "memory_questions": [
                "don't remember", "don't recall", "never heard of you", "never worked with",
                "don't know you", "who did i work with"
            ],
            "repeat_requests": [
                "can you repeat", "say that again", "didn't catch that", "what did you say",
                "could you repeat", "pardon", "excuse me", "come again"
            ]
        }
        
        # Delay filling responses for LYZR processing
        self.delay_fillers = [
            "That's a great question, let me make sure I give you the most accurate information.",
            "I want to provide you with the best answer possible, please give me just a moment.",
            "Let me check on that for you to ensure I'm giving you the correct details.",
            "That's an excellent point, let me get you the most up-to-date information.",
            "I appreciate you asking that, let me pull up the specifics for you."
        ]
        
        # Silence detection responses (matching user requirements)
        self.silence_responses = {
            "first": "I'm sorry, I didn't hear anything. Did you say something?",
            "second": "I'm sorry, I didn't hear anything. Did you say something?",
            "final": "You can call us back at 8-3-3, 2-2-7, 8-5-0-0. Have a great day."
        }
        
        self._configure()
    
    def _configure(self):
        """Configure the voice processor"""
        try:
            self._configured = True
            logger.info("✅ Enhanced Voice Processor configured successfully")
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
        confidence: float = 0.8,
        is_interruption: bool = False
    ) -> Dict[str, Any]:
        """
        Enhanced processing with clarifying questions and interruption handling
        """
        start_time = time.time()
        
        # Handle interruptions
        if is_interruption:
            return await self._handle_interruption(customer_input, session, start_time)
        
        # Sanitize input
        customer_input = customer_input.lower().strip().replace(".", "").replace(",", "")
        
        logger.info(
            f"🗣️ Processing input: '{customer_input}' for session {session.session_id} "
            f"in stage: {session.conversation_stage.value if hasattr(session.conversation_stage, 'value') else session.conversation_stage}"
        )
        
        try:
            # PRIORITY 1: Check for clarifying questions FIRST (before state machine)
            clarifying_response = await self._check_clarifying_questions(customer_input, session, start_time)
            if clarifying_response:
                return clarifying_response
            
            # PRIORITY 2: State machine logic for conversation flow
            if session.conversation_stage == ConversationStage.GREETING:
                if self._is_interested(customer_input):
                    return await self._handle_initial_interest(session, start_time)
                elif self._is_not_interested(customer_input):
                    return await self._handle_initial_disinterest(session, start_time)
                elif self._is_dnc_request(customer_input):
                    return await self._handle_dnc_request(session, start_time)
                elif self._is_maybe(customer_input):
                    return await self._handle_maybe_response(session, start_time)
                else:
                    return await self._handle_unclear_response(session, start_time, "greeting")
            
            elif session.conversation_stage == ConversationStage.SCHEDULING:
                if self._is_interested(customer_input):
                    return await self._handle_scheduling_confirmation(session, start_time)
                elif self._is_not_interested(customer_input):
                    return await self._handle_scheduling_rejection(session, start_time)
                elif self._is_dnc_request(customer_input):
                    return await self._handle_dnc_request(session, start_time)
                else:
                    return await self._handle_unclear_response(session, start_time, "scheduling")
            
            elif session.conversation_stage == ConversationStage.DNC_CHECK:
                if self._is_interested(customer_input):
                    return await self._handle_keep_communications(session, start_time)
                elif self._is_not_interested(customer_input) or self._is_dnc_request(customer_input):
                    return await self._handle_dnc_confirmation(session, start_time)
                else:
                    return await self._handle_unclear_response(session, start_time, "dnc_check")
            
            # If we're in GOODBYE or any unexpected stage, end the call
            else:
                logger.info(f"✅ In final stage: {session.conversation_stage.value if hasattr(session.conversation_stage, 'value') else session.conversation_stage}")
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
            return await self._create_response(
                response_text="I apologize, I'm having some technical difficulties. Thank you for your patience.",
                response_category="error",
                conversation_stage=ConversationStage.GOODBYE,
                end_conversation=True,
                outcome="error",
                start_time=start_time,
                detected_intent="error"
            )
    
    async def _check_clarifying_questions(
        self, 
        customer_input: str, 
        session: CallSession, 
        start_time: float
    ) -> Optional[Dict[str, Any]]:
        """Check for and handle clarifying questions"""
        
        # Identity questions: "Who is this?", "Where are you calling from?"
        if any(phrase in customer_input for phrase in self.response_patterns["identity_questions"]):
            return await self._handle_identity_question(session, start_time)
        
        # AI questions: "Are you an AI?"
        if any(phrase in customer_input for phrase in self.response_patterns["ai_questions"]):
            return await self._handle_ai_question(session, start_time)
        
        # Memory questions: "I don't remember working with you"
        if any(phrase in customer_input for phrase in self.response_patterns["memory_questions"]):
            return await self._handle_memory_question(session, start_time)
        
        # Repeat requests: "Can you say that again?"
        if any(phrase in customer_input for phrase in self.response_patterns["repeat_requests"]):
            return await self._handle_repeat_request(session, start_time)
        
        return None
    
    async def _handle_identity_question(self, session: CallSession, start_time: float) -> Dict[str, Any]:
        """Handle 'Who is this?' or 'Where are you calling from?' questions"""
        
        client_name = session.client_data.get("first_name", "")
        
        return await self._create_response(
            response_text=(
                f"Hi {client_name}, this is Alex from Altruis Advisor Group. "
                f"We're a health insurance brokerage that's helped you in the past. "
                f"I'm calling to see if we can assist you during this year's Open Enrollment. "
                f"Are you interested in reviewing your options?"
            ),
            response_category="identity_clarification",
            conversation_stage=session.conversation_stage,  # Stay in same stage
            end_conversation=False,
            outcome="identity_clarified",
            start_time=start_time,
            detected_intent="identity_question"
        )
    
    async def _handle_ai_question(self, session: CallSession, start_time: float) -> Dict[str, Any]:
        """Handle 'Are you an AI?' questions"""
        
        return await self._create_response(
            response_text=(
                "I'm Alex, a representative from Altruis Advisor Group. "
                "I'm calling because we've helped you with health insurance before, "
                "and I wanted to see if we could assist you this year. "
                "Would you be interested in exploring your options?"
            ),
            response_category="ai_clarification",
            conversation_stage=session.conversation_stage,  # Stay in same stage
            end_conversation=False,
            outcome="ai_question_handled",
            start_time=start_time,
            detected_intent="ai_question"
        )
    
    async def _handle_memory_question(self, session: CallSession, start_time: float) -> Dict[str, Any]:
        """Handle 'I don't remember working with you' questions"""
        
        agent_name = session.client_data.get("last_agent", "one of our agents")
        
        return await self._create_response(
            response_text=(
                f"No worries at all! You previously worked with {agent_name} here at Altruis "
                f"for your health insurance needs. We're a brokerage that helps people find "
                f"the best coverage options. Since it's Open Enrollment season, I wanted to "
                f"reach out to see if you'd like assistance this year. Are you interested?"
            ),
            response_category="memory_clarification",
            conversation_stage=session.conversation_stage,  # Stay in same stage
            end_conversation=False,
            outcome="memory_clarified",
            start_time=start_time,
            detected_intent="memory_question"
        )
    
    async def _handle_repeat_request(self, session: CallSession, start_time: float) -> Dict[str, Any]:
        """Handle 'Can you repeat that?' requests"""
        
        client_name = session.client_data.get("first_name", "")
        
        return await self._create_response(
            response_text=(
                f"Of course! I'm Alex from Altruis Advisor Group. We've helped you "
                f"with health insurance before, and I'm calling to see if we can "
                f"assist you during Open Enrollment this year. Are you interested "
                f"in reviewing your options?"
            ),
            response_category="repeat_response",
            conversation_stage=session.conversation_stage,  # Stay in same stage
            end_conversation=False,
            outcome="repeated_message",
            start_time=start_time,
            detected_intent="repeat_request"
        )
    
    async def _handle_interruption(
        self, 
        customer_input: str, 
        session: CallSession, 
        start_time: float
    ) -> Dict[str, Any]:
        """Handle customer interruptions while agent is speaking"""
        
        logger.info(f"🛑 Customer interrupted: '{customer_input}'")
        
        # Quick responses for common interruptions
        if any(word in customer_input.lower() for word in ["yes", "yeah", "okay", "sure"]):
            return await self._create_response(
                response_text="Great! Let me continue with the details.",
                response_category="interruption_acknowledgment",
                conversation_stage=session.conversation_stage,
                end_conversation=False,
                outcome="interruption_positive",
                start_time=start_time,
                detected_intent="positive_interruption"
            )
        
        elif any(word in customer_input.lower() for word in ["no", "stop", "wait"]):
            return await self._create_response(
                response_text="I understand. What would you like to know?",
                response_category="interruption_acknowledgment",
                conversation_stage=session.conversation_stage,
                end_conversation=False,
                outcome="interruption_negative",
                start_time=start_time,
                detected_intent="negative_interruption"
            )
        
        else:
            return await self._create_response(
                response_text="Yes? How can I help you?",
                response_category="interruption_acknowledgment",
                conversation_stage=session.conversation_stage,
                end_conversation=False,
                outcome="interruption_unclear",
                start_time=start_time,
                detected_intent="unclear_interruption"
            )
    
    async def process_with_lyzr_delay_filler(
        self, 
        customer_input: str, 
        session: CallSession
    ) -> Dict[str, Any]:
        """Process complex questions with LYZR while providing delay filler"""
        
        start_time = time.time()
        
        # Get a delay filler response
        import random
        filler_text = random.choice(self.delay_fillers)
        
        # Start LYZR processing in background
        lyzr_task = asyncio.create_task(self._process_with_lyzr_agent(customer_input, session))
        
        # Return immediate filler response
        return await self._create_response(
            response_text=filler_text,
            response_category="lyzr_delay_filler",
            conversation_stage=session.conversation_stage,
            end_conversation=False,
            outcome="processing_complex_question",
            start_time=start_time,
            detected_intent="complex_question",
            lyzr_task=lyzr_task  # Pass task for later completion
        )
    
    async def _process_with_lyzr_agent(self, customer_input: str, session: CallSession) -> Dict[str, Any]:
        """Process complex questions with LYZR agent"""
        
        try:
            from services.lyzr_client import lyzr_client
            
            if not lyzr_client.is_configured():
                return {"success": False, "error": "LYZR not configured"}
            
            # Get LYZR response
            lyzr_result = await lyzr_client.get_agent_response(
                session_id=session.lyzr_session_id,
                customer_message=customer_input,
                context={
                    "conversation_stage": session.conversation_stage.value if hasattr(session.conversation_stage, 'value') else session.conversation_stage,
                    "client_name": session.client_data.get("first_name", ""),
                    "is_first_interaction": len(session.conversation_turns) == 0
                }
            )
            
            if lyzr_result["success"]:
                return {
                    "success": True,
                    "response_text": lyzr_result["response"],
                    "lyzr_used": True,
                    "session_ended": lyzr_result.get("session_ended", False)
                }
            else:
                # LYZR failed, use fallback
                return {
                    "success": True,
                    "response_text": "I'd be happy to have one of our specialists call you back with detailed information. Are you interested?",
                    "lyzr_used": False,
                    "fallback_used": True
                }
                
        except Exception as e:
            logger.error(f"❌ LYZR processing error: {e}")
            return {
                "success": True,
                "response_text": "Let me have a specialist call you back with that information. Would that work for you?",
                "lyzr_used": False,
                "fallback_used": True
            }
    
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
    
    # --- State transition handlers (same as before) ---
    
    async def _handle_initial_interest(self, session: CallSession, start_time: float) -> Dict[str, Any]:
        """Handle when user expresses initial interest"""
        logger.info("✅ Customer interested in service - Moving to SCHEDULING stage")
        
        agent_name = session.client_data.get("last_agent", "your previous agent")
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
        """Handle when user is not interested"""
        logger.info("❌ Customer not interested - Moving to DNC_CHECK stage")
        
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
        """Handle when user confirms they want to schedule"""
        logger.info("✅ Customer confirmed scheduling - Ending call with success")
        
        agent_name = session.client_data.get("last_agent", "your agent")
        session.conversation_stage = ConversationStage.GOODBYE
        
        return await self._create_response(
            response_text=(
                f"Perfect! You'll receive an email with {agent_name}'s available time slots. "
                f"Simply click on the time that works best for you. "
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
        """Handle when user declines scheduling"""
        logger.info("❌ Customer declined scheduling - Ending call")
        
        agent_name = session.client_data.get("last_agent", "your agent")
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
        """Handle do-not-call request"""
        logger.info("🚫 Customer requested DNC - Ending call")
        
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
        """Handle when user wants to keep receiving communications"""
        logger.info("✅ Customer wants to keep communications - Ending call")
        
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
        """Handle when user confirms DNC"""
        logger.info("🚫 Customer confirmed DNC - Ending call")
        
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
            conversation_stage=session.conversation_stage,
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
            conversation_stage=session.conversation_stage,
            end_conversation=False,
            outcome="clarification_needed",
            start_time=start_time,
            detected_intent="unclear"
        )
    
    async def _handle_silence_detection(self, session: CallSession, silence_count: int, start_time: float) -> Dict[str, Any]:
        """Handle silence detection with progressive responses"""
        
        if silence_count == 1:
            response_text = self.silence_responses["first"]
            end_conversation = False
            outcome = "silence_first"
        elif silence_count == 2:
            response_text = self.silence_responses["second"]
            end_conversation = False
            outcome = "silence_second"
        else:
            response_text = self.silence_responses["final"]
            end_conversation = True
            outcome = "silence_final"
        
        return await self._create_response(
            response_text=response_text,
            response_category="silence_detection",
            conversation_stage=session.conversation_stage,
            end_conversation=end_conversation,
            outcome=outcome,
            start_time=start_time,
            detected_intent="silence"
        )
    
    async def _create_response(
        self,
        response_text: str,
        response_category: str,
        conversation_stage: ConversationStage,
        end_conversation: bool,
        outcome: str,
        start_time: float,
        detected_intent: str = None,
        lyzr_task: Optional[asyncio.Task] = None
    ) -> Dict[str, Any]:
        """Create standardized response"""
        
        if hasattr(conversation_stage, 'value'):
            stage_value = conversation_stage.value if hasattr(conversation_stage, 'value') else conversation_stage
        else:
            stage_value = conversation_stage
        
        response = {
            "success": True,
            "response_text": response_text,
            "response_category": response_category,
            "conversation_stage": stage_value,
            "end_conversation": end_conversation,
            "outcome": outcome,
            "processing_time_ms": int((time.time() - start_time) * 1000),
            "detected_intent": detected_intent or outcome
        }
        
        if lyzr_task:
            response["lyzr_task"] = lyzr_task
        
        return response
    
    async def close(self):
        """Close HTTP client"""
        await self.httpx_client.aclose()

# Global instance
voice_processor = VoiceProcessor()