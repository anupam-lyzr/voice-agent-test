#!/usr/bin/env python3
"""
Test Voicemail Functionality
Tests the voicemail audio generation and concatenation
"""

import asyncio
import sys
from pathlib import Path

# Add the app directory to the path
sys.path.append(str(Path(__file__).parent / "ecs-api-service" / "app"))

async def test_voicemail_generation():
    """Test voicemail audio generation"""
    
    try:
        from services.segmented_audio_service import SegmentedAudioService
        
        print("🔍 Testing voicemail audio generation...")
        
        # Initialize the audio service
        audio_service = SegmentedAudioService()
        
        # Test client names
        test_clients = ["John", "Mary", "Robert", "Sarah"]
        
        for client_name in test_clients:
            print(f"\n🎵 Testing voicemail for: {client_name}")
            
            # Generate voicemail audio
            result = await audio_service.generate_concatenated_audio(
                template_name="voicemail",
                replacements={
                    "CLIENT_NAME": client_name.lower()
                }
            )
            
            if result.get("success"):
                print(f"✅ Successfully generated voicemail for {client_name}")
                print(f"   Audio URL: {result.get('audio_url')}")
                print(f"   Duration: {result.get('duration_seconds', 'N/A')} seconds")
            else:
                print(f"❌ Failed to generate voicemail for {client_name}")
                print(f"   Error: {result.get('error')}")
        
        print("\n✅ Voicemail test completed!")
        
    except Exception as e:
        print(f"❌ Test failed: {e}")
        import traceback
        traceback.print_exc()

async def test_voicemail_script():
    """Test the voicemail script generation"""
    
    try:
        print("\n🔍 Testing voicemail script generation...")
        
        # Import the script
        from scripts.generate_segmented_audio import SCRIPT_SEGMENTS, check_missing_segments
        
        # Check if voicemail segments exist
        print("📋 Checking voicemail segments...")
        
        # Check for voicemail segments
        voicemail_segments = ["voicemail_start", "voicemail_middle"]
        
        for segment in voicemail_segments:
            if segment in SCRIPT_SEGMENTS:
                print(f"✅ Found voicemail segment: {segment}")
                print(f"   Text: {SCRIPT_SEGMENTS[segment][:50]}...")
            else:
                print(f"❌ Missing voicemail segment: {segment}")
        
        print("\n✅ Voicemail script test completed!")
        
    except Exception as e:
        print(f"❌ Script test failed: {e}")
        import traceback
        traceback.print_exc()

async def main():
    """Main test function"""
    
    print("🚀 Starting Voicemail Functionality Tests")
    print("=" * 50)
    
    # Test 1: Voicemail script
    await test_voicemail_script()
    
    # Test 2: Voicemail audio generation
    await test_voicemail_generation()
    
    print("\n" + "=" * 50)
    print("🎉 All tests completed!")

if __name__ == "__main__":
    asyncio.run(main())
