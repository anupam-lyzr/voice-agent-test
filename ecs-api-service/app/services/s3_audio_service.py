"""
S3 Audio Service - Production Ready
Handles loading audio files from S3 in production environment
"""

import boto3
import logging
import os
import tempfile
from pathlib import Path
from typing import Optional, Dict, Any
import hashlib

logger = logging.getLogger(__name__)

class S3AudioService:
    """Service for loading audio files from S3 in production"""
    
    def __init__(self):
        self.s3_bucket = os.getenv("S3_BUCKET_AUDIO", "voice-agent-audio-testing")
        self.s3_region = os.getenv("AWS_REGION", "us-east-1")
        self.environment = os.getenv("ENVIRONMENT", "development")
        
        # Initialize S3 client (uses ECS task role automatically)
        self.s3_client = boto3.client('s3', region_name=self.s3_region)
        
        # Local cache directory for downloaded files
        self.cache_dir = Path("/tmp/audio-cache")
        self.cache_dir.mkdir(parents=True, exist_ok=True)
        
        # Track downloaded files to avoid re-downloading
        self._downloaded_files = set()
        
        logger.info(f"🎵 S3 Audio Service initialized for bucket: {self.s3_bucket}")
        logger.info(f"🌍 Environment: {self.environment}")
    
    def is_production(self) -> bool:
        """Check if we're in production environment"""
        # Check environment variable
        if self.environment.lower() in ["production", "prod"]:
            return True
        
        # Also check if S3 bucket is configured (fallback detection)
        if self.s3_bucket and self.s3_bucket != "voice-agent-audio-testing":
            return True
        
        return False
    
    async def get_audio_file_path(self, audio_type: str, filename: str) -> Optional[Path]:
        """
        Get audio file path - from S3 in production, local in development
        
        Args:
            audio_type: Type of audio (segments, names/clients, names/agents)
            filename: Name of the audio file
            
        Returns:
            Path to the audio file or None if not found
        """
        if not self.is_production():
            # In development, use local files
            return self._get_local_audio_path(audio_type, filename)
        
        # In production, use S3
        return await self._get_s3_audio_path(audio_type, filename)
    
    def _get_local_audio_path(self, audio_type: str, filename: str) -> Optional[Path]:
        """Get local audio file path"""
        try:
            # Try different possible local paths
            possible_paths = [
                Path("audio-generation") / audio_type / filename,
                Path("app/audio-generation") / audio_type / filename,
                Path("static/audio") / audio_type / filename
            ]
            
            for path in possible_paths:
                if path.exists():
                    logger.debug(f"📁 Found local audio file: {path}")
                    return path
            
            logger.warning(f"⚠️ Local audio file not found: {audio_type}/{filename}")
            return None
            
        except Exception as e:
            logger.error(f"❌ Error getting local audio path: {e}")
            return None
    
    async def _get_s3_audio_path(self, audio_type: str, filename: str) -> Optional[Path]:
        """Get S3 audio file path (download if needed)"""
        try:
            # Create S3 key
            s3_key = f"audio-files/{audio_type}/{filename}"
            
            # Check if already downloaded
            cache_key = f"{audio_type}_{filename}"
            if cache_key in self._downloaded_files:
                cached_path = self.cache_dir / audio_type / filename
                if cached_path.exists():
                    logger.debug(f"📁 Using cached S3 audio file: {cached_path}")
                    return cached_path
            
            # Download from S3
            local_path = await self._download_from_s3(s3_key, audio_type, filename)
            if local_path:
                self._downloaded_files.add(cache_key)
                logger.info(f"✅ Downloaded audio from S3: {s3_key} -> {local_path}")
                return local_path
            
            logger.warning(f"⚠️ S3 audio file not found: {s3_key}")
            return None
            
        except Exception as e:
            logger.error(f"❌ Error getting S3 audio path: {e}")
            return None
    
    async def _download_from_s3(self, s3_key: str, audio_type: str, filename: str) -> Optional[Path]:
        """Download audio file from S3"""
        try:
            # Create local directory structure
            local_dir = self.cache_dir / audio_type
            local_dir.mkdir(parents=True, exist_ok=True)
            
            local_path = local_dir / filename
            
            # Download file from S3
            self.s3_client.download_file(
                self.s3_bucket,
                s3_key,
                str(local_path)
            )
            
            return local_path
            
        except Exception as e:
            logger.error(f"❌ Failed to download from S3: {s3_key} - {e}")
            # Add more detailed error information for debugging
            if hasattr(e, 'response') and hasattr(e.response, 'Error'):
                error_code = e.response['Error'].get('Code', 'Unknown')
                error_message = e.response['Error'].get('Message', 'Unknown error')
                logger.error(f"❌ S3 Error Code: {error_code}, Message: {error_message}")
            logger.error(f"❌ S3 Bucket: {self.s3_bucket}, Region: {getattr(settings, 'aws_region', 'not_set')}")
            return None
    
    async def get_audio_files_batch(self, audio_files: list) -> Dict[str, Optional[Path]]:
        """
        Get multiple audio files efficiently
        
        Args:
            audio_files: List of tuples (audio_type, filename)
            
        Returns:
            Dict mapping (audio_type, filename) to file path
        """
        results = {}
        
        for audio_type, filename in audio_files:
            path = await self.get_audio_file_path(audio_type, filename)
            results[f"{audio_type}/{filename}"] = path
        
        return results
    
    async def preload_audio_files(self, audio_files: list) -> Dict[str, bool]:
        """
        Preload audio files for better performance
        
        Args:
            audio_files: List of tuples (audio_type, filename)
            
        Returns:
            Dict mapping (audio_type, filename) to success status
        """
        results = {}
        
        for audio_type, filename in audio_files:
            try:
                path = await self.get_audio_file_path(audio_type, filename)
                results[f"{audio_type}/{filename}"] = path is not None
            except Exception as e:
                logger.error(f"❌ Failed to preload {audio_type}/{filename}: {e}")
                results[f"{audio_type}/{filename}"] = False
        
        return results
    
    def clear_cache(self):
        """Clear the local cache"""
        try:
            import shutil
            shutil.rmtree(self.cache_dir)
            self.cache_dir.mkdir(parents=True, exist_ok=True)
            self._downloaded_files.clear()
            logger.info("🧹 Audio cache cleared")
        except Exception as e:
            logger.error(f"❌ Error clearing cache: {e}")
    
    def get_cache_stats(self) -> Dict[str, Any]:
        """Get cache statistics"""
        try:
            cache_size = sum(f.stat().st_size for f in self.cache_dir.rglob('*') if f.is_file())
            file_count = len(list(self.cache_dir.rglob('*')))
            
            return {
                "cache_size_bytes": cache_size,
                "cache_size_mb": round(cache_size / (1024 * 1024), 2),
                "file_count": file_count,
                "downloaded_files": len(self._downloaded_files),
                "cache_directory": str(self.cache_dir)
            }
        except Exception as e:
            logger.error(f"❌ Error getting cache stats: {e}")
            return {"error": str(e)}

# Global instance
s3_audio_service = S3AudioService()
