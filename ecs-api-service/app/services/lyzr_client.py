"""
LYZR Agent Client Service
Handles conversation and summary agent interactions
"""

import asyncio
import httpx
import json
import logging
import time
from typing import Dict, Any, Optional
from datetime import datetime
import uuid

from shared.config.settings import settings

logger = logging.getLogger(__name__)

class LYZRAgentClient:
    """Client for LYZR conversation and summary agents"""
    
    def __init__(self):
        self.api_key = settings.lyzr_user_api_key
        self.base_url = settings.lyzr_api_base_url
        self.conversation_agent_id = settings.lyzr_conversation_agent_id
        self.summary_agent_id = settings.lyzr_summary_agent_id
        
        # HTTP client with optimized settings
        self.session = httpx.AsyncClient(
            timeout=30.0,  # Longer timeout for AI processing
            limits=httpx.Limits(
                max_keepalive_connections=5,
                max_connections=15
            )
        )
        
        # Performance tracking
        self.conversations_count = 0
        self.summaries_count = 0
        self.total_latency = 0.0
        self.errors_count = 0
        
        # Session management
        self.active_sessions = {}
    
    def is_configured(self) -> bool:
        """Check if LYZR is properly configured"""
        return bool(
            self.api_key and 
            self.conversation_agent_id and 
            not self.api_key.startswith("your_")
        )
    
    async def start_conversation(self, client_name: str, phone_number: str) -> Dict[str, Any]:
        """Start a new conversation session"""
        if not self.is_configured():
            return {
                "success": False,
                "error": "LYZR not configured",
                "session_id": None
            }
        
        try:
            session_id = f"voice-{uuid.uuid4().hex[:12]}"
            
            # Store session info
            self.active_sessions[session_id] = {
                "client_name": client_name,
                "phone_number": phone_number,
                "started_at": datetime.utcnow(),
                "turn_count": 0
            }
            
            logger.info(f"🤖 Started LYZR session {session_id} for {client_name}")
            
            return {
                "success": True,
                "session_id": session_id,
                "message": "Conversation session started"
            }
            
        except Exception as e:
            logger.error(f"❌ Failed to start LYZR session: {e}")
            return {
                "success": False,
                "error": str(e),
                "session_id": None
            }
    
    async def get_agent_response(
        self, 
        session_id: str, 
        customer_message: str,
        context: Optional[Dict[str, Any]] = None
    ) -> Dict[str, Any]:
        """Get response from LYZR conversation agent"""
        
        if not self.is_configured():
            return {
                "success": False,
                "error": "LYZR not configured",
                "response": "I apologize, but I'm having technical difficulties. Let me transfer you to a human agent.",
                "session_ended": True
            }
        
        start_time = time.time()
        
        try:
            # Get session info
            session_info = self.active_sessions.get(session_id, {})
            client_name = session_info.get("client_name", "")
            
            # Prepare the message with context
            full_message = self._prepare_message_with_context(
                customer_message, 
                client_name, 
                context
            )
            
            # Make request to LYZR
            url = f"{self.base_url}/v3/inference/chat/"
            
            headers = {
                "Content-Type": "application/json",
                "x-api-key": self.api_key
            }
            
            data = {
                "user_id": self.api_key,
                "agent_id": self.conversation_agent_id,
                "session_id": session_id,
                "message": full_message
            }
            
            response = await self.session.post(url, headers=headers, json=data)
            
            # Calculate latency
            latency = (time.time() - start_time) * 1000  # ms
            self.total_latency += latency
            
            if response.status_code == 200:
                result = response.json()
                agent_response = result.get("response", "").strip()
                
                # Update session
                if session_id in self.active_sessions:
                    self.active_sessions[session_id]["turn_count"] += 1
                
                self.conversations_count += 1
                
                # Check if conversation should end
                should_end = self._should_end_conversation(agent_response, customer_message)
                
                logger.info(f"🤖 LYZR response in {latency:.0f}ms: '{agent_response[:50]}...'")
                
                return {
                    "success": True,
                    "response": agent_response,
                    "latency_ms": latency,
                    "session_ended": should_end,
                    "turn_count": session_info.get("turn_count", 0) + 1
                }
            
            else:
                error_msg = f"LYZR API error: {response.status_code}"
                logger.error(f"❌ {error_msg}")
                self.errors_count += 1
                
                # Provide fallback response
                fallback_response = self._get_fallback_response(customer_message)
                
                return {
                    "success": False,
                    "error": error_msg,
                    "response": fallback_response,
                    "latency_ms": latency,
                    "session_ended": True,
                    "fallback_used": True
                }
                
        except Exception as e:
            latency = (time.time() - start_time) * 1000
            logger.error(f"❌ LYZR conversation failed: {e}")
            self.errors_count += 1
            
            # Provide fallback response
            fallback_response = self._get_fallback_response(customer_message)
            
            return {
                "success": False,
                "error": str(e),
                "response": fallback_response,
                "latency_ms": latency,
                "session_ended": True,
                "fallback_used": True
            }
    
    async def generate_call_summary(
        self, 
        conversation_transcript: str, 
        client_name: str,
        call_outcome: str
    ) -> Dict[str, Any]:
        """Generate call summary using LYZR summary agent"""
        
        if not settings.lyzr_summary_agent_id:
            return {
                "success": False,
                "error": "Summary agent not configured",
                "summary": self._generate_basic_summary(conversation_transcript, call_outcome)
            }
        
        start_time = time.time()
        
        try:
            # Prepare summary prompt
            summary_prompt = self._create_summary_prompt(
                conversation_transcript, 
                client_name, 
                call_outcome
            )
            
            url = f"{self.base_url}/v3/inference/chat/"
            
            headers = {
                "Content-Type": "application/json",
                "x-api-key": self.api_key
            }
            
            data = {
                "user_id": self.api_key,
                "agent_id": settings.lyzr_summary_agent_id,
                "session_id": f"summary-{int(time.time())}",
                "message": summary_prompt
            }
            
            response = await self.session.post(url, headers=headers, json=data)
            
            latency = (time.time() - start_time) * 1000
            
            if response.status_code == 200:
                result = response.json()
                summary_text = result.get("response", "").strip()
                
                self.summaries_count += 1
                
                # Parse structured summary
                parsed_summary = self._parse_summary_response(summary_text, call_outcome)
                
                logger.info(f"📝 Summary generated in {latency:.0f}ms")
                
                return {
                    "success": True,
                    "summary": parsed_summary,
                    "raw_summary": summary_text,
                    "latency_ms": latency
                }
            
            else:
                logger.error(f"❌ Summary API error: {response.status_code}")
                fallback_summary = self._generate_basic_summary(conversation_transcript, call_outcome)
                
                return {
                    "success": False,
                    "error": f"API error: {response.status_code}",
                    "summary": fallback_summary,
                    "latency_ms": latency,
                    "fallback_used": True
                }
                
        except Exception as e:
            latency = (time.time() - start_time) * 1000
            logger.error(f"❌ Summary generation failed: {e}")
            
            fallback_summary = self._generate_basic_summary(conversation_transcript, call_outcome)
            
            return {
                "success": False,
                "error": str(e),
                "summary": fallback_summary,
                "latency_ms": latency,
                "fallback_used": True
            }
    
    def _prepare_message_with_context(
        self, 
        customer_message: str, 
        client_name: str, 
        context: Optional[Dict[str, Any]]
    ) -> str:
        """Prepare customer message with additional context"""
        
        # Base message
        message = f"Customer ({client_name}): {customer_message}"
        
        # Add context if available
        if context:
            if context.get("is_first_interaction"):
                message += "\n[Context: This is the first interaction in the call]"
            
            if context.get("previous_response"):
                message += f"\n[Previous agent response: {context['previous_response'][:100]}...]"
            
            if context.get("call_duration_seconds"):
                duration = context["call_duration_seconds"]
                message += f"\n[Call duration: {duration}s]"
        
        return message
    
    def _should_end_conversation(self, agent_response: str, customer_message: str) -> bool:
        """Determine if conversation should end"""
        
        # End phrases from agent
        end_phrases = [
            "goodbye", "thank you for your time", "have a great day",
            "we'll be in touch", "someone will contact you",
            "end the call", "transfer you", "talk to you soon"
        ]
        
        agent_lower = agent_response.lower()
        for phrase in end_phrases:
            if phrase in agent_lower:
                return True
        
        # End phrases from customer
        customer_end_phrases = [
            "not interested", "don't call", "remove me", "stop calling",
            "bye", "goodbye", "hang up", "end call"
        ]
        
        customer_lower = customer_message.lower()
        for phrase in customer_end_phrases:
            if phrase in customer_lower:
                return True
        
        return False
    
    def _get_fallback_response(self, customer_message: str) -> str:
        """Get fallback response when LYZR is unavailable"""
        
        customer_lower = customer_message.lower()
        
        # Simple pattern matching for common responses
        if any(word in customer_lower for word in ["yes", "interested", "sure", "okay"]):
            return "That's wonderful! I'll have one of our specialists contact you within 24 hours to discuss your options. Thank you for your time today!"
        
        elif any(word in customer_lower for word in ["no", "not interested", "busy"]):
            return "I understand. Thank you for your time. Have a great day!"
        
        elif any(word in customer_lower for word in ["stop", "remove", "don't call"]):
            return "I'll make sure to remove you from our calling list. Thank you, and have a good day."
        
        else:
            return "I apologize, but I'm having technical difficulties. Let me have one of our team members call you back. Thank you for your patience."
    
    def _create_summary_prompt(self, transcript: str, client_name: str, call_outcome: str) -> str:
        """Create structured prompt for call summary"""
        
        prompt = f"""Please analyze this voice call transcript and provide a structured summary:

Client: {client_name}
Call Outcome: {call_outcome}

Transcript:
{transcript}

Please provide a JSON response with the following structure:
{{
    "outcome": "{call_outcome}",
    "sentiment": "positive|neutral|negative",
    "key_points": ["point1", "point2", "point3"],
    "customer_concerns": ["concern1", "concern2"],
    "customer_interests": ["interest1", "interest2"],
    "recommended_actions": ["action1", "action2"],
    "agent_notes": "detailed notes for follow-up",
    "urgency": "high|medium|low",
    "follow_up_timeframe": "within_24_hours|within_week|next_month",
    "interest_level": "high|medium|low",
    "services_mentioned": ["service1", "service2"],
    "objections_raised": ["objection1", "objection2"],
    "conversation_quality": "excellent|good|fair|poor",
    "call_duration_assessment": "appropriate|too_short|too_long"
}}

Focus on extracting actionable insights for the follow-up team."""
        
        return prompt
    
    def _parse_summary_response(self, summary_text: str, call_outcome: str) -> Dict[str, Any]:
        """Parse LYZR summary response into structured format"""
        
        try:
            # Try to extract JSON from response
            import re
            json_match = re.search(r'\{.*\}', summary_text, re.DOTALL)
            
            if json_match:
                json_str = json_match.group()
                parsed = json.loads(json_str)
                
                # Validate required fields
                if isinstance(parsed, dict):
                    return parsed
            
        except Exception as e:
            logger.warning(f"Failed to parse JSON summary: {e}")
        
        # Fallback parsing
        return self._generate_basic_summary("", call_outcome)
    
    def _generate_basic_summary(self, transcript: str, call_outcome: str) -> Dict[str, Any]:
        """Generate basic summary when LYZR is unavailable"""
        
        # Extract basic info from transcript
        word_count = len(transcript.split()) if transcript else 0
        
        # Determine sentiment based on outcome
        sentiment_map = {
            "interested": "positive",
            "not_interested": "neutral", 
            "dnc_requested": "negative",
            "no_answer": "neutral"
        }
        
        return {
            "outcome": call_outcome,
            "sentiment": sentiment_map.get(call_outcome, "neutral"),
            "key_points": [f"Call completed with outcome: {call_outcome}"],
            "customer_concerns": [],
            "customer_interests": ["health insurance"] if call_outcome == "interested" else [],
            "recommended_actions": ["follow_up_call"] if call_outcome == "interested" else [],
            "agent_notes": f"Automated call completed. Transcript length: {word_count} words.",
            "urgency": "high" if call_outcome == "interested" else "low",
            "follow_up_timeframe": "within_24_hours" if call_outcome == "interested" else "next_month",
            "interest_level": "high" if call_outcome == "interested" else "low",
            "services_mentioned": ["health insurance"],
            "objections_raised": [],
            "conversation_quality": "good",
            "call_duration_assessment": "appropriate",
            "generated_by": "fallback_system"
        }
    
    def end_session(self, session_id: str):
        """End a conversation session"""
        if session_id in self.active_sessions:
            session_info = self.active_sessions.pop(session_id)
            logger.info(f"🏁 Ended LYZR session {session_id} after {session_info.get('turn_count', 0)} turns")
    
    def get_statistics(self) -> Dict[str, Any]:
        """Get LYZR agent statistics"""
        avg_latency = (self.total_latency / max(1, self.conversations_count))
        error_rate = (self.errors_count / max(1, self.conversations_count + self.summaries_count + self.errors_count)) * 100
        
        return {
            "configured": self.is_configured(),
            "conversations_count": self.conversations_count,
            "summaries_count": self.summaries_count,
            "average_latency_ms": round(avg_latency, 1),
            "total_errors": self.errors_count,
            "error_rate_percent": round(error_rate, 1),
            "active_sessions": len(self.active_sessions),
            "conversation_agent_id": self.conversation_agent_id,
            "summary_agent_id": settings.lyzr_summary_agent_id
        }
    
    async def test_connection(self) -> Dict[str, Any]:
        """Test LYZR connection with sample conversation"""
        if not self.is_configured():
            return {"success": False, "error": "LYZR not configured"}
        
        try:
            # Test conversation agent
            session_result = await self.start_conversation("Test User", "+1234567890")
            if not session_result["success"]:
                return {"success": False, "error": "Failed to start session"}
            
            session_id = session_result["session_id"]
            
            # Test getting a response
            response_result = await self.get_agent_response(
                session_id, 
                "Hello, this is a test message."
            )
            
            # Clean up
            self.end_session(session_id)
            
            return {
                "success": response_result["success"],
                "latency_ms": response_result.get("latency_ms", 0),
                "response_length": len(response_result.get("response", "")),
                "message": "Connection test completed"
            }
            
        except Exception as e:
            return {"success": False, "error": str(e)}

# Global instance
lyzr_client = LYZRAgentClient()