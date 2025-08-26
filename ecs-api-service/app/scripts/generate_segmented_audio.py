"""
Enhanced Segmented Audio Generation Script - Non-Medicare Support
Generates pre-segmented audio for both Medicare and Non-Medicare clients
"""

import asyncio
import json
import logging
import os
import sys
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Set

# Add the parent directory to Python path so we can import from services
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

# Load environment variables from .env file in the root directory
from dotenv import load_dotenv
root_dir = os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))
env_path = os.path.join(root_dir, '.env')
load_dotenv(env_path)

# Import your services
from services.elevenlabs_client import elevenlabs_client

logger = logging.getLogger(__name__)

# Directory setup - Generate in the app directory, not scripts directory
# Get the app directory (parent of scripts)
SCRIPT_DIR = Path(__file__).parent
APP_DIR = SCRIPT_DIR.parent
OUTPUT_DIR = APP_DIR / "audio-generation"
SEGMENTS_DIR = OUTPUT_DIR / "segments"
CLIENT_NAMES_DIR = OUTPUT_DIR / "names" / "clients"
AGENT_NAMES_DIR = OUTPUT_DIR / "names" / "agents"

def ensure_directories_exist():
    """Create necessary directories"""
    logger.info(f"🔧 Creating directories in: {OUTPUT_DIR}")
    SEGMENTS_DIR.mkdir(parents=True, exist_ok=True)
    CLIENT_NAMES_DIR.mkdir(parents=True, exist_ok=True)
    AGENT_NAMES_DIR.mkdir(parents=True, exist_ok=True)
    logger.info(f"✅ Created: {SEGMENTS_DIR}")
    logger.info(f"✅ Created: {CLIENT_NAMES_DIR}")
    logger.info(f"✅ Created: {AGENT_NAMES_DIR}")

def convert_phone_to_natural_speech(phone: str) -> str:
    """Convert phone number to natural speech format"""
    if phone == "833.227.8500":
        return "8-3-3, 2-2-7, 8-5-0-0"
    return phone

