#!/usr/bin/env python3
"""
Test script to debug Deepgram connection issues
"""

import asyncio
import os
import sys
import logging

# Add the app directory to the path
sys.path.append(os.path.join(os.path.dirname(__file__), 'app'))

from app.services.deepgram_client import deepgram_client
from app.shared.config.settings import settings

# Set up logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

async def test_deepgram():
    """Test Deepgram connection and configuration"""
    
    print("🔍 Testing Deepgram Configuration...")
    print(f"API Key configured: {bool(settings.deepgram_api_key)}")
    print(f"API Key starts with 'dg_': {settings.deepgram_api_key.startswith('dg_') if settings.deepgram_api_key else False}")
    print(f"API Key length: {len(settings.deepgram_api_key) if settings.deepgram_api_key else 0}")
    print(f"STT Model: {settings.stt_model}")
    print(f"STT Language: {settings.stt_language}")
    
    print("\n🔍 Testing Deepgram Client...")
    print(f"Client configured: {deepgram_client.is_configured()}")
    
    if not deepgram_client.is_configured():
        print("❌ Deepgram client not properly configured!")
        return
    
    print("\n🔍 Testing Deepgram Connection...")
    try:
        result = await deepgram_client.test_connection()
        print(f"Connection test result: {result}")
        
        if result.get("success"):
            print("✅ Deepgram connection successful!")
        else:
            print(f"❌ Deepgram connection failed: {result.get('error')}")
            
    except Exception as e:
        print(f"❌ Exception during connection test: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    asyncio.run(test_deepgram())
