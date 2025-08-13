#!/usr/bin/env python3
"""
Generate segmented audio files using ElevenLabs API
Updated to use existing audio-generation directory structure
"""

import os
import json
import asyncio
import sys
import re
from pathlib import Path
import logging

# Add parent directory to path to import services
sys.path.append(str(Path(__file__).parent.parent))

# Load .env file from the correct location (root directory)
try:
    from dotenv import load_dotenv
    # Look for .env in multiple locations
    env_paths = [
        Path(__file__).parent.parent.parent / '.env',  # Root directory
        Path(__file__).parent.parent / '.env',         # ecs-api-service directory
        Path.cwd() / '.env'                            # Current working directory
    ]
    
    env_loaded = False
    for env_path in env_paths:
        if env_path.exists():
            load_dotenv(env_path)
            print(f"✅ Loaded .env from: {env_path}")
            env_loaded = True
            break
    
    if not env_loaded:
        print("⚠️ No .env file found in expected locations")
        
except ImportError:
    print("⚠️ python-dotenv not installed, using system environment variables")

from services.elevenlabs_client import elevenlabs_client
from shared.config.settings import settings

# Set up logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Get the app directory
APP_DIR = Path(__file__).parent.parent.resolve()

# Use your existing audio-generation directory structure
OUTPUT_DIR = APP_DIR / 'audio-generation'
SEGMENTS_DIR = OUTPUT_DIR / 'segments'
NAMES_DIR = OUTPUT_DIR / 'names'
CLIENT_NAMES_DIR = NAMES_DIR / 'clients'
AGENT_NAMES_DIR = NAMES_DIR / 'agents'

def ensure_directories_exist():
    """Ensure all required directories exist"""
    directories = [OUTPUT_DIR, SEGMENTS_DIR, NAMES_DIR, CLIENT_NAMES_DIR, AGENT_NAMES_DIR]
    for directory in directories:
        directory.mkdir(parents=True, exist_ok=True)
        logger.info(f"✅ Directory ensured: {directory}")

def convert_phone_to_natural_speech(phone_number):
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

# AAG Script Segments with email scheduling mentions
SCRIPT_SEGMENTS = {
    # Main Greeting Segments
    "greeting_start": "Hello ",
    "greeting_middle": ", Alex here from Altruis Advisor Group. We've helped you with your health insurance needs in the past and I just wanted to reach out to see if we can be of service to you this year during Open Enrollment? A simple Yes or No is fine, and remember, our services are completely free of charge.",
    
    # Agent Introduction Segments (with email mention)
    "agent_intro_start": "Wonderful! I see that ",
    "agent_intro_middle": " was the last agent who helped you. I'd love to connect you with them again. We'll send you an email shortly with their available time slots, and you can choose what works best for your schedule. Does that sound good?",
    
    # Not Interested Flow Segments
    "not_interested_start": "No problem at all! Would you like to continue receiving occasional health insurance updates from our team? We promise to keep them informative and not overwhelming. A simple yes or no will do!",
    
    # Schedule Confirmation Segments (with email mention)
    "schedule_start": "Perfect! You'll receive an email within the next few minutes with ",
    "schedule_middle": "'s calendar. Simply click on the time that works best for you, and it will automatically schedule your 15-minute discovery call. Thank you so much for your time today, and have a wonderful day!",
    
    # No Schedule Flow Segments
    "no_schedule_start": "I completely understand. ",
    "no_schedule_middle": " will make a note of our conversation, and we'll be here whenever you're ready to explore your options. Thank you for your time today. Have a wonderful day!",
    
    # DNC Flow (Complete - no names needed)
    "dnc_confirmation": "I completely understand. I'll make sure you're removed from all future calls right away. You'll receive a confirmation email shortly. Our contact information will be in that email if you ever change your mind - remember, our service is always free. Have a wonderful day!",
    
    # Keep Communications (Complete - no names needed)
    "keep_communications": "Great! We'll keep you in the loop with helpful health insurance updates throughout the year. If you ever need assistance, just reach out - we're always here to help, and our service is always free. Thank you for your time today!",
    
    # Generic Responses (Complete - no names needed)
    "goodbye": "Thank you for your time today. Have a wonderful day!",
    "clarification": "I apologize, I didn't quite catch that. Would you be interested in reviewing your health insurance options for this year's open enrollment? A simple yes or no would be great.",
    "error": "I apologize, I'm having some technical difficulties. Thank you for your patience.",
    
    # Voicemail Script Segments (for concatenation) - Updated with natural phone number
    "voicemail_start": "Hello ",
    "voicemail_middle": f", Alex here from Altruis Advisor Group. We've helped with your health insurance needs in the past and we wanted to reach out to see if we could be of assistance this year during Open Enrollment. There have been a number of important changes to the Affordable Care Act that may impact your situation - so it may make sense to do a quick policy review. As always, our services are completely free of charge - if you'd like to review your policy please call us at {convert_phone_to_natural_speech('833.227.8500')}. We look forward to hearing from you - take care!"
}

# Additional client names to generate (you already have many)
ADDITIONAL_CLIENT_NAMES = [
    "Joseph", "Thomas", "Charles", "Mary", "Richard", "Kenneth", 
    "Steven", "Andrew", "Brian", "George", "Edward", "Ronald"
]