# UPDATED SCRIPT SEGMENTS - Now includes Non-Medicare variants
SCRIPT_SEGMENTS = {
    # HELLO SEGMENT (for natural flow with client names)
    "hello": "Hello",
    
    # NON-MEDICARE GREETING SEGMENTS (New script)
    "non_medicare_greeting_middle": ", Alex calling on behalf of Anthony Fracchia and Altruis Advisor Group, we've helped you with your health insurance needs in the past and I'm reaching out to see if we can be of service to you this year during Open Enrollment? A simple 'Yes' or 'No' is fine, and remember, our services are completely free of charge.",
    
    # MEDICARE GREETING SEGMENTS (Original script)
    "medicare_greeting_middle": ", this is Alex from Altruis Advisor Group. We've helped you with your health insurance needs in the past and I just wanted to reach out to see if we can be of service to you this year during Open Enrollment? A simple Yes or No is fine, and remember, our services are completely free of charge.",
    
    # DEFAULT/FALLBACK GREETING (for unknown client types)
    "default_greeting_middle": ", this is Alex from Altruis Advisor Group. We've helped you with your insurance needs in the past and I just wanted to reach out to see if we can be of service to you this year during Open Enrollment? A simple Yes or No is fine, and remember, our services are completely free of charge.",
    
    # AGENT INTRODUCTION SEGMENTS (shared across all client types)
    "agent_intro_start": "Great, looks like ",
    "agent_intro_middle": " was the last agent you worked with here at Altruis. Would you like to schedule a quick 15-minute discovery call with them to get reacquainted? A simple Yes or No will do!",
    
    # SCHEDULE CONFIRMATION SEGMENTS (shared)
    "schedule_start": "Perfect! I'll send you an email shortly with ",
    "schedule_middle": "available time slots. You can review the calendar and choose a time that works best for your schedule. Thank you so much for your time today, and have a wonderful day!",
    
    # NO SCHEDULE FOLLOW-UP SEGMENTS (shared)
    "no_schedule_start": "No problem, ",
    "no_schedule_middle": " will reach out to you and the two of you can work together to determine the best next steps. We look forward to servicing you, have a wonderful day!",
    
    # DNC CONFIRMATION (shared)
    "dnc_confirmation": "Understood, we will make sure you are removed from all future communications and send you a confirmation email once that is done. If you'd like to connect with one of our insurance experts in the future please feel free to reach out — we are always here to help and our service is always free of charge. Have a wonderful day!",
    
    # KEEP COMMUNICATIONS (shared)
    "keep_communications": "Great! We'll keep you in the loop with helpful health insurance updates throughout the year. If you ever need assistance, just reach out - we're always here to help, and our service is always free. Thank you for your time today!",
    
    # NOT INTERESTED START (shared)
    "not_interested_start": "No problem, would you like to continue receiving general health insurance communications from our team? Again, a simple Yes or No will do!",
    
    # VOICEMAIL SEGMENTS - Non-Medicare version (Updated)
    "voicemail_start": "Hello",
    "non_medicare_voicemail_middle": f", Alex calling on behalf of Anthony Fracchia and Altruis Advisor Group. We've helped with your health insurance needs in the past and we wanted to reach out to see if we could be of assistance this year during Open Enrollment. There have been a number of important changes to the Affordable Care Act that may impact your situation - so it may make sense to do a quick policy review. As always, our services are completely free of charge - if you'd like to review your policy please call us at {convert_phone_to_natural_speech('833.227.8500')}. We look forward to hearing from you - take care!",
    
    # VOICEMAIL SEGMENTS - Medicare version (Updated)
    "medicare_voicemail_middle": f", Alex here from Altruis Advisor Group. We've helped with your health insurance needs in the past and we wanted to reach out to see if we could be of assistance this year during Open Enrollment. There have been a number of important changes to the Affordable Care Act that may impact your situation - so it may make sense to do a quick policy review. As always, our services are completely free of charge - if you'd like to review your policy please call us at {convert_phone_to_natural_speech('833.227.8500')}. We look forward to hearing from you - take care!",
    
    # DEFAULT VOICEMAIL (Updated)
    "default_voicemail_middle": f", Alex here from Altruis Advisor Group. We've helped with your health insurance needs in the past and we wanted to reach out to see if we could be of assistance this year during Open Enrollment. There have been a number of important changes to the Affordable Care Act that may impact your situation - so it may make sense to do a quick policy review. As always, our services are completely free of charge - if you'd like to review your policy please call us at {convert_phone_to_natural_speech('833.227.8500')}. We look forward to hearing from you - take care!",
    
    # STATIC RESPONSES (no concatenation needed)
    "goodbye": "Thank you for your time today. Have a wonderful day!",
    "clarification": "I want to make sure I understand correctly. Can we help service you this year during Open Enrollment? Please say Yes if you're interested, or No if you're not interested.",
    "error": "I apologize, I'm having some technical difficulties. Please call us back at 8-3-3, 2-2-7, 8-5-0-0.",
    
    # CLARIFYING QUESTIONS RESPONSES (new for better handling)
    "identity_clarification": "I'm Alex calling from Altruis Advisor Group. We're a health insurance agency that has helped you with your coverage in the past. We're reaching out to see if we can assist you during this year's Open Enrollment period. Are you interested in reviewing your options?",
    
    "ai_clarification": "I'm Alex, a digital assistant from Altruis Advisor Group. I'm here to help connect you with our team regarding your health insurance options during Open Enrollment. We've worked with you before and wanted to see if we can be of service again this year. Are you interested?",
    
    "memory_clarification": "I understand, sometimes it's been a while since we last spoke. You worked with our team here at Altruis Advisor Group for your health insurance needs. We're reaching out because Open Enrollment is here, and we wanted to see if we can help you review your options again this year. Are you interested?",
    
    "repeat_response": "Of course! I'm Alex from Altruis Advisor Group. We've helped you with health insurance before, and I'm calling to see if we can assist you during Open Enrollment this year. Are you interested in reviewing your options? A simple yes or no is fine.",
    
    "confusion_clarification": "Let me clarify. I'm Alex from Altruis Advisor Group, a health insurance agency. We're calling because it's Open Enrollment season and we wanted to see if you'd like help reviewing your health insurance options. We've assisted you before. Would you be interested? Just yes or no is fine.",
    
    # NO SPEECH HANDLING SCRIPTS
    "no_speech_first": "I'm sorry, I can't seem to hear you clearly. If you said something, could you please speak a bit louder? I'm here to help.",
    "no_speech_second": "I'm still having trouble hearing you. If you're there, please try speaking directly into your phone. Are you interested in reviewing your health insurance options?",
    "no_speech_final": "I apologize, but I'm having difficulty hearing your response. If you'd like to speak with someone, please call us back at 8-3-3, 2-2-7, 8-5-0-0. Thank you and have a great day.",
    
    # NEW: Additional response categories from updated voice processor
    "lyzr_delay_filler": "That's a great question, let me make sure I give you the most accurate information.",
    "interruption_acknowledgment": "Of course, I'm here to help. What would you like to know?",
    "busy_call_back": "No problem at all! I'll call you back at a better time. Have a great day!",
    "silence_detection": "I'm sorry, I didn't hear anything. Did you say something?"
}

