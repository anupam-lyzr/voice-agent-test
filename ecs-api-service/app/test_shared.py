#!/usr/bin/env python3
"""Test shared code imports"""

try:
    from shared.config.settings import settings
    from shared.models.client import Client, ClientInfo, CallOutcome
    from shared.models.call_session import CallSession, ConversationStage
    from shared.utils.database import DatabaseClient
    from shared.utils.redis_client import RedisClient
    
    print("✅ All shared imports successful in API service")
    print(f"   App name: {settings.app_name}")
    print(f"   Debug mode: {settings.debug}")
    print(f"   MongoDB URI: {settings.mongodb_uri}")
    
except Exception as e:
    print(f"❌ Import error in API service: {e}")
    exit(1)
