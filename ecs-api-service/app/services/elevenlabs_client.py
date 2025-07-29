"""
ElevenLabs TTS Client Service
Optimized for ultra-fast text-to-speech generation
"""

import asyncio
import httpx
import json
import logging
import time
from typing import Dict, Any, Optional, Union
import hashlib

from shared.config.settings import settings

logger = logging.getLogger(__name__)

class ElevenLabsTTSClient:
    """Optimized ElevenLabs client for voice synthesis"""
    
    def __init__(self):
        self.api_key = settings.elevenlabs_api_key
        self.base_url = "https://api.elevenlabs.io/v1"
        
        # HTTP client with optimized settings
        self.session = httpx.AsyncClient(
            timeout=15.0,  # Longer timeout for TTS generation
            limits=httpx.Limits(
                max_keepalive_connections=5,
                max_connections=20,
                keepalive_expiry=30.0
            )
        )
        
        # Performance tracking
        self.generations_count = 0
        self.total_latency = 0.0
        self.errors_count = 0
        self.total_characters = 0
        
        # Audio cache for repeated phrases
        self.audio_cache = {}
        
        # Voice settings optimized for natural speech
        self.voice_settings = {
            "stability": settings.voice_stability,
            "similarity_boost": settings.voice_similarity_boost,
            "style": settings.voice_style,
            "use_speaker_boost": settings.use_speaker_boost,
            "speed": settings.voice_speed if hasattr(settings, 'voice_speed') else 0.87  # Default speed
        }
    
    def is_configured(self) -> bool:
        """Check if ElevenLabs is properly configured"""
        return bool(self.api_key and not self.api_key.startswith("your_"))
    
    async def generate_speech(
        self, 
        text: str, 
        voice_id: Optional[str] = None,
        optimize_streaming_latency: int = 4,
        output_format: str = "mp3_22050_32"
    ) -> Dict[str, Any]:
        """Generate speech from text with optimized settings"""
        
        if not self.is_configured():
            return {
                "success": False,
                "error": "ElevenLabs API key not configured",
                "audio_data": None
            }
        
        if not text.strip():
            return {
                "success": False,
                "error": "Empty text provided",
                "audio_data": None
            }
        
        # Use default voice if not specified
        if not voice_id:
            voice_id = settings.default_voice_id
        
        # Check cache first
        cache_key = self._create_cache_key(text, voice_id)
        if cache_key in self.audio_cache:
            logger.info(f"🔄 Using cached audio for: '{text[:30]}...'")
            return self.audio_cache[cache_key]
        
        start_time = time.time()
        
        try:
            # Prepare request
            url = f"{self.base_url}/text-to-speech/{voice_id}/stream"
            
            headers = {
                "Accept": "audio/mpeg",
                "Content-Type": "application/json",
                "xi-api-key": self.api_key
            }
            
            # Clean text for better TTS
            cleaned_text = self._clean_text_for_speech(text)
            
            data = {
                "text": cleaned_text,
                "model_id": settings.tts_model,  # eleven_turbo_v2_5 for speed
                "voice_settings": self.voice_settings,
                "optimize_streaming_latency": optimize_streaming_latency,
                "output_format": output_format
            }
            
            # Make request
            response = await self.session.post(
                url,
                headers=headers,
                json=data
            )
            
            # Calculate latency
            latency = (time.time() - start_time) * 1000  # ms
            self.total_latency += latency
            
            if response.status_code == 200:
                audio_data = response.content
                
                # Update statistics
                self.generations_count += 1
                self.total_characters += len(text)
                
                result = {
                    "success": True,
                    "audio_data": audio_data,
                    "latency_ms": latency,
                    "character_count": len(text),
                    "voice_id": voice_id,
                    "text": cleaned_text
                }
                
                # Cache successful result
                self.audio_cache[cache_key] = result
                
                logger.info(f"🔊 TTS generated in {latency:.0f}ms: '{text[:50]}...'")
                
                return result
            
            else:
                error_msg = f"ElevenLabs API error: {response.status_code}"
                if response.status_code == 429:
                    error_msg += " (Rate limit exceeded)"
                elif response.status_code == 401:
                    error_msg += " (Invalid API key)"
                
                logger.error(f"❌ {error_msg}")
                self.errors_count += 1
                
                return {
                    "success": False,
                    "error": error_msg,
                    "audio_data": None,
                    "latency_ms": latency
                }
                
        except Exception as e:
            latency = (time.time() - start_time) * 1000
            logger.error(f"❌ ElevenLabs TTS failed: {e}")
            self.errors_count += 1
            
            return {
                "success": False,
                "error": str(e),
                "audio_data": None,
                "latency_ms": latency
            }
    
    def _clean_text_for_speech(self, text: str) -> str:
        """Clean and optimize text for natural speech synthesis"""
        # Remove or replace problematic characters
        text = text.replace("&", "and")
        text = text.replace("@", "at")
        text = text.replace("#", "number")
        text = text.replace("$", "dollar")
        text = text.replace("%", "percent")
        
        # Handle phone numbers (make them more natural)
        import re
        phone_pattern = r'\+?1?[\s-]?\(?(\d{3})\)?[\s-]?(\d{3})[\s-]?(\d{4})'
        text = re.sub(phone_pattern, r'\1 \2 \3', text)
        
        # Handle common abbreviations
        abbreviations = {
            "Dr.": "Doctor",
            "Mr.": "Mister", 
            "Mrs.": "Misses",
            "Ms.": "Miss",
            "LLC": "L L C",
            "Inc.": "Incorporated",
            "Corp.": "Corporation",
            "Ltd.": "Limited",
            "Ave.": "Avenue",
            "St.": "Street",
            "Blvd.": "Boulevard"
        }
        
        for abbr, full in abbreviations.items():
            text = text.replace(abbr, full)
        
        # Clean up extra whitespace
        text = " ".join(text.split())
        
        return text.strip()
    
    def _create_cache_key(self, text: str, voice_id: str) -> str:
        """Create cache key for audio"""
        content = f"{text}:{voice_id}:{json.dumps(self.voice_settings, sort_keys=True)}"
        return hashlib.md5(content.encode()).hexdigest()
    
    async def get_available_voices(self) -> Dict[str, Any]:
        """Get available voices from ElevenLabs"""
        if not self.is_configured():
            return {"success": False, "error": "API key not configured"}
        
        try:
            url = f"{self.base_url}/voices"
            headers = {"xi-api-key": self.api_key}
            
            response = await self.session.get(url, headers=headers)
            
            if response.status_code == 200:
                voices_data = response.json()
                return {
                    "success": True,
                    "voices": voices_data.get("voices", [])
                }
            else:
                return {
                    "success": False,
                    "error": f"API error: {response.status_code}"
                }
                
        except Exception as e:
            return {"success": False, "error": str(e)}
    
    async def get_voice_info(self, voice_id: str) -> Dict[str, Any]:
        """Get information about a specific voice"""
        if not self.is_configured():
            return {"success": False, "error": "API key not configured"}
        
        try:
            url = f"{self.base_url}/voices/{voice_id}"
            headers = {"xi-api-key": self.api_key}
            
            response = await self.session.get(url, headers=headers)
            
            if response.status_code == 200:
                return {"success": True, "voice": response.json()}
            else:
                return {"success": False, "error": f"API error: {response.status_code}"}
                
        except Exception as e:
            return {"success": False, "error": str(e)}
    
    def clear_cache(self):
        """Clear the audio cache"""
        self.audio_cache.clear()
        logger.info("🗑️ Audio cache cleared")
    
    def get_statistics(self) -> Dict[str, Any]:
        """Get TTS generation statistics"""
        avg_latency = (self.total_latency / max(1, self.generations_count))
        avg_chars_per_generation = (self.total_characters / max(1, self.generations_count))
        error_rate = (self.errors_count / max(1, self.generations_count + self.errors_count)) * 100
        
        return {
            "configured": self.is_configured(),
            "generations_count": self.generations_count,
            "average_latency_ms": round(avg_latency, 1),
            "total_characters": self.total_characters,
            "average_chars_per_generation": round(avg_chars_per_generation, 1),
            "total_errors": self.errors_count,
            "error_rate_percent": round(error_rate, 1),
            "cache_size": len(self.audio_cache),
            "model": settings.tts_model,
            "default_voice": settings.default_voice_id
        }
    
    async def test_connection(self) -> Dict[str, Any]:
        """Test ElevenLabs connection with sample text"""
        if not self.is_configured():
            return {"success": False, "error": "API key not configured"}
        
        try:
            test_text = "Hello, this is a test."
            result = await self.generate_speech(test_text)
            
            return {
                "success": result["success"],
                "latency_ms": result.get("latency_ms", 0),
                "audio_size_bytes": len(result.get("audio_data", b"")),
                "message": "Connection test completed"
            }
            
        except Exception as e:
            return {"success": False, "error": str(e)}

# Global instance
elevenlabs_client = ElevenLabsTTSClient()