# AGENT NAMES (from the Excel data)
AGENT_NAMES = [
    "Anthony Fracchia",
    "Hineth Pettway", 
    "India Watson",
    "Keith Braswell",
    "LaShawn Boyd"
]

# COMMON CLIENT NAMES (from Excel analysis + additional)
COMMON_CLIENT_NAMES = [
    # From Excel file analysis
    "Lori", "Stephen", "Maryellen", "Rhonda", "Donna", "Zein", "Caroline", 
    "Randa", "Edward", "Billie", "Jason", "Brian", "Heather", "Khitam",
    
    # Additional common names
    "Michael", "Christopher", "Matthew", "Anthony", "Mark", "Donald", "Steven",
    "Paul", "Andrew", "Joshua", "Kenneth", "Kevin", "Brian", "George",
    "Timothy", "Ronald", "Jason", "Edward", "Jeffrey", "Ryan", "Jacob",
    "Gary", "Nicholas", "Eric", "Jonathan", "Stephen", "Larry", "Justin",
    "Scott", "Brandon", "Benjamin", "Samuel", "Gregory", "Alexander", "Patrick",
    "Jack", "Dennis", "Jerry", "Tyler", "Aaron", "Jose", "Henry", "Adam",
    "Douglas", "Nathan", "Peter", "Zachary", "Kyle", "Noah", "Alan",
    
    # Female names
    "Mary", "Patricia", "Jennifer", "Linda", "Elizabeth", "Barbara", "Susan",
    "Jessica", "Sarah", "Karen", "Nancy", "Lisa", "Betty", "Helen", "Sandra",
    "Donna", "Carol", "Ruth", "Sharon", "Michelle", "Laura", "Sarah", "Kimberly",
    "Deborah", "Dorothy", "Lisa", "Nancy", "Karen", "Betty", "Helen", "Sandra",
    "Margaret", "Maria", "Carol", "Ruth", "Sharon", "Michelle", "Laura", "Sarah"
]

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

def check_missing_names():
    """Check which names need to be generated"""
    missing_clients = []
    missing_agents = []
    
    # Check client names
    for name in COMMON_CLIENT_NAMES:
        filepath = CLIENT_NAMES_DIR / f"{name.lower()}.mp3"
        if not filepath.exists():
            missing_clients.append(name)
    
    # Check agent names
    for name in AGENT_NAMES:
        filename = name.lower().replace(' ', '_').replace('.', '')
        filepath = AGENT_NAMES_DIR / f"{filename}.mp3"
        if not filepath.exists():
            missing_agents.append(name)
    
    return missing_clients, missing_agents

async def generate_missing_audio():
    """Generate only missing audio files"""
    
    logger.info("🔍 Checking for missing audio files...")
    
    # Check what we need to generate
    existing_segments, missing_segments = check_missing_segments()
    missing_clients, missing_agents = check_missing_names()
    
    logger.info(f"✅ Existing segments: {len(existing_segments)}")
    logger.info(f"❌ Missing segments: {len(missing_segments)}")
    logger.info(f"❌ Missing client names: {len(missing_clients)}")
    logger.info(f"❌ Missing agent names: {len(missing_agents)}")
    
    total_to_generate = len(missing_segments) + len(missing_clients) + len(missing_agents)
    
    if total_to_generate == 0:
        logger.info("✅ All audio files already exist!")
        await update_manifest()
        return
    
    logger.info(f"🎵 Generating {total_to_generate} missing audio files...")
    
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
    
    # Generate missing agent names
    if missing_agents:
        logger.info(f"\n👨‍💼 Generating {len(missing_agents)} missing agent names...")
        for name in missing_agents:
            logger.info(f"Generating: {name}")
            
            result = await elevenlabs_client.generate_speech(name)
            
            if result.get("success") and result.get("audio_data"):
                filename = name.lower().replace(' ', '_').replace('.', '')
                filepath = AGENT_NAMES_DIR / f"{filename}.mp3"
                with open(filepath, "wb") as f:
                    f.write(result["audio_data"])
                logger.info(f"✅ Generated: {name}")
            else:
                logger.error(f"❌ Failed: {name}")
            
            # Small delay between requests
            await asyncio.sleep(0.5)
    
    # Generate "Hello {client_name}" combinations for natural flow
    await generate_hello_combinations()
    
    # Update manifest
    await update_manifest()
    
    logger.info("\n✅ Audio generation complete!")

