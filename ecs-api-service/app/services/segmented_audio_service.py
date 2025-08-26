"""
Segmented Audio Service - Production Ready
Handles real-time audio concatenation for personalized responses with S3 support
"""

import asyncio
import hashlib
import logging
import os
import re
import subprocess
import time
import uuid
from pathlib import Path
from typing import Dict, Any, Optional, List
from datetime import datetime

from shared.config.settings import settings

logger = logging.getLogger(__name__)

class SegmentedAudioService:
    """Service for concatenating audio segments with real names"""

    def __init__(self):
        # Import S3 audio service
        try:
            from services.s3_audio_service import s3_audio_service
            self.s3_audio_service = s3_audio_service
        except ImportError:
            self.s3_audio_service = None
            logger.warning("⚠️ S3 Audio Service not available, using local files only")
        
        # Use the correct path based on your structure
        self.base_dir = Path("audio-generation")
        if not self.base_dir.exists():
            # Try app/audio-generation if the first path doesn't exist
            self.base_dir = Path("app/audio-generation")
            
        self.segments_dir = self.base_dir / "segments"
        self.client_names_dir = self.base_dir / "names" / "clients"
        self.agent_names_dir = self.base_dir / "names" / "agents"
        self.cache_dir = self.base_dir / "concatenated_cache"
        self.temp_dir = Path("static/audio/temp")

        # Ensure temp directory exists
        self.temp_dir.mkdir(parents=True, exist_ok=True)
        
        # Load manifest if exists
        self.manifest = self._load_manifest()
        
        # Updated templates based on your audio files
        self.templates = {
            "greeting": {
                "segments": ["[CLIENT_NAME]", "greeting_middle"],
                "description": "Personalized greeting with client name"
            },
            "non_medicare_greeting": {
                "segments": ["[CLIENT_NAME]", "non_medicare_greeting_middle"],
                "description": "Non-Medicare client greeting with client name"
            },
            "medicare_greeting": {
                "segments": ["[CLIENT_NAME]", "medicare_greeting_middle"],
                "description": "Medicare client greeting with client name"
            },
            "default_greeting": {
                "segments": ["[CLIENT_NAME]", "default_greeting_middle"],
                "description": "Default greeting with client name"
            },
            "agent_intro": {
                "segments": ["agent_intro_start", "[AGENT_NAME]", "agent_intro_middle"],
                "description": "Agent introduction with agent name"
            },
            "schedule_confirmation": {
                "segments": ["schedule_start", "[AGENT_NAME]", "schedule_middle"],
                "description": "Schedule confirmation with agent name"
            },
            "no_schedule_followup": {
                "segments": ["no_schedule_start", "[AGENT_NAME]", "no_schedule_middle"],
                "description": "No schedule follow-up with agent name"
            },
            # Static responses (no concatenation needed)
            "not_interested": {
                "segments": ["not_interested_start"],
                "description": "Not interested response"
            },
            "dnc_confirmation": {
                "segments": ["dnc_confirmation"],
                "description": "Do not call confirmation"
            },
            "keep_communications": {
                "segments": ["keep_communications"],
                "description": "Keep communications confirmation"
            },
            "goodbye": {
                "segments": ["goodbye"],
                "description": "Simple goodbye"
            },
            "clarification": {
                "segments": ["clarification"],
                "description": "General clarification"
            },
            # Voicemail templates (restored)
            "voicemail": {
                "segments": ["[CLIENT_NAME]", "default_voicemail_middle"],
                "description": "Personalized voicemail with client name and natural phone number"
            },
            "non_medicare_voicemail": {
                "segments": ["[CLIENT_NAME]", "non_medicare_voicemail_middle"],
                "description": "Non-Medicare client voicemail with client name"
            },
            "medicare_voicemail": {
                "segments": ["[CLIENT_NAME]", "medicare_voicemail_middle"],
                "description": "Medicare client voicemail with client name"
            },
            # NEW: Missing templates that were causing errors
            "identity_clarification": {
                "segments": ["identity_clarification"],
                "description": "Identity clarification response"
            },
            "ai_clarification": {
                "segments": ["ai_clarification"],
                "description": "AI clarification response"
            },
            "memory_clarification": {
                "segments": ["memory_clarification"],
                "description": "Memory clarification response"
            },
            "repeat_response": {
                "segments": ["repeat_response"],
                "description": "Repeat request response"
            },
            "confusion_clarification": {
                "segments": ["confusion_clarification"],
                "description": "Confusion clarification response"
            },
            "no_speech_first": {
                "segments": ["no_speech_first"],
                "description": "First silence detection response"
            },
            "no_speech_second": {
                "segments": ["no_speech_second"],
                "description": "Second silence detection response"
            },
            "no_speech_final": {
                "segments": ["no_speech_final"],
                "description": "Final silence detection response"
            },
            "lyzr_delay_filler": {
                "segments": ["lyzr_delay_filler"],
                "description": "LYZR delay filler response"
            },
            "lyzr_response": {
                "segments": ["lyzr_response"],
                "description": "LYZR response"
            },
            "interruption_acknowledgment": {
                "segments": ["interruption_acknowledgment"],
                "description": "Interruption acknowledgment response"
            },
            "repeat_request": {
                "segments": ["repeat_request"],
                "description": "Repeat request response"
            },
            "error": {
                "segments": ["error"],
                "description": "Error response"
            },
            # NEW: Missing templates for updated voice processor
            "busy_call_back": {
                "segments": ["busy_call_back"],
                "description": "Busy/call back response"
            },
            "silence_detection": {
                "segments": ["silence_detection"],
                "description": "Silence detection response"
            }
        }
        
        # Performance tracking
        self.concatenations_count = 0
        self.cache_hits = 0
        self.generation_time_total = 0.0
    
    def convert_phone_to_natural_speech(self, phone_number: str) -> str:
        """
        Convert phone number to natural speech format
        Example: "833.227.8500" -> "eight three three, two two seven, eight five zero zero"
        """
        # Remove any non-digit characters
        digits_only = re.sub(r'[^\d]', '', phone_number)
        
        if not digits_only:
            return phone_number
        
        # Convert each digit to word
        digit_words = {
            '0': 'zero', '1': 'one', '2': 'two', '3': 'three', '4': 'four',
            '5': 'five', '6': 'six', '7': 'seven', '8': 'eight', '9': 'nine'
        }
        
        # Group digits for natural speaking (3-3-4 format for US numbers)
        if len(digits_only) == 10:  # Standard US number
            area_code = digits_only[:3]
            prefix = digits_only[3:6]
            line_number = digits_only[6:]
            
            # Convert each group to words
            area_words = ' '.join([digit_words[d] for d in area_code])
            prefix_words = ' '.join([digit_words[d] for d in prefix])
            line_words = ' '.join([digit_words[d] for d in line_number])
            
            return f"{area_words}, {prefix_words}, {line_words}"
        elif len(digits_only) == 11 and digits_only[0] == '1':  # US number with country code
            area_code = digits_only[1:4]
            prefix = digits_only[4:7]
            line_number = digits_only[7:]
            
            area_words = ' '.join([digit_words[d] for d in area_code])
            prefix_words = ' '.join([digit_words[d] for d in prefix])
            line_words = ' '.join([digit_words[d] for d in line_number])
            
            return f"{area_words}, {prefix_words}, {line_words}"
        else:
            # For other formats, just convert each digit
            return ' '.join([digit_words[d] for d in digits_only])
    
    def _load_manifest(self) -> Dict[str, Any]:
        """Load segments manifest if available"""
        try:
            manifest_path = self.base_dir / "segments_manifest.json"
            if manifest_path.exists():
                import json
                with open(manifest_path, 'r') as f:
                    return json.load(f)
            return {}
        except Exception as e:
            logger.warning(f"Could not load manifest: {e}")
            return {}
    
    async def get_personalized_audio(
        self, 
        template_name: str, 
        client_name: Optional[str] = None,
        agent_name: Optional[str] = None,
        context: Optional[Dict[str, Any]] = None
    ) -> Dict[str, Any]:
        """Get personalized audio by concatenating segments with names"""
        
        start_time = time.time()
        
        logger.info(f"🎯 get_personalized_audio called - Template: '{template_name}', Client: '{client_name}', Context: {context}")
        
        try:
            # Check if template exists
            if template_name not in self.templates:
                logger.error(f"❌ Unknown template: {template_name}")
                return {"success": False, "error": f"Unknown template: {template_name}"}
            
            template = self.templates[template_name]
            logger.info(f"📋 Template segments: {template['segments']}")
            
            # Check if concatenation is needed
            if not self._needs_concatenation(template["segments"]):
                # Simple static response
                return await self._get_static_audio(template["segments"][0])
            
            # Generate cache key
            cache_key = self._generate_cache_key(template_name, client_name, agent_name)
            
            # Check local cache first (concatenated_cache directory)
            cached_file = self.cache_dir / f"{cache_key}.mp3"
            if cached_file.exists():
                # Copy to temp for serving
                temp_filename = f"cached_{cache_key[:12]}_{uuid.uuid4().hex[:8]}.mp3"
                temp_path = self.temp_dir / temp_filename
                
                import shutil
                shutil.copy2(cached_file, temp_path)
                
                audio_url = f"{settings.base_url.rstrip('/')}/static/audio/temp/{temp_filename}"
                
                self.cache_hits += 1
                logger.info(f"⚡ Cache hit for: {template_name}")
                
                return {
                    "success": True,
                    "audio_url": audio_url,
                    "generation_time_ms": int((time.time() - start_time) * 1000),
                    "source": "cache"
                }
            
            # Generate audio by concatenation
            concatenation_context = {"template_name": template_name, **(context or {})}
            logger.info(f"🔧 Concatenation context: {concatenation_context}")
            
            audio_url = await self._concatenate_segments(
                template["segments"], 
                client_name, 
                agent_name,
                cache_key,
                concatenation_context
            )
            
            if audio_url:
                self.concatenations_count += 1
                generation_time = int((time.time() - start_time) * 1000)
                self.generation_time_total += generation_time
                
                logger.info(f"✅ Generated personalized audio: {template_name} ({generation_time}ms)")
                
                return {
                    "success": True,
                    "audio_url": audio_url,
                    "generation_time_ms": generation_time,
                    "source": "concatenated"
                }
            else:
                # Fallback to dynamic TTS
                return await self._fallback_to_dynamic_tts(template_name, client_name, agent_name)
        
        except Exception as e:
            logger.error(f"❌ Segmented audio error: {e}")
            return await self._fallback_to_dynamic_tts(template_name, client_name, agent_name)
    
    def _needs_concatenation(self, segments: List[str]) -> bool:
        """Check if segments need concatenation (contain placeholders)"""
        return any("[" in segment and "]" in segment for segment in segments)
    
    async def _get_static_audio(self, segment_name: str) -> Dict[str, Any]:
        """Get static audio file URL"""
        try:
            audio_file = self.segments_dir / f"{segment_name}.mp3"
            
            if audio_file.exists():
                # Copy to temp directory for serving
                temp_filename = f"static_{segment_name}_{uuid.uuid4().hex[:8]}.mp3"
                temp_path = self.temp_dir / temp_filename
                
                import shutil
                shutil.copy2(audio_file, temp_path)
                
                audio_url = f"{settings.base_url.rstrip('/')}/static/audio/temp/{temp_filename}"
                
                return {
                    "success": True,
                    "audio_url": audio_url,
                    "generation_time_ms": 50,  # Very fast for static
                    "source": "static"
                }
            else:
                logger.error(f"❌ Static audio file not found: {audio_file}")
                return {"success": False, "error": "Static audio file not found"}
        
        except Exception as e:
            logger.error(f"❌ Static audio error: {e}")
            return {"success": False, "error": str(e)}
    
    async def _concatenate_segments(
        self, 
        segments: List[str], 
        client_name: Optional[str],
        agent_name: Optional[str],
        cache_key: str,
        context: Optional[Dict[str, Any]] = None
    ) -> Optional[str]:
        """Concatenate audio segments with names"""
        
        try:
            # Collect audio files to concatenate
            audio_files = []
            
            for segment in segments:
                if segment == "[CLIENT_NAME]" and client_name:
                    # Get client name audio (this will now return "Hello {client_name}" combination or just name based on context)
                    client_file = await self._get_name_audio(client_name, "client", context)
                    if client_file:
                        audio_files.append(client_file)
                    else:
                        logger.warning(f"⚠️ Client name audio not found: {client_name}")
                        return None
                
                elif segment == "[AGENT_NAME]" and agent_name:
                    # Get agent name audio
                    agent_file = await self._get_name_audio(agent_name, "agent", context)
                    if agent_file:
                        audio_files.append(agent_file)
                    else:
                        logger.warning(f"⚠️ Agent name audio not found: {agent_name}")
                        return None
                
                else:
                    # Get segment audio with improved priority: Local → S3 → On-demand
                    filename = f"{segment}.mp3"
                    
                    # 1. First check local audio-generation folder
                    segment_file = self.segments_dir / filename
                    if segment_file.exists():
                        logger.info(f"📁 Using local segment: {segment}")
                        audio_files.append(str(segment_file))
                        continue
                    
                    # 2. Check S3 if available
                    if self.s3_audio_service:
                        audio_path = await self.s3_audio_service.get_audio_file_path("segments", filename)
                        if audio_path:
                            logger.info(f"☁️ Using S3 segment: {segment}")
                            audio_files.append(str(audio_path))
                            continue
                    
                    # 3. Generate on-demand if not found anywhere
                    logger.info(f"🔄 Generating segment on-demand: {segment}")
                    generated_path = await self._generate_segment_audio(segment)
                    if generated_path:
                        audio_files.append(str(generated_path))
                    else:
                        logger.error(f"❌ Failed to generate segment: {segment}")
                        return None
            
            if not audio_files:
                logger.error("❌ No audio files to concatenate")
                return None
            
            # Concatenate using ffmpeg
            output_filename = f"concat_{cache_key[:12]}_{uuid.uuid4().hex[:8]}.mp3"
            output_path = self.temp_dir / output_filename
            
            success = await self._ffmpeg_concatenate(audio_files, str(output_path))
            
            if success:
                # Also save to cache
                cache_path = self.cache_dir / f"{cache_key}.mp3"
                import shutil
                shutil.copy2(output_path, cache_path)
                
                audio_url = f"{settings.base_url.rstrip('/')}/static/audio/temp/{output_filename}"
                return audio_url
            else:
                return None
        
        except Exception as e:
            logger.error(f"❌ Concatenation error: {e}")
            return None
    
    async def _get_name_audio(self, name: str, name_type: str, context: Optional[Dict[str, Any]] = None) -> Optional[str]:
        """Get audio file for a name (client or agent)"""
        
        try:
            if name_type == "client":
                # Check if we should use "Hello {name}" combination based on context
                should_use_hello_combination = False
                template_name = context.get("template_name", "") if context else ""
                
                logger.info(f"🔍 Context check for client '{name}' - Template: '{template_name}'")
                
                # Only use "Hello {name}" for greeting and voicemail templates
                if template_name in ["greeting", "non_medicare_greeting", "medicare_greeting", "default_greeting", 
                                   "voicemail", "non_medicare_voicemail", "medicare_voicemail"]:
                    should_use_hello_combination = True
                    logger.info(f"✅ Using 'Hello {name}' combination for template: {template_name}")
                else:
                    logger.info(f"ℹ️ Using individual client name for template: {template_name}")
                
                if should_use_hello_combination:
                    # First, try "Hello {name}" combination for natural flow
                    hello_combinations_dir = self.client_names_dir / "hello_combinations"
                    hello_combinations_dir.mkdir(exist_ok=True)  # Ensure directory exists
                    hello_filename = f"hello_{name.lower()}.mp3"
                    hello_filepath = hello_combinations_dir / hello_filename
                    
                    if hello_filepath.exists():
                        logger.info(f"✅ Using existing 'Hello {name}' combination for greeting/voicemail")
                        return str(hello_filepath)
                    else:
                        # Generate "Hello {name}" combination on-demand
                        logger.info(f"🔄 Generating 'Hello {name}' combination on-demand")
                        return await self._generate_hello_combination(name)
                
                # For all other contexts, use just the client name (no "Hello" prefix)
                filename = f"{name.lower()}.mp3"
                
                # 1. First check local audio-generation folder
                name_file = self.client_names_dir / filename
                if name_file.exists():
                    logger.info(f"📁 Using local client name: {name}")
                    return str(name_file)
                
                # 2. Check S3 if available
                if self.s3_audio_service:
                    audio_path = await self.s3_audio_service.get_audio_file_path("names/clients", filename)
                    if audio_path:
                        logger.info(f"☁️ Using S3 client name: {name}")
                        return str(audio_path)
                
                # 3. Try first name only (local → S3)
                first_name = name.split()[0].lower()
                filename = f"{first_name}.mp3"
                
                name_file = self.client_names_dir / filename
                if name_file.exists():
                    logger.info(f"📁 Using local first name: {first_name}")
                    return str(name_file)
                
                if self.s3_audio_service:
                    audio_path = await self.s3_audio_service.get_audio_file_path("names/clients", filename)
                    if audio_path:
                        logger.info(f"☁️ Using S3 first name: {first_name}")
                        return str(audio_path)
                
                # 4. Generate on-demand if not found anywhere
                logger.info(f"🔄 Generating client name on-demand: {name}")
                return await self._generate_name_audio(name, "client")
            
            elif name_type == "agent":
                # Handle agent name audio with improved priority: Local → S3 → On-demand
                agent_filename = name.lower().replace(' ', '_').replace('.', '')
                filename = f"{agent_filename}.mp3"
                
                # 1. First check local audio-generation folder
                name_file = self.agent_names_dir / filename
                if name_file.exists():
                    logger.info(f"📁 Using local agent name: {name}")
                    return str(name_file)
                
                # 2. Check S3 if available
                if self.s3_audio_service:
                    audio_path = await self.s3_audio_service.get_audio_file_path("names/agents", filename)
                    if audio_path:
                        logger.info(f"☁️ Using S3 agent name: {name}")
                        return str(audio_path)
                
                # 3. Generate on-demand if not found anywhere
                logger.info(f"🔄 Generating agent name on-demand: {name}")
                return await self._generate_name_audio(name, "agent")
            
            return None
        
        except Exception as e:
            logger.error(f"❌ Name audio error: {e}")
            return None
    
    async def _generate_name_audio(self, name: str, name_type: str) -> Optional[str]:
        """Generate audio for a name on-demand"""
        
        try:
            # Import ElevenLabs client
            from services.elevenlabs_client import elevenlabs_client
            
            # Generate audio
            result = await elevenlabs_client.generate_speech(name)
            
            if result.get("success") and result.get("audio_data"):
                # Save to appropriate directory
                if name_type == "client":
                    filename = f"{name.lower()}.mp3"
                    save_path = self.client_names_dir / filename
                else:
                    filename = f"{name.lower().replace(' ', '_')}.mp3"
                    save_path = self.agent_names_dir / filename
                
                # Save file
                with open(save_path, "wb") as f:
                    f.write(result["audio_data"])
                
                logger.info(f"✅ Generated name audio: {name}")
                return str(save_path)
            
            return None
        
        except Exception as e:
            logger.error(f"❌ Name generation error: {e}")
            return None
    
    async def _generate_segment_audio(self, segment_name: str) -> Optional[str]:
        """Generate audio for a segment on-demand"""
        
        try:
            # Import ElevenLabs client
            from services.elevenlabs_client import elevenlabs_client
            
            # Get the text for this segment from the script segments
            # We need to import the script segments from the generation script
            script_segments = self._get_script_segments()
            text = script_segments.get(segment_name, "")
            
            if not text:
                logger.error(f"❌ No text found for segment: {segment_name}")
                return None
            
            logger.info(f"🎵 Generating segment audio: {segment_name} - '{text[:50]}...'")
            
            result = await elevenlabs_client.generate_speech(text)
            
            if result.get("success") and result.get("audio_data"):
                # Save to segments directory
                filename = f"{segment_name}.mp3"
                save_path = self.segments_dir / filename
                
                # Ensure directory exists
                self.segments_dir.mkdir(parents=True, exist_ok=True)
                
                # Save file
                with open(save_path, "wb") as f:
                    f.write(result["audio_data"])
                
                logger.info(f"✅ Generated segment audio: {segment_name}")
                return str(save_path)
            
            logger.error(f"❌ Failed to generate segment: {segment_name}")
            return None
        
        except Exception as e:
            logger.error(f"❌ Segment generation error: {e}")
            return None
    
    def _get_script_segments(self) -> Dict[str, str]:
        """Get script segments text for on-demand generation"""
        # This should match the SCRIPT_SEGMENTS from generate_segmented_audio.py
        return {
            # Greeting segments
            "greeting_middle": ", Alex here from Altruis Advisor Group. We've helped you with your health insurance needs in the past and I just wanted to reach out to see if we can be of service to you this year during Open Enrollment? A simple Yes or No is fine, and remember, our services are completely free of charge.",
            "non_medicare_greeting_middle": ", Alex calling on behalf of Anthony Fracchia and Altruis Advisor Group, we've helped you with your health insurance needs in the past and I'm reaching out to see if we can be of service to you this year during Open Enrollment? A simple 'Yes' or 'No' is fine, and remember, our services are completely free of charge.",
            "medicare_greeting_middle": ", this is Alex from Altruis Advisor Group. We've helped you with your health insurance needs in the past and I just wanted to reach out to see if we can be of service to you this year during Open Enrollment? A simple Yes or No is fine, and remember, our services are completely free of charge.",
            "default_greeting_middle": ", this is Alex from Altruis Advisor Group. We've helped you with your insurance needs in the past and I just wanted to reach out to see if we can be of service to you this year during Open Enrollment? A simple Yes or No is fine, and remember, our services are completely free of charge.",
            
            # Agent segments
            "agent_intro_start": "Great, looks like ",
            "agent_intro_middle": " was the last agent you worked with here at Altruis. Would you like to schedule a quick 15-minute discovery call with them to get reacquainted? A simple Yes or No will do!",
            "schedule_start": "Perfect! I'll send you an email shortly with ",
            "schedule_middle": "available time slots. You can review the calendar and choose a time that works best for your schedule. Thank you so much for your time today, and have a wonderful day!",
            "no_schedule_start": "No problem, ",
            "no_schedule_middle": " will reach out to you and the two of you can work together to determine the best next steps. We look forward to servicing you, have a wonderful day!",
            
            # Voicemail segments
            "non_medicare_voicemail_middle": ", Alex calling on behalf of Anthony Fracchia and Altruis Advisor Group. We've helped with your health insurance needs in the past and we wanted to reach out to see if we could be of assistance this year during Open Enrollment. There have been a number of important changes to the Affordable Care Act that may impact your situation - so it may make sense to do a quick policy review. As always, our services are completely free of charge - if you'd like to review your policy please call us at 8-3-3, 2-2-7, 8-5-0-0. We look forward to hearing from you - take care!",
            "medicare_voicemail_middle": ", Alex here from Altruis Advisor Group. We've helped with your health insurance needs in the past and we wanted to reach out to see if we could be of assistance this year during Open Enrollment. There have been a number of important changes to the Affordable Care Act that may impact your situation - so it may make sense to do a quick policy review. As always, our services are completely free of charge - if you'd like to review your policy please call us at 8-3-3, 2-2-7, 8-5-0-0. We look forward to hearing from you - take care!",
            "default_voicemail_middle": ", Alex here from Altruis Advisor Group. We've helped with your health insurance needs in the past and we wanted to reach out to see if we could be of assistance this year during Open Enrollment. There have been a number of important changes to the Affordable Care Act that may impact your situation - so it may make sense to do a quick policy review. As always, our services are completely free of charge - if you'd like to review your policy please call us at 8-3-3, 2-2-7, 8-5-0-0. We look forward to hearing from you - take care!",
            
            # Static responses
            "dnc_confirmation": "Understood, we will make sure you are removed from all future communications and send you a confirmation email once that is done. If you'd like to connect with one of our insurance experts in the future please feel free to reach out — we are always here to help and our service is always free of charge. Have a wonderful day!",
            "keep_communications": "Great! We'll keep you in the loop with helpful health insurance updates throughout the year. If you ever need assistance, just reach out - we're always here to help, and our service is always free. Thank you for your time today!",
            "not_interested_start": "No problem, would you like to continue receiving general health insurance communications from our team? Again, a simple Yes or No will do!",
            "goodbye": "Thank you for your time today. Have a wonderful day!",
            "clarification": "I want to make sure I understand correctly. Can we help service you this year during Open Enrollment? Please say Yes if you're interested, or No if you're not interested.",
            "error": "I apologize, I'm having some technical difficulties. Please call us back at 8-3-3, 2-2-7, 8-5-0-0.",
            
            # Clarifying responses
            "identity_clarification": "I'm Alex calling from Altruis Advisor Group. We're a health insurance agency that has helped you with your coverage in the past. We're reaching out to see if we can assist you during this year's Open Enrollment period. Are you interested in reviewing your options?",
            "ai_clarification": "I'm Alex, a digital assistant from Altruis Advisor Group. I'm here to help connect you with our team regarding your health insurance options during Open Enrollment. We've worked with you before and wanted to see if we can be of service again this year. Are you interested?",
            "memory_clarification": "I understand, sometimes it's been a while since we last spoke. You worked with our team here at Altruis Advisor Group for your health insurance needs. We're reaching out because Open Enrollment is here, and we wanted to see if we can help you review your options again this year. Are you interested?",
            "repeat_response": "Of course! I'm Alex from Altruis Advisor Group. We've helped you with health insurance before, and I'm calling to see if we can assist you during Open Enrollment this year. Are you interested in reviewing your options? A simple yes or no is fine.",
            "confusion_clarification": "Let me clarify. I'm Alex from Altruis Advisor Group, a health insurance agency. We're calling because it's Open Enrollment season and we wanted to see if you'd like help reviewing your health insurance options. We've assisted you before. Would you be interested? Just yes or no is fine.",
            
            # No speech handling
            "no_speech_first": "I'm sorry, I can't seem to hear you clearly. If you said something, could you please speak a bit louder? I'm here to help.",
            "no_speech_second": "I'm still having trouble hearing you. If you're there, please try speaking directly into your phone. Are you interested in reviewing your health insurance options?",
            "no_speech_final": "I apologize, but I'm having difficulty hearing your response. If you'd like to speak with someone, please call us back at 8-3-3, 2-2-7, 8-5-0-0. Thank you and have a great day.",
            
            # Additional response categories
            "lyzr_delay_filler": "That's a great question, let me make sure I give you the most accurate information.",
            "interruption_acknowledgment": "Of course, I'm here to help. What would you like to know?",
            "busy_call_back": "No problem at all! I'll call you back at a better time. Have a great day!",
            "silence_detection": "I'm sorry, I didn't hear anything. Did you say something?"
        }
    
    async def _generate_hello_combination(self, name: str) -> Optional[str]:
        """Generate 'Hello {client_name}' combination on-demand"""
        
        try:
            # Import ElevenLabs client
            from services.elevenlabs_client import elevenlabs_client
            
            # Generate "Hello {name}" as a single phrase
            hello_text = f"Hello {name}"
            logger.info(f"🎵 Generating: {hello_text}")
            
            result = await elevenlabs_client.generate_speech(hello_text)
            
            if result.get("success") and result.get("audio_data"):
                # Save to hello_combinations directory
                hello_combinations_dir = self.client_names_dir / "hello_combinations"
                hello_combinations_dir.mkdir(exist_ok=True)
                
                hello_filename = f"hello_{name.lower()}.mp3"
                hello_filepath = hello_combinations_dir / hello_filename
                
                with open(hello_filepath, "wb") as f:
                    f.write(result["audio_data"])
                
                logger.info(f"✅ Generated 'Hello {name}' combination: {hello_filepath}")
                return str(hello_filepath)
            else:
                logger.error(f"❌ Failed to generate 'Hello {name}' combination: {result.get('error', 'Unknown error')}")
                return None
        
        except Exception as e:
            logger.error(f"❌ Hello combination generation error: {e}")
            return None
    
    async def _ffmpeg_concatenate(self, audio_files: List[str], output_path: str) -> bool:
        """Concatenate audio files using ffmpeg"""
        
        try:
            # Create concat file list
            concat_file = self.temp_dir / f"concat_{uuid.uuid4().hex[:8]}.txt"
            
            with open(concat_file, 'w') as f:
                for audio_file in audio_files:
                    # Use absolute paths to avoid issues
                    abs_path = Path(audio_file).absolute()
                    # Escape path for ffmpeg
                    escaped_path = str(abs_path).replace("'", "'\"'\"'")
                    f.write(f"file '{escaped_path}'\n")
            
            # Run ffmpeg concatenation with better error handling
            cmd = [
                'ffmpeg', '-y',  # -y to overwrite output file
                '-f', 'concat',
                '-safe', '0',
                '-i', str(concat_file.absolute()),
                '-c', 'copy',  # Copy without re-encoding for speed
                '-loglevel', 'error',  # Only show errors
                str(Path(output_path).absolute())
            ]
            
            # Run async subprocess
            process = await asyncio.create_subprocess_exec(
                *cmd,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE
            )
            
            stdout, stderr = await process.communicate()
            
            # Clean up concat file
            concat_file.unlink(missing_ok=True)
            
            if process.returncode == 0 and Path(output_path).exists():
                logger.debug(f"✅ FFmpeg concatenation successful: {output_path}")
                return True
            else:
                error_msg = stderr.decode() if stderr else "Unknown error"
                logger.error(f"❌ FFmpeg concatenation failed: {error_msg}")
                return False
        
        except Exception as e:
            logger.error(f"❌ FFmpeg concatenation error: {e}")
            return False
    
    async def _fallback_to_dynamic_tts(
        self, 
        template_name: str, 
        client_name: Optional[str],
        agent_name: Optional[str]
    ) -> Dict[str, Any]:
        """Fallback to dynamic TTS generation"""
        
        try:
            # Import ElevenLabs client
            from services.elevenlabs_client import elevenlabs_client
            
            # Create full text based on template
            full_text = self._build_full_text(template_name, client_name, agent_name)
            
            if full_text:
                result = await elevenlabs_client.generate_speech(full_text)
                
                if result.get("success") and result.get("audio_data"):
                    # Save fallback audio
                    filename = f"fallback_{template_name}_{uuid.uuid4().hex[:8]}.mp3"
                    output_path = self.temp_dir / filename
                    
                    with open(output_path, "wb") as f:
                        f.write(result["audio_data"])
                    
                    audio_url = f"{settings.base_url.rstrip('/')}/static/audio/temp/{filename}"
                    
                    logger.info(f"⚠️ Using fallback TTS for: {template_name}")
                    
                    return {
                        "success": True,
                        "audio_url": audio_url,
                        "generation_time_ms": result.get("latency_ms", 2000),
                        "source": "fallback_tts"
                    }
            
            return {"success": False, "error": "Fallback TTS failed"}
        
        except Exception as e:
            logger.error(f"❌ Fallback TTS error: {e}")
            return {"success": False, "error": str(e)}
    
    def _build_full_text(self, template_name: str, client_name: Optional[str], agent_name: Optional[str]) -> Optional[str]:
        """Build full text for dynamic TTS based on AAG script"""
        
        templates = {
            # Greeting templates
            "greeting": f"Hello {client_name or '[NAME]'}, Alex here from Altruis Advisor Group. We've helped you with your health insurance needs in the past and I just wanted to reach out to see if we can be of service to you this year during Open Enrollment? A simple Yes or No is fine, and remember, our services are completely free of charge.",
            "non_medicare_greeting": f"Hello {client_name or '[NAME]'}, Alex calling on behalf of Anthony Fracchia and Altruis Advisor Group, we've helped you with your health insurance needs in the past and I'm reaching out to see if we can be of service to you this year during Open Enrollment? A simple 'Yes' or 'No' is fine, and remember, our services are completely free of charge.",
            "medicare_greeting": f"Hello {client_name or '[NAME]'}, this is Alex from Altruis Advisor Group. We've helped you with your health insurance needs in the past and I just wanted to reach out to see if we can be of service to you this year during Open Enrollment? A simple Yes or No is fine, and remember, our services are completely free of charge.",
            "default_greeting": f"Hello {client_name or '[NAME]'}, this is Alex from Altruis Advisor Group. We've helped you with your insurance needs in the past and I just wanted to reach out to see if we can be of service to you this year during Open Enrollment? A simple Yes or No is fine, and remember, our services are completely free of charge.",
            
            # Voicemail templates
            "voicemail": f"Hello {client_name or '[NAME]'}, Alex here from Altruis Advisor Group. We've helped with your health insurance needs in the past and we wanted to reach out to see if we could be of assistance this year during Open Enrollment. There have been a number of important changes to the Affordable Care Act that may impact your situation - so it may make sense to do a quick policy review. As always, our services are completely free of charge - if you'd like to review your policy please call us at 8-3-3, 2-2-7, 8-5-0-0. We look forward to hearing from you - take care!",
            "non_medicare_voicemail": f"Hello {client_name or '[NAME]'}, Alex calling on behalf of Anthony Fracchia and Altruis Advisor Group. We've helped with your health insurance needs in the past and we wanted to reach out to see if we could be of assistance this year during Open Enrollment. There have been a number of important changes to the Affordable Care Act that may impact your situation - so it may make sense to do a quick policy review. As always, our services are completely free of charge - if you'd like to review your policy please call us at 8-3-3, 2-2-7, 8-5-0-0. We look forward to hearing from you - take care!",
            "medicare_voicemail": f"Hello {client_name or '[NAME]'}, Alex here from Altruis Advisor Group. We've helped with your health insurance needs in the past and we wanted to reach out to see if we could be of assistance this year during Open Enrollment. There have been a number of important changes to the Affordable Care Act that may impact your situation - so it may make sense to do a quick policy review. As always, our services are completely free of charge - if you'd like to review your policy please call us at 8-3-3, 2-2-7, 8-5-0-0. We look forward to hearing from you - take care!",
            
            # Agent-based templates
            "agent_intro": f"Great, looks like {agent_name or '[AGENT]'} was the last agent you worked with here at Altruis. Would you like to schedule a quick 15-minute discovery call with them to get reacquainted? A simple Yes or No will do!",
            "schedule_confirmation": f"Perfect! I'll send you an email shortly with {agent_name or '[AGENT]'}'s available time slots. You can review the calendar and choose a time that works best for your schedule. Thank you so much for your time today, and have a wonderful day!",
            "no_schedule_followup": f"No problem, {agent_name or '[AGENT]'} will reach out to you and the two of you can work together to determine the best next steps. We look forward to servicing you, have a wonderful day!",
            
            # Static responses
            "not_interested": "No problem, would you like to continue receiving general health insurance communications from our team? Again, a simple Yes or No will do!",
            "dnc_confirmation": "Understood, we will make sure you are removed from all future communications and send you a confirmation email once that is done. Our contact details will be in that email as well, so if you do change your mind in the future please feel free to reach out – we are always here to help and our service is always free of charge. Have a wonderful day!",
            "keep_communications": "Great, we're happy to keep you informed throughout the year regarding the ever-changing world of health insurance. If you'd like to connect with one of our insurance experts in the future please feel free to reach out – we are always here to help and our service is always free of charge. Have a wonderful day!",
            "goodbye": "Thank you for your time today. Have a wonderful day!",
            "clarification": "I want to make sure I understand correctly. Can we help service you this year during Open Enrollment? Please say Yes if you're interested, or No if you're not interested."
        }
        
        return templates.get(template_name)
    
    def _generate_cache_key(self, template_name: str, client_name: Optional[str], agent_name: Optional[str]) -> str:
        """Generate cache key for personalized audio"""
        
        key_parts = [template_name]
        
        if client_name:
            key_parts.append(f"client_{client_name.lower().replace(' ', '_')}")
        
        if agent_name:
            key_parts.append(f"agent_{agent_name.lower().replace(' ', '_')}")
        
        cache_key = "_".join(key_parts)
        
        # Generate hash for consistent key length
        return hashlib.md5(cache_key.encode()).hexdigest()
    
    async def cleanup_old_files(self, max_age_hours: int = 24):
        """Clean up old temporary audio files"""
        try:
            import time
            current_time = time.time()
            cleaned_count = 0
            
            for file_path in self.temp_dir.glob("*.mp3"):
                # Check file age
                file_age = current_time - file_path.stat().st_mtime
                age_hours = file_age / 3600
                
                if age_hours > max_age_hours:
                    file_path.unlink()
                    cleaned_count += 1
            
            if cleaned_count > 0:
                logger.info(f"🗑️ Cleaned up {cleaned_count} old audio files")
            
            return cleaned_count
        
        except Exception as e:
            logger.error(f"❌ Cleanup error: {e}")
            return 0
    
    def get_performance_stats(self) -> Dict[str, Any]:
        """Get performance statistics"""
        
        if self.concatenations_count == 0:
            return {
                "total_concatenations": 0,
                "cache_hits": 0,
                "cache_hit_rate_percent": 0,
                "avg_generation_time_ms": 0,
                "performance_improvement": "No requests yet",
                "directories": {
                    "segments": len(list(self.segments_dir.glob("*.mp3"))) if self.segments_dir.exists() else 0,
                    "client_names": len(list(self.client_names_dir.glob("*.mp3"))) if self.client_names_dir.exists() else 0,
                    "agent_names": len(list(self.agent_names_dir.glob("*.mp3"))) if self.agent_names_dir.exists() else 0,
                    "temp_files": len(list(self.temp_dir.glob("*.mp3"))) if self.temp_dir.exists() else 0,
                    "cached_files": len(list(self.cache_dir.glob("*.mp3"))) if self.cache_dir.exists() else 0
                }
            }
        
        avg_generation_time = self.generation_time_total / self.concatenations_count
        cache_hit_rate = (self.cache_hits / (self.concatenations_count + self.cache_hits)) * 100 if (self.concatenations_count + self.cache_hits) > 0 else 0
        
        return {
            "total_concatenations": self.concatenations_count,
            "cache_hits": self.cache_hits,
            "cache_hit_rate_percent": round(cache_hit_rate, 1),
            "avg_generation_time_ms": round(avg_generation_time, 1),
            "performance_improvement": f"{cache_hit_rate:.1f}% faster responses via caching",
            "directories": {
                "segments": len(list(self.segments_dir.glob("*.mp3"))) if self.segments_dir.exists() else 0,
                "client_names": len(list(self.client_names_dir.glob("*.mp3"))) if self.client_names_dir.exists() else 0,
                "agent_names": len(list(self.agent_names_dir.glob("*.mp3"))) if self.agent_names_dir.exists() else 0,
                "temp_files": len(list(self.temp_dir.glob("*.mp3"))) if self.temp_dir.exists() else 0,
                "cached_files": len(list(self.cache_dir.glob("*.mp3"))) if self.cache_dir.exists() else 0
            }
        }
    
    async def is_configured(self) -> bool:
        """Check if segmented audio service is properly configured"""
        try:
            # Check if segments directory exists and has files
            if not self.segments_dir.exists():
                logger.warning(f"Segments directory not found: {self.segments_dir}")
                return False
            
            # Check for essential segments based on your files
            essential_segments = ["greeting_start", "greeting_middle", "goodbye", "agent_intro_start", "agent_intro_middle"]
            missing_segments = []
            
            for segment in essential_segments:
                segment_file = self.segments_dir / f"{segment}.mp3"
                if not segment_file.exists():
                    missing_segments.append(segment)
            
            if missing_segments:
                logger.warning(f"Missing essential segments: {missing_segments}")
                return False
            
            # Check for ffmpeg
            try:
                process = await asyncio.create_subprocess_exec(
                    'ffmpeg', '-version',
                    stdout=asyncio.subprocess.PIPE,
                    stderr=asyncio.subprocess.PIPE
                )
                await process.communicate()
                ffmpeg_available = process.returncode == 0
            except Exception:
                ffmpeg_available = False
                logger.warning("FFmpeg not available")
            
            return ffmpeg_available
        
        except Exception as e:
            logger.error(f"Configuration check error: {e}")
            return False

# Global instance
segmented_audio_service = SegmentedAudioService()