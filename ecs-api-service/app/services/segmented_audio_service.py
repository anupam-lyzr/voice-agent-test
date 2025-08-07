"""
Segmented Audio Service - Production Ready
Handles real-time audio concatenation for personalized responses
"""

import asyncio
import hashlib
import logging
import os
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
        
        # Performance tracking
        self.concatenations_count = 0
        self.cache_hits = 0
        self.generation_time_total = 0.0
        
        # Updated templates based on your audio files
        self.templates = {
            "greeting": {
                "segments": ["greeting_start", "[CLIENT_NAME]", "greeting_middle"],
                "description": "Personalized greeting with client name"
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
                "description": "Clarification request"
            }
        }
    
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
        
        try:
            # Check if template exists
            if template_name not in self.templates:
                logger.error(f"❌ Unknown template: {template_name}")
                return {"success": False, "error": f"Unknown template: {template_name}"}
            
            template = self.templates[template_name]
            
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
            audio_url = await self._concatenate_segments(
                template["segments"], 
                client_name, 
                agent_name,
                cache_key
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
        cache_key: str
    ) -> Optional[str]:
        """Concatenate audio segments with names"""
        
        try:
            # Collect audio files to concatenate
            audio_files = []
            
            for segment in segments:
                if segment == "[CLIENT_NAME]" and client_name:
                    # Get client name audio
                    client_file = await self._get_name_audio(client_name, "client")
                    if client_file:
                        audio_files.append(client_file)
                    else:
                        logger.warning(f"⚠️ Client name audio not found: {client_name}")
                        return None
                
                elif segment == "[AGENT_NAME]" and agent_name:
                    # Get agent name audio
                    agent_file = await self._get_name_audio(agent_name, "agent")
                    if agent_file:
                        audio_files.append(agent_file)
                    else:
                        logger.warning(f"⚠️ Agent name audio not found: {agent_name}")
                        return None
                
                else:
                    # Get segment audio
                    segment_file = self.segments_dir / f"{segment}.mp3"
                    if segment_file.exists():
                        audio_files.append(str(segment_file))
                    else:
                        logger.error(f"❌ Segment not found: {segment}")
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
    
    async def _get_name_audio(self, name: str, name_type: str) -> Optional[str]:
        """Get audio file for a name (client or agent)"""
        
        try:
            if name_type == "client":
                # Look for client name audio - try exact match first
                name_file = self.client_names_dir / f"{name.lower()}.mp3"
                
                if not name_file.exists():
                    # Try first name only
                    first_name = name.split()[0].lower()
                    name_file = self.client_names_dir / f"{first_name}.mp3"
                
                if name_file.exists():
                    return str(name_file)
                else:
                    # Generate on-demand if not found
                    logger.info(f"🔄 Generating missing client name: {name}")
                    return await self._generate_name_audio(name, "client")
            
            elif name_type == "agent":
                # Look for agent name audio - handle your specific agent names
                agent_filename = name.lower().replace(' ', '_').replace('.', '')
                name_file = self.agent_names_dir / f"{agent_filename}.mp3"
                
                if name_file.exists():
                    return str(name_file)
                else:
                    # Generate on-demand if not found
                    logger.info(f"🔄 Generating missing agent name: {name}")
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
            "greeting": f"Hello {client_name or '[NAME]'}, Alex here from Altruis Advisor Group. We've helped you with your health insurance needs in the past and I just wanted to reach out to see if we can be of service to you this year during Open Enrollment? A simple Yes or No is fine, and remember, our services are completely free of charge.",
            
            "agent_intro": f"Great, looks like {agent_name or '[AGENT]'} was the last agent you worked with here at Altruis. Would you like to schedule a quick 15-minute discovery call with them to get reacquainted? A simple Yes or No will do!",
            
            "schedule_confirmation": f"Perfect! I'll send you an email shortly with {agent_name}'s available time slots. You can review the calendar and choose a time that works best for your schedule. Thank you so much for your time today, and have a wonderful day!",
            
            "no_schedule_followup": f"No problem, {agent_name or '[AGENT]'} will reach out to you and the two of you can work together to determine the best next steps. We look forward to servicing you, have a wonderful day!",
            
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