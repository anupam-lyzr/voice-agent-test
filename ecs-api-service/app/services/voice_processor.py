"""
Voice Processing Service
Handles customer speech analysis and conversation flow management
"""

import asyncio
import hashlib
import httpx
import logging
import time
from typing import Dict, Any, Optional, Tuple
from datetime import datetime

from shared.config.settings import settings
from shared.models.call_session import CallSession, ConversationStage
from shared.models.client import Client
from shared.utils.database import get_client_by_phone
from shared.utils.redis_client import response_cache

logger = logging.getLogger(__name__)

class VoiceProcessor:
    """Processes customer speech and manages conversation flow"""
    
    def __init__(self):
        # HTTP client for LYZR API
        self.lyzr_session = httpx.AsyncClient(
            timeout=settings.webhook_timeout,
            limits=httpx.Limits(max_keepalive_connections=5)
        )
        
        # Static response patterns for optimization
        self.static_patterns = {
            "interested": {
                "keywords": ["yes", "yeah", "yep", "sure", "interested", "okay", "ok", "absolutely", "definitely"],
                "response": "Excellent! What time would work best for you - morning, afternoon, or evening?",
                "category": "interested",
                "next_stage": ConversationStage.SCHEDULING,
                "intent": "customer_interested"
            },
            "not_interested": {
                "keywords": ["no", "nope", "not interested", "busy", "not right now", "maybe later", "can't", "unable"],
                "response": "I understand. Would you like us to remove you from future promotional calls?",
                "category": "not_interested", 
                "next_stage": ConversationStage.DNC_QUESTION,
                "intent": "customer_not_interested"
            },
            "time_morning": {
                "keywords": ["morning", "am", "early", "before noon", "8", "9", "10", "11"],
                "response": "Perfect! Our insurance specialist will call you tomorrow morning. Thank you so much!",
                "category": "schedule_morning",
                "next_stage": ConversationStage.COMPLETED,
                "intent": "schedule_morning",
                "end_conversation": True,
                "customer_interested": True
            },
            "time_afternoon": {
                "keywords": ["afternoon", "pm", "after lunch", "later", "1", "2", "3", "4", "5"],
                "response": "Great! Our team will reach out to you this afternoon. Thank you for your interest!",
                "category": "schedule_afternoon", 
                "next_stage": ConversationStage.COMPLETED,
                "intent": "schedule_afternoon",
                "end_conversation": True,
                "customer_interested": True
            },
            "time_anytime": {
                "keywords": ["anytime", "any time", "flexible", "whenever", "doesn't matter", "either"],
                "response": "Perfect! Our specialist will call you within 24 hours. Thank you!",
                "category": "schedule_anytime",
                "next_stage": ConversationStage.COMPLETED,
                "intent": "schedule_anytime", 
                "end_conversation": True,
                "customer_interested": True
            },
            "dnc_yes": {
                "keywords": ["yes", "remove", "take me off", "don't call", "add me", "please"],
                "response": "Done! You've been added to our do-not-call list. Have a great day!",
                "category": "dnc_confirmation",
                "next_stage": ConversationStage.COMPLETED,
                "intent": "dnc_requested",
                "end_conversation": True,
                "dnc_requested": True
            },
            "dnc_no": {
                "keywords": ["no", "keep", "don't remove", "it's okay", "that's fine"],
                "response": "No problem! Thank you for your time today. Have a wonderful day!",
                "category": "goodbye",
                "next_stage": ConversationStage.COMPLETED,
                "intent": "keep_on_list",
                "end_conversation": True
            }
        }
        
        # Performance tracking
        self.optimized_responses = 0
        self.lyzr_api_calls = 0
        self.total_processing_time = 0
    
    async def process_customer_speech(
        self,
        session: CallSession,
        customer_speech: str,
        client_phone: str
    ) -> Dict[str, Any]:
        """
        Process customer speech and generate appropriate response
        Returns: {success: bool, response_text: str, response_category: str, ...}
        """
        start_time = time.time()
        
        try:
            logger.info(f"🎯 Processing speech: '{customer_speech}' (Stage: {session.conversation_stage.value})")
            
            # Clean and normalize speech
            clean_speech = self._clean_customer_speech(customer_speech)
            
            # Check for empty or meaningless input
            if not clean_speech or self._is_filler_speech(clean_speech):
                return {
                    "success": True,
                    "response_text": "I'm sorry, I didn't catch that. Could you please repeat?",
                    "response_category": "clarification",
                    "generation_time_ms": (time.time() - start_time) * 1000,
                    "detected_intent": "unclear"
                }
            
            # Try optimized static response first
            static_result = self._try_static_response(clean_speech, session.conversation_stage)
            
            if static_result:
                self.optimized_responses += 1
                processing_time = (time.time() - start_time) * 1000
                self.total_processing_time += processing_time
                
                logger.info(f"⚡ Static response: {static_result['intent']} ({processing_time:.0f}ms)")
                
                return {
                    "success": True,
                    "response_text": static_result["response"],
                    "response_category": static_result["category"],
                    "conversation_stage": static_result["next_stage"].value,
                    "detected_intent": static_result["intent"],
                    "end_conversation": static_result.get("end_conversation", False),
                    "customer_interested": static_result.get("customer_interested", False),
                    "customer_not_interested": static_result.get("customer_not_interested", False),
                    "dnc_requested": static_result.get("dnc_requested", False),
                    "generation_time_ms": processing_time,
                    "method": "static_optimization"
                }
            
            # Fall back to LYZR API for complex responses
            lyzr_result = await self._get_lyzr_response(
                clean_speech, 
                session,
                client_phone
            )
            
            if lyzr_result["success"]:
                self.lyzr_api_calls += 1
                processing_time = (time.time() - start_time) * 1000
                self.total_processing_time += processing_time
                
                logger.info(f"🤖 LYZR response: ({processing_time:.0f}ms)")
                
                # Analyze LYZR response for conversation control
                analysis = self._analyze_lyzr_response(lyzr_result["response_text"], session)
                
                return {
                    "success": True,
                    "response_text": lyzr_result["response_text"],
                    "response_category": "dynamic",
                    "conversation_stage": analysis.get("next_stage", session.conversation_stage.value),
                    "detected_intent": analysis.get("intent", "complex_query"),
                    "end_conversation": analysis.get("end_conversation", False),
                    "customer_interested": analysis.get("customer_interested", False),
                    "customer_not_interested": analysis.get("customer_not_interested", False),
                    "dnc_requested": analysis.get("dnc_requested", False),
                    "generation_time_ms": processing_time,
                    "method": "lyzr_api"
                }
            
            # Final fallback
            processing_time = (time.time() - start_time) * 1000
            logger.warning(f"⚠️ All processing methods failed, using fallback")
            
            return {
                "success": True,
                "response_text": "I understand. Thank you for your time today.",
                "response_category": "fallback",
                "end_conversation": True,
                "generation_time_ms": processing_time,
                "method": "fallback"
            }
            
        except Exception as e:
            logger.error(f"❌ Speech processing error: {e}")
            return {
                "success": False,
                "error": str(e),
                "message": "I apologize, there was a technical issue. Thank you for calling."
            }
    
    def _clean_customer_speech(self, speech: str) -> str:
        """Clean and normalize customer speech"""
        if not speech:
            return ""
        
        # Remove extra whitespace and convert to lowercase
        clean = speech.strip().lower()
        
        # Remove common speech recognition artifacts
        clean = clean.replace(".", "").replace(",", "").replace("?", "").replace("!", "")
        
        # Handle common speech variations
        clean = clean.replace("yeah", "yes").replace("yep", "yes").replace("uh-huh", "yes")
        clean = clean.replace("nope", "no").replace("nah", "no").replace("uh-uh", "no")
        
        return clean.strip()
    
    def _is_filler_speech(self, speech: str) -> bool:
        """Check if speech is just filler words"""
        filler_words = {"um", "uh", "hmm", "ah", "er", "like", "you know", "well", "so"}
        
        words = set(speech.split())
        meaningful_words = words - filler_words
        
        # If less than 2 meaningful words, consider it filler
        return len(meaningful_words) < 2
    
    def _try_static_response(
        self, 
        speech: str, 
        conversation_stage: ConversationStage
    ) -> Optional[Dict[str, Any]]:
        """Try to match speech with static response patterns"""
        
        speech_words = speech.split()
        
        # Different matching logic based on conversation stage
        if conversation_stage == ConversationStage.INTEREST_CHECK:
            # First response after greeting - check for yes/no
            for pattern_name in ["interested", "not_interested"]:
                pattern = self.static_patterns[pattern_name]
                if any(keyword in speech for keyword in pattern["keywords"]):
                    return pattern
        
        elif conversation_stage == ConversationStage.SCHEDULING:
            # Customer responding to time question
            for pattern_name in ["time_morning", "time_afternoon", "time_anytime"]:
                pattern = self.static_patterns[pattern_name]
                if any(keyword in speech for keyword in pattern["keywords"]):
                    return pattern
            
            # Also check for general interested responses
            if any(keyword in speech for keyword in self.static_patterns["interested"]["keywords"]):
                return {
                    "response": "What time would work best for you?",
                    "category": "time_clarification",
                    "next_stage": ConversationStage.SCHEDULING,
                    "intent": "needs_time_clarification"
                }
        
        elif conversation_stage == ConversationStage.DNC_QUESTION:
            # Customer responding to do-not-call question
            for pattern_name in ["dnc_yes", "dnc_no"]:
                pattern = self.static_patterns[pattern_name]
                if any(keyword in speech for keyword in pattern["keywords"]):
                    return pattern
        
        return None
    
    async def _get_lyzr_response(
        self,
        speech: str,
        session: CallSession,
        client_phone: str
    ) -> Dict[str, Any]:
        """Get response from LYZR agent API"""
        
        if not settings.lyzr_conversation_agent_id or not settings.lyzr_user_api_key:
            return {"success": False, "error": "LYZR not configured"}
        
        try:
            # Get client for context
            client = await get_client_by_phone(client_phone)
            client_name = client.client.full_name if client else "Customer"
            
            # Build conversation context
            context_message = self._build_conversation_context(speech, session, client_name)
            
            # LYZR API call
            url = f"{settings.lyzr_api_base_url}/v3/inference/chat/"
            
            headers = {
                "Content-Type": "application/json",
                "x-api-key": settings.lyzr_user_api_key
            }
            
            data = {
                "user_id": settings.lyzr_user_api_key,
                "agent_id": settings.lyzr_conversation_agent_id,
                "session_id": session.lyzr_session_id,
                "message": context_message
            }
            
            response = await self.lyzr_session.post(url, headers=headers, json=data)
            
            if response.status_code == 200:
                result = response.json()
                agent_response = result.get("response", "").strip()
                
                if agent_response:
                    # Clean response for voice
                    clean_response = self._clean_response_for_voice(agent_response)
                    return {"success": True, "response_text": clean_response}
            
            logger.error(f"LYZR API error: {response.status_code} - {response.text}")
            return {"success": False, "error": f"API error: {response.status_code}"}
            
        except Exception as e:
            logger.error(f"LYZR API call error: {e}")
            return {"success": False, "error": str(e)}
    
    def _build_conversation_context(
        self, 
        current_speech: str, 
        session: CallSession,
        client_name: str
    ) -> str:
        """Build context message for LYZR"""
        
        # Get conversation history
        history_lines = []
        for turn in session.conversation_turns[-3:]:  # Last 3 turns for context
            if turn.customer_speech:
                history_lines.append(f"Customer: {turn.customer_speech}")
            history_lines.append(f"Agent: {turn.agent_response}")
        
        # Build context
        context_parts = [
            f"Customer: {client_name}",
            f"Call Stage: {session.conversation_stage.value}",
            f"Turn: {len(session.conversation_turns) + 1}"
        ]
        
        if history_lines:
            context_parts.append("Recent conversation:")
            context_parts.extend(history_lines)
        
        context_parts.append(f"Customer just said: {current_speech}")
        context_parts.append("Respond naturally and conversationally.")
        
        return "\n".join(context_parts)
    
    def _clean_response_for_voice(self, response: str) -> str:
        """Clean LYZR response for voice synthesis"""
        
        # Remove markdown
        response = response.replace("**", "").replace("*", "")
        
        # Replace symbols
        response = response.replace("&", " and ").replace("%", " percent ")
        
        # Improve pronunciations
        response = response.replace("Dr.", "Doctor").replace("Mr.", "Mister")
        
        # Limit length
        if len(response) > 300:
            sentences = response[:300].split('.')
            if len(sentences) > 1:
                response = '.'.join(sentences[:-1]) + '.'
            else:
                response = response[:297] + "..."
        
        return response.strip()
    
    def _analyze_lyzr_response(
        self, 
        response: str, 
        session: CallSession
    ) -> Dict[str, Any]:
        """Analyze LYZR response to determine conversation flow"""
        
        response_lower = response.lower()
        analysis = {"intent": "complex_query"}
        
        # Check for conversation ending signals
        ending_phrases = [
            "thank you for your time", "have a great day", "goodbye", 
            "our specialist will call", "we'll be in touch"
        ]
        
        if any(phrase in response_lower for phrase in ending_phrases):
            analysis["end_conversation"] = True
            analysis["next_stage"] = ConversationStage.COMPLETED.value
        
        # Check for interest indicators
        interest_phrases = ["excellent", "great", "wonderful", "perfect"]
        if any(phrase in response_lower for phrase in interest_phrases):
            analysis["customer_interested"] = True
            if "time" in response_lower:
                analysis["next_stage"] = ConversationStage.SCHEDULING.value
        
        # Check for not interested indicators
        not_interested_phrases = ["understand", "no problem", "remove you"]
        if any(phrase in response_lower for phrase in not_interested_phrases):
            analysis["customer_not_interested"] = True
            if "remove" in response_lower or "do not call" in response_lower:
                analysis["next_stage"] = ConversationStage.DNC_QUESTION.value
        
        return analysis
    
    def get_performance_stats(self) -> Dict[str, Any]:
        """Get voice processing performance statistics"""
        total_requests = self.optimized_responses + self.lyzr_api_calls
        
        if total_requests == 0:
            return {"no_requests": True}
        
        optimization_rate = (self.optimized_responses / total_requests) * 100
        avg_processing_time = self.total_processing_time / total_requests if total_requests > 0 else 0
        
        return {
            "total_requests": total_requests,
            "optimized_responses": self.optimized_responses,
            "lyzr_api_calls": self.lyzr_api_calls,
            "optimization_rate": optimization_rate,
            "average_processing_time_ms": avg_processing_time,
            "time_saved_ms": self.optimized_responses * 1200,  # Estimated LYZR call time
            "performance_improvement": f"{optimization_rate:.1f}% of responses optimized for speed"
        }