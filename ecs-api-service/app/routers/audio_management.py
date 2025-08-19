from fastapi import APIRouter, HTTPException, BackgroundTasks
from fastapi.responses import JSONResponse
import boto3
import os
import asyncio
import logging
from pathlib import Path
from typing import Dict, Any, List
import subprocess
import sys

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

router = APIRouter(prefix="/audio", tags=["Audio Management"])

# S3 Configuration
S3_BUCKET_NAME = os.getenv("S3_BUCKET_AUDIO", "voice-agent-audio-testing")
S3_REGION = os.getenv("AWS_REGION", "us-east-1")

# Initialize S3 client (uses ECS task role automatically)
s3_client = boto3.client('s3', region_name=S3_REGION)

@router.post("/generate")
async def generate_audio_files(background_tasks: BackgroundTasks):
    """
    Generate all audio files locally
    """
    try:
        logger.info("🎵 Starting audio generation...")
        
        # Add to background tasks
        background_tasks.add_task(generate_audio_background)
        
        return JSONResponse(
            status_code=202,
            content={
                "message": "Audio generation started in background",
                "status": "processing"
            }
        )
    except Exception as e:
        logger.error(f"❌ Error starting audio generation: {e}")
        raise HTTPException(status_code=500, detail=str(e))

async def generate_audio_background():
    """
    Background task to generate audio files
    """
    try:
        logger.info("🎵 Running audio generation script...")
        
        # Run the audio generation script
        script_path = Path(__file__).parent.parent / "scripts" / "generate_segmented_audio.py"
        
        if not script_path.exists():
            logger.error(f"❌ Script not found: {script_path}")
            return
        
        # Run the script
        result = subprocess.run(
            [sys.executable, str(script_path)],
            capture_output=True,
            text=True,
            cwd=Path(__file__).parent.parent
        )
        
        if result.returncode == 0:
            logger.info("✅ Audio generation completed successfully")
            logger.info(f"Output: {result.stdout}")
        else:
            logger.error(f"❌ Audio generation failed: {result.stderr}")
            
    except Exception as e:
        logger.error(f"❌ Error in background audio generation: {e}")

@router.post("/upload-to-s3")
async def upload_audio_to_s3(background_tasks: BackgroundTasks):
    """
    Upload generated audio files to S3
    """
    try:
        logger.info("☁️ Starting S3 upload...")
        
        # Add to background tasks
        background_tasks.add_task(upload_audio_to_s3_background)
        
        return JSONResponse(
            status_code=202,
            content={
                "message": "S3 upload started in background",
                "status": "processing"
            }
        )
    except Exception as e:
        logger.error(f"❌ Error starting S3 upload: {e}")
        raise HTTPException(status_code=500, detail=str(e))

async def upload_audio_to_s3_background():
    """
    Background task to upload audio files to S3
    """
    try:
        audio_dir = Path(__file__).parent.parent / "audio-generation"
        
        if not audio_dir.exists():
            logger.error(f"❌ Audio directory not found: {audio_dir}")
            return
        
        logger.info(f"☁️ Uploading audio files from: {audio_dir}")
        
        # Upload all audio files recursively
        for file_path in audio_dir.rglob("*"):
            if file_path.is_file():
                # Calculate S3 key (relative path from audio-generation)
                relative_path = file_path.relative_to(audio_dir)
                s3_key = f"audio-files/{relative_path}"
                
                try:
                    # Upload file to S3
                    s3_client.upload_file(
                        str(file_path),
                        S3_BUCKET_NAME,
                        s3_key,
                        ExtraArgs={'ContentType': 'audio/wav'}
                    )
                    logger.info(f"✅ Uploaded: {s3_key}")
                except Exception as e:
                    logger.error(f"❌ Failed to upload {s3_key}: {e}")
        
        logger.info("✅ S3 upload completed")
        
    except Exception as e:
        logger.error(f"❌ Error in background S3 upload: {e}")

