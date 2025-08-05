"""
Updated Hybrid TTS Service - Integrated with Segmented Audio
Combines pre-generated segments with dynamic name insertion for optimal performance
"""

import asyncio
import hashlib
import httpx
import logging
import os
import time
import uuid
from typing import Dict, Any, Optional
from datetime import datetime

from shared.config.settings import settings
# from shared.utils.redis_client import response_cache
# response_cache will be imported when needed
response_cache = None

logger = logging.getLogger(__name__)

class HybridTTSService:
    """Service that uses segmented audio for personalized responses with real names"""
    
    def __init__(self):
        # Import segmented audio service
        from services.segmented_audio_service import segmented_audio_service
        self.segmented_service = segmented_audio_service
        
        # ElevenLabs client for fallback
        self.elevenlabs_session = httpx.AsyncClient(timeout=settings.webhook_timeout)
        
        # Performance tracking
        self.static_responses = 0
        self.segmented_responses = 0
        self.dynamic_responses = 0
        self.total_requests = 0
        
        # Response type mapping for AAG script
        self.response_mapping = {
            # Personalized responses (need concatenation)
            "greeting": {
                "template": "greeting",
                "needs_client_name": True,
                "needs_agent_name": False
            },
            "agent_introduction": {
                "template": "agent_intro", 
                "needs_client_name": False,
                "needs_agent_name": True
            },
            "schedule_confirmation": {
                "template": "schedule_confirmation",
                "needs_client_name": False,
                "needs_agent_name": True
            },
            "no_schedule_followup": {
                "template": "no_schedule_followup",
                "needs_client_name": False,
                "needs_agent_name": True
            },
            
            # Static responses (no names needed)
            "not_interested": {
                "template": "not_interested",
                "needs_client_name": False,
                "needs_agent_name": False
            },
            "dnc_confirmation": {
                "template": "dnc_confirmation", 
                "needs_client_name": False,
                "needs_agent_name": False
            },
            "keep_communications": {
                "template": "keep_communications",
                "needs_client_name": False,
                "needs_agent_name": False
            },
            "goodbye": {
                "template": "goodbye",
                "needs_client_name": False,
                "needs_agent_name": False
            },
            "clarification": {
                "template": "clarification",
                "needs_client_name": False,
                "needs_agent_name": False
            }
        }
    
    async def get_response_audio(
        self, 
        text: str, 
        response_type: str = "dynamic",
        client_data: Optional[Dict[str, Any]] = None,
        conversation_context: Optional[Dict[str, Any]] = None
    ) -> Dict[str, Any]:
        """
        Get audio response using segmented approach for personalized content
        """
        start_time = time.time()
        self.total_requests += 1
        
        try:
            logger.info(f"🎵 Processing audio request: {response_type}")
            
            # 1. Check if we have a mapped response type
            if response_type in self.response_mapping:
                return await self._get_mapped_response(response_type, client_data, start_time)
            
            # 2. Try to detect response type from text
            detected_type = self._detect_response_type(text)
            if detected_type:
                return await self._get_mapped_response(detected_type, client_data, start_time)
            
            # 3. Check for simple static responses
            static_result = await self._try_static_response(text)
            if static_result["success"]:
                self.static_responses += 1
                generation_time = (time.time() - start_time) * 1000
                
                return {
                    **static_result,
                    "generation_time_ms": generation_time,
                    "type": "static_segment"
                }
            
            # 4. Check cached dynamic responses
            cache_key = self._generate_text_cache_key(text, client_data)
            try:
                from shared.utils.redis_client import response_cache
                if response_cache:
                    cached_url = await response_cache.get_cached_response(cache_key)
                    if cached_url:
                        generation_time = (time.time() - start_time) * 1000
                        logger.info(f"💾 Cached TTS served: ({generation_time:.0f}ms)")
                        
                        return {
                            "success": True,
                            "audio_url": cached_url,
                            "generation_time_ms": generation_time,
                            "type": "cached"
                        }
            except ImportError:
                logger.warning("Redis cache not available")
                
            # 5. Generate dynamic TTS with ElevenLabs
            dynamic_result = await self._generate_dynamic_tts(text, client_data)
            if dynamic_result["success"]:
                self.dynamic_responses += 1
                generation_time = (time.time() - start_time) * 1000
                
                # Cache the result
                if response_cache:
                    await response_cache.cache_response(cache_key, dynamic_result["audio_url"], expire_seconds=3600)
                
                logger.info(f"🎤 Dynamic TTS generated: ({generation_time:.0f}ms)")
                
                return {
                    **dynamic_result,
                    "generation_time_ms": generation_time,
                    "type": "dynamic"
                }
            
            # 6. Final fallback
            logger.warning(f"⚠️ All TTS methods failed for: '{text[:50]}'")
            return {
                "success": False,
                "error": "All TTS methods failed",
                "generation_time_ms": (time.time() - start_time) * 1000,
                "type": "failed"
            }
            
        except Exception as e:
            logger.error(f"❌ Hybrid TTS error: {e}")
            return {
                "success": False,
                "error": str(e),
                "generation_time_ms": (time.time() - start_time) * 1000,
                "type": "error"
            }
    
    async def _get_mapped_response(
        self, 
        response_type: str, 
        client_data: Optional[Dict[str, Any]], 
        start_time: float
    ) -> Dict[str, Any]:
        """Get response using mapped template"""
        
        try:
            mapping = self.response_mapping[response_type]
            template_name = mapping["template"]
            
            # Extract names from client data
            client_name = None
            agent_name = None
            
            if client_data:
                if mapping["needs_client_name"]:
                    client_name = (client_data.get("client_name") or 
                                 client_data.get("first_name") or
                                 client_data.get("name"))
                
                if mapping["needs_agent_name"]:
                    agent_name = (client_data.get("agent_name") or
                                client_data.get("last_agent") or
                                client_data.get("assigned_agent"))
            
            # Get personalized audio using segmented service
            result = await self.segmented_service.get_personalized_audio(
                template_name=template_name,
                client_name=client_name,
                agent_name=agent_name,
                context=client_data
            )
            
            if result["success"]:
                self.segmented_responses += 1
                logger.info(f"🎯 Segmented audio served: {response_type} ({result['generation_time_ms']}ms)")
                
                return {
                    **result,
                    "type": "segmented"
                }
            else:
                # Fallback to dynamic TTS
                logger.warning(f"⚠️ Segmented audio failed for {response_type}, using fallback")
                return await self._fallback_to_dynamic(response_type, client_name, agent_name, start_time)
        
        except Exception as e:
            logger.error(f"❌ Mapped response error: {e}")
            return await self._fallback_to_dynamic(response_type, client_name, agent_name, start_time)
    
    def _detect_response_type(self, text: str) -> Optional[str]:
        """Detect response type from text content"""
        
        text_lower = text.lower()
        
        # Greeting detection
        if any(phrase in text_lower for phrase in ["hello", "alex here", "altruis advisor", "open enrollment"]):
            return "greeting"
        
        # Agent introduction detection
        if any(phrase in text_lower for phrase in ["looks like", "last agent", "discovery call", "get reacquainted"]):
            return "agent_introduction"
        
        # Schedule confirmation detection
        if any(phrase in text_lower for phrase in ["check", "calendar", "scheduled", "calendar invitation"]):
            return "schedule_confirmation"
        
        # No schedule follow-up detection
        if any(phrase in text_lower for phrase in ["will reach out", "work together", "best next steps"]):
            return "no_schedule_followup"
        
        # Static response detection
        if any(phrase in text_lower for phrase in ["continue receiving", "communications from our team"]):
            return "not_interested"
        
        if any(phrase in text_lower for phrase in ["removed from all future", "confirmation email"]):
            return "dnc_confirmation"
        
        if any(phrase in text_lower for phrase in ["keep you informed", "ever-changing world"]):
            return "keep_communications"
        
        if any(phrase in text_lower for phrase in ["thank you for your time", "wonderful day"]):
            return "goodbye"
        
        if any(phrase in text_lower for phrase in ["understand correctly", "yes if you're interested"]):
            return "clarification"
        
        return None
    
    async def _try_static_response(self, text: str) -> Dict[str, Any]:
        """Try to match with static response segments"""
        
        # For short, common responses that don't need personalization
        static_phrases = {
            "thank you": "goodbye",
            "goodbye": "goodbye", 
            "have a great day": "goodbye",
            "understood": "dnc_confirmation",
            "i understand": "not_interested"
        }
        
        text_lower = text.lower().strip()
        
        for phrase, template in static_phrases.items():
            if phrase in text_lower and len(text_lower) < 50:  # Short responses only
                result = await self.segmented_service.get_personalized_audio(template)
                return result
        
        return {"success": False}
    
    async def _generate_dynamic_tts(
        self, 
        text: str,
        client_data: Optional[Dict[str, Any]] = None
    ) -> Dict[str, Any]:
        """Generate TTS using ElevenLabs API"""
        
        if not settings.elevenlabs_api_key or settings.elevenlabs_api_key.startswith("your_"):
            return {"success": False, "error": "ElevenLabs API key not configured"}
        
        try:
            # Clean and optimize text for TTS
            clean_text = self._clean_text_for_tts(text, client_data)
            
            url = f"https://api.elevenlabs.io/v1/text-to-speech/{settings.default_voice_id}"
            
            headers = {
                "Accept": "audio/mpeg",
                "Content-Type": "application/json",
                "xi-api-key": settings.elevenlabs_api_key
            }
            
            data = {
                "text": clean_text,
                "model_id": settings.tts_model,
                "voice_settings": settings.elevenlabs_voice_settings,
                "output_format": settings.tts_output_format
            }
            
            response = await self.elevenlabs_session.post(url, headers=headers, json=data)
            
            if response.status_code == 200:
                # Save audio file
                filename = f"dynamic_{uuid.uuid4().hex[:8]}.mp3"
                
                if settings.environment == "development":
                    # Save locally for development
                    os.makedirs("static/audio/temp", exist_ok=True)
                    filepath = f"static/audio/temp/{filename}"
                    
                    with open(filepath, "wb") as f:
                        f.write(response.content)
                    
                    audio_url = f"{settings.base_url.rstrip('/')}/static/audio/temp/{filename}"
                    
                else:
                    # TODO: Upload to S3 for production
                    audio_url = f"{settings.base_url.rstrip('/')}/static/audio/temp/{filename}"
                
                return {
                    "success": True,
                    "audio_url": audio_url,
                    "file_size": len(response.content)
                }
            
            else:
                logger.error(f"ElevenLabs API error: {response.status_code} - {response.text}")
                return {"success": False, "error": f"API error: {response.status_code}"}
                
        except Exception as e:
            logger.error(f"Dynamic TTS generation error: {e}")
            return {"success": False, "error": str(e)}
    
    async def _fallback_to_dynamic(
        self, 
        response_type: str, 
        client_name: Optional[str],
        agent_name: Optional[str],
        start_time: float
    ) -> Dict[str, Any]:
        """Fallback to dynamic TTS when segmented fails"""
        
        # Build full text based on AAG script
        full_text = self._build_aag_script_text(response_type, client_name, agent_name)
        
        if full_text:
            result = await self._generate_dynamic_tts(full_text)
            if result["success"]:
                generation_time = (time.time() - start_time) * 1000
                logger.info(f"⚠️ Using fallback TTS for: {response_type}")
                
                return {
                    **result,
                    "generation_time_ms": generation_time,
                    "type": "fallback_dynamic"
                }
        
        return {
            "success": False,
            "error": "Fallback TTS failed",
            "generation_time_ms": (time.time() - start_time) * 1000
        }
    
    def _build_aag_script_text(
        self, 
        response_type: str, 
        client_name: Optional[str],
        agent_name: Optional[str]
    ) -> Optional[str]:
        """Build full text using AAG script templates"""
        
        templates = {
            "greeting": f"Hello {client_name or '[NAME]'}, Alex here from Altruis Advisor Group. We've helped you with your health insurance needs in the past and I just wanted to reach out to see if we can be of service to you this year during Open Enrollment? A simple Yes or No is fine, and remember, our services are completely free of charge.",
            
            "agent_introduction": f"Great, looks like {agent_name or '[AGENT]'} was the last agent you worked with here at Altruis. Would you like to schedule a quick 15-minute discovery call with them to get reacquainted? A simple Yes or No will do!",
            
            "schedule_confirmation": f"Great, give me a moment while I check {agent_name or '[AGENT]'}'s calendar... Perfect! I've scheduled a 15-minute discovery call for you. You should receive a calendar invitation shortly. Thank you and have a wonderful day!",
            
            "no_schedule_followup": f"No problem, {agent_name or '[AGENT]'} will reach out to you and the two of you can work together to determine the best next steps. We look forward to servicing you, have a wonderful day!",
            
            "not_interested": "No problem, would you like to continue receiving general health insurance communications from our team? Again, a simple Yes or No will do!",
            
            "dnc_confirmation": "Understood, we will make sure you are removed from all future communications and send you a confirmation email once that is done. Our contact details will be in that email as well, so if you do change your mind in the future please feel free to reach out – we are always here to help and our service is always free of charge. Have a wonderful day!",
            
            "keep_communications": "Great, we're happy to keep you informed throughout the year regarding the ever-changing world of health insurance. If you'd like to connect with one of our insurance experts in the future please feel free to reach out – we are always here to help and our service is always free of charge. Have a wonderful day!",
            
            "goodbye": "Thank you for your time today. Have a wonderful day!",
            
            "clarification": "I want to make sure I understand correctly. Can we help service you this year during Open Enrollment? Please say Yes if you're interested, or No if you're not interested."
        }
        
        return templates.get(response_type)
    
    def _clean_text_for_tts(self, text: str, client_data: Optional[Dict[str, Any]] = None) -> str:
        """Clean and personalize text for optimal TTS"""
        
        # Replace client placeholders
        if client_data:
            text = text.replace("{client_name}", client_data.get("client_name", ""))
            text = text.replace("{first_name}", client_data.get("first_name", ""))
            text = text.replace("{agent_name}", client_data.get("agent_name", ""))
        
        # Clean up markdown and symbols
        text = text.replace("**", "").replace("*", "").replace("#", "").replace("`", "")
        text = text.replace("&", " and ").replace("%", " percent ").replace("@", " at ")
        
        # Improve pronunciations
        text = text.replace("Dr.", "Doctor").replace("Mr.", "Mister").replace("Mrs.", "Missus")
        text = text.replace("vs.", "versus").replace("etc.", "etcetera")
        
        # Ensure proper ending
        if not text.endswith(('.', '!', '?')):
            text += '.'
        
        return text.strip()
    
    def _generate_text_cache_key(self, text: str, client_data: Optional[Dict[str, Any]] = None) -> str:
        """Generate cache key for text-based responses"""
        content = text
        if client_data:
            content += str(sorted(client_data.items()))
        
        return hashlib.md5(content.encode()).hexdigest()
    
    async def is_configured(self) -> bool:
        """Check if hybrid TTS service is configured"""
        try:
            # Check if segmented service is configured
            segmented_configured = await self.segmented_service.is_configured()
            
            # Check if ElevenLabs is configured for fallback
            elevenlabs_configured = bool(settings.elevenlabs_api_key and 
                                    not settings.elevenlabs_api_key.startswith("your_"))
            
            return segmented_configured or elevenlabs_configured
        except Exception:
            return False
        
    def get_performance_stats(self) -> Dict[str, Any]:
        """Get performance statistics"""
        if self.total_requests == 0:
            return {"no_requests": True}
        
        segmented_rate = (self.segmented_responses / self.total_requests) * 100
        static_rate = (self.static_responses / self.total_requests) * 100
        dynamic_rate = (self.dynamic_responses / self.total_requests) * 100
        
        # Get segmented service stats
        segmented_stats = self.segmented_service.get_performance_stats()
        
        return {
            "total_requests": self.total_requests,
            "segmented_responses": self.segmented_responses,
            "static_responses": self.static_responses,
            "dynamic_responses": self.dynamic_responses,
            "segmented_rate": segmented_rate,
            "static_rate": static_rate,
            "dynamic_rate": dynamic_rate,
            "performance_improvement": f"{segmented_rate + static_rate:.1f}% faster responses via segmented audio",
            "segmented_service_stats": segmented_stats
        }