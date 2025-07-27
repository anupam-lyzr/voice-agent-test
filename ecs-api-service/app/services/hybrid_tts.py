"""
Hybrid TTS Service
Combines pre-generated static audio with dynamic ElevenLabs TTS for optimal performance
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
from shared.utils.redis_client import response_cache

logger = logging.getLogger(__name__)

class HybridTTSService:
    """Service that intelligently chooses between static and dynamic TTS"""
    
    def __init__(self):
        # Static audio mappings
        self.static_responses = {
            "greeting": {
                "pattern": ["hello", "hi", "greeting", "introduce"],
                "audio_file": "greeting.mp3",
                "base_text": "Hello {client_name}, this is Alex from Altrius Advisor Group..."
            },
            "interested": {
                "pattern": ["excellent", "great", "wonderful", "perfect", "interested", "time works best"],
                "audio_file": "interested_followup.mp3",
                "base_text": "Excellent! What time would work best for you - morning, afternoon, or evening?"
            },
            "not_interested": {
                "pattern": ["understand", "no problem", "remove", "future calls"],
                "audio_file": "not_interested_followup.mp3", 
                "base_text": "I understand. Would you like us to remove you from future promotional calls?"
            },
            "schedule_morning": {
                "pattern": ["morning", "am", "early", "before noon"],
                "audio_file": "schedule_morning.mp3",
                "base_text": "Perfect! Our insurance specialist will call you tomorrow morning. Thank you!"
            },
            "schedule_afternoon": {
                "pattern": ["afternoon", "pm", "after lunch", "later"],
                "audio_file": "schedule_afternoon.mp3",
                "base_text": "Great! Our team will reach out to you this afternoon. Thank you!"
            },
            "dnc_confirmation": {
                "pattern": ["added", "do-not-call", "removed", "great day"],
                "audio_file": "dnc_confirmation.mp3",
                "base_text": "Done! You've been added to our do-not-call list. Have a great day!"
            },
            "goodbye": {
                "pattern": ["thank you", "goodbye", "great day", "wonderful day"],
                "audio_file": "goodbye.mp3",
                "base_text": "Thank you for your time today. Have a wonderful day!"
            }
        }
        
        # ElevenLabs client
        self.elevenlabs_session = httpx.AsyncClient(timeout=settings.webhook_timeout)
        
        # Performance tracking
        self.static_cache_hits = 0
        self.dynamic_generations = 0
        self.total_requests = 0
    
    async def get_response_audio(
        self, 
        text: str, 
        response_type: str = "dynamic",
        client_data: Optional[Dict[str, Any]] = None,
        conversation_context: Optional[Dict[str, Any]] = None
    ) -> Dict[str, Any]:
        """
        Get audio response using hybrid approach
        Returns: {success: bool, audio_url: str, type: str, generation_time_ms: float}
        """
        start_time = time.time()
        self.total_requests += 1
        
        try:
            # 1. Try static audio first for common responses
            static_result = await self._try_static_audio(text, response_type, client_data)
            if static_result["success"]:
                self.static_cache_hits += 1
                generation_time = (time.time() - start_time) * 1000
                
                logger.info(f"⚡ Static audio served: {response_type} ({generation_time:.0f}ms)")
                
                return {
                    **static_result,
                    "generation_time_ms": generation_time,
                    "type": "static"
                }
            
            # 2. Check cached dynamic responses
            cache_key = self._generate_cache_key(text, client_data)
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
            
            # 3. Generate dynamic TTS with ElevenLabs
            dynamic_result = await self._generate_dynamic_tts(text, client_data)
            if dynamic_result["success"]:
                self.dynamic_generations += 1
                generation_time = (time.time() - start_time) * 1000
                
                # Cache the result
                if response_cache:
                    await response_cache.cache_response(cache_key, dynamic_result["audio_url"])
                
                logger.info(f"🎤 Dynamic TTS generated: ({generation_time:.0f}ms)")
                
                return {
                    **dynamic_result,
                    "generation_time_ms": generation_time,
                    "type": "dynamic"
                }
            
            # 4. Fallback - return failure (will use Twilio TTS)
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
    
    async def _try_static_audio(
        self, 
        text: str, 
        response_type: str,
        client_data: Optional[Dict[str, Any]] = None
    ) -> Dict[str, Any]:
        """Try to match text with static audio responses"""
        
        text_lower = text.lower().strip()
        
        # Check direct response type match
        if response_type in self.static_responses:
            static_config = self.static_responses[response_type]
            
            # For greeting, personalize with client name
            if response_type == "greeting" and client_data:
                client_name = client_data.get("client_name", client_data.get("first_name", ""))
                if client_name:
                    # Use personalized static audio if available
                    audio_url = await self._get_static_audio_url(static_config["audio_file"])
                    if audio_url:
                        return {"success": True, "audio_url": audio_url}
            else:
                # Standard static audio
                audio_url = await self._get_static_audio_url(static_config["audio_file"])
                if audio_url:
                    return {"success": True, "audio_url": audio_url}
        
        # Pattern matching for dynamic responses that might match static patterns
        for static_type, config in self.static_responses.items():
            if any(pattern in text_lower for pattern in config["pattern"]):
                # Check text similarity
                if self._text_similarity(text, config["base_text"]) > 0.7:
                    audio_url = await self._get_static_audio_url(config["audio_file"])
                    if audio_url:
                        logger.info(f"📋 Pattern matched static audio: {static_type}")
                        return {"success": True, "audio_url": audio_url}
        
        return {"success": False}
    
    async def _get_static_audio_url(self, filename: str) -> Optional[str]:
        """Get URL for static audio file"""
        
        # Check if running locally (development)
        if settings.environment == "development":
            local_path = f"audio-generation/generated_audio/{filename}"
            if os.path.exists(local_path):
                # In development, serve from local static directory
                return f"{settings.base_url.rstrip('/')}/static/audio/{filename}"
        
        # In production, get from S3
        if settings.s3_bucket_audio:
            # Check Redis cache first
            if response_cache:
                cached_url = await response_cache.get_static_audio_url(filename)
                if cached_url:
                    return cached_url
            
            # Generate S3 URL
            s3_url = f"https://{settings.s3_bucket_audio}.s3.{settings.aws_region}.amazonaws.com/{filename}"
            
            # Cache the URL
            if response_cache:
                await response_cache.cache_static_audio_url(filename, s3_url)
            
            return s3_url
        
        return None
    
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
                    os.makedirs("static/audio", exist_ok=True)
                    filepath = f"static/audio/{filename}"
                    
                    with open(filepath, "wb") as f:
                        f.write(response.content)
                    
                    audio_url = f"{settings.base_url.rstrip('/')}/static/audio/{filename}"
                    
                else:
                    # TODO: Upload to S3 for production
                    # For now, return a placeholder
                    audio_url = f"{settings.base_url.rstrip('/')}/static/audio/{filename}"
                
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
    
    def _clean_text_for_tts(self, text: str, client_data: Optional[Dict[str, Any]] = None) -> str:
        """Clean and personalize text for optimal TTS"""
        
        # Replace client placeholders
        if client_data:
            text = text.replace("{client_name}", client_data.get("client_name", ""))
            text = text.replace("{first_name}", client_data.get("first_name", ""))
        
        # Clean up markdown and symbols
        text = text.replace("**", "").replace("*", "").replace("#", "").replace("`", "")
        text = text.replace("&", " and ").replace("%", " percent ").replace("@", " at ")
        
        # Improve pronunciations
        text = text.replace("Dr.", "Doctor").replace("Mr.", "Mister").replace("Mrs.", "Missus")
        text = text.replace("vs.", "versus").replace("etc.", "etcetera")
        
        # Limit length for faster generation
        if len(text) > 500:
            sentences = text[:500].split('.')
            if len(sentences) > 1:
                text = '.'.join(sentences[:-1]) + '.'
            else:
                text = text[:497] + "..."
        
        # Ensure proper ending
        if not text.endswith(('.', '!', '?')):
            text += '.'
        
        return text.strip()
    
    def _text_similarity(self, text1: str, text2: str) -> float:
        """Calculate simple text similarity score"""
        words1 = set(text1.lower().split())
        words2 = set(text2.lower().split())
        
        if not words1 or not words2:
            return 0.0
        
        intersection = words1.intersection(words2)
        union = words1.union(words2)
        
        return len(intersection) / len(union)
    
    def _generate_cache_key(self, text: str, client_data: Optional[Dict[str, Any]] = None) -> str:
        """Generate cache key for response"""
        # Create a hash of text + client context
        content = text
        if client_data:
            content += str(sorted(client_data.items()))
        
        return hashlib.md5(content.encode()).hexdigest()
    
    def get_performance_stats(self) -> Dict[str, Any]:
        """Get performance statistics"""
        if self.total_requests == 0:
            return {"no_requests": True}
        
        static_rate = (self.static_cache_hits / self.total_requests) * 100
        dynamic_rate = (self.dynamic_generations / self.total_requests) * 100
        
        return {
            "total_requests": self.total_requests,
            "static_cache_hits": self.static_cache_hits,
            "dynamic_generations": self.dynamic_generations,
            "static_hit_rate": static_rate,
            "dynamic_rate": dynamic_rate,
            "performance_improvement": f"{static_rate:.1f}% faster responses via static audio"
        }