# Check which segments are missing
def check_missing_segments():
    """Check which segments need to be generated"""
    missing_segments = []
    existing_segments = []
    
    for segment_name in SCRIPT_SEGMENTS.keys():
        filepath = SEGMENTS_DIR / f"{segment_name}.mp3"
        if filepath.exists():
            existing_segments.append(segment_name)
        else:
            missing_segments.append(segment_name)
    
    return existing_segments, missing_segments

# Check which names are missing
def check_missing_names():
    """Check which names need to be generated"""
    missing_clients = []
    missing_agents = []
    
    # Check client names
    for name in ADDITIONAL_CLIENT_NAMES:
        filepath = CLIENT_NAMES_DIR / f"{name.lower()}.mp3"
        if not filepath.exists():
            missing_clients.append(name)
    
    # You already have agent names, but check anyway
    existing_agents = ["anthony_fracchia", "hineth_pettway", "india_watson", 
                      "keith_braswell", "lashawn_boyd"]
    
    return missing_clients, existing_agents

async def generate_missing_audio():
    """Generate only missing audio files"""
    
    logger.info("🔍 Checking for missing audio files...")
    
    # Check what we need to generate
    existing_segments, missing_segments = check_missing_segments()
    missing_clients, existing_agents = check_missing_names()
    
    logger.info(f"✅ Existing segments: {len(existing_segments)}")
    logger.info(f"❌ Missing segments: {len(missing_segments)}")
    logger.info(f"❌ Missing client names: {len(missing_clients)}")
    
    # Generate missing segments
    if missing_segments:
        logger.info(f"\n🎵 Generating {len(missing_segments)} missing segments...")
        for segment_name in missing_segments:
            text = SCRIPT_SEGMENTS[segment_name]
            logger.info(f"Generating: {segment_name}")
            
            result = await elevenlabs_client.generate_speech(text)
            
            if result.get("success") and result.get("audio_data"):
                filepath = SEGMENTS_DIR / f"{segment_name}.mp3"
                with open(filepath, "wb") as f:
                    f.write(result["audio_data"])
                logger.info(f"✅ Generated: {segment_name}")
            else:
                logger.error(f"❌ Failed: {segment_name}")
            
            # Small delay between requests
            await asyncio.sleep(0.5)
    
    # Generate missing client names
    if missing_clients:
        logger.info(f"\n👥 Generating {len(missing_clients)} missing client names...")
        for name in missing_clients:
            logger.info(f"Generating: {name}")
            
            result = await elevenlabs_client.generate_speech(name)
            
            if result.get("success") and result.get("audio_data"):
                filepath = CLIENT_NAMES_DIR / f"{name.lower()}.mp3"
                with open(filepath, "wb") as f:
                    f.write(result["audio_data"])
                logger.info(f"✅ Generated: {name}")
            else:
                logger.error(f"❌ Failed: {name}")
            
            # Small delay between requests
            await asyncio.sleep(0.5)
    
    # Update manifest
    await update_manifest()
    
    logger.info("\n✅ Audio generation complete!")

async def update_manifest():
    """Update the segments manifest"""
    
    # Get all existing files
    segments = [f.stem for f in SEGMENTS_DIR.glob("*.mp3")]
    client_names = [f.stem for f in CLIENT_NAMES_DIR.glob("*.mp3")]
    agent_names = [f.stem for f in AGENT_NAMES_DIR.glob("*.mp3")]
    
    manifest = {
        "last_updated": datetime.utcnow().isoformat(),
        "segments": {
            "count": len(segments),
            "files": sorted(segments)
        },
        "client_names": {
            "count": len(client_names),
            "files": sorted(client_names)
        },
        "agent_names": {
            "count": len(agent_names),
            "files": sorted(agent_names)
        },
        "concatenation_templates": {
            "greeting": ["greeting_start", "[CLIENT_NAME]", "greeting_middle"],
            "agent_intro": ["agent_intro_start", "[AGENT_NAME]", "agent_intro_middle"],
            "schedule": ["schedule_start", "[AGENT_NAME]", "schedule_middle"],
            "no_schedule": ["no_schedule_start", "[AGENT_NAME]", "no_schedule_middle"],
            "voicemail": ["voicemail_start", "[CLIENT_NAME]", "voicemail_middle"]
        }
    }
    
    manifest_path = OUTPUT_DIR / 'segments_manifest.json'
    with open(manifest_path, 'w') as f:
        json.dump(manifest, f, indent=2)
    
    logger.info(f"📄 Manifest updated: {manifest_path}")

async def main():
    """Main function"""
    
    # Ensure directories exist before generating
    ensure_directories_exist()
    
    # Check if ElevenLabs is configured
    if not elevenlabs_client.is_configured():
        logger.error("❌ ElevenLabs API key not configured in settings!")
        logger.error("Please set ELEVENLABS_API_KEY in your .env file")
        return
    
    await generate_missing_audio()

if __name__ == '__main__':
    # Import datetime for manifest
    from datetime import datetime
    
    asyncio.run(main())