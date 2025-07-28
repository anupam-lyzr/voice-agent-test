"""
Deepgram STT Client Service
Optimized for ultra-fast speech-to-text processing
"""

import asyncio
import httpx
import json
import logging
import time
from typing import Dict, Any, Optional, Union
import base64

from shared.config.settings import settings

logger = logging.getLogger(__name__)

class DeepgramSTTClient:
    """Optimized Deepgram client for voice processing"""
    
    def __init__(self):
        self.api_key = settings.deepgram_api_key
        self.base_url = "https://api.deepgram.com/v1"
        
        # HTTP client with optimized settings
        self.session = httpx.AsyncClient(
            timeout=8.0,  # Fast timeout for real-time processing
            limits=httpx.Limits(
                max_keepalive_connections=10,
                max_connections=50,
                keepalive_expiry=30.0
            )
        )
        
        # Performance tracking
        self.transcriptions_count = 0
        self.total_latency = 0.0
        self.errors_count = 0
        
        # Cache for repeated phrases
        self.transcription_cache = {}
    
    def is_configured(self) -> bool:
        """Check if Deepgram is properly configured"""
        return bool(self.api_key and not self.api_key.startswith("your_"))
    
    async def transcribe_audio(
        self, 
        audio_data: Union[bytes, str], 
        audio_format: str = "webm",
        language: str = "en-US"
    ) -> Dict[str, Any]:
        """Transcribe audio data with optimized parameters"""
        
        if not self.is_configured():
            return {
                "success": False,
                "error": "Deepgram API key not configured",
                "transcript": "",
                "confidence": 0.0
            }
        
        start_time = time.time()
        
        try:
            # Prepare headers
            headers = {
                "Authorization": f"Token {self.api_key}",
                "Content-Type": f"audio/{audio_format}"
            }
            
            # Optimized parameters for speed and accuracy
            params = {
                "model": settings.stt_model,  # nova-2 for speed
                "language": language,
                "punctuate": True,
                "smart_format": True,
                "utterances": False,  # Disable for speed
                "diarize": False,     # Disable for speed
                "numerals": True,
                "profanity_filter": False
            }
            
            # Make request
            url = f"{self.base_url}/listen"
            
            # Handle different audio input types
            if isinstance(audio_data, str):
                # Base64 encoded audio
                audio_bytes = base64.b64decode(audio_data)
            else:
                audio_bytes = audio_data
            
            response = await self.session.post(
                url,
                headers=headers,
                params=params,
                content=audio_bytes
            )
            
            # Calculate latency
            latency = (time.time() - start_time) * 1000  # ms
            self.total_latency += latency
            
            if response.status_code == 200:
                result = response.json()
                
                # Extract transcript and confidence
                transcript_data = self._extract_transcript(result)
                
                self.transcriptions_count += 1
                
                logger.info(f"🎤 Transcription completed in {latency:.0f}ms: '{transcript_data['transcript'][:50]}...'")
                
                return {
                    "success": True,
                    "transcript": transcript_data["transcript"],
                    "confidence": transcript_data["confidence"],
                    "latency_ms": latency,
                    "raw_response": result
                }
            
            else:
                error_msg = f"Deepgram API error: {response.status_code}"
                logger.error(f"❌ {error_msg}")
                self.errors_count += 1
                
                return {
                    "success": False,
                    "error": error_msg,
                    "transcript": "",
                    "confidence": 0.0,
                    "latency_ms": latency
                }
                
        except Exception as e:
            latency = (time.time() - start_time) * 1000
            logger.error(f"❌ Deepgram transcription failed: {e}")
            self.errors_count += 1
            
            return {
                "success": False,
                "error": str(e),
                "transcript": "",
                "confidence": 0.0,
                "latency_ms": latency
            }
    
    def _extract_transcript(self, response_data: Dict[str, Any]) -> Dict[str, Any]:
        """Extract transcript and confidence from Deepgram response"""
        try:
            results = response_data.get("results", {})
            channels = results.get("channels", [])
            
            if not channels:
                return {"transcript": "", "confidence": 0.0}
            
            alternatives = channels[0].get("alternatives", [])
            
            if not alternatives:
                return {"transcript": "", "confidence": 0.0}
            
            # Get best alternative
            best_alternative = alternatives[0]
            transcript = best_alternative.get("transcript", "").strip()
            confidence = best_alternative.get("confidence", 0.0)
            
            return {
                "transcript": transcript,
                "confidence": confidence
            }
            
        except Exception as e:
            logger.error(f"Failed to extract transcript: {e}")
            return {"transcript": "", "confidence": 0.0}
    
    async def transcribe_streaming(self, audio_stream) -> Dict[str, Any]:
        """Transcribe streaming audio (for real-time processing)"""
        # TODO: Implement streaming transcription for real-time calls
        # This would use Deepgram's streaming API
        pass
    
    def is_meaningful_speech(self, transcript: str, confidence: float) -> bool:
        """Check if transcription contains meaningful speech"""
        if not transcript or confidence < 0.6:
            return False
        
        # Filter out common filler words only
        filler_words = {"uh", "um", "er", "ah", "like", "you know"}
        words = transcript.lower().split()
        meaningful_words = [w for w in words if w not in filler_words]
        
        return len(meaningful_words) > 0
    
    def get_statistics(self) -> Dict[str, Any]:
        """Get transcription statistics"""
        avg_latency = (self.total_latency / max(1, self.transcriptions_count))
        error_rate = (self.errors_count / max(1, self.transcriptions_count + self.errors_count)) * 100
        
        return {
            "configured": self.is_configured(),
            "transcriptions_count": self.transcriptions_count,
            "average_latency_ms": round(avg_latency, 1),
            "total_errors": self.errors_count,
            "error_rate_percent": round(error_rate, 1),
            "model": settings.stt_model
        }
    
    async def test_connection(self) -> Dict[str, Any]:
        """Test Deepgram connection with sample audio"""
        if not self.is_configured():
            return {"success": False, "error": "API key not configured"}
        
        try:
            # Use a small test audio sample (silence)
            test_audio = b'\x00' * 1024  # 1KB of silence
            
            result = await self.transcribe_audio(test_audio, "wav")
            
            return {
                "success": result["success"],
                "latency_ms": result.get("latency_ms", 0),
                "message": "Connection test completed"
            }
            
        except Exception as e:
            return {"success": False, "error": str(e)}

# Global instance
deepgram_client = DeepgramSTTClient()