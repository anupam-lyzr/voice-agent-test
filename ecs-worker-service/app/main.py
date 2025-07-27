"""
Voice Agent Worker Service
Processes campaign queue and handles outbound calls
"""

import asyncio
import logging
import signal
import sys
from datetime import datetime

# Import shared utilities
from shared.config.settings import settings
from shared.utils.database import init_database, close_database
from shared.utils.redis_client import init_redis, close_redis

# Import services
from services.campaign_processor import CampaignProcessor
from services.crm_integration import CRMIntegrationService

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
        self.campaign_processor = CampaignProcessor()
        self.crm_service = CRMIntegrationService()
        self.processing_interval = 300  # 5 minutes
        self.batch_size = 25  # Process 25 clients at a time
    
    async def start(self):
        """Start the worker service"""
        logger.info(f"🚀 Starting {settings.app_name} Worker Service")
        logger.info(f"🎯 Environment: {settings.environment}")
        logger.info(f"📊 Max concurrent calls: {settings.max_concurrent_calls}")
        logger.info(f"⏰ Business hours: {settings.business_start_hour}:00-{settings.business_end_hour}:00 {settings.business_timezone}")
        
        # Initialize database and cache
        try:
            await init_database()
            await init_redis()
            logger.info("✅ Database and cache initialized")
        except Exception as e:
            logger.error(f"❌ Initialization failed: {e}")
            return
        
        # Validate configuration
        self._validate_configuration()
        
        # Check business hours
        if settings.is_business_hours():
            logger.info("✅ Within business hours - worker active")
            self.campaign_processor.start_campaign()
        else:
            logger.info("⏰ Outside business hours - worker will wait")
        
        self.running = True
        
        # Setup signal handlers
        signal.signal(signal.SIGINT, self._signal_handler)
        signal.signal(signal.SIGTERM, self._signal_handler)
        
        logger.info("🔄 Worker service started - monitoring for campaign tasks")
        
        # Main worker loop
        await self._worker_loop()
    
    def _validate_configuration(self):
        """Validate worker configuration"""
        validation = settings.validate_required_settings()
        
        logger.info("🔍 Configuration validation:")
        for key, result in validation.items():
            status = "✅" if result['valid'] else "⚠️"
            logger.info(f"   {status} {key}: {result['message']}")
        
        # Check CRM configuration
        crm_stats = self.crm_service.get_statistics()
        logger.info(f"💼 CRM Configuration:")
        logger.info(f"   Capsule CRM: {'✅' if crm_stats['capsule_configured'] else '⚠️'}")
        logger.info(f"   Google Calendar: {'✅' if crm_stats['google_calendar_configured'] else '⚠️'}")
        logger.info(f"   Agents loaded: {crm_stats['agents_configured']}")
    
    async def _worker_loop(self):
        """Main worker processing loop"""
        while self.running:
            try:
                # Check business hours
                if not settings.is_business_hours():
                    logger.info("⏰ Outside business hours - sleeping")
                    await asyncio.sleep(1800)  # Sleep 30 minutes
                    continue
                
                # Process campaign batch
                logger.info(f"🎯 Processing campaign batch (size: {self.batch_size})")
                
                batch_result = await self.campaign_processor.process_campaign_batch(
                    batch_size=self.batch_size
                )
                
                if batch_result.get("success"):
                    calls_initiated = batch_result.get("calls_initiated", 0)
                    calls_failed = batch_result.get("calls_failed", 0)
                    
                    logger.info(f"📊 Batch complete: {calls_initiated} calls initiated, {calls_failed} failed")
                    
                    # Process any completed calls that need CRM integration
                    await self._process_crm_updates()
                    
                elif batch_result.get("skipped"):
                    logger.info(f"⏭️ Batch skipped: {batch_result.get('reason')}")
                
                else:
                    logger.error(f"❌ Batch processing error: {batch_result.get('error')}")
                
                # Log progress
                await self._log_campaign_progress()
                
                # Sleep between iterations
                logger.info(f"💤 Sleeping for {self.processing_interval} seconds...")
                await asyncio.sleep(self.processing_interval)
                
            except Exception as e:
                logger.error(f"❌ Worker loop error: {e}")
                await asyncio.sleep(60)  # Wait 1 minute on error
    
    async def _process_crm_updates(self):
        """Process clients that need CRM updates"""
        try:
            # This would query for clients who were marked as interested
            # and need agent assignment, meeting scheduling, etc.
            
            # For now, just log that we would do this
            logger.debug("🔄 Checking for CRM updates...")
            
            # TODO: Implement actual CRM update processing
            # 1. Query clients with outcome = "interested" and no agent assigned
            # 2. Process each client through CRM integration service
            # 3. Update client records with results
            
        except Exception as e:
            logger.error(f"❌ CRM update processing error: {e}")
    
    async def _log_campaign_progress(self):
        """Log current campaign progress"""
        try:
            progress = await self.campaign_processor.get_campaign_progress()
            
            if "campaign_stats" in progress:
                stats = progress["campaign_stats"]
                processor_stats = progress["processor_stats"]
                
                logger.info("📈 Campaign Progress:")
                logger.info(f"   Total clients: {stats.get('total_clients', 0)}")
                logger.info(f"   Completed calls: {stats.get('completed_calls', 0)}")
                logger.info(f"   Interested clients: {stats.get('interested_clients', 0)}")
                logger.info(f"   Success rate: {processor_stats.get('success_rate', 0):.1f}%")
                
                # Log CRM statistics
                crm_stats = self.crm_service.get_statistics()
                logger.info(f"💼 CRM Stats: {crm_stats['agent_assignments']} assignments, {crm_stats['meetings_scheduled']} meetings")
                
        except Exception as e:
            logger.error(f"Progress logging error: {e}")
    
    def _signal_handler(self, signum, frame):
        """Handle shutdown signals"""
        logger.info(f"📡 Received signal {signum} - shutting down gracefully")
        self.running = False
    
    async def stop(self):
        """Stop the worker service"""
        logger.info("🛑 Stopping worker service")
        self.running = False
        
        # Get final statistics
        try:
            progress = await self.campaign_processor.get_campaign_progress()
            processor_stats = progress.get("processor_stats", {})
            crm_stats = self.crm_service.get_statistics()
            
            logger.info("📊 Final Statistics:")
            logger.info(f"   Clients processed: {processor_stats.get('clients_processed', 0)}")
            logger.info(f"   Calls initiated: {processor_stats.get('calls_initiated', 0)}")
            logger.info(f"   Calls failed: {processor_stats.get('calls_failed', 0)}")
            logger.info(f"   Agent assignments: {crm_stats['agent_assignments']}")
            logger.info(f"   Meetings scheduled: {crm_stats['meetings_scheduled']}")
            
        except Exception as e:
            logger.error(f"Error getting final statistics: {e}")
        
        await close_database()
        await close_redis()
        
        logger.info("✅ Worker service stopped")

async def main():
    """Main entry point"""
    worker = WorkerService()
    
    try:
        await worker.start()
    except KeyboardInterrupt:
        logger.info("🛑 Keyboard interrupt received")
    except Exception as e:
        logger.error(f"❌ Worker service error: {e}")
        import traceback
        traceback.print_exc()
    finally:
        await worker.stop()

if __name__ == "__main__":
    asyncio.run(main())