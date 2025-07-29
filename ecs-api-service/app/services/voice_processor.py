"""
Voice Processor Service
Handles customer speech processing and response generation
"""

import asyncio
import httpx
import logging
import time
from typing import Dict, Any, Optional, List
from datetime import datetime

from shared.config.settings import settings
from shared.models.call_session import CallSession, ConversationStage
from shared.utils.redis_client import response_cache

logger = logging.getLogger(__name__)

class VoiceProcessor:
    """Service for processing customer speech and generating responses"""
    
    def __init__(self):
        self.httpx_client = httpx.AsyncClient(timeout=30.0)
        
        # Common response patterns for faster processing
        self.response_patterns = {
            "yes_responses": ["yes", "yeah", "yep", "sure", "absolutely", "definitely", "of course"],
            "no_responses": ["no", "nope", "not really", "not interested", "no thanks"],
            "time_morning": ["morning", "am", "early", "before noon", "9", "10", "11"],
            "time_afternoon": ["afternoon", "pm", "after lunch", "1", "2", "3", "4"],
            "time_evening": ["evening", "night", "after 5", "5", "6", "7"],
            "dnc_requests": ["remove", "do not call", "don't call", "take me off", "unsubscribe"]
        }
    
    async def process_customer_speech(
        self,
        session: CallSession,
        customer_speech: str,
        client_phone: str
    ) -> Dict[str, Any]:
        """Process customer speech and generate appropriate response"""
        
        start_time = time.time()
        logger.info(f"🗣️ Processing speech: '{customer_speech}' for session {session.session_id}")
        
        try:
            # Clean and normalize speech
            normalized_speech = self._normalize_speech(customer_speech)
            
            # Quick pattern matching for common responses
            pattern_result = self._check_response_patterns(normalized_speech, session)
            if pattern_result:
                logger.info(f"⚡ Pattern match found: {pattern_result['response_category']}")
                pattern_result["generation_time_ms"] = int((time.time() - start_time) * 1000)
                return pattern_result
            
            # Use LYZR agent for complex responses
            lyzr_result = await self._process_with_lyzr_agent(
                session=session,
                customer_speech=normalized_speech,
                client_phone=client_phone
            )
            
            if lyzr_result["success"]:
                lyzr_result["generation_time_ms"] = int((time.time() - start_time) * 1000)
                return lyzr_result
            
            # Fallback response
            fallback_result = self._create_fallback_response(session)
            fallback_result["generation_time_ms"] = int((time.time() - start_time) * 1000)
            return fallback_result
            
        except Exception as e:
            logger.error(f"❌ Voice processing error: {e}")
            return {
                "success": False,
                "error": str(e),
                "response_text": "I apologize, there was an issue. Thank you for your time.",
                "end_conversation": True,
                "final_outcome": "error"
            }
    
    def _normalize_speech(self, speech: str) -> str:
        """Normalize customer speech for processing"""
        
        if not speech:
            return ""
        
        # Convert to lowercase and strip
        normalized = speech.lower().strip()
        
        # Remove common filler words and artifacts
        filler_words = ["um", "uh", "er", "ah", "like", "you know", "well"]
        words = normalized.split()
        filtered_words = [word for word in words if word not in filler_words]
        
        return " ".join(filtered_words)
    
    def _check_response_patterns(self, speech: str, session: CallSession) -> Optional[Dict[str, Any]]:
        """Check speech against common response patterns"""
        
        speech_lower = speech.lower()
        
        # Check for "Yes" responses
        if any(pattern in speech_lower for pattern in self.response_patterns["yes_responses"]):
            if session.conversation_stage == ConversationStage.GREETING:
                return {
                    "success": True,
                    "response_text": "Excellent! What time would work best for you - morning, afternoon, or evening?",
                    "response_category": "interested",
                    "detected_intent": "interested",
                    "conversation_stage": "time_preference",
                    "end_conversation": False
                }
        
        # Check for "No" responses
        if any(pattern in speech_lower for pattern in self.response_patterns["no_responses"]):
            if session.conversation_stage == ConversationStage.GREETING:
                return {
                    "success": True,
                    "response_text": "I understand. Would you like us to remove you from future promotional calls?",
                    "response_category": "not_interested",
                    "detected_intent": "not_interested",
                    "conversation_stage": "dnc_check",
                    "end_conversation": False
                }
        
        # Check for time preferences
        if any(pattern in speech_lower for pattern in self.response_patterns["time_morning"]):
            return {
                "success": True,
                "response_text": "Perfect! Our insurance specialist will call you tomorrow morning between 9 and 11 AM. Thank you!",
                "response_category": "schedule_morning",
                "detected_intent": "schedule_morning",
                "end_conversation": True,
                "final_outcome": "scheduled_morning"
            }
        
        if any(pattern in speech_lower for pattern in self.response_patterns["time_afternoon"]):
            return {
                "success": True,
                "response_text": "Great! Our team will reach out to you this afternoon between 1 and 4 PM. Thank you!",
                "response_category": "schedule_afternoon",
                "detected_intent": "schedule_afternoon",
                "end_conversation": True,
                "final_outcome": "scheduled_afternoon"
            }
        
        # Check for DNC requests
        if any(pattern in speech_lower for pattern in self.response_patterns["dnc_requests"]):
            return {
                "success": True,
                "response_text": "Done! You've been added to our do-not-call list. Have a great day!",
                "response_category": "dnc_confirmation",
                "detected_intent": "dnc_request",
                "end_conversation": True,
                "final_outcome": "dnc_requested"
            }
        
        return None
    
    async def _process_with_lyzr_agent(
        self,
        session: CallSession,
        customer_speech: str,
        client_phone: str
    ) -> Dict[str, Any]:
        """Process speech using LYZR agent"""
        
        try:
            # Check cache first
            cache_key = f"lyzr_response:{session.lyzr_agent_id}:{hash(customer_speech)}:{session.conversation_stage}"
            cached_response = await response_cache.get(cache_key)
            
            if cached_response:
                logger.info("⚡ Using cached LYZR response")
                return cached_response
            
            # Prepare LYZR request
            lyzr_payload = {
                "user_id": session.lyzr_session_id,
                "agent_id": session.lyzr_agent_id,
                "message": customer_speech,
                "session_id": session.lyzr_session_id,
                "context": {
                    "conversation_stage": session.conversation_stage.value,
                    "turn_count": len(session.conversation_turns),
                    "client_phone": client_phone,
                    "call_duration": self._get_call_duration(session)
                }
            }
            
            # Call LYZR agent
            response = await self.httpx_client.post(
                f"{settings.lyzr_api_base_url}/chat/completions",
                headers={
                    "Authorization": f"Bearer {settings.lyzr_user_api_key}",
                    "Content-Type": "application/json"
                },
                json=lyzr_payload,
                timeout=15.0
            )
            
            if response.status_code == 200:
                lyzr_response = response.json()
                
                # Parse LYZR response
                result = self._parse_lyzr_response(lyzr_response, session)
                
                # Cache successful response
                if result["success"]:
                    await response_cache.set(cache_key, result, expire_seconds=300)
                
                return result
            
            else:
                logger.error(f"LYZR API error: {response.status_code} - {response.text}")
                return {"success": False, "error": f"LYZR API error: {response.status_code}"}
        
        except asyncio.TimeoutError:
            logger.error("LYZR API timeout")
            return {"success": False, "error": "LYZR API timeout"}
        
        except Exception as e:
            logger.error(f"LYZR processing error: {e}")
            return {"success": False, "error": str(e)}
    
    def _parse_lyzr_response(self, lyzr_response: Dict[str, Any], session: CallSession) -> Dict[str, Any]:
        """Parse LYZR agent response into structured format"""
        
        try:
            # Extract response text
            if "choices" in lyzr_response and lyzr_response["choices"]:
                response_text = lyzr_response["choices"][0]["message"]["content"]
            elif "response" in lyzr_response:
                response_text = lyzr_response["response"]
            else:
                response_text = "Thank you for your time."
            
            # Determine if conversation should end
            end_indicators = ["goodbye", "thank you for your time", "have a great day", "end call"]
            end_conversation = any(indicator in response_text.lower() for indicator in end_indicators)
            
            # Determine response category
            response_category = self._categorize_response(response_text)
            
            # Determine conversation stage
            conversation_stage = self._determine_next_stage(response_text, session)
            
            # Detect customer intent
            detected_intent = self._detect_intent(response_text)
            
            return {
                "success": True,
                "response_text": response_text,
                "response_category": response_category,
                "detected_intent": detected_intent,
                "conversation_stage": conversation_stage,
                "end_conversation": end_conversation,
                "final_outcome": self._determine_outcome(response_text) if end_conversation else None
            }
            
        except Exception as e:
            logger.error(f"Error parsing LYZR response: {e}")
            return {
                "success": False,
                "error": f"Response parsing error: {e}",
                "response_text": "Thank you for your time.",
                "end_conversation": True
            }
    
    def _categorize_response(self, response_text: str) -> str:
        """Categorize the response for TTS selection"""
        
        text_lower = response_text.lower()
        
        if "excellent" in text_lower or "great" in text_lower or "perfect" in text_lower:
            return "interested"
        elif "understand" in text_lower or "remove" in text_lower:
            return "not_interested"
        elif "morning" in text_lower:
            return "schedule_morning"
        elif "afternoon" in text_lower:
            return "schedule_afternoon"
        elif "do-not-call" in text_lower or "added" in text_lower:
            return "dnc_confirmation"
        elif "goodbye" in text_lower or "great day" in text_lower:
            return "goodbye"
        else:
            return "dynamic"
    
    def _determine_next_stage(self, response_text: str, session: CallSession) -> str:
        """Determine the next conversation stage"""
        
        text_lower = response_text.lower()
        
        if "time" in text_lower and "work" in text_lower:
            return "time_preference"
        elif "remove" in text_lower or "do-not-call" in text_lower:
            return "dnc_check"
        elif "morning" in text_lower or "afternoon" in text_lower:
            return "scheduling"
        elif "goodbye" in text_lower or "thank you" in text_lower:
            return "closing"
        else:
            return session.conversation_stage.value  # Keep current stage
    
    def _detect_intent(self, response_text: str) -> str:
        """Detect customer intent from response"""
        
        text_lower = response_text.lower()
        
        if "excellent" in text_lower or "interested" in text_lower:
            return "interested"
        elif "not interested" in text_lower or "understand" in text_lower:
            return "not_interested"
        elif "morning" in text_lower:
            return "schedule_morning"
        elif "afternoon" in text_lower:
            return "schedule_afternoon"
        elif "remove" in text_lower or "do-not-call" in text_lower:
            return "dnc_request"
        else:
            return "unclear"
    
    def _determine_outcome(self, response_text: str) -> str:
        """Determine final call outcome"""
        
        text_lower = response_text.lower()
        
        if "morning" in text_lower:
            return "scheduled_morning"
        elif "afternoon" in text_lower:
            return "scheduled_afternoon"
        elif "do-not-call" in text_lower:
            return "dnc_requested"
        elif "not interested" in text_lower:
            return "not_interested"
        else:
            return "completed"
    
    def _create_fallback_response(self, session: CallSession) -> Dict[str, Any]:
        """Create fallback response when other methods fail"""
        
        if session.conversation_stage == ConversationStage.GREETING:
            response_text = "I understand. Would you like us to remove you from future calls?"
            category = "not_interested"
            next_stage = "dnc_check"
            end_conversation = False
        else:
            response_text = "Thank you for your time today. Have a wonderful day!"
            category = "goodbye"
            next_stage = "closing"
            end_conversation = True
        
        return {
            "success": True,
            "response_text": response_text,
            "response_category": category,
            "detected_intent": "fallback",
            "conversation_stage": next_stage,
            "end_conversation": end_conversation,
            "final_outcome": "completed" if end_conversation else None
        }
    
    def _get_call_duration(self, session: CallSession) -> int:
        """Get call duration in seconds"""
        
        if session.answered_at:
            duration = (datetime.utcnow() - session.answered_at).total_seconds()
            return int(duration)
        return 0
    
    async def close(self):
        """Close HTTP client"""
        await self.httpx_client.aclose()

