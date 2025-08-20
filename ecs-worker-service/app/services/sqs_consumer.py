"""
SQS Consumer Service
Handles SQS queue processing for campaign management
"""

import asyncio
import json
import logging
from typing import List, Dict, Any, Optional
from datetime import datetime

# For local development without AWS
try:
    import boto3
    from botocore.exceptions import ClientError, NoCredentialsError
    AWS_AVAILABLE = True
except ImportError:
    AWS_AVAILABLE = False
    logger = logging.getLogger(__name__)
    logger.warning("⚠️ boto3 not available - SQS will be mocked")

from shared.config.settings import settings
from shared.utils.database import client_repo
from shared.utils.database import db_client

logger = logging.getLogger(__name__)

class SQSConsumer:
    """Consumes messages from SQS queue for campaign processing"""
    
    def __init__(self):
        self.sqs_client = None
        self.queue_url = None
        
        # Check if we're in development mode or if AWS credentials are not available
        is_development = getattr(settings, 'environment', 'development').lower() == 'development'
        
        # Initialize SQS client if AWS is available, configured, and we're in production
        if AWS_AVAILABLE and settings.aws_region and not is_development:
            try:
                self.sqs_client = boto3.client('sqs', region_name=settings.aws_region)
                # Use configured SQS queue URL from settings
                if settings.sqs_queue_url:
                    self.queue_url = settings.sqs_queue_url
                    logger.info(f"✅ SQS client initialized with queue: {self.queue_url}")
                else:
                    # Fallback to hardcoded URL if not configured
                    self.queue_url = f"https://sqs.{settings.aws_region}.amazonaws.com/{settings.aws_account_id}/voice-agent-campaign-queue"
                    logger.warning(f"⚠️ SQS_QUEUE_URL not configured, using fallback: {self.queue_url}")
            except (NoCredentialsError, Exception) as e:
                logger.warning(f"⚠️ SQS not available: {e}")
                self.sqs_client = None
        else:
            if is_development:
                logger.info("🔧 Running in development mode - SQS operations will be mocked")
            else:
                logger.info("🔧 AWS not configured - SQS operations will be mocked")
    
    async def process_queue(self, max_messages: int = 10) -> List[Dict[str, Any]]:
        """Process messages from SQS queue"""
        
        if not self.sqs_client:
            # Mock queue processing for local development
            return await self._mock_queue_processing()
        
        try:
            # Receive messages from SQS
            response = self.sqs_client.receive_message(
                QueueUrl=self.queue_url,
                MaxNumberOfMessages=max_messages,
                WaitTimeSeconds=5,  # Long polling
                VisibilityTimeout=300  # 5 minutes to process
            )
            
            messages = response.get('Messages', [])
            processed_messages = []
            
            for message in messages:
                try:
                    # Process individual message
                    processed = await self._process_message(message)
                    if processed:
                        processed_messages.append(processed)
                        
                        # Delete message from queue after successful processing
                        self.sqs_client.delete_message(
                            QueueUrl=self.queue_url,
                            ReceiptHandle=message['ReceiptHandle']
                        )
                        
                except Exception as e:
                    logger.error(f"❌ Error processing SQS message: {e}")
                    # Message will become visible again after visibility timeout
            
            return processed_messages
            
        except ClientError as e:
            error_code = e.response['Error']['Code']
            if error_code == 'AWS.SimpleQueueService.NonExistentQueue':
                logger.warning(f"⚠️ SQS queue does not exist: {self.queue_url}")
                logger.info("🔧 Falling back to mock queue processing")
                return await self._mock_queue_processing()
            else:
                logger.error(f"❌ SQS error: {e}")
            return []
        except Exception as e:
            logger.error(f"❌ Queue processing error: {e}")
            return []
    
    async def _process_message(self, message: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        """Process individual SQS message"""
        
        try:
            # Parse message body
            body = json.loads(message['Body'])
            message_type = body.get('type', 'unknown')
            
            logger.info(f"📥 Processing SQS message: {message_type}")
            
            if message_type == 'start_campaign':
                return await self._handle_start_campaign(body)
            
            elif message_type == 'process_client_batch':
                return await self._handle_client_batch(body)
            
            elif message_type == 'update_client_status':
                return await self._handle_client_status_update(body)
            
            elif message_type == 'pause_campaign':
                return await self._handle_pause_campaign(body)
            
            elif message_type == 'resume_campaign':
                return await self._handle_resume_campaign(body)
            
            else:
                logger.warning(f"⚠️ Unknown message type: {message_type}")
                return None
                
        except json.JSONDecodeError as e:
            logger.error(f"❌ Invalid JSON in SQS message: {e}")
            return None
        except Exception as e:
            logger.error(f"❌ Error processing message: {e}")
            return None
    
    async def _handle_start_campaign(self, body: Dict[str, Any]) -> Dict[str, Any]:
        """Handle campaign start message"""
        
        campaign_id = body.get('campaign_id', 'default')
        batch_size = body.get('batch_size', 50)
        
        logger.info(f"🚀 Starting campaign: {campaign_id} with batch size: {batch_size}")
        
        # Ensure database connection before processing
        if not await db_client.ensure_connected():
            logger.error("❌ Cannot process campaign - database not available")
            return {
                "type": "start_campaign",
                "campaign_id": campaign_id,
                "error": "Database not available",
                "processed_at": datetime.utcnow().isoformat()
            }
        
        # Update clients to ready status
        ready_count = await client_repo.mark_clients_ready_for_campaign(batch_size)
        
        return {
            "type": "start_campaign",
            "campaign_id": campaign_id,
            "clients_marked_ready": ready_count,
            "processed_at": datetime.utcnow().isoformat()
        }
    
    async def _handle_client_batch(self, body: Dict[str, Any]) -> Dict[str, Any]:
        """Handle client batch processing message"""
        
        client_ids = body.get('client_ids', [])
        
        logger.info(f"📋 Processing client batch: {len(client_ids)} clients")
        
        processed_count = 0
        for client_id in client_ids:
            try:
                # Mark client as ready for processing
                await client_repo.update_client_campaign_status(client_id, "ready")
                processed_count += 1
            except Exception as e:
                logger.error(f"❌ Error updating client {client_id}: {e}")
        
        return {
            "type": "process_client_batch",
            "clients_processed": processed_count,
            "total_clients": len(client_ids),
            "processed_at": datetime.utcnow().isoformat()
        }
    
    async def _handle_client_status_update(self, body: Dict[str, Any]) -> Dict[str, Any]:
        """Handle client status update message"""
        
        client_id = body.get('client_id')
        new_status = body.get('status')
        
        if client_id and new_status:
            try:
                await client_repo.update_client_campaign_status(client_id, new_status)
                logger.info(f"✅ Updated client {client_id} status to: {new_status}")
                
                return {
                    "type": "update_client_status",
                    "client_id": client_id,
                    "status": new_status,
                    "success": True,
                    "processed_at": datetime.utcnow().isoformat()
                }
            except Exception as e:
                logger.error(f"❌ Error updating client status: {e}")
                return {
                    "type": "update_client_status",
                    "client_id": client_id,
                    "success": False,
                    "error": str(e)
                }
        
        return None
    
    async def _handle_pause_campaign(self, body: Dict[str, Any]) -> Dict[str, Any]:
        """Handle campaign pause message"""
        
        campaign_id = body.get('campaign_id', 'default')
        
        logger.info(f"⏸️ Pausing campaign: {campaign_id}")
        
        # Update campaign status in database
        # This would pause new call initiations
        
        return {
            "type": "pause_campaign",
            "campaign_id": campaign_id,
            "paused_at": datetime.utcnow().isoformat()
        }
    
    async def _handle_resume_campaign(self, body: Dict[str, Any]) -> Dict[str, Any]:
        """Handle campaign resume message"""
        
        campaign_id = body.get('campaign_id', 'default')
        
        logger.info(f"▶️ Resuming campaign: {campaign_id}")
        
        # Update campaign status in database
        # This would resume call initiations
        
        return {
            "type": "resume_campaign",
            "campaign_id": campaign_id,
            "resumed_at": datetime.utcnow().isoformat()
        }
    
    async def _mock_queue_processing(self) -> List[Dict[str, Any]]:
        """Mock queue processing for local development"""
        
        # Simulate periodic campaign start messages during business hours
        if settings.is_business_hours():
            current_time = datetime.utcnow()
            
            # Every 5 minutes during business hours, simulate a batch message
            if current_time.minute % 5 == 0:
                return [{
                    "type": "start_campaign",
                    "campaign_id": "mock_campaign",
                    "clients_marked_ready": 10,
                    "processed_at": current_time.isoformat(),
                    "mock": True
                }]
        
        return []
    
    async def send_message(self, message_type: str, payload: Dict[str, Any]) -> bool:
        """Send message to SQS queue"""
        
        if not self.sqs_client:
            logger.info(f"🔧 Mock sending SQS message: {message_type}")
            return True
        
        try:
            message_body = {
                "type": message_type,
                "timestamp": datetime.utcnow().isoformat(),
                **payload
            }
            
            response = self.sqs_client.send_message(
                QueueUrl=self.queue_url,
                MessageBody=json.dumps(message_body)
            )
            
            logger.info(f"✅ Sent SQS message: {message_type}")
            return True
            
        except Exception as e:
            logger.error(f"❌ Error sending SQS message: {e}")
            return False
    
    async def close(self):
        """Close SQS client"""
        if self.sqs_client:
            # SQS client doesn't need explicit closing
            logger.info("✅ SQS consumer closed")
        else:
            logger.info("✅ Mock SQS consumer closed")