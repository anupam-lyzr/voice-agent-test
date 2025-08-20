"""
Enhanced Hybrid TTS Service - Client Type Aware
Determines appropriate scripts and audio based on Medicare/Non-Medicare client types
"""

import asyncio
import logging
import time
from typing import Dict, Any, Optional

from shared.config.settings import settings
from services.segmented_audio_service import SegmentedAudioService
from services.elevenlabs_client import elevenlabs_client
from services.client_data_service import ClientDataService, ClientType

logger = logging.getLogger(__name__)

class HybridTTSService:
    """Enhanced hybrid TTS service with client type detection and appropriate script selection"""
    
    def __init__(self):
        self.segmented_audio = SegmentedAudioService()
        self.client_data_service = ClientDataService()
        self._configured = False
        
        # Performance tracking
        self.static_responses = 0
        self.dynamic_responses = 0
        self.segmented_responses = 0
        self.fallback_responses = 0
    
    async def get_response_audio(
        self,
        text: str,
        response_type: str,
        client_data: Optional[Dict[str, Any]] = None,
        agent_data: Optional[Dict[str, Any]] = None,
        context: Optional[Dict[str, Any]] = None
    ) -> Dict[str, Any]:
        """Get appropriate audio response based on client type and response type"""
        
        start_time = time.time()
        
        try:
            # Analyze client data to determine type and scripts
            if client_data:
                enhanced_client_data = self.client_data_service.analyze_client_data(client_data)
            else:
                enhanced_client_data = self._get_default_client_data()
            
            logger.info(f"🎯 Processing {response_type} for {enhanced_client_data['client_type'].value} client: {enhanced_client_data.get('first_name', 'Unknown')}")
            
            # Route to appropriate handler based on response type
            if response_type in ["greeting", "voicemail"]:
                return await self._handle_personalized_response(
                    response_type, enhanced_client_data, start_time
                )
            elif response_type in ["agent_intro", "schedule_confirmation", "no_schedule_followup"]:
                return await self._handle_agent_based_response(
                    response_type, enhanced_client_data, start_time
                )
            elif response_type in [
                "dnc_confirmation", "keep_communications", "not_interested",
                "goodbye", "clarification", "error", "identity_clarification",
                "ai_clarification", "memory_clarification", "repeat_response", 
                "confusion_clarification"
            ]:
                return await self._handle_static_response(response_type, start_time)
            elif response_type in ["silence_detection", "no_speech_first", "no_speech_second", "no_speech_final"]:
                return await self._handle_silence_response(response_type, start_time)
            else:
                # Dynamic response for complex cases
                return await self._handle_dynamic_response(
                    text, response_type, enhanced_client_data, start_time
                )
                
        except Exception as e:
            logger.error(f"❌ Hybrid TTS error: {e}")
            return await self._create_emergency_fallback(text, start_time)
    
    async def _handle_personalized_response(
        self, 
        response_type: str, 
        client_data: Dict[str, Any], 
        start_time: float
    ) -> Dict[str, Any]:
        """Handle greeting and voicemail with client name personalization"""
        
        try:
            client_name = client_data.get("first_name", "")
            client_type = client_data.get("client_type", ClientType.UNKNOWN)
            
            # Determine template based on client type
            if response_type == "greeting":
                if client_type == ClientType.NON_MEDICARE:
                    template_name = "non_medicare_greeting"
                elif client_type == ClientType.MEDICARE:
                    template_name = "medicare_greeting"
                else:
                    template_name = "default_greeting"
            else:  # voicemail
                # Use client-type specific voicemail template
                if client_type == ClientType.NON_MEDICARE:
                    template_name = "non_medicare_voicemail"
                elif client_type == ClientType.MEDICARE:
                    template_name = "medicare_voicemail"
                else:
                    template_name = "voicemail"  # Default fallback
            
            # Try segmented audio first
            segmented_result = await self.segmented_audio.get_personalized_audio(
                template_name=template_name,
                client_name=client_name,
                context={"client_type": client_type.value}
            )
            
            if segmented_result.get("success"):
                self.segmented_responses += 1
                
                return {
                    "success": True,
                    "audio_url": segmented_result["audio_url"],
                    "generation_time_ms": int((time.time() - start_time) * 1000),
                    "source": "segmented_audio",
                    "template_used": template_name,
                    "client_type": client_type.value
                }
            
            # Fallback to dynamic TTS with appropriate script
            scripts = self.client_data_service.get_scripts_for_client_type(client_type)
            script_text = scripts.get(response_type, "")
            
            if script_text:
                formatted_text = self.client_data_service.format_script_with_data(script_text, client_data)
                return await self._generate_dynamic_audio(formatted_text, start_time, "dynamic_fallback")
            
            # Final fallback
            return await self._create_emergency_fallback("Hello, thank you for calling.", start_time)
            
        except Exception as e:
            logger.error(f"❌ Personalized response error: {e}")
            return await self._create_emergency_fallback("Hello, thank you for calling.", start_time)
    
    async def _handle_agent_based_response(
        self,
        response_type: str,
        client_data: Dict[str, Any],
        start_time: float
    ) -> Dict[str, Any]:
        """Handle responses that include agent names"""
        
        try:
            # Get agent name from client data
            agent_name = client_data.get("last_agent", "our team")
            
            # Try segmented audio
            segmented_result = await self.segmented_audio.get_personalized_audio(
                template_name=response_type,
                agent_name=agent_name
            )
            
            if segmented_result.get("success"):
                self.segmented_responses += 1
                
                return {
                    "success": True,
                    "audio_url": segmented_result["audio_url"],
                    "generation_time_ms": int((time.time() - start_time) * 1000),
                    "source": "segmented_audio",
                    "template_used": response_type
                }
            
            # Fallback to dynamic TTS
            client_type = client_data.get("client_type", ClientType.UNKNOWN)
            scripts = self.client_data_service.get_scripts_for_client_type(client_type)
            script_text = scripts.get(response_type, "")
            
            if script_text:
                formatted_text = self.client_data_service.format_script_with_data(script_text, client_data)
                return await self._generate_dynamic_audio(formatted_text, start_time, "dynamic_fallback")
            
            return await self._create_emergency_fallback("Thank you for your time.", start_time)
            
        except Exception as e:
            logger.error(f"❌ Agent-based response error: {e}")
            return await self._create_emergency_fallback("Thank you for your time.", start_time)
    
    async def _handle_static_response(self, response_type: str, start_time: float) -> Dict[str, Any]:
        """Handle static responses that don't need personalization"""
        
        try:
            # Try segmented audio first (pre-generated static files)
            segmented_result = await self.segmented_audio.get_personalized_audio(
                template_name=response_type
            )
            
            if segmented_result.get("success"):
                self.static_responses += 1
                
                return {
                    "success": True,
                    "audio_url": segmented_result["audio_url"],
                    "generation_time_ms": int((time.time() - start_time) * 1000),
                    "source": "static_audio",
                    "template_used": response_type
                }
            
            # Fallback to dynamic generation with predefined text
            fallback_texts = {
                "dnc_confirmation": "Understood, we will make sure you are removed from all future communications. Have a wonderful day!",
                "keep_communications": "Great! We'll keep you in the loop with helpful health insurance updates. Thank you for your time today!",
                "not_interested": "No problem, would you like to continue receiving general health insurance communications from our team?",
                "goodbye": "Thank you for your time today. Have a wonderful day!",
                "clarification": "I want to make sure I understand correctly. Can we help service you this year during Open Enrollment?",
                "error": "I apologize, I'm having some technical difficulties. Please call us back at 8-3-3, 2-2-7, 8-5-0-0.",
                "identity_clarification": "I'm Alex calling from Altruis Advisor Group. We're a health insurance agency that has helped you with your coverage in the past.",
                "ai_clarification": "I'm Alex, a digital assistant from Altruis Advisor Group. I'm here to help connect you with our team regarding your health insurance options.",
                "memory_clarification": "I understand, sometimes it's been a while since we last spoke. You worked with our team here at Altruis Advisor Group for your health insurance needs.",
                "repeat_response": "Of course! I'm Alex from Altruis Advisor Group. We've helped you with health insurance before, and I'm calling to see if we can assist you during Open Enrollment this year.",
                "confusion_clarification": "Let me clarify. I'm Alex from Altruis Advisor Group, a health insurance agency. We're calling because it's Open Enrollment season."
            }
            
            fallback_text = fallback_texts.get(response_type, "Thank you for calling.")
            return await self._generate_dynamic_audio(fallback_text, start_time, "static_fallback")
            
        except Exception as e:
            logger.error(f"❌ Static response error: {e}")
            return await self._create_emergency_fallback("Thank you for calling.", start_time)
    

    
    async def _handle_dynamic_response(
        self,
        text: str,
        response_type: str,
        client_data: Dict[str, Any],
        start_time: float
    ) -> Dict[str, Any]:
        """Handle dynamic responses that need real-time generation"""
        
        try:
            # Use provided text or generate from client data
            if not text and client_data:
                client_type = client_data.get("client_type", ClientType.UNKNOWN)
                scripts = self.client_data_service.get_scripts_for_client_type(client_type)
                text = scripts.get(response_type, "Thank you for calling.")
                text = self.client_data_service.format_script_with_data(text, client_data)
            
            if not text:
                text = "Thank you for calling."
            
            return await self._generate_dynamic_audio(text, start_time, "dynamic_complex")
            
        except Exception as e:
            logger.error(f"❌ Dynamic response error: {e}")
            return await self._create_emergency_fallback(text or "Thank you for calling.", start_time)
    
    async def _handle_silence_response(self, response_type: str, start_time: float) -> Dict[str, Any]:
        """Handle silence detection responses with fallback to segmented audio"""
        
        try:
            # Try segmented audio first for consistency
            segmented_result = await self.segmented_audio.get_personalized_audio(
                template_name=response_type
            )
            
            if segmented_result.get("success"):
                self.static_responses += 1
                
                return {
                    "success": True,
                    "audio_url": segmented_result["audio_url"],
                    "generation_time_ms": int((time.time() - start_time) * 1000),
                    "source": "static_audio",
                    "template_used": response_type
                }
            
            # Fallback texts for silence detection (matching user requirements)
            silence_texts = {
                "no_speech_first": "I'm sorry, I didn't hear anything. Did you say something?",
                "no_speech_second": "I'm sorry, I didn't hear anything. Did you say something?",
                "no_speech_final": "You can call us back at 8-3-3, 2-2-7, 8-5-0-0. Have a great day.",
                "silence_detection": "I'm sorry, I didn't hear anything. Did you say something?"
            }
            
            text = silence_texts.get(response_type, silence_texts["silence_detection"])
            
            # Generate audio using ElevenLabs for natural speech
            return await self._generate_dynamic_audio(text, start_time, "silence_response")
            
        except Exception as e:
            logger.error(f"❌ Silence response error: {e}")
            return await self._create_emergency_fallback("I'm sorry, I didn't hear anything.", start_time)
    
    async def _generate_dynamic_audio(self, text: str, start_time: float, source: str) -> Dict[str, Any]:
        """Generate audio using ElevenLabs TTS"""
        
        try:
            result = await elevenlabs_client.generate_speech(text)
            
            if result.get("success") and result.get("audio_data"):
                # Save to temp file
                import uuid
                from pathlib import Path
                
                temp_dir = Path("static/audio/temp")
                temp_dir.mkdir(parents=True, exist_ok=True)
                
                filename = f"dynamic_{uuid.uuid4().hex[:12]}.mp3"
                filepath = temp_dir / filename
                
                with open(filepath, "wb") as f:
                    f.write(result["audio_data"])
                
                audio_url = f"{settings.base_url.rstrip('/')}/static/audio/temp/{filename}"
                
                self.dynamic_responses += 1
                
                return {
                    "success": True,
                    "audio_url": audio_url,
                    "generation_time_ms": int((time.time() - start_time) * 1000),
                    "source": source,
                    "elevenlabs_latency": result.get("latency_ms", 0)
                }
            
            return await self._create_emergency_fallback(text, start_time)
            
        except Exception as e:
            logger.error(f"❌ Dynamic audio generation error: {e}")
            return await self._create_emergency_fallback(text, start_time)
    
    async def _create_emergency_fallback(self, text: str, start_time: float) -> Dict[str, Any]:
        """Create emergency fallback response"""
        
        self.fallback_responses += 1
        
        return {
            "success": False,
            "error": "Audio generation failed",
            "fallback_text": text or "Thank you for calling.",
            "generation_time_ms": int((time.time() - start_time) * 1000),
            "source": "emergency_fallback"
        }
    
    def _get_default_client_data(self) -> Dict[str, Any]:
        """Get default client data structure"""
        
        return {
            "first_name": "",
            "last_name": "",
            "full_name": "",
            "phone": "",
            "email": "",
            "tags": "",
            "client_type": ClientType.UNKNOWN,
            "is_medicare_client": False,
            "is_non_medicare_client": False,
            "agent_info": None,
            "script_type": "default_script",
            "greeting_template": "default_greeting",
            "voicemail_template": "default_voicemail"
        }
    
    def get_performance_stats(self) -> Dict[str, Any]:
        """Get performance statistics"""
        
        total_responses = (
            self.static_responses + 
            self.dynamic_responses + 
            self.segmented_responses + 
            self.fallback_responses
        )
        
        if total_responses == 0:
            return {
                "total_responses": 0,
                "static_percentage": 0,
                "dynamic_percentage": 0,
                "segmented_percentage": 0,
                "fallback_percentage": 0
            }
        
        return {
            "total_responses": total_responses,
            "static_responses": self.static_responses,
            "dynamic_responses": self.dynamic_responses,
            "segmented_responses": self.segmented_responses,
            "fallback_responses": self.fallback_responses,
            "static_percentage": round((self.static_responses / total_responses) * 100, 1),
            "dynamic_percentage": round((self.dynamic_responses / total_responses) * 100, 1),
            "segmented_percentage": round((self.segmented_responses / total_responses) * 100, 1),
            "fallback_percentage": round((self.fallback_responses / total_responses) * 100, 1)
        }

# Create service instance
hybrid_tts_service = HybridTTSService()