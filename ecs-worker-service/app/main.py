"""
Voice Agent Worker Service - Complete Implementation
Processes campaign queue and handles outbound calls
"""

import asyncio
import logging
import signal
import sys
import time
from datetime import datetime
from contextlib import asynccontextmanager
from typing import Dict, Any, List

# Import shared utilities
from shared.config.settings import settings
from shared.utils.database import init_database, close_database, client_repo
from shared.utils.redis_client import init_redis, close_redis, metrics_cache

# Import worker services
from services.campaign_processor import CampaignProcessor
from services.sqs_consumer import SQSConsumer
from services.crm_integration import CRMIntegration
from services.agent_assignment import AgentAssignment

# Configure logging
logging.basicConfig(
    level=logging.INFO if settings.debug else logging.WARNING,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

class WorkerService:
    """Main worker service class"""
    
    def __init__(self):
        self.running = False
        self.processed_count = 0
        self.start_time = None
        
        # Initialize service components
        self.campaign_processor = CampaignProcessor()
        self.sqs_consumer = SQSConsumer()
        self.crm_integration = CRMIntegration()
        self.agent_assignment = AgentAssignment()
        
        # Setup signal handlers
        signal.signal(signal.SIGINT, self._signal_handler)
        signal.signal(signal.SIGTERM, self._signal_handler)
    
    async def start(self):
        """Start the worker service"""
        
        logger.info(f"🚀 Starting {settings.app_name} Worker Service")
        logger.info(f"🎯 Environment: {settings.environment}")
        logger.info(f"🔧 Debug mode: {settings.debug}")
        
        # Initialize database and cache
        try:
            await init_database()
            await init_redis()
            logger.info("✅ Database and cache initialized")
        except Exception as e:
            logger.error(f"❌ Initialization failed: {e}")
            return
        
        # Validate required settings
        if not settings.is_business_hours():
            logger.info("⏰ Outside business hours - worker in standby mode")
        
        # Start campaign processor
        self.campaign_processor.start_campaign()
        self.start_time = datetime.utcnow()
        self.running = True
        
        logger.info("🌐 Worker Service ready for campaign processing")
        
        # Main processing loop
        await self._main_processing_loop()
    
    async def _main_processing_loop(self):
        """Main processing loop"""
        
        while self.running:
            try:
                # Check if we should process campaigns
                if settings.is_business_hours():
                    await self._process_campaign_tasks()
                else:
                    # Outside business hours - just maintain heartbeat
                    logger.info("⏰ Outside business hours - standby mode")
                    await asyncio.sleep(300)  # 5 minutes
                    continue
                
                # Brief pause between processing cycles
                await asyncio.sleep(30)  # 30 seconds between cycles
                
            except Exception as e:
                logger.error(f"❌ Error in main processing loop: {e}")
                await asyncio.sleep(60)  # Wait longer after errors
    
    async def _process_campaign_tasks(self):
        """Process campaign tasks during business hours"""
        
        try:
            # 1. Check SQS queue for new campaign requests
            sqs_messages = await self.sqs_consumer.process_queue()
            
            if sqs_messages:
                logger.info(f"📥 Processed {len(sqs_messages)} SQS messages")
            
            # 2. Process campaign batch
            batch_result = await self.campaign_processor.process_campaign_batch()
            
            if batch_result.get("clients_processed", 0) > 0:
                self.processed_count += batch_result["clients_processed"]
                logger.info(f"📊 Processed {batch_result['clients_processed']} clients (total: {self.processed_count})")
                
                # 3. Handle CRM integration for completed calls
                await self._process_crm_updates()
                
                # 4. Handle agent assignments for interested clients
                await self._process_agent_assignments()
            
            # 5. Update metrics
            await self._update_metrics(batch_result)
            
        except Exception as e:
            logger.error(f"❌ Error processing campaign tasks: {e}")
    
    async def _process_crm_updates(self):
        """Process CRM updates for completed calls"""
        
        try:
            # Get clients that need CRM updates
            clients_for_crm = await client_repo.get_clients_needing_crm_update(limit=50)
            
            if clients_for_crm:
                logger.info(f"🏷️ Processing CRM updates for {len(clients_for_crm)} clients")
                
                for client in clients_for_crm:
                    try:
                        await self.crm_integration.update_client_record(client)
                        logger.info(f"✅ CRM updated for {client.client.full_name}")
                    except Exception as e:
                        logger.error(f"❌ CRM update failed for {client.client.full_name}: {e}")
        
        except Exception as e:
            logger.error(f"❌ Error processing CRM updates: {e}")
    
    async def _process_agent_assignments(self):
        """Process agent assignments for interested clients"""
        
        try:
            # Get clients that need agent assignment
            clients_for_assignment = await client_repo.get_clients_needing_assignment(limit=20)
            
            if clients_for_assignment:
                logger.info(f"👥 Processing agent assignments for {len(clients_for_assignment)} clients")
                
                for client in clients_for_assignment:
                    try:
                        assignment_result = await self.agent_assignment.assign_agent(client)
                        
                        if assignment_result["success"]:
                            logger.info(f"✅ Agent assigned to {client.client.full_name}: {assignment_result['agent_name']}")
                        else:
                            logger.warning(f"⚠️ Agent assignment failed for {client.client.full_name}: {assignment_result['error']}")
                    
                    except Exception as e:
                        logger.error(f"❌ Agent assignment error for {client.client.full_name}: {e}")
        
        except Exception as e:
            logger.error(f"❌ Error processing agent assignments: {e}")
    
    async def _update_metrics(self, batch_result: Dict[str, Any]):
        """Update performance metrics"""
        
        try:
            metrics = {
                "worker_processed_count": self.processed_count,
                "worker_uptime_seconds": int((datetime.utcnow() - self.start_time).total_seconds()) if self.start_time else 0,
                "last_batch_size": batch_result.get("clients_processed", 0),
                "last_batch_success_rate": batch_result.get("success_rate", 0),
                "business_hours_active": settings.is_business_hours(),
                "timestamp": datetime.utcnow().isoformat()
            }
            
            await metrics_cache.set("worker_metrics", metrics, expire_seconds=300)
            
        except Exception as e:
            logger.error(f"❌ Error updating metrics: {e}")
    
    def _signal_handler(self, signum, frame):
        """Handle shutdown signals"""
        logger.info(f"📡 Received signal {signum} - shutting down gracefully")
        self.running = False
    
    async def stop(self):
        """Stop the worker service"""
        logger.info("🛑 Stopping worker service")
        self.running = False
        
        try:
            # Cleanup services
            await self.campaign_processor.cleanup_old_calls()
            await self.sqs_consumer.close()
            
            # Close database and cache connections
            await close_database()
            await close_redis()
            
            logger.info(f"✅ Worker service stopped (processed {self.processed_count} tasks)")
            
        except Exception as e:
            logger.error(f"❌ Error during shutdown: {e}")

# Health check endpoint for container
async def health_check():
    """Simple health check for container orchestration"""
    try:
        # Check if we can connect to database
        from shared.utils.database import db_client
        if db_client and db_client.is_connected():
            return {"status": "healthy", "service": "worker"}
        else:
            return {"status": "unhealthy", "service": "worker", "error": "database_disconnected"}
    except Exception as e:
        return {"status": "unhealthy", "service": "worker", "error": str(e)}

async def main():
    """Main entry point"""
    
    # Check if this is a health check call
    if len(sys.argv) > 1 and sys.argv[1] == "health":
        health_result = await health_check()
        print(f"Health: {health_result['status']}")
        sys.exit(0 if health_result['status'] == 'healthy' else 1)
    
    # Normal startup
    worker = WorkerService()
    
    try:
        await worker.start()
    except KeyboardInterrupt:
        logger.info("🛑 Keyboard interrupt received")
    except Exception as e:
        logger.error(f"❌ Worker service error: {e}")
        sys.exit(1)
    finally:
        await worker.stop()

if __name__ == "__main__":
    asyncio.run(main())