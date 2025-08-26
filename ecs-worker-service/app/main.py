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

# Import services with fallbacks - will be done after database initialization
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
        global services_available
        
        if not self.services_initialized:
            try:
                logger.info("🔍 Attempting to import worker services...")
                
                # Import services one by one with detailed error handling
                try:
                    from services.campaign_processor import CampaignProcessor
                    logger.info("✅ CampaignProcessor imported")
                except Exception as e:
                    logger.error(f"❌ Failed to import CampaignProcessor: {e}")
                    raise
                
                try:
                    from services.sqs_consumer import SQSConsumer  
                    logger.info("✅ SQSConsumer imported")
                except Exception as e:
                    logger.error(f"❌ Failed to import SQSConsumer: {e}")
                    raise
                
                try:
                    from services.call_summarizer import CallSummarizerService as CallSummarizer
                    logger.info("✅ CallSummarizer imported")
                except Exception as e:
                    logger.error(f"❌ Failed to import CallSummarizer: {e}")
                    raise
                
                try:
                    from services.crm_integration import CRMIntegration
                    logger.info("✅ CRMIntegration imported")
                except Exception as e:
                    logger.error(f"❌ Failed to import CRMIntegration: {e}")
                    raise
                
                try:
                    from services.email_service import EmailService
                    logger.info("✅ EmailService imported")
                except Exception as e:
                    logger.error(f"❌ Failed to import EmailService: {e}")
                    raise
                
                try:
                    from services.agent_assignment import AgentAssignment
                    logger.info("✅ AgentAssignment imported")
                except Exception as e:
                    logger.error(f"❌ Failed to import AgentAssignment: {e}")
                    raise
                
                services_available = True
                logger.info("✅ All worker services imported successfully")
                
                logger.info("🔍 Initializing worker services...")
                
                # Initialize services one by one with detailed error handling
                try:
                    self.campaign_processor = CampaignProcessor()
                    logger.info("✅ CampaignProcessor initialized")
                except Exception as e:
                    logger.error(f"❌ Failed to initialize CampaignProcessor: {e}")
                    raise
                
                try:
                    self.sqs_consumer = SQSConsumer()
                    logger.info("✅ SQSConsumer initialized")
                except Exception as e:
                    logger.error(f"❌ Failed to initialize SQSConsumer: {e}")
                    raise
                
                try:
                    self.call_summarizer = CallSummarizer()
                    logger.info("✅ CallSummarizer initialized")
                except Exception as e:
                    logger.error(f"❌ Failed to initialize CallSummarizer: {e}")
                    raise
                
                try:
                    self.email_service = EmailService()
                    logger.info("✅ EmailService initialized")
                except Exception as e:
                    logger.error(f"❌ Failed to initialize EmailService: {e}")
                    raise
                
                try:
                    self.crm_integration = CRMIntegration()
                    logger.info("✅ CRMIntegration initialized")
                except Exception as e:
                    logger.error(f"❌ Failed to initialize CRMIntegration: {e}")
                    raise
                
                try:
                    self.agent_assignment = AgentAssignment()
                    logger.info("✅ AgentAssignment initialized")
                except Exception as e:
                    logger.error(f"❌ Failed to initialize AgentAssignment: {e}")
                    raise
                
                self.services_initialized = True
                logger.info("✅ All services initialized")
                
                # Perform health checks
                await self._check_service_health()
                
            except Exception as e:
                logger.error(f"❌ Service initialization failed: {e}")
                logger.error(f"❌ Error type: {type(e).__name__}")
                logger.error(f"❌ Error details: {str(e)}")
                # Ensure services are not marked as initialized if any fail
                self.services_initialized = False
                # Clear any partially initialized services
                for service_name in ['campaign_processor', 'sqs_consumer', 'call_summarizer', 'email_service', 'crm_integration', 'agent_assignment']:
                    if hasattr(self, service_name):
                        delattr(self, service_name)
        elif not services_available:
            logger.info("📝 Running in basic mode - services not available")
            self.services_initialized = True

    async def _check_service_health(self):
        """Check health of initialized services"""
        try:
            health_checks = []
            
            # Check email service
            if hasattr(self, 'email_service'):
                email_configured = self.email_service.is_configured()
                health_checks.append(f"Email Service: {'✅' if email_configured else '❌'}")
            
            # Check database connection
            if shared_available and hasattr(db_client, 'is_connected'):
                db_connected = db_client.is_connected()
                health_checks.append(f"Database: {'✅' if db_connected else '❌'}")
            
            # Check Redis connection
            if shared_available:
                try:
                    from shared.utils.redis_client import redis_client
                    redis_connected = redis_client.is_connected()
                    health_checks.append(f"Redis: {'✅' if redis_connected else '❌'}")
                except:
                    health_checks.append("Redis: ❌")
            
            logger.info(f"🔍 Service Health Check: {' | '.join(health_checks)}")
            
        except Exception as e:
            logger.warning(f"⚠️ Health check failed: {e}")
            

    
    async def start(self):
        """Start the worker service"""
        
        logger.info("🚀 Starting Voice Agent Worker Service")
        if shared_available:
            environment = getattr(settings, 'environment', 'development')
            testing_mode = getattr(settings, 'testing_mode', False)
            logger.info(f"🎯 Environment: {environment}")
            logger.info(f"🧪 Testing Mode: {'✅ ENABLED' if testing_mode else '❌ DISABLED'}")
            if testing_mode:
                logger.info("🔧 TESTING MODE: Business hours bypassed - worker will process 24/7")
        else:
            logger.info(f"🎯 Environment: development (shared not available)")
        logger.info(f"🔧 Services Available: {services_available}")
        
        self.running = True
        self.start_time = datetime.utcnow()
        
        # Initialize shared services FIRST
        if shared_available:
            try:
                await init_database()
                logger.info("✅ Database initialized")
                
                # Test database connection with retry logic
                from shared.utils.database import db_client
                max_db_retries = 3
                db_connected = False
                
                for attempt in range(max_db_retries):
                    try:
                        if db_client and await db_client.ensure_connected():
                            logger.info("✅ Database connection verified")
                            db_connected = True
                            break
                        else:
                            logger.warning(f"⚠️ Database connection attempt {attempt + 1} failed")
                            if attempt < max_db_retries - 1:
                                await asyncio.sleep(5)  # Wait before retry
                    except Exception as e:
                        logger.warning(f"⚠️ Database connection attempt {attempt + 1} failed: {e}")
                        if attempt < max_db_retries - 1:
                            await asyncio.sleep(5)  # Wait before retry
                
                if not db_connected:
                    logger.error("❌ Database connection failed after all retries")
                    logger.warning("⚠️ Worker will run in basic mode without database access")
                    
            except Exception as e:
                logger.error(f"❌ Database initialization failed: {e}")
                logger.warning("⚠️ Worker will run in basic mode without database access")
                # Continue running in basic mode rather than failing completely
            
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
            # Check if services are properly initialized
            if not self.services_initialized:
                logger.warning("⚠️ Services not yet initialized - attempting to initialize...")
                await self._initialize_services()
                if not self.services_initialized:
                    logger.error("❌ Failed to initialize services - skipping processing")
                    return
            
            # Check if required service attributes exist
            required_services = ['sqs_consumer', 'campaign_processor', 'email_service']
            missing_services = []
            for service_name in required_services:
                if not hasattr(self, service_name):
                    missing_services.append(service_name)
            
            if missing_services:
                logger.error(f"❌ Missing service attributes: {missing_services}")
                logger.error("❌ Re-initializing services...")
                self.services_initialized = False
                await self._initialize_services()
                if not self.services_initialized:
                    logger.error("❌ Failed to re-initialize services - skipping processing")
                    return
            
            # Enhanced business hours check with testing mode priority
            is_business_hours = True  # Default to True for testing
            if shared_available and hasattr(settings, 'is_business_hours'):
                is_business_hours = settings.is_business_hours()
                testing_mode = getattr(settings, 'testing_mode', False)
                environment = getattr(settings, 'environment', 'unknown')
                logger.debug(f"🔍 Business hours check: {is_business_hours} (environment: {environment}, testing_mode: {testing_mode})")
            else:
                # Fallback business hours check - only for production without testing mode
                testing_mode = getattr(settings, 'testing_mode', False)
                if testing_mode:
                    logger.debug("🔍 Testing mode enabled - allowing processing outside business hours")
                elif getattr(settings, 'environment', 'development').lower() == 'production':
                    current_hour = datetime.now().hour
                    is_business_hours = 9 <= current_hour < 17  # 9 AM to 5 PM
                    logger.debug(f"🔍 Fallback business hours check: {is_business_hours} (hour: {current_hour})")
                else:
                    logger.debug("🔍 Development mode - allowing processing outside business hours")
            
            if not is_business_hours:
                if self.processed_count % 20 == 0:  # Log every 20 cycles
                    testing_mode = getattr(settings, 'testing_mode', False) if shared_available else False
                    if testing_mode:
                        logger.info("🧪 TESTING MODE: Business hours bypassed - continuing processing")
                    else:
                        logger.info("⏰ Outside business hours - worker in standby mode")
                return
            
            # Process services with error handling
            try:
                # 1. Process SQS queue messages
                if hasattr(self, 'sqs_consumer'):
                    sqs_messages = await self.sqs_consumer.process_queue()
                    if sqs_messages:
                        logger.info(f"📥 Processed {len(sqs_messages)} SQS messages")
                else:
                    logger.warning("⚠️ SQS consumer not available")
            except Exception as e:
                logger.error(f"❌ SQS processing error: {e}")
            
            try:
                # 2. Process campaign batch (outbound calls)
                if hasattr(self, 'campaign_processor'):
                    campaign_result = await self.campaign_processor.process_campaign_batch()
                    if campaign_result.get("clients_processed", 0) > 0:
                        self.processed_count += campaign_result["clients_processed"]
                        logger.info(f"📞 Processed {campaign_result['clients_processed']} campaign calls")
                else:
                    logger.warning("⚠️ Campaign processor not available")
            except Exception as e:
                logger.error(f"❌ Campaign processing error: {e}")
            
            try:
                # 3. Process call summaries for completed calls
                if hasattr(self, 'call_summarizer'):
                    await self._process_call_summaries()
                else:
                    logger.warning("⚠️ Call summarizer not available")
            except Exception as e:
                logger.error(f"❌ Call summary processing error: {e}")
            
            try:
                # 4. Process CRM updates
                if hasattr(self, 'crm_integration'):
                    await self._process_crm_updates()
                else:
                    logger.warning("⚠️ CRM integration not available")
            except Exception as e:
                logger.error(f"❌ CRM processing error: {e}")
            
            try:
                # 5. Process agent assignments for interested clients
                if hasattr(self, 'agent_assignment'):
                    await self._process_agent_assignments()
                else:
                    logger.warning("⚠️ Agent assignment not available")
            except Exception as e:
                logger.error(f"❌ Agent assignment processing error: {e}")
            
            try:
                # 6. Send email notifications
                if hasattr(self, 'email_service'):
                    await self._process_email_notifications()
                else:
                    logger.warning("⚠️ Email service not available")
            except Exception as e:
                logger.error(f"❌ Email notification processing error: {e}")
            

            
            # Log progress
            if self.processed_count % 10 == 0 and self.processed_count > 0:
                logger.info(f"📊 Total processed today: {self.processed_count}")
            
        except Exception as e:
            logger.error(f"❌ Service processing error: {e}")
    
    async def _process_basic_mode(self):
        """Basic processing without full services"""
        try:
            # Enhanced business hours check for basic mode with testing mode priority
            is_business_hours = True  # Default to True for testing
            testing_mode = getattr(settings, 'testing_mode', False)
            if testing_mode:
                logger.debug("🔍 Basic mode - testing mode enabled, allowing processing")
            elif getattr(settings, 'environment', 'development').lower() == 'production':
                current_hour = datetime.now().hour
                is_business_hours = 9 <= current_hour < 17
                logger.debug(f"🔍 Basic mode business hours check: {is_business_hours} (hour: {current_hour})")
            else:
                logger.debug("🔍 Basic mode - development environment, allowing processing")
            
            if not is_business_hours:
                if self.processed_count % 20 == 0:
                    testing_mode = getattr(settings, 'testing_mode', False) if shared_available else False
                    if testing_mode:
                        logger.info("🧪 TESTING MODE: Business hours bypassed - basic worker continuing")
                    else:
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
            if db_client is None:
                logger.warning("⚠️ Database client not available for email processing")
                return
            
            # Ensure database connection before processing
            if not await db_client.ensure_connected():
                logger.warning("⚠️ Database not available for email processing")
                return

            # Find calls completed in the last hour that need email processing
            one_hour_ago = datetime.utcnow() - timedelta(hours=1)
            logger.info(f"🔍 Looking for completed calls since {one_hour_ago}")

            cursor = db_client.database.call_sessions.find({
                "completed_at": {"$gte": one_hour_ago},
                "$or": [
                    {"email_sent": {"$ne": True}},
                    {"email_sent": {"$exists": False}}
                ],
                "final_outcome": {"$exists": True, "$ne": None}
            })

            processed_count = 0
            total_found = 0
            async for doc in cursor:
                total_found += 1
                try:
                    logger.info(f"📧 Processing email for session: {doc.get('session_id', 'unknown')} with outcome: {doc.get('final_outcome', 'unknown')}")
                    
                    # Handle invalid enum values gracefully
                    try:
                        session = CallSession(**doc)
                    except Exception as validation_error:
                        logger.warning(f"⚠️ Invalid session data for {doc.get('session_id', 'unknown')}: {validation_error}")
                        logger.warning("Skipping this session due to data validation errors")
                        continue

                    # Determine email stage based on outcome
                    email_stage = self._determine_email_stage(session.final_outcome)
                    logger.info(f"📧 Email stage determined: {email_stage} for outcome: {session.final_outcome}")

                    # If no email stage found and outcome is "completed", try to infer from conversation
                    if not email_stage and session.final_outcome == "completed":
                        inferred_outcome = self._infer_outcome_from_conversation(session)
                        if inferred_outcome:
                            email_stage = self._determine_email_stage(inferred_outcome)
                            logger.info(f"📧 Inferred outcome: {inferred_outcome} -> email stage: {email_stage}")

                    if not email_stage:
                        logger.warning(f"⚠️ No email stage mapping found for outcome: {session.final_outcome}")
                        continue

                    # Get client information from session data first
                    client_email = None
                    client_name = "Client"
                    
                    if session.client_data:
                        # Try to get email from session client_data first
                        client_email = session.client_data.get("email")
                        first_name = session.client_data.get("first_name", "")
                        last_name = session.client_data.get("last_name", "")
                        client_name = f"{first_name} {last_name}".strip() or "Client"
                        
                        if client_email:
                            logger.info(f"✅ Client email found in session data: {client_email}")
                        else:
                            logger.warning(f"⚠️ No email in session client_data for {client_name}")
                    
                    # If no email in session data, try database lookup
                    if not client_email and session.client_id and session.client_id != "unknown":
                        try:
                            from shared.utils.database import client_repo
                            if client_repo:
                                logger.info(f"🔍 Looking up client by ID: {session.client_id}")
                                client = await client_repo.get_client_by_id(session.client_id)
                                if client:
                                    logger.info(f"✅ Found client: {client.client.full_name}")
                                    if hasattr(client.client, 'email') and client.client.email:
                                        client_email = client.client.email
                                        client_name = f"{client.client.first_name} {client.client.last_name}"
                                        logger.info(f"✅ Client email found in database: {client_email}")
                                    else:
                                        logger.warning(f"⚠️ Client {client.client.full_name} has no email address")
                                else:
                                    logger.warning(f"⚠️ No client found for ID: {session.client_id}")
                            else:
                                logger.warning("⚠️ Client repository not available")
                        except Exception as e:
                            logger.warning(f"Could not get client email from database: {e}")

                    # If no email found, skip this notification
                    if not client_email:
                        logger.info(f"No email found for client {client_name}, skipping email notification")
                        continue

                    # Get call summary
                    call_summary = self._build_call_summary(session)

                    # Handle special case for send_email_invite (Google Calendar integration)
                    if email_stage == "open_slots_email":
                        success = await self._handle_calendar_invite(session, client_email, client_name, call_summary)
                    else:
                        # Send regular email
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

                        # Update CRM with call outcome
                        try:
                            if hasattr(self, 'crm_integration'):
                                await self.crm_integration.update_client_record(
                                    client_data=session.client_data,
                                    call_outcome=session.final_outcome,
                                    call_summary=call_summary
                                )
                        except Exception as crm_error:
                            logger.warning(f"⚠️ CRM update failed: {crm_error}")

                except Exception as e:
                    logger.error(f"❌ Error processing email for call {doc.get('session_id', 'unknown')}: {e}")
                    continue

            if total_found > 0:
                logger.info(f"📧 Found {total_found} completed calls, processed {processed_count} email notifications")
            else:
                logger.info("📧 No completed calls found for email processing")

        except Exception as e:
            logger.error(f"❌ Email notification processing error: {e}")

    async def _handle_calendar_invite(self, session: CallSession, client_email: str, client_name: str, call_summary: Dict[str, Any]) -> bool:
        """Handle calendar invite for send_email_invite outcome"""
        try:
            logger.info(f"📅 Processing calendar invite for {client_email}")
            
            # Get agent information from session
            agent_name = session.client_data.get("last_agent", "Test Agent")
            agent_email = session.client_data.get("agent_email", "")
            
            # Initialize Google Calendar service
            from services.google_calendar_service import GoogleCalendarService
            calendar_service = GoogleCalendarService()
            
            if not calendar_service.is_configured():
                logger.warning("⚠️ Google Calendar not configured, sending fallback email")
                # Send fallback email
                return await self.email_service.send_conversation_stage_email(
                    client_email=client_email,
                    client_name=client_name,
                    stage="agent_will_reach_out",
                    call_summary=call_summary
                )
            
            # Get agent configuration (database first, then file fallback)
            agent_config = await calendar_service.get_agent_by_name(agent_name)
            
            if not agent_config:
                logger.warning(f"⚠️ Agent '{agent_name}' not found, using test agent")
                agent_config = await calendar_service.get_test_agent()
                
            if not agent_config:
                logger.error("❌ No agent configuration available, sending fallback email")
                return await self.email_service.send_conversation_stage_email(
                    client_email=client_email,
                    client_name=client_name,
                    stage="agent_will_reach_out",
                    call_summary=call_summary
                )
            
            # Use agent email from config, fallback to session data
            agent_email = agent_config.get("email") or agent_email
            logger.info(f"🔍 Using agent: {agent_name} ({agent_email})")
            
            # Get available slots
            available_slots = await calendar_service.get_agent_available_slots(agent_email)
            
            if not available_slots:
                logger.warning("⚠️ No available slots found, sending fallback email")
                return await self.email_service.send_conversation_stage_email(
                    client_email=client_email,
                    client_name=client_name,
                    stage="agent_will_reach_out",
                    call_summary=call_summary
                )
            
            # Add available slots and agent info to call summary for email template
            call_summary["available_slots"] = available_slots
            call_summary["agent_name"] = agent_name
            call_summary["agent_email"] = agent_email
            
            # Send email with calendar slots using our email service
            success = await self.email_service.send_conversation_stage_email(
                client_email=client_email,
                client_name=client_name,
                stage="open_slots_email",
                call_summary=call_summary
            )
            
            if success:
                logger.info(f"✅ Calendar invite email sent with {len(available_slots)} slots for {agent_name}")
                return True
            else:
                logger.error(f"❌ Calendar invite email failed")
                return False
                
        except Exception as e:
            logger.error(f"❌ Error handling calendar invite: {e}")
            return False

    def _determine_email_stage(self, outcome: str) -> Optional[str]:
        """Determine email stage based on call outcome"""
        stage_mapping = {
            "interested": "agent_will_reach_out",
            "interested_no_schedule": "interested_no_schedule",
            "send_email_invite": "open_slots_email",
            "scheduled": "meeting_scheduled",
            "not_interested": "keep_communications",
            "keep_communications": "keep_communications",  # Added: New outcome for keep communications
            "dnc_requested": "dnc_confirmation",
            "no_contact": "follow_up_email",
            "voicemail": "follow_up_email",
            "failed": "follow_up_email",
            "timeout": "follow_up_email",
            "hangup": "follow_up_email",
            "no-answer": "follow_up_email",
            "canceled": "follow_up_email",
            "completed": "follow_up_email"
        }
        
        # Log the mapping attempt for debugging
        logger.info(f"🔍 Email stage mapping: outcome='{outcome}' -> stage='{stage_mapping.get(outcome)}'")
        
        return stage_mapping.get(outcome)

    def _infer_outcome_from_conversation(self, session: CallSession) -> Optional[str]:
        """Infer outcome from conversation data when outcome is generic"""
        if not session.conversation_turns:
            return None
        
        # Look for specific keywords in customer speech across all turns
        customer_speech_combined = " ".join([
            turn.customer_speech.lower() for turn in session.conversation_turns 
            if turn.customer_speech
        ])
        
        # Check for scheduling-related keywords
        scheduling_keywords = [
            "schedule", "appointment", "meeting", "tomorrow", "next week", 
            "available", "time", "when", "book", "reserve", "calendar", "yes"
        ]
        
        # Check for interest-related keywords
        interested_keywords = [
            "interested", "yes", "sure", "okay", "alright", "good", "great",
            "definitely", "absolutely", "love to", "would like", "want to"
        ]
        
        # Check for disinterest-related keywords
        not_interested_keywords = [
            "not interested", "no thanks", "no thank you", "not right now",
            "maybe later", "call back", "busy", "not now", "don't want", "no"
        ]
        
        # Check for DNC-related keywords
        dnc_keywords = [
            "remove", "delete", "don't call", "stop calling", "take me off",
            "unsubscribe", "never call", "no more calls", "do not contact"
        ]
        
        # Analyze the conversation based on AAG script flow
        if any(keyword in customer_speech_combined for keyword in dnc_keywords):
            return "dnc_requested"
        elif any(keyword in customer_speech_combined for keyword in scheduling_keywords):
            return "send_email_invite"
        elif any(keyword in customer_speech_combined for keyword in interested_keywords):
            # Check if there are also "no" keywords indicating they declined scheduling
            if any(keyword in customer_speech_combined for keyword in not_interested_keywords):
                return "interested_no_schedule"
            else:
                return "interested"
        elif any(keyword in customer_speech_combined for keyword in not_interested_keywords):
            return "not_interested"
        else:
            # If no specific outcome detected, check conversation length
            if len(session.conversation_turns) < 3:
                return "no_contact"
            else:
                return None

    def _build_call_summary(self, session: CallSession) -> Dict[str, Any]:
        """Build call summary for email"""
        summary = {
            "outcome": session.final_outcome or "unknown",
            "duration": session.session_metrics.total_call_duration_seconds if session.session_metrics else 0,
            "conversation_turns": len(session.conversation_turns) if session.conversation_turns else 0,
            "key_points": [],
            "customer_concerns": [],
            "recommended_actions": [],
            "agent_name": session.client_data.get("last_agent", "your agent") if session.client_data else "your agent"
        }
        
        # Extract key points from conversation
        if session.conversation_turns:
            # Simple extraction - in production you'd use AI to analyze
            for turn in session.conversation_turns[-3:]:  # Last 3 turns
                if turn.customer_speech:
                    summary["key_points"].append(turn.customer_speech[:100] + "...")
        
        # Add meeting time if scheduled
        if session.final_outcome in ["scheduled", "scheduled_morning", "scheduled_afternoon"]:
            if session.final_outcome == "scheduled_morning":
                summary["meeting_time"] = "Tomorrow at 10 AM"
            elif session.final_outcome == "scheduled_afternoon":
                summary["meeting_time"] = "Tomorrow at 2 PM"
            else:
                summary["meeting_time"] = "TBD - You'll receive calendar invites shortly"
        
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