async def generate_hello_combinations():
    """Generate 'Hello {client_name}' combinations for natural flow"""
    
    logger.info(f"\n👋 Generating 'Hello [CLIENT_NAME]' combinations for natural flow...")
    logger.info(f"📁 Client names directory: {CLIENT_NAMES_DIR}")
    logger.info(f"👥 Total client names to process: {len(COMMON_CLIENT_NAMES)}")
    
    # Create a special directory for hello combinations
    hello_combinations_dir = CLIENT_NAMES_DIR / "hello_combinations"
    hello_combinations_dir.mkdir(exist_ok=True)
    logger.info(f"📂 Hello combinations directory: {hello_combinations_dir}")
    
    generated_count = 0
    existing_count = 0
    
    for name in COMMON_CLIENT_NAMES:
        # Check if this combination already exists
        hello_filename = f"hello_{name.lower()}.mp3"
        hello_filepath = hello_combinations_dir / hello_filename
        
        if hello_filepath.exists():
            logger.info(f"✅ Hello {name} already exists: {hello_filepath}")
            existing_count += 1
            continue
        
        # Generate "Hello {name}" as a single phrase
        hello_text = f"Hello {name}"
        logger.info(f"🎵 Generating: {hello_text}")
        
        result = await elevenlabs_client.generate_speech(hello_text)
        
        if result.get("success") and result.get("audio_data"):
            with open(hello_filepath, "wb") as f:
                f.write(result["audio_data"])
            logger.info(f"✅ Generated: {hello_text} -> {hello_filepath}")
            generated_count += 1
        else:
            logger.error(f"❌ Failed: {hello_text} - {result.get('error', 'Unknown error')}")
        
        # Small delay between requests
        await asyncio.sleep(0.5)
    
    logger.info(f"✅ Generated {generated_count} new 'Hello [CLIENT_NAME]' combinations")
    logger.info(f"✅ Skipped {existing_count} 'Hello [CLIENT_NAME]' combinations (already exist)")
    logger.info(f"📊 Total processed: {generated_count + existing_count} out of {len(COMMON_CLIENT_NAMES)} client names")

async def update_manifest():
    """Update the segments manifest with new templates"""
    
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
            # Non-Medicare templates - Updated to use hello combinations
            "non_medicare_greeting": ["[CLIENT_NAME]", "non_medicare_greeting_middle"],
            "non_medicare_voicemail": ["[CLIENT_NAME]", "non_medicare_voicemail_middle"],
            
            # Medicare templates - Updated to use hello combinations
            "medicare_greeting": ["[CLIENT_NAME]", "medicare_greeting_middle"],
            "medicare_voicemail": ["[CLIENT_NAME]", "medicare_voicemail_middle"],
            
            # Default templates - Updated to use hello combinations
            "default_greeting": ["[CLIENT_NAME]", "default_greeting_middle"],
            "default_voicemail": ["[CLIENT_NAME]", "default_voicemail_middle"],
            
            # Shared templates (agent-based)
            "agent_intro": ["agent_intro_start", "[AGENT_NAME]", "agent_intro_middle"],
            "schedule_confirmation": ["schedule_start", "[AGENT_NAME]", "schedule_middle"],
            "no_schedule_followup": ["no_schedule_start", "[AGENT_NAME]", "no_schedule_middle"],
            
            # Static responses (no concatenation)
            "dnc_confirmation": ["dnc_confirmation"],
            "keep_communications": ["keep_communications"],
            "not_interested": ["not_interested_start"],
            "goodbye": ["goodbye"],
            "clarification": ["clarification"],
            "error": ["error"],
            
            # Clarifying responses
            "identity_clarification": ["identity_clarification"],
            "ai_clarification": ["ai_clarification"],
            "memory_clarification": ["memory_clarification"],
            "repeat_response": ["repeat_response"],
            "confusion_clarification": ["confusion_clarification"],
            
            # No speech handling
            "no_speech_first": ["no_speech_first"],
            "no_speech_second": ["no_speech_second"],
            "no_speech_final": ["no_speech_final"]
        },
        "client_types": {
            "non_medicare": {
                "greeting_template": "non_medicare_greeting",
                "voicemail_template": "non_medicare_voicemail",
                "description": "Non-Medicare clients with Anthony Fracchia introduction"
            },
            "medicare": {
                "greeting_template": "medicare_greeting", 
                "voicemail_template": "medicare_voicemail",
                "description": "Medicare clients with standard Altruis introduction"
            },
            "default": {
                "greeting_template": "default_greeting",
                "voicemail_template": "default_voicemail", 
                "description": "Fallback for unknown client types"
            }
        }
    }
    
    manifest_path = OUTPUT_DIR / 'segments_manifest.json'
    with open(manifest_path, 'w') as f:
        json.dump(manifest, f, indent=2)
    
    logger.info(f"📄 Manifest updated: {manifest_path}")

