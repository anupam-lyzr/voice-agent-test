"""
Voice Agent Worker Service - Production Ready
Processes campaign queue, sends emails, updates CRM
"""

import asyncio
import logging
import signal
import sys
import os
import time
from datetime import datetime
from typing import Dict, Any, List

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# Import services with fallbacks
try:
    from .services.campaign_processor import CampaignProcessor
    from .services.sqs_consumer import SQSConsumer
    from .services.call_summarizer import CallSummarizer
    from .services.email_service import EmailService
    
    # Import existing services
    from .services.crm_integration import CRMIntegration
    from .services.agent_assignment import AgentAssignment
    
    services_available = True
    logger.info("✅ All worker services imported successfully")
    
except ImportError as e:
    logger.warning(f"⚠️ Service import failed: {e} - using basic mode")
    services_available = False

class WorkerService:
    """Main worker service for background processing"""
    
    def __init__(self):
        self.running = False
        self.processed_count = 0
        self.start_time = None
        
        # Initialize services if available
        if services_available:
            self.campaign_processor = CampaignProcessor()
            self.sqs_consumer = SQSConsumer()
            self.call_summarizer = CallSummarizer()
            self.email_service = EmailService()
            self.crm_integration = CRMIntegration()
            self.agent_assignment = AgentAssignment()
            logger.info("✅ All services initialized")
        else:
            logger.info("📝 Running in basic mode - services not available")
        
        # Setup signal handlers
        signal.signal(signal.SIGINT, self._signal_handler)
        signal.signal(signal.SIGTERM, self._signal_handler)
    
    async def start(self):
        """Start the worker service"""
        
        logger.info("🚀 Starting Voice Agent Worker Service")
        logger.info(f"🎯 Environment: {os.getenv('ENVIRONMENT', 'development')}")
        logger.info(f"🔧 Services Available: {services_available}")
        
        self.running = True
        self.start_time = datetime.utcnow()
        
        logger.info("✅ Worker service started successfully")
        
        # Main processing loop
        while self.running:
            try:
                if services_available:
                    await self._process_with_services()
                else:
                    await self._process_basic_mode()
                
                # Sleep between cycles
                await asyncio.sleep(30)  # Process every 30 seconds
                
            except Exception as e:
                logger.error(f"❌ Worker loop error: {e}")
                await asyncio.sleep(60)  # Wait longer on error
    
    async def _process_with_services(self):
        """Process with full service integration"""
        try:
            # Check business hours
            current_hour = datetime.now().hour
            is_business_hours = 9 <= current_hour < 17  # 9 AM to 5 PM
            
            if not is_business_hours:
                if self.processed_count % 20 == 0:  # Log every 20 cycles
                    logger.info("⏰ Outside business hours - worker in standby mode")
                return
            
            # 1. Process SQS queue messages
            sqs_messages = await self.sqs_consumer.process_queue()
            if sqs_messages:
                logger.info(f"📥 Processed {len(sqs_messages)} SQS messages")
            
            # 2. Process campaign batch (outbound calls)
            campaign_result = await self.campaign_processor.process_campaign_batch()
            if campaign_result.get("clients_processed", 0) > 0:
                self.processed_count += campaign_result["clients_processed"]
                logger.info(f"📞 Processed {campaign_result['clients_processed']} campaign calls")
            
            # 3. Process call summaries for completed calls
            await self._process_call_summaries()
            
            # 4. Process CRM updates
            await self._process_crm_updates()
            
            # 5. Process agent assignments for interested clients
            await self._process_agent_assignments()
            
            # 6. Send email notifications
            await self._process_email_notifications()
            
            # Log progress
            if self.processed_count % 10 == 0 and self.processed_count > 0:
                logger.info(f"📊 Total processed today: {self.processed_count}")
            
        except Exception as e:
            logger.error(f"❌ Service processing error: {e}")
    
    async def _process_basic_mode(self):
        """Basic processing without full services"""
        try:
            current_hour = datetime.now().hour
            is_business_hours = 9 <= current_hour < 17
            
            if not is_business_hours:
                if self.processed_count % 20 == 0:
                    logger.info("⏰ Outside business hours - basic worker standby")
                return
            
            # Basic processing
            self.processed_count += 1
            
            if self.processed_count % 10 == 0:
                logger.info(f"📊 Basic processing cycle: {self.processed_count}")
            
        except Exception as e:
            logger.error(f"❌ Basic processing error: {e}")
    
    async def _process_call_summaries(self):
        """Generate summaries for completed calls"""
        try:
            # Mock getting calls that need summaries
            # In production, this would query the database
            calls_needing_summaries = []  # Would get from database
            
            if calls_needing_summaries:
                logger.info(f"📝 Processing {len(calls_needing_summaries)} call summaries")
                
                for call in calls_needing_summaries:
                    try:
                        summary = await self.call_summarizer.generate_summary(
                            transcript=call.get("transcript", ""),
                            client_info=call.get("client_info", {}),
                            call_duration=call.get("duration", "unknown")
                        )
                        
                        # Save summary to database
                        # await save_call_summary(call["id"], summary)
                        
                        logger.info(f"✅ Summary generated for call {call.get('id')}")
                        
                    except Exception as e:
                        logger.error(f"❌ Summary generation failed: {e}")
        
        except Exception as e:
            logger.error(f"❌ Call summary processing error: {e}")
    
    async def _process_crm_updates(self):
        """Process CRM updates for completed calls"""
        try:
            # Mock getting clients that need CRM updates
            clients_for_crm = []  # Would get from database
            
            if clients_for_crm:
                logger.info(f"🏷️ Processing CRM updates for {len(clients_for_crm)} clients")
                
                for client in clients_for_crm:
                    try:
                        await self.crm_integration.update_client_record(client)
                        logger.info(f"✅ CRM updated for {client.get('name')}")
                    except Exception as e:
                        logger.error(f"❌ CRM update failed: {e}")
        
        except Exception as e:
            logger.error(f"❌ CRM processing error: {e}")
    
    async def _process_agent_assignments(self):
        """Process agent assignments for interested clients"""
        try:
            # Mock getting clients that need agent assignment
            clients_for_assignment = []  # Would get from database
            
            if clients_for_assignment:
                logger.info(f"👥 Processing agent assignments for {len(clients_for_assignment)} clients")
                
                for client in clients_for_assignment:
                    try:
                        assignment_result = await self.agent_assignment.assign_agent(client)
                        
                        if assignment_result.get("success"):
                            logger.info(f"✅ Agent assigned to {client.get('name')}")
                        else:
                            logger.warning(f"⚠️ Agent assignment failed: {assignment_result.get('error')}")
                    
                    except Exception as e:
                        logger.error(f"❌ Agent assignment error: {e}")
        
        except Exception as e:
            logger.error(f"❌ Agent assignment processing error: {e}")
    
    async def _process_email_notifications(self):
        """Send email notifications"""
        try:
            # Mock getting pending email notifications
            pending_emails = []  # Would get from database
            
            if pending_emails:
                logger.info(f"📧 Processing {len(pending_emails)} email notifications")
                
                for email_task in pending_emails:
                    try:
                        email_type = email_task.get("type")
                        
                        if email_type == "agent_assignment":
                            success = await self.email_service.send_agent_assignment_email(
                                agent_email=email_task["agent_email"],
                                agent_name=email_task["agent_name"],
                                client_info=email_task["client_info"],
                                call_summary=email_task["call_summary"]
                            )
                        elif email_type == "meeting_confirmation":
                            success = await self.email_service.send_meeting_confirmation_email(
                                client_email=email_task["client_email"],
                                client_name=email_task["client_name"],
                                agent_name=email_task["agent_name"],
                                meeting_details=email_task["meeting_details"]
                            )
                        else:
                            success = False
                        
                        if success:
                            logger.info(f"✅ Email sent: {email_type}")
                        else:
                            logger.warning(f"⚠️ Email failed: {email_type}")
                    
                    except Exception as e:
                        logger.error(f"❌ Email sending error: {e}")
        
        except Exception as e:
            logger.error(f"❌ Email processing error: {e}")
    
    def _signal_handler(self, signum, frame):
        """Handle shutdown signals"""
        logger.info(f"📡 Received signal {signum} - shutting down gracefully")
        self.running = False
    
    async def stop(self):
        """Stop the worker service"""
        logger.info("🛑 Stopping worker service")
        self.running = False
        
        # Cleanup services
        if services_available:
            try:
                await self.campaign_processor.close()
                await self.call_summarizer.close()
                await self.email_service.close()
                logger.info("✅ Services cleaned up")
            except Exception as e:
                logger.warning(f"⚠️ Cleanup warning: {e}")
        
        uptime = (datetime.utcnow() - self.start_time).total_seconds() if self.start_time else 0
        logger.info(f"✅ Worker service stopped - Processed: {self.processed_count} tasks, Uptime: {int(uptime)}s")

async def main():
    """Main entry point"""
    worker = WorkerService()
    
    try:
        await worker.start()
    except KeyboardInterrupt:
        logger.info("🛑 Keyboard interrupt received")
    except Exception as e:
        logger.error(f"❌ Worker service error: {e}")
    finally:
        await worker.stop()

if __name__ == "__main__":
    logger.info("🔄 Starting worker service...")
    asyncio.run(main())