# Additional helper functions for client record updates
async def update_client_record(session: CallSession, response_result: Dict[str, Any]):
    """Update client record based on call outcome"""
    
    try:
        from shared.utils.database import client_repo
        from shared.models.client import CRMTag, CallOutcome
        
        outcome = response_result.get("final_outcome")
        
        if outcome == "scheduled_morning":
            await client_repo.add_crm_tag(session.client_id, CRMTag.INTERESTED)
            await client_repo.update_call_outcome(session.client_id, CallOutcome.INTERESTED)
        
        elif outcome == "scheduled_afternoon":
            await client_repo.add_crm_tag(session.client_id, CRMTag.INTERESTED)
            await client_repo.update_call_outcome(session.client_id, CallOutcome.INTERESTED)
        
        elif outcome == "dnc_requested":
            await client_repo.add_crm_tag(session.client_id, CRMTag.DNC_REQUESTED)
            await client_repo.update_call_outcome(session.client_id, CallOutcome.DNC_REQUESTED)
        
        elif outcome == "not_interested":
            await client_repo.add_crm_tag(session.client_id, CRMTag.NOT_INTERESTED)
            await client_repo.update_call_outcome(session.client_id, CallOutcome.NOT_INTERESTED)
        
        else:
            await client_repo.update_call_outcome(session.client_id, CallOutcome.COMPLETED)
        
        logger.info(f"✅ Updated client record for {session.client_id} with outcome: {outcome}")
        
    except Exception as e:
        logger.error(f"❌ Failed to update client record: {e}")

