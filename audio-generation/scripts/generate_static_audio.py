#!/usr/bin/env python3
"""
Generate static audio files using ElevenLabs API
"""

import os
import json
import asyncio
import httpx
from pathlib import Path

# Configuration
ELEVENLABS_API_KEY = os.getenv('ELEVENLABS_API_KEY')
VOICE_ID = os.getenv('VOICE_ID', 'pNInz6obpgDQGcFmaJgB')  # Adam voice
OUTPUT_DIR = Path('audio-generation/generated_audio')
CONTENT_DIR = Path('audio-generation/audio_content')

# Voice settings for natural speech
VOICE_SETTINGS = {
    "stability": 0.35,
    "similarity_boost": 0.75,
    "style": 0.45,
    "use_speaker_boost": True
}

async def generate_audio_file(text: str, filename: str):
    """Generate audio file using ElevenLabs API"""
    
    if not ELEVENLABS_API_KEY or ELEVENLABS_API_KEY == 'your_elevenlabs_api_key':
        print(f"⚠️  ElevenLabs API key not configured, skipping {filename}")
        return False
    
    url = f"https://api.elevenlabs.io/v1/text-to-speech/{VOICE_ID}"
    
    headers = {
        "Accept": "audio/mpeg",
        "Content-Type": "application/json", 
        "xi-api-key": ELEVENLABS_API_KEY
    }
    
    data = {
        "text": text,
        "model_id": "eleven_turbo_v2_5",
        "voice_settings": VOICE_SETTINGS,
        "output_format": "mp3_22050_32"
    }
    
    try:
        async with httpx.AsyncClient(timeout=30.0) as client:
            response = await client.post(url, headers=headers, json=data)
            
            if response.status_code == 200:
                # Save audio file
                output_path = OUTPUT_DIR / filename
                with open(output_path, 'wb') as f:
                    f.write(response.content)
                
                print(f"✅ Generated: {filename} ({len(response.content)} bytes)")
                return True
            else:
                print(f"❌ Failed to generate {filename}: {response.status_code}")
                return False
                
    except Exception as e:
        print(f"❌ Error generating {filename}: {str(e)}")
        return False

async def main():
    """Generate all static audio files"""
    
    print("🎵 Generating static audio files...")
    
    # Create output directory
    OUTPUT_DIR.mkdir(exist_ok=True)
    
    # Audio files to generate
    audio_files = {
        'greeting.mp3': 'greeting.txt',
        'interested_followup.mp3': 'interested_followup.txt',
        'not_interested_followup.mp3': 'not_interested_followup.txt',
        'schedule_morning.mp3': 'schedule_morning.txt',
        'schedule_afternoon.mp3': 'schedule_afternoon.txt',
        'dnc_confirmation.mp3': 'dnc_confirmation.txt',
        'goodbye.mp3': 'goodbye.txt'
    }
    
    # Track results
    successful = 0
    failed = 0
    
    # Generate each audio file
    for audio_filename, text_filename in audio_files.items():
        text_path = CONTENT_DIR / text_filename
        
        if not text_path.exists():
            print(f"⚠️  Text file not found: {text_path}")
            failed += 1
            continue
        
        # Read text content
        with open(text_path, 'r') as f:
            text = f.read().strip()
        
        # Generate audio
        success = await generate_audio_file(text, audio_filename)
        
        if success:
            successful += 1
        else:
            failed += 1
        
        # Small delay between requests
        await asyncio.sleep(1)
    
    # Create manifest file
    manifest = {
        'generated_at': str(asyncio.get_event_loop().time()),
        'voice_id': VOICE_ID,
        'voice_settings': VOICE_SETTINGS,
        'files': list(audio_files.keys()),
        'successful': successful,
        'failed': failed
    }
    
    manifest_path = OUTPUT_DIR / 'manifest.json'
    with open(manifest_path, 'w') as f:
        json.dump(manifest, f, indent=2)
    
    print(f"\n📊 Generation Summary:")
    print(f"✅ Successful: {successful}")
    print(f"❌ Failed: {failed}")
    print(f"📄 Manifest: {manifest_path}")

if __name__ == '__main__':
    asyncio.run(main())