@router.post("/sync-from-s3")
async def sync_audio_from_s3(background_tasks: BackgroundTasks):
    """
    Download audio files from S3 to local cache
    """
    try:
        logger.info("📥 Starting S3 sync...")
        
        # Add to background tasks
        background_tasks.add_task(sync_audio_from_s3_background)
        
        return JSONResponse(
            status_code=202,
            content={
                "message": "S3 sync started in background",
                "status": "processing"
            }
        )
    except Exception as e:
        logger.error(f"❌ Error starting S3 sync: {e}")
        raise HTTPException(status_code=500, detail=str(e))

async def sync_audio_from_s3_background():
    """
    Background task to sync audio files from S3
    """
    try:
        audio_dir = Path(__file__).parent.parent / "audio-generation"
        audio_dir.mkdir(parents=True, exist_ok=True)
        
        logger.info(f"📥 Syncing audio files to: {audio_dir}")
        
        # List objects in S3 bucket
        try:
            paginator = s3_client.get_paginator('list_objects_v2')
            pages = paginator.paginate(Bucket=S3_BUCKET_NAME, Prefix='audio-files/')
            
            for page in pages:
                if 'Contents' in page:
                    for obj in page['Contents']:
                        s3_key = obj['Key']
                        
                        # Skip if it's a directory
                        if s3_key.endswith('/'):
                            continue
                        
                        # Calculate local file path
                        relative_path = s3_key.replace('audio-files/', '')
                        local_path = audio_dir / relative_path
                        
                        # Create directory if needed
                        local_path.parent.mkdir(parents=True, exist_ok=True)
                        
                        try:
                            # Download file from S3
                            s3_client.download_file(
                                S3_BUCKET_NAME,
                                s3_key,
                                str(local_path)
                            )
                            logger.info(f"✅ Downloaded: {relative_path}")
                        except Exception as e:
                            logger.error(f"❌ Failed to download {s3_key}: {e}")
            
            logger.info("✅ S3 sync completed")
            
        except Exception as e:
            logger.error(f"❌ S3 sync failed: {e}")
            
            # Provide helpful error information for common S3 permission issues
            if "AccessDenied" in str(e) or "not authorized" in str(e).lower():
                logger.error(f"❌ S3 Permission Error: The ECS task role needs the following IAM permissions:")
                logger.error(f"❌ - s3:ListBucket on resource: arn:aws:s3:::{S3_BUCKET_NAME}")
                logger.error(f"❌ - s3:GetObject on resource: arn:aws:s3:::{S3_BUCKET_NAME}/*")
                logger.error(f"❌ Current bucket: {S3_BUCKET_NAME}, Region: {S3_REGION}")
            elif "NoSuchBucket" in str(e):
                logger.error(f"❌ S3 Bucket Error: Bucket '{S3_BUCKET_NAME}' does not exist")
            elif "InvalidAccessKeyId" in str(e):
                logger.error(f"❌ AWS Credentials Error: Invalid or missing AWS credentials")
        
    except Exception as e:
        logger.error(f"❌ Error in background S3 sync: {e}")