# Pattern matching utilities
class ResponsePatternMatcher:
    """Advanced pattern matching for common customer responses"""
    
    def __init__(self):
        self.patterns = {
            "affirmative": {
                "keywords": ["yes", "yeah", "yep", "sure", "okay", "ok", "absolutely", "definitely", "of course", "sounds good"],
                "phrases": ["that works", "that's fine", "sounds great", "i'm interested"]
            },
            "negative": {
                "keywords": ["no", "nope", "not really", "not interested", "no thanks", "not today"],
                "phrases": ["not interested", "don't want", "not looking", "not right now"]
            },
            "time_morning": {
                "keywords": ["morning", "am", "early", "9", "10", "11"],
                "phrases": ["in the morning", "before noon", "early morning", "9 am", "10 am", "11 am"]
            },
            "time_afternoon": {
                "keywords": ["afternoon", "pm", "lunch", "1", "2", "3", "4"],
                "phrases": ["in the afternoon", "after lunch", "1 pm", "2 pm", "3 pm", "4 pm"]
            },
            "time_evening": {
                "keywords": ["evening", "night", "5", "6", "7"],
                "phrases": ["in the evening", "after work", "5 pm", "6 pm", "7 pm"]
            },
            "dnc_request": {
                "keywords": ["remove", "unsubscribe", "stop", "don't call"],
                "phrases": ["take me off", "remove me", "don't call me", "stop calling", "do not call"]
            }
        }
    
    def match_pattern(self, speech: str) -> Optional[str]:
        """Match speech against patterns and return category"""
        
        speech_lower = speech.lower()
        
        for category, pattern_data in self.patterns.items():
            # Check keywords
            if any(keyword in speech_lower for keyword in pattern_data["keywords"]):
                return category
            
            # Check phrases
            if any(phrase in speech_lower for phrase in pattern_data["phrases"]):
                return category
        
        return None
    
    def get_confidence_score(self, speech: str, category: str) -> float:
        """Get confidence score for pattern match"""
        
        if category not in self.patterns:
            return 0.0
        
        speech_lower = speech.lower()
        pattern_data = self.patterns[category]
        
        keyword_matches = sum(1 for keyword in pattern_data["keywords"] if keyword in speech_lower)
        phrase_matches = sum(1 for phrase in pattern_data["phrases"] if phrase in speech_lower)
        
        total_patterns = len(pattern_data["keywords"]) + len(pattern_data["phrases"])
        total_matches = keyword_matches + phrase_matches
        
        return min(total_matches / total_patterns, 1.0)