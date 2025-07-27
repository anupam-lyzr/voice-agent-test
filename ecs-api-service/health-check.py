#!/usr/bin/env python3
"""
Health check script for API service
"""

import sys
import httpx
import asyncio

async def health_check():
    """Check if the API service is healthy"""
    try:
        async with httpx.AsyncClient() as client:
            response = await client.get("http://localhost:8000/health", timeout=10.0)
            
            if response.status_code == 200:
                data = response.json()
                print(f"✅ API Service healthy: {data.get('status', 'unknown')}")
                return True
            else:
                print(f"❌ API Service unhealthy: HTTP {response.status_code}")
                return False
                
    except Exception as e:
        print(f"❌ Health check failed: {str(e)}")
        return False

if __name__ == '__main__':
    result = asyncio.run(health_check())
    sys.exit(0 if result else 1)