@router.get("/status")
async def get_audio_status():
    """
    Get status of audio files (local and S3)
    """
    try:
        audio_dir = Path(__file__).parent.parent / "audio-generation"
        
        # Count local files
        local_files = []
        if audio_dir.exists():
            for file_path in audio_dir.rglob("*"):
                if file_path.is_file():
                    local_files.append(str(file_path.relative_to(audio_dir)))
        
        # Count S3 files
        s3_files = []
        s3_error = None
        try:
            paginator = s3_client.get_paginator('list_objects_v2')
            pages = paginator.paginate(Bucket=S3_BUCKET_NAME, Prefix='audio-files/')
            
            for page in pages:
                if 'Contents' in page:
                    for obj in page['Contents']:
                        if not obj['Key'].endswith('/'):
                            s3_files.append(obj['Key'].replace('audio-files/', ''))
        except Exception as e:
            s3_error = str(e)
            logger.warning(f"⚠️ Could not list S3 files: {e}")
            
            # Provide helpful error information for common S3 permission issues
            if "AccessDenied" in str(e) or "not authorized" in str(e).lower():
                logger.error(f"❌ S3 Permission Error: The ECS task role needs the following IAM permissions:")
                logger.error(f"❌ - s3:ListBucket on resource: arn:aws:s3:::{S3_BUCKET_NAME}")
                logger.error(f"❌ - s3:GetObject on resource: arn:aws:s3:::{S3_BUCKET_NAME}/*")
                logger.error(f"❌ - s3:PutObject on resource: arn:aws:s3:::{S3_BUCKET_NAME}/*")
                logger.error(f"❌ Current bucket: {S3_BUCKET_NAME}, Region: {S3_REGION}")
            elif "NoSuchBucket" in str(e):
                logger.error(f"❌ S3 Bucket Error: Bucket '{S3_BUCKET_NAME}' does not exist")
            elif "InvalidAccessKeyId" in str(e):
                logger.error(f"❌ AWS Credentials Error: Invalid or missing AWS credentials")
        
        # Get S3 audio service cache stats
        cache_stats = {}
        try:
            from services.s3_audio_service import s3_audio_service
            cache_stats = s3_audio_service.get_cache_stats()
        except Exception as e:
            logger.warning(f"⚠️ Could not get cache stats: {e}")
        
        return {
            "local_files_count": len(local_files),
            "s3_files_count": len(s3_files),
            "local_files": local_files[:10],  # Show first 10
            "s3_files": s3_files[:10],  # Show first 10
            "s3_bucket": S3_BUCKET_NAME,
            "s3_error": s3_error,  # Include S3 error if any
            "cache_stats": cache_stats
        }
        
    except Exception as e:
        logger.error(f"❌ Error getting audio status: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@router.post("/generate-and-upload")
async def generate_and_upload_audio(background_tasks: BackgroundTasks):
    """
    Generate audio files and upload to S3 in sequence
    """
    try:
        logger.info("🎵 Starting generate and upload process...")
        
        # Add to background tasks
        background_tasks.add_task(generate_and_upload_background)
        
        return JSONResponse(
            status_code=202,
            content={
                "message": "Generate and upload process started in background",
                "status": "processing"
            }
        )
    except Exception as e:
        logger.error(f"❌ Error starting generate and upload: {e}")
        raise HTTPException(status_code=500, detail=str(e))

async def generate_and_upload_background():
    """
    Background task to generate audio and upload to S3
    """
    try:
        # Step 1: Generate audio files
        logger.info("🎵 Step 1: Generating audio files...")
        await generate_audio_background()
        
        # Step 2: Upload to S3
        logger.info("☁️ Step 2: Uploading to S3...")
        await upload_audio_to_s3_background()
        
        logger.info("✅ Generate and upload process completed")
        
    except Exception as e:
        logger.error(f"❌ Error in generate and upload background task: {e}")

@router.post("/clear-cache")
async def clear_audio_cache():
    """
    Clear the S3 audio cache
    """
    try:
        from services.s3_audio_service import s3_audio_service
        s3_audio_service.clear_cache()
        
        return {
            "message": "Audio cache cleared successfully",
            "status": "success"
        }
        
    except Exception as e:
        logger.error(f"❌ Error clearing audio cache: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@router.get("/cache-stats")
async def get_cache_stats():
    """
    Get S3 audio cache statistics
    """
    try:
        from services.s3_audio_service import s3_audio_service
        stats = s3_audio_service.get_cache_stats()
        
        return {
            "cache_stats": stats,
            "status": "success"
        }
        
    except Exception as e:
        logger.error(f"❌ Error getting cache stats: {e}")
        raise HTTPException(status_code=500, detail=str(e))
