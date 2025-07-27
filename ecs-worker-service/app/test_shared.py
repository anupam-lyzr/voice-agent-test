#!/usr/bin/env python3
"""Test shared code imports"""

try:
    from shared.config.settings import settings
    from shared.models.client import Client, ClientInfo, CallOutcome, CRMTag
    from shared.models.call_session import CallSession, ConversationStage
    from shared.utils.database import DatabaseClient, init_database
    from shared.utils.redis_client import RedisClient, init_redis
    
    print("✅ All shared imports successful in Worker service")
    print(f"   App name: {settings.app_name}")
    print(f"   Business hours check: {settings.is_business_hours()}")
    print(f"   Max concurrent calls: {settings.max_concurrent_calls}")
    
except Exception as e:
    print(f"❌ Import error in Worker service: {e}")
    exit(1)