async def generate_all_audio():
    """Generate all audio files (force regeneration)"""
    
    logger.info("🎵 Generating ALL audio files (force regeneration)...")
    
    total_files = len(SCRIPT_SEGMENTS) + len(COMMON_CLIENT_NAMES) + len(AGENT_NAMES)
    logger.info(f"📊 Total files to generate: {total_files}")
    
    # Generate all segments
    logger.info(f"\n🎵 Generating {len(SCRIPT_SEGMENTS)} segments...")
    for segment_name, text in SCRIPT_SEGMENTS.items():
        logger.info(f"Generating: {segment_name}")
        
        result = await elevenlabs_client.generate_speech(text)
        
        if result.get("success") and result.get("audio_data"):
            filepath = SEGMENTS_DIR / f"{segment_name}.mp3"
            with open(filepath, "wb") as f:
                f.write(result["audio_data"])
            logger.info(f"✅ Generated: {segment_name}")
        else:
            logger.error(f"❌ Failed: {segment_name}")
        
        await asyncio.sleep(0.5)
    
    # Generate all client names
    logger.info(f"\n👥 Generating {len(COMMON_CLIENT_NAMES)} client names...")
    for name in COMMON_CLIENT_NAMES:
        logger.info(f"Generating: {name}")
        
        result = await elevenlabs_client.generate_speech(name)
        
        if result.get("success") and result.get("audio_data"):
            filepath = CLIENT_NAMES_DIR / f"{name.lower()}.mp3"
            with open(filepath, "wb") as f:
                f.write(result["audio_data"])
            logger.info(f"✅ Generated: {name}")
        else:
            logger.error(f"❌ Failed: {name}")
        
        await asyncio.sleep(0.5)
    
    # Generate all agent names
    logger.info(f"\n👨‍💼 Generating {len(AGENT_NAMES)} agent names...")
    for name in AGENT_NAMES:
        logger.info(f"Generating: {name}")
        
        result = await elevenlabs_client.generate_speech(name)
        
        if result.get("success") and result.get("audio_data"):
            filename = name.lower().replace(' ', '_').replace('.', '')
            filepath = AGENT_NAMES_DIR / f"{filename}.mp3"
            with open(filepath, "wb") as f:
                f.write(result["audio_data"])
            logger.info(f"✅ Generated: {name}")
        else:
            logger.error(f"❌ Failed: {name}")
        
        await asyncio.sleep(0.5)
    
    # Generate "Hello {client_name}" combinations for natural flow
    await generate_hello_combinations()
    
    # Update manifest
    await update_manifest()
    
    logger.info("\n✅ All audio generation complete!")

async def main():
    """Main function"""
    
    logger.info(f"🎯 Script running from: {Path(__file__).parent}")
    logger.info(f"🎯 App directory: {APP_DIR}")
    logger.info(f"🎯 Output directory: {OUTPUT_DIR}")
    
    # Ensure directories exist before generating
    ensure_directories_exist()
    
    # Check if ElevenLabs is configured
    if not elevenlabs_client.is_configured():
        logger.error("❌ ElevenLabs API key not configured in settings!")
        logger.info("💡 Please configure ELEVENLABS_API_KEY in your environment")
        return
    
    logger.info("🎤 ElevenLabs client configured successfully")
    
    # Generate missing audio (recommended for production)
    # await generate_missing_audio()
    
    # Uncomment the line below to force regenerate all audio
    await generate_all_audio()

if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    asyncio.run(main())