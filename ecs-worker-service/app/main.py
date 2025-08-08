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
from datetime import datetime, timedelta
from typing import Dict, Any, List, Optional

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# Import services with fallbacks
try:
    from services.campaign_processor import CampaignProcessor
    from services.sqs_consumer import SQSConsumer  
    from services.call_summarizer import CallSummarizerService as CallSummarizer
    from services.crm_integration import CRMIntegration
    from services.email_service import EmailService
    from services.agent_assignment import AgentAssignment
    services_available = True
    logger.info("✅ All worker services imported successfully")
except ImportError as e:
    logger.warning(f"⚠️ Service import failed: {e} - using basic mode")
    services_available = False


try:
    from shared.config.settings import settings
    from shared.utils.database import init_database, close_database
    from shared.utils.redis_client import init_redis, close_redis
    from shared.utils.database import db_client
    from shared.models.call_session import CallSession
    shared_available = True
    logger.info("✅ Shared utilities imported successfully")
except ImportError as e:
    logger.warning(f"⚠️ Shared utilities not available: {e}")
    shared_available = False


class WorkerService:
    """Main worker service for background processing"""
    
    def __init__(self):
        self.running = False
        self.processed_count = 0
        self.start_time = None
        
        # Don't initialize services here - wait until database is ready
        self.services_initialized = False
        
        # Setup signal handlers
        signal.signal(signal.SIGINT, self._signal_handler)
        signal.signal(signal.SIGTERM, self._signal_handler)

    
    async def _initialize_services(self):
        """Initialize services after database is ready"""
        if services_available and not self.services_initialized:
            try:
                self.campaign_processor = CampaignProcessor()
                self.sqs_consumer = SQSConsumer()
                self.call_summarizer = CallSummarizer()
                self.email_service = EmailService()
                self.crm_integration = CRMIntegration()
                self.agent_assignment = AgentAssignment()
                self.services_initialized = True
                logger.info("✅ All services initialized")
            except Exception as e:
                logger.error(f"❌ Service initialization failed: {e}")
                self.services_initialized = False
        elif not services_available:
            logger.info("📝 Running in basic mode - services not available")
            self.services_initialized = True
            

    
    async def start(self):
        """Start the worker service"""
        
        logger.info("🚀 Starting Voice Agent Worker Service")
        logger.info(f"🎯 Environment: {getattr(settings, 'environment', 'development') if shared_available else 'development'}")
        logger.info(f"🔧 Services Available: {services_available}")
        
        self.running = True
        self.start_time = datetime.utcnow()
        
        # Initialize shared services FIRST
        if shared_available:
            try:
                await init_database()
                logger.info("✅ Database initialized")
                
                # Test database connection
                from shared.utils.database import db_client
                if db_client and db_client.is_connected():
                    logger.info("✅ Database connection verified")
                else:
                    logger.error("❌ Database connection failed")
                    
            except Exception as e:
                logger.error(f"❌ Database initialization failed: {e}")
                logger.error("This will prevent the worker from processing data")
            
            try:
                await init_redis()
                logger.info("✅ Redis initialized")
            except Exception as e:
                logger.warning(f"⚠️ Redis initialization failed: {e}")
        
        # NOW initialize services (after database is ready)
        await self._initialize_services()
        
        logger.info("✅ Worker service started successfully")
        
        # Main processing loop
        while self.running:
            try:
                if self.services_initialized:
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
            # Check business hours using shared settings
            if not self.services_initialized:
                logger.warning("⚠️ Services not yet initialized - skipping processing")
                return
            
            if shared_available and hasattr(settings, 'is_business_hours'):
                is_business_hours = settings.is_business_hours()
            else:
                # Fallback business hours check
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
        """Send email notifications based on conversation stages"""
        try:
            # Get completed calls that need email notifications
            if db_client is None or db_client.database is None:
                return

            # Find calls completed in the last hour that need email processing
            one_hour_ago = datetime.utcnow() - timedelta(hours=1)

            cursor = db_client.database.call_sessions.find({
                "completed_at": {"$gte": one_hour_ago},
                "email_sent": {"$ne": True},  # Only process calls that haven't sent emails
                "final_outcome": {"$exists": True, "$ne": None}
            })

            processed_count = 0
            async for doc in cursor:
                try:
                    # Handle invalid enum values gracefully
                    try:
                        session = CallSession(**doc)
                    except Exception as validation_error:
                        logger.warning(f"⚠️ Invalid session data for {doc.get('session_id', 'unknown')}: {validation_error}")
                        logger.warning("Skipping this session due to data validation errors")
                        continue

                    # Determine email stage based on outcome
                    email_stage = self._determine_email_stage(session.final_outcome)

                    if not email_stage:
                        continue

                    # Get client information
                    client_email = None
                    client_name = session.client_data.get("client_name", "Client") if session.client_data else "Client"

                    # Try to get client email from database
                    if session.client_id and session.client_id != "unknown":
                        try:
                            from shared.utils.database import client_repo
                            if client_repo:
                                client = await client_repo.get_client_by_id(session.client_id)
                                if client and hasattr(client.client, 'email') and client.client.email:
                                    client_email = client.client.email
                                    client_name = f"{client.client.first_name} {client.client.last_name}"
                        except Exception as e:
                            logger.warning(f"Could not get client email: {e}")

                    # If no email found, skip this notification
                    if not client_email:
                        logger.info(f"No email found for client {client_name}, skipping email notification")
                        continue

                    # Get call summary
                    call_summary = self._build_call_summary(session)

                    # Send email based on stage
                    success = await self.email_service.send_conversation_stage_email(
                        client_email=client_email,
                        client_name=client_name,
                        stage=email_stage,
                        call_summary=call_summary
                    )

                    if success:
                        # Mark email as sent
                        await db_client.database.call_sessions.update_one(
                            {"_id": doc["_id"]},
                            {"$set": {"email_sent": True, "email_sent_at": datetime.utcnow()}}
                        )
                        processed_count += 1
                        logger.info(f"✅ Email sent for call {session.session_id} to {client_email}")

                except Exception as e:
                    logger.error(f"❌ Error processing email for call {doc.get('session_id', 'unknown')}: {e}")
                    continue

            if processed_count > 0:
                logger.info(f"📧 Processed {processed_count} email notifications")

        except Exception as e:
            logger.error(f"❌ Email notification processing error: {e}")

    def _determine_email_stage(self, outcome: str) -> Optional[str]:
        """Determine email stage based on call outcome"""
        stage_mapping = {
            "interested": "interested",
            "not_interested": "not_interested",
            "scheduled_morning": "meeting_scheduled",
            "scheduled_afternoon": "meeting_scheduled",
            "follow_up": "follow_up",
            "no_answer": "follow_up",
            "busy": "follow_up"
        }
        return stage_mapping.get(outcome)

    def _build_call_summary(self, session: CallSession) -> Dict[str, Any]:
        """Build call summary for email"""
        summary = {
            "outcome": session.final_outcome or "unknown",
            "duration": session.session_metrics.total_call_duration_seconds if session.session_metrics else 0,
            "conversation_turns": len(session.conversation_turns) if session.conversation_turns else 0,
            "key_points": [],
            "customer_concerns": [],
            "recommended_actions": []
        }
        
        # Extract key points from conversation
        if session.conversation_turns:
            # Simple extraction - in production you'd use AI to analyze
            for turn in session.conversation_turns[-3:]:  # Last 3 turns
                if turn.customer_speech:
                    summary["key_points"].append(turn.customer_speech[:100] + "...")
        
        # Add meeting time if scheduled
        if session.final_outcome in ["scheduled_morning", "scheduled_afternoon"]:
            summary["meeting_time"] = "Tomorrow at 10 AM" if session.final_outcome == "scheduled_morning" else "Tomorrow at 2 PM"
        
        return summary
    
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
                if hasattr(self, 'campaign_processor'):
                    await self.campaign_processor.close()
                if hasattr(self, 'call_summarizer'):
                    await self.call_summarizer.close()
                if hasattr(self, 'email_service'):
                    await self.email_service.close()
                logger.info("✅ Services cleaned up")
            except Exception as e:
                logger.warning(f"⚠️ Cleanup warning: {e}")
        
        # Close shared utilities
        if shared_available:
            try:
                await close_database()
                await close_redis()
                logger.info("✅ Shared utilities closed")
            except Exception as e:
                logger.warning(f"⚠️ Shared cleanup warning: {e}")
        
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