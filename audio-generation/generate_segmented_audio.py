#!/usr/bin/env python3
"""
Generate segmented audio files using ElevenLabs API
"""

import os
import json
import asyncio
import sys
try:
    import httpx
except ImportError:
    print("❌ httpx not installed. Please run: pip3 install httpx")
    sys.exit(1)
import sys

# Python 3.9 compatibility fix
if sys.version_info >= (3, 9):
    pass  # asyncio.run is available

import httpx
from pathlib import Path

# Get the directory of the current script to build robust paths
SCRIPT_DIR = Path(__file__).parent.resolve()

# Configuration
ELEVENLABS_API_KEY = 'sk_76450d6c6b4d7f6ed594189cfdc5d307ae96b9e98fc0d494'
VOICE_ID = 'xtENCNNHEgtE8xBjLMt0'  # Adam voice

# Set paths relative to the script's parent directory
OUTPUT_DIR = SCRIPT_DIR / 'generated_audio'
SEGMENTS_DIR = OUTPUT_DIR / 'segments'
NAMES_DIR = OUTPUT_DIR / 'names'
CLIENT_NAMES_DIR = NAMES_DIR / 'clients'
AGENT_NAMES_DIR = NAMES_DIR / 'agents'

# Voice settings for natural speech
VOICE_SETTINGS = {
    "stability": 0.55,
    "use_speaker_boost": True,
    "similarity_boost": 0.7,
    "style": 0.19999999999999996,
    "speed": 0.8700000000000001
}

# AAG Script Segments (EXACT from document)
SCRIPT_SEGMENTS = {
    # Main Greeting Segments
    "greeting_start": "Hello ",
    "greeting_middle": ", Alex here from Altruis Advisor Group. We've helped you with your health insurance needs in the past and I just wanted to reach out to see if we can be of service to you this year during Open Enrollment? A simple Yes or No is fine, and remember, our services are completely free of charge.",
    
    # Agent Introduction Segments
    "agent_intro_start": "Great, looks like ",
    "agent_intro_middle": " was the last agent you worked with here at Altruis. Would you like to schedule a quick 15-minute discovery call with them to get reacquainted? A simple Yes or No will do!",
    
    # Not Interested Flow Segments
    "not_interested_start": "No problem, would you like to continue receiving general health insurance communications from our team? Again, a simple Yes or No will do!",
    
    # Schedule Confirmation Segments  
    "schedule_start": "Great, give me a moment while I check ",
    "schedule_middle": "'s calendar... Perfect! I've scheduled a 15-minute discovery call for you. You should receive a calendar invitation shortly. Thank you and have a wonderful day!",
    
    # No Schedule Flow Segments
    "no_schedule_start": "No problem, ",
    "no_schedule_middle": " will reach out to you and the two of you can work together to determine the best next steps. We look forward to servicing you, have a wonderful day!",
    
    # DNC Flow (Complete - no names needed)
    "dnc_confirmation": "Understood, we will make sure you are removed from all future communications and send you a confirmation email once that is done. Our contact details will be in that email as well, so if you do change your mind in the future please feel free to reach out – we are always here to help and our service is always free of charge. Have a wonderful day!",
    
    # Keep Communications (Complete - no names needed)
    "keep_communications": "Great, we're happy to keep you informed throughout the year regarding the ever-changing world of health insurance. If you'd like to connect with one of our insurance experts in the future please feel free to reach out – we are always here to help and our service is always free of charge. Have a wonderful day!",
    
    # Generic Responses (Complete - no names needed)
    "goodbye": "Thank you for your time today. Have a wonderful day!",
    "clarification": "I want to make sure I understand correctly. Can we help service you this year during Open Enrollment? Please say Yes if you're interested, or No if you're not interested."
}

# Common Client Names (from typical AAG client base)
COMMON_CLIENT_NAMES = [
    "John", "Jane", "Michael", "Sarah", "David", "Lisa", "Robert", "Jennifer", 
    "William", "Patricia", "James", "Elizabeth", "Christopher", "Linda", "Daniel", 
    "Barbara", "Matthew", "Susan", "Anthony", "Jessica", "Mark", "Karen", "Donald", 
    "Nancy", "Steven", "Betty", "Paul", "Helen", "Andrew", "Sandra", "Joshua", 
    "Donna", "Kenneth", "Carol", "Kevin", "Ruth", "Brian", "Sharon", "George", 
    "Michelle", "Edward", "Laura", "Ronald", "Emily", "Timothy", "Kimberly", 
    "Jason", "Deborah", "Jeffrey", "Dorothy", "Ryan", "Amy", "Jacob", "Angela",
    "Gary", "Ashley", "Nicholas", "Brenda", "Eric", "Emma", "Jonathan", "Olivia",
    "Stephen", "Cynthia", "Larry", "Marie", "Justin", "Janet", "Scott", "Catherine",
    "Brandon", "Frances", "Benjamin", "Christine", "Samuel", "Samantha", "Gregory",
    "Debra", "Alexander", "Rachel", "Frank", "Carolyn", "Raymond", "Martha"
]

# AAG Agent Names (EXACT from document)
AAG_AGENTS = [
    "Anthony Fracchia",
    "LaShawn Boyd", 
    "India Watson",
    "Hineth Pettway",
    "Keith Braswell"
]

async def generate_audio_file(text: str, filename: str, output_dir: Path):
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
        timeout = httpx.Timeout(30.0)   
        async with httpx.AsyncClient(timeout=timeout) as client:
            response = await client.post(url, headers=headers, json=data)
            
            if response.status_code == 200:
                # Save audio file
                output_path = output_dir / filename
                with open(output_path, 'wb') as f:
                    f.write(response.content)
                
                print(f"✅ Generated: {filename} ({len(response.content)} bytes)")
                return True
            else:
                print(f"❌ Failed to generate {filename}: {response.status_code}")
                print(f"Error: {response.text}")
                return False
                
    except Exception as e:
        print(f"❌ Error generating {filename}: {str(e)}")
        return False

async def generate_segments():
    """Generate all script segments"""
    
    print("🎵 Generating AAG script segments...")
    
    # Create output directories
    SEGMENTS_DIR.mkdir(parents=True, exist_ok=True)
    
    successful = 0
    failed = 0
    
    # Generate each segment
    for segment_name, text in SCRIPT_SEGMENTS.items():
        filename = f"{segment_name}.mp3"
        
        success = await generate_audio_file(text, filename, SEGMENTS_DIR)
        
        if success:
            successful += 1
        else:
            failed += 1
        
        # Small delay between requests
        await asyncio.sleep(1)
    
    print(f"\n📊 Segments Generation Summary:")
    print(f"✅ Successful: {successful}")
    print(f"❌ Failed: {failed}")
    
    return successful, failed

async def generate_client_names():
    """Generate common client names"""
    
    print("\n👥 Generating client names...")
    
    # Create output directory
    CLIENT_NAMES_DIR.mkdir(parents=True, exist_ok=True)
    
    successful = 0
    failed = 0
    
    # Generate each name (first 20 for initial setup)
    for name in COMMON_CLIENT_NAMES[:20]:  # Limit for initial setup
        filename = f"{name.lower()}.mp3"
        
        # Skip if already exists
        if (CLIENT_NAMES_DIR / filename).exists():
            print(f"⏭️  Skipping existing: {filename}")
            successful += 1
            continue
        
        success = await generate_audio_file(name, filename, CLIENT_NAMES_DIR)
        
        if success:
            successful += 1
        else:
            failed += 1
        
        # Small delay between requests
        await asyncio.sleep(0.5)
    
    print(f"\n📊 Client Names Generation Summary:")
    print(f"✅ Successful: {successful}")
    print(f"❌ Failed: {failed}")
    
    return successful, failed

async def generate_agent_names():
    """Generate AAG agent names"""
    
    print("\n🏢 Generating agent names...")
    
    # Create output directory
    AGENT_NAMES_DIR.mkdir(parents=True, exist_ok=True)
    
    successful = 0
    failed = 0
    
    # Generate each agent name
    for agent_name in AAG_AGENTS:
        # Create filename from agent name
        filename = f"{agent_name.lower().replace(' ', '_')}.mp3"
        
        success = await generate_audio_file(agent_name, filename, AGENT_NAMES_DIR)
        
        if success:
            successful += 1
        else:
            failed += 1
        
        # Small delay between requests
        await asyncio.sleep(1)
    
    print(f"\n📊 Agent Names Generation Summary:")
    print(f"✅ Successful: {successful}")
    print(f"❌ Failed: {failed}")
    
    return successful, failed

async def create_manifest():
    """Create manifest file with all generated segments and names"""
    
    manifest = {
        "generated_at": str(asyncio.get_event_loop().time()),
        "voice_id": VOICE_ID,
        "voice_settings": VOICE_SETTINGS,
        "segments": {
            "count": len(SCRIPT_SEGMENTS),
            "files": list(SCRIPT_SEGMENTS.keys())
        },
        "client_names": {
            "count": 20,  # Initial set
            "files": [name.lower() for name in COMMON_CLIENT_NAMES[:20]]
        },
        "agent_names": {
            "count": len(AAG_AGENTS),
            "files": [agent.lower().replace(' ', '_') for agent in AAG_AGENTS]
        },
        "concatenation_examples": {
            "greeting": ["greeting_start", "[client_name]", "greeting_middle"],
            "agent_intro": ["agent_intro_start", "[agent_name]", "agent_intro_middle"],
            "schedule": ["schedule_start", "[agent_name]", "schedule_middle"],
            "no_schedule": ["no_schedule_start", "[agent_name]", "no_schedule_middle"]
        }
    }
    
    manifest_path = OUTPUT_DIR / 'segments_manifest.json'
    with open(manifest_path, 'w') as f:
        json.dump(manifest, f, indent=2)
    
    print(f"📄 Manifest created: {manifest_path}")

async def main():
    """Generate all segmented audio files"""
    
    print("🚀 Starting AAG Segmented Audio Generation...")
    print("=" * 50)
    
    # Generate segments
    seg_success, seg_failed = await generate_segments()
    
    # Generate client names
    client_success, client_failed = await generate_client_names()
    
    # Generate agent names  
    agent_success, agent_failed = await generate_agent_names()
    
    # Create manifest
    await create_manifest()
    
    # Final summary
    total_success = seg_success + client_success + agent_success
    total_failed = seg_failed + client_failed + agent_failed
    
    print("\n" + "=" * 50)
    print("🎉 AAG SEGMENTED AUDIO GENERATION COMPLETE!")
    print("=" * 50)
    print(f"📊 OVERALL SUMMARY:")
    print(f"   ✅ Total Successful: {total_success}")
    print(f"   ❌ Total Failed: {total_failed}")
    print(f"   📁 Output Directory: {OUTPUT_DIR}")
    print("\n📋 GENERATED STRUCTURE:")
    print(f"   🎵 Script Segments: {seg_success} files")
    print(f"   👥 Client Names: {client_success} files") 
    print(f"   🏢 Agent Names: {agent_success} files")
    print("\n🔗 READY FOR CONCATENATION!")
    print("   Use SegmentedAudioService to combine segments with names")

if __name__ == '__main__':
    asyncio.run(main())
