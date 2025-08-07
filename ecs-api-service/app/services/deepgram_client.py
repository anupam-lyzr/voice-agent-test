"""
Deepgram STT Client Service
Using official Deepgram Python SDK for optimal performance
"""

import asyncio
import logging
import time
from typing import Dict, Any, Optional, Union
import base64
import io

# Set up logger first
logger = logging.getLogger(__name__)

# For now, let's use REST API only to avoid SDK compatibility issues
DEEPGRAM_SDK_AVAILABLE = False
logger.info("Using REST API for Deepgram (SDK disabled for compatibility)")

from shared.config.settings import settings

class DeepgramSTTClient:
    """Deepgram client using official Python SDK"""
    
    def __init__(self):
        self.api_key = settings.deepgram_api_key
        
        # Initialize Deepgram client if SDK is available
        if DEEPGRAM_SDK_AVAILABLE and self.api_key:
            try:
                self.deepgram_client = DeepgramClient(self.api_key)
                self.use_sdk = True
                logger.info("✅ Using Deepgram Python SDK")
            except Exception as e:
                logger.warning(f"⚠️ Failed to initialize Deepgram SDK: {e}")
                self.use_sdk = False
        else:
            self.use_sdk = False
        
        # Performance tracking
        self.transcriptions_count = 0
        self.total_latency = 0.0
        self.errors_count = 0
    
    def is_configured(self) -> bool:
        """Check if Deepgram is properly configured"""
        return bool(self.api_key and not self.api_key.startswith("your_") and len(self.api_key) > 10)
    
    def get_api_key_type(self) -> str:
        """Get the type of API key being used"""
        if not self.api_key:
            return "none"
        elif self.api_key.startswith("dg_"):
            return "project_key"
        else:
            return "user_key"
    
    async def transcribe_audio(
        self, 
        audio_data: Union[bytes, str], 
        audio_format: str = "webm",
        language: str = "en-US"
    ) -> Dict[str, Any]:
        """Transcribe audio data using Deepgram SDK"""
        
        if not self.is_configured():
            return {
                "success": False,
                "error": "Deepgram API key not configured",
                "transcript": "",
                "confidence": 0.0
            }
        
        start_time = time.time()
        
        try:
            # Handle different audio input types
            if isinstance(audio_data, str):
                # Base64 encoded audio
                audio_bytes = base64.b64decode(audio_data)
            else:
                audio_bytes = audio_data
            
            # Validate audio data
            if not audio_bytes or len(audio_bytes) == 0:
                return {
                    "success": False,
                    "error": "Empty audio data provided",
                    "transcript": "",
                    "confidence": 0.0,
                    "latency_ms": 0
                }
            
            logger.info(f"🎤 Transcribing audio: {len(audio_bytes)} bytes, format: {audio_format}")
            
            if self.use_sdk and DEEPGRAM_SDK_AVAILABLE:
                # Use Deepgram SDK
                return await self._transcribe_with_sdk(audio_bytes, audio_format, language, start_time)
            else:
                # Fallback to REST API (if SDK not available)
                return await self._transcribe_with_rest_api(audio_bytes, audio_format, language, start_time)
                
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
    
    async def _transcribe_with_sdk(
        self, 
        audio_bytes: bytes, 
        audio_format: str, 
        language: str, 
        start_time: float
    ) -> Dict[str, Any]:
        """Transcribe using Deepgram SDK"""
        try:
            # Create options
            options = PrerecordedOptions(
                model=settings.stt_model,
                language=language,
                smart_format=True,
                punctuate=True,
                numerals=True,
                profanity_filter=False
            )
            
            # Create audio source from bytes
            audio_source = {"buffer": audio_bytes, "mimetype": f"audio/{audio_format}"}
            
            # Transcribe
            response = self.deepgram_client.listen.prerecorded.v("1").transcribe_file(
                audio_source,
                options
            )
            
            # Calculate latency
            latency = (time.time() - start_time) * 1000
            self.total_latency += latency
            self.transcriptions_count += 1
            
            # Extract transcript
            transcript_data = self._extract_transcript_from_sdk(response)
            
            logger.info(f"🎤 SDK Transcription completed in {latency:.0f}ms: '{transcript_data['transcript'][:50]}...'")
            
            return {
                "success": True,
                "transcript": transcript_data["transcript"],
                "confidence": transcript_data["confidence"],
                "latency_ms": latency,
                "method": "sdk"
            }
            
        except Exception as e:
            latency = (time.time() - start_time) * 1000
            logger.error(f"❌ SDK transcription failed: {e}")
            self.errors_count += 1
            
            return {
                "success": False,
                "error": f"SDK Error: {str(e)}",
                "transcript": "",
                "confidence": 0.0,
                "latency_ms": latency
            }
    
    def _extract_transcript_from_sdk(self, response) -> Dict[str, Any]:
        """Extract transcript and confidence from Deepgram SDK response"""
        try:
            # SDK response structure
            results = response.results
            if not results:
                return {"transcript": "", "confidence": 0.0}
            
            channels = results.channels
            if not channels:
                return {"transcript": "", "confidence": 0.0}
            
            alternatives = channels[0].alternatives
            if not alternatives:
                return {"transcript": "", "confidence": 0.0}
            
            # Get best alternative
            best_alternative = alternatives[0]
            transcript = best_alternative.transcript.strip()
            confidence = best_alternative.confidence
            
            return {
                "transcript": transcript,
                "confidence": confidence
            }
            
        except Exception as e:
            logger.error(f"Failed to extract transcript from SDK: {e}")
            return {"transcript": "", "confidence": 0.0}
    
    def _extract_transcript(self, response_data: Dict[str, Any]) -> Dict[str, Any]:
        """Extract transcript and confidence from Deepgram REST API response"""
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
            "api_key_type": self.get_api_key_type(),
            "sdk_available": DEEPGRAM_SDK_AVAILABLE,
            "using_sdk": self.use_sdk,
            "transcriptions_count": self.transcriptions_count,
            "average_latency_ms": round(avg_latency, 1),
            "total_errors": self.errors_count,
            "error_rate_percent": round(error_rate, 1),
            "model": settings.stt_model
        }
    
    async def _transcribe_with_rest_api(
        self, 
        audio_bytes: bytes, 
        audio_format: str, 
        language: str, 
        start_time: float
    ) -> Dict[str, Any]:
        """Fallback to REST API if SDK is not available"""
        try:
            import httpx
            
            # HTTP client for REST API
            async with httpx.AsyncClient(timeout=8.0) as session:
                headers = {
                    "Authorization": f"Token {self.api_key}",
                    "Content-Type": f"audio/{audio_format}",
                    "Accept": "application/json"
                }
                
                params = {
                    "model": settings.stt_model,
                    "language": language,
                    "punctuate": True,
                    "smart_format": True,
                    "numerals": True,
                    "profanity_filter": False
                }
                
                url = "https://api.deepgram.com/v1/listen"
                
                response = await session.post(
                    url,
                    headers=headers,
                    params=params,
                    content=audio_bytes
                )
                
                latency = (time.time() - start_time) * 1000
                
                if response.status_code == 200:
                    result = response.json()
                    transcript_data = self._extract_transcript(result)
                    
                    self.transcriptions_count += 1
                    self.total_latency += latency
                    
                    return {
                        "success": True,
                        "transcript": transcript_data["transcript"],
                        "confidence": transcript_data["confidence"],
                        "latency_ms": latency,
                        "method": "rest_api"
                    }
                else:
                    self.errors_count += 1
                    return {
                        "success": False,
                        "error": f"REST API Error: {response.status_code}",
                        "transcript": "",
                        "confidence": 0.0,
                        "latency_ms": latency
                    }
                    
        except Exception as e:
            latency = (time.time() - start_time) * 1000
            self.errors_count += 1
            return {
                "success": False,
                "error": f"REST API Exception: {str(e)}",
                "transcript": "",
                "confidence": 0.0,
                "latency_ms": latency
            }
    
    async def test_connection(self) -> Dict[str, Any]:
        """Test Deepgram connection with sample audio"""
        if not self.is_configured():
            return {"success": False, "error": "API key not configured"}
        
        try:
            # Create a minimal valid WAV file for testing
            wav_header = (
                b'RIFF' + b'\x24\x00\x00\x00' + b'WAVE' + b'fmt ' + 
                b'\x10\x00\x00\x00' + b'\x01\x00' + b'\x01\x00' + 
                b'\x44\xAC\x00\x00' + b'\x88\x58\x01\x00' + b'\x02\x00' + 
                b'\x10\x00' + b'data' + b'\x00\x00\x00\x00'
            )
            
            result = await self.transcribe_audio(wav_header, "wav")
            
            return {
                "success": result["success"],
                "latency_ms": result.get("latency_ms", 0),
                "message": "Connection test completed",
                "api_key_type": self.get_api_key_type(),
                "sdk_available": DEEPGRAM_SDK_AVAILABLE,
                "using_sdk": self.use_sdk
            }
            
        except Exception as e:
            return {"success": False, "error": str(e)}

# Global instance
deepgram_client = DeepgramSTTClient()