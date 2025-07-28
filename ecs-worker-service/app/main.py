"""
Minimal Worker Service for testing Docker build
"""

import asyncio
import os
import time

async def worker_main():
    """Main worker loop"""
    print("🔧 Worker Service Starting...")
    
    while True:
        print(f"⚡ Worker heartbeat: {time.strftime('%H:%M:%S')}")
        await asyncio.sleep(30)

if __name__ == "__main__":
    print("🚀 Starting Voice Agent Worker Service")
    asyncio.run(worker_main())
