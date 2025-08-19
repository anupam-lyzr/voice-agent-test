"""
Call Summarizer Service
Generates call summaries using LYZR Summary Agent
"""

import asyncio
import httpx
import logging
import json
from typing import Dict, Any, Optional
from datetime import datetime

from shared.config.settings import settings
from shared.models.client import Client, CallSummary
from shared.models.call_session import CallSession

logger = logging.getLogger(__name__)

class CallSummarizerService:
    """Service for generating call summaries with LYZR"""
    
    def __init__(self):
        # HTTP client for LYZR API
        self.lyzr_session = httpx.AsyncClient(
            timeout=30.0,  # Longer timeout for summary generation
            limits=httpx.Limits(max_keepalive_connections=5)
        )
        
        # Statistics
        self.summaries_generated = 0
        self.summaries_failed = 0
    
    async def generate_call_summary(
        self,
        call_session: CallSession,
        client: Client,
        call_outcome: str
    ) -> Dict[str, Any]:
        """Generate comprehensive call summary using LYZR Summary Agent"""
        
        logger.info(f"📝 Generating call summary for {client.client.full_name}")
        
        try:
            # Prepare transcript and context
            summary_request = self._prepare_summary_request(call_session, client, call_outcome)
            
            # Generate summary with LYZR
            lyzr_result = await self._call_lyzr_summary_agent(summary_request)
            
            if lyzr_result["success"]:
                # Parse and structure the summary
                structured_summary = self._parse_lyzr_summary(
                    lyzr_result["summary_text"],
                    call_session,
                    client,
                    call_outcome
                )
                
                self.summaries_generated += 1
                
                logger.info(f"✅ Call summary generated for {client.client.full_name}")
                
                return {
                    "success": True,
                    "summary": structured_summary,
                    "raw_summary": lyzr_result["summary_text"]
                }
            
            else:
                # Fallback to basic summary
                fallback_summary = self._generate_fallback_summary(
                    call_session, client, call_outcome
                )
                
                self.summaries_failed += 1
                
                return {
                    "success": True,
                    "summary": fallback_summary,
                    "method": "fallback",
                    "lyzr_error": lyzr_result.get("error")
                }
                
        except Exception as e:
            logger.error(f"❌ Call summary generation error: {e}")
            self.summaries_failed += 1
            
            # Return basic fallback summary
            fallback_summary = self._generate_fallback_summary(
                call_session, client, call_outcome
            )
            
            return {
                "success": True,
                "summary": fallback_summary,
                "method": "error_fallback",
                "error": str(e)
            }
    
    def _prepare_summary_request(
        self,
        call_session: CallSession,
        client: Client,
        call_outcome: str
    ) -> Dict[str, Any]:
        """Prepare the summary request for LYZR"""
        
        # Get full conversation transcript
        transcript = call_session.get_transcript()
        
        # Prepare context information
        context = {
            "client_name": client.client.full_name,
            "phone_number": client.client.phone,
            "last_agent": client.client.last_agent,
            "call_duration": call_session.session_metrics.total_call_duration_seconds,
            "total_turns": len(call_session.conversation_turns),
            "call_outcome": call_outcome,
            "conversation_stage_reached": call_session.conversation_stage.value if hasattr(call_session.conversation_stage, 'value') else call_session.conversation_stage
        }
        
        # Build comprehensive prompt for LYZR Summary Agent
        summary_prompt = f"""
Please analyze this customer service call and provide a comprehensive summary.

CALL CONTEXT:
- Customer: {context['client_name']}
- Phone: {context['phone_number']}
- Duration: {context['call_duration']} seconds
- Conversation turns: {context['total_turns']}
- Final outcome: {context['call_outcome']}
- Stage reached: {context['conversation_stage_reached']}

CONVERSATION TRANSCRIPT:
{transcript}

Please provide a structured summary including:
1. Call outcome (interested/not_interested/dnc_requested/no_answer)
2. Customer sentiment (positive/neutral/negative)
3. Key conversation points
4. Customer concerns or objections
5. Recommended next actions
6. Agent notes for follow-up
7. Urgency level (high/medium/low)
8. Interest level assessment
9. Services mentioned or discussed
10. Overall conversation quality assessment

Format as JSON with these fields:
- outcome
- sentiment  
- key_points (array)
- customer_concerns (array)
- recommended_actions (array)
- agent_notes (string)
- urgency
- follow_up_timeframe
- interest_level
- services_mentioned (array)
- objections_raised (array)
- conversation_quality
- agent_performance
"""
        
        return {
            "prompt": summary_prompt,
            "context": context,
            "transcript": transcript
        }
    
    async def _call_lyzr_summary_agent(self, summary_request: Dict[str, Any]) -> Dict[str, Any]:
        """Call LYZR Summary Agent API"""
        
        if not settings.lyzr_summary_agent_id or not settings.lyzr_user_api_key:
            return {"success": False, "error": "LYZR Summary Agent not configured"}
        
        try:
            url = f"{settings.lyzr_api_base_url}/v3/inference/chat/"
            
            headers = {
                "Content-Type": "application/json",
                "x-api-key": settings.lyzr_user_api_key
            }
            
            data = {
                "user_id": settings.lyzr_user_api_key,
                "agent_id": settings.lyzr_summary_agent_id,
                "session_id": f"summary-{datetime.utcnow().strftime('%Y%m%d%H%M%S')}",
                "message": summary_request["prompt"]
            }
            
            logger.info("🤖 Calling LYZR Summary Agent...")
            
            response = await self.lyzr_session.post(url, headers=headers, json=data)
            
            if response.status_code == 200:
                result = response.json()
                summary_text = result.get("response", "").strip()
                
                if summary_text:
                    return {"success": True, "summary_text": summary_text}
                else:
                    return {"success": False, "error": "Empty response from LYZR"}
            
            else:
                logger.error(f"LYZR Summary API error: {response.status_code} - {response.text}")
                return {"success": False, "error": f"API error: {response.status_code}"}
                
        except Exception as e:
            logger.error(f"LYZR Summary API call error: {e}")
            return {"success": False, "error": str(e)}
    
    def _parse_lyzr_summary(
        self,
        summary_text: str,
        call_session: CallSession,
        client: Client,
        call_outcome: str
    ) -> CallSummary:
        """Parse LYZR summary response into structured format"""
        
        try:
            # Try to parse as JSON first
            if summary_text.strip().startswith('{'):
                summary_data = json.loads(summary_text)
                
                return CallSummary(
                    summary_id=f"lyzr-{datetime.utcnow().strftime('%Y%m%d%H%M%S')}",
                    outcome=summary_data.get("outcome", call_outcome),
                    sentiment=summary_data.get("sentiment", "neutral"),
                    key_points=summary_data.get("key_points", []),
                    customer_concerns=summary_data.get("customer_concerns", []),
                    recommended_actions=summary_data.get("recommended_actions", []),
                    agent_notes=summary_data.get("agent_notes", ""),
                    urgency=summary_data.get("urgency", "medium"),
                    follow_up_timeframe=summary_data.get("follow_up_timeframe", "within_week"),
                    interest_level=summary_data.get("interest_level", "unknown"),
                    services_mentioned=summary_data.get("services_mentioned", []),
                    objections_raised=summary_data.get("objections_raised", []),
                    conversation_quality=summary_data.get("conversation_quality", "good"),
                    agent_performance=summary_data.get("agent_performance", "good")
                )
            
            else:
                # Parse natural language summary
                return self._parse_natural_language_summary(
                    summary_text, call_session, client, call_outcome
                )
                
        except json.JSONDecodeError:
            # Fallback to natural language parsing
            return self._parse_natural_language_summary(
                summary_text, call_session, client, call_outcome
            )
        except Exception as e:
            logger.error(f"Summary parsing error: {e}")
            return self._generate_fallback_summary(call_session, client, call_outcome)
    
    def _parse_natural_language_summary(
        self,
        summary_text: str,
        call_session: CallSession,
        client: Client,
        call_outcome: str
    ) -> CallSummary:
        """Parse natural language summary from LYZR"""
        
        # Extract key information using simple text analysis
        text_lower = summary_text.lower()
        
        # Determine sentiment
        sentiment = "neutral"
        if any(word in text_lower for word in ["positive", "happy", "satisfied", "pleased"]):
            sentiment = "positive"
        elif any(word in text_lower for word in ["negative", "frustrated", "angry", "upset"]):
            sentiment = "negative"
        
        # Extract key points (sentences that contain important information)
        key_points = []
        sentences = summary_text.split('.')
        for sentence in sentences[:3]:  # Take first 3 sentences as key points
            if len(sentence.strip()) > 20:
                key_points.append(sentence.strip())
        
        # Determine urgency
        urgency = "medium"
        if any(word in text_lower for word in ["urgent", "immediate", "asap", "quickly"]):
            urgency = "high"
        elif any(word in text_lower for word in ["later", "no rush", "whenever"]):
            urgency = "low"
        
        # Determine interest level
        interest_level = "unknown"
        if call_outcome == "interested":
            interest_level = "high"
        elif call_outcome == "not_interested":
            interest_level = "low"
        elif any(word in text_lower for word in ["maybe", "consider", "think about"]):
            interest_level = "medium"
        
        return CallSummary(
            summary_id=f"lyzr-nl-{datetime.utcnow().strftime('%Y%m%d%H%M%S')}",
            outcome=call_outcome,
            sentiment=sentiment,
            key_points=key_points,
            customer_concerns=[],
            recommended_actions=["Follow up with assigned agent"],
            agent_notes=summary_text[:200] + "..." if len(summary_text) > 200 else summary_text,
            urgency=urgency,
            follow_up_timeframe="within_week",
            interest_level=interest_level,
            services_mentioned=["insurance"],
            objections_raised=[],
            conversation_quality="good",
            agent_performance="good"
        )
    
    def _generate_fallback_summary(
        self,
        call_session: CallSession,
        client: Client,
        call_outcome: str
    ) -> CallSummary:
        """Generate basic fallback summary when LYZR is unavailable"""
        
        # Basic analysis based on call session data
        key_points = []
        
        if call_session.conversation_turns:
            key_points.append(f"Call lasted {call_session.session_metrics.total_call_duration_seconds} seconds")
            key_points.append(f"Had {len(call_session.conversation_turns)} conversation turns")
            
            if call_session.session_metrics.static_responses_used > 0:
                key_points.append(f"Used {call_session.session_metrics.static_responses_used} standard responses")
        
        # Determine next actions based on outcome
        recommended_actions = []
        if call_outcome == "interested":
            recommended_actions = ["Assign to agent", "Schedule discovery call", "Send follow-up email"]
        elif call_outcome == "not_interested":
            recommended_actions = ["Update CRM status", "Add to nurture campaign"]
        elif call_outcome == "dnc_requested":
            recommended_actions = ["Add to do-not-call list", "Update compliance status"]
        else:
            recommended_actions = ["Review call for quality", "Consider retry if appropriate"]
        
        return CallSummary(
            summary_id=f"fallback-{datetime.utcnow().strftime('%Y%m%d%H%M%S')}",
            outcome=call_outcome,
            sentiment="neutral",
            key_points=key_points,
            customer_concerns=[],
            recommended_actions=recommended_actions,
            agent_notes=f"Automated summary - Call outcome: {call_outcome}. Customer: {client.client.full_name}",
            urgency="medium",
            follow_up_timeframe="within_week",
            interest_level="unknown",
            services_mentioned=["insurance"],
            objections_raised=[],
            conversation_quality="unknown",
            agent_performance="automated_call"
        )
    
    def get_statistics(self) -> Dict[str, Any]:
        """Get call summarizer statistics"""
        total_attempts = self.summaries_generated + self.summaries_failed
        success_rate = (self.summaries_generated / total_attempts * 100) if total_attempts > 0 else 0
        
        return {
            "summaries_generated": self.summaries_generated,
            "summaries_failed": self.summaries_failed,
            "total_attempts": total_attempts,
            "success_rate": success_rate,
            "lyzr_summary_agent_configured": bool(
                settings.lyzr_summary_agent_id and 
                settings.lyzr_user_api_key and
                not settings.lyzr_summary_agent_id.startswith("your_")
            )
        }