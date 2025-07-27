"""
Campaign Processing Service
Handles outbound call initiation and campaign management
"""

import asyncio
import logging
import time
import uuid
from typing import List, Dict, Any, Optional
from datetime import datetime, timedelta
from twilio.rest import Client as TwilioClient
from twilio.base.exceptions import TwilioRestException

from shared.config.settings import settings
from shared.models.client import Client, CampaignStatus, CallOutcome, CRMTag
from shared.utils.database import client_repo, session_repo
from shared.utils.redis_client import metrics_cache

logger = logging.getLogger(__name__)

class CampaignProcessor:
    """Processes campaign queue and initiates outbound calls"""
    
    def __init__(self):
        # Initialize Twilio client
        if settings.twilio_account_sid and settings.twilio_auth_token:
            self.twilio_client = TwilioClient(
                settings.twilio_account_sid,
                settings.twilio_auth_token
            )
        else:
            self.twilio_client = None
            logger.warning("⚠️ Twilio credentials not configured")
        
        # Campaign statistics
        self.calls_initiated = 0
        self.calls_failed = 0
        self.clients_processed = 0
        self.campaign_start_time = None
    
    async def process_campaign_batch(self, batch_size: int = 50) -> Dict[str, Any]:
        """Process a batch of clients for calling"""
        
        if not settings.is_business_hours():
            logger.info("⏰ Outside business hours - skipping campaign processing")
            return {"skipped": True, "reason": "outside_business_hours"}
        
        if not self.twilio_client:
            logger.error("❌ Twilio not configured - cannot process campaign")
            return {"error": "twilio_not_configured"}
        
        try:
            # Get clients ready for calling
            clients = await client_repo.get_clients_for_campaign(limit=batch_size)
            
            if not clients:
                logger.info("📋 No clients ready for calling")
                return {
                    "success": True,
                    "clients_processed": 0,
                    "message": "No clients ready for calling"
                }
            
            logger.info(f"🎯 Processing {len(clients)} clients for calling")
            
            # Process each client
            results = []
            for client in clients:
                result = await self._process_single_client(client)
                results.append(result)
                
                # Small delay between calls to avoid overwhelming Twilio
                await asyncio.sleep(1)
            
            # Calculate summary
            successful_calls = sum(1 for r in results if r.get("call_initiated"))
            failed_calls = len(results) - successful_calls
            
            # Update statistics
            self.calls_initiated += successful_calls
            self.calls_failed += failed_calls
            self.clients_processed += len(clients)
            
            # Record metrics
            if metrics_cache:
                await metrics_cache.record_daily_stat("calls_initiated", successful_calls)
                await metrics_cache.record_daily_stat("calls_failed", failed_calls)
                await metrics_cache.record_daily_stat("clients_processed", len(clients))
            
            logger.info(f"✅ Batch complete: {successful_calls} calls initiated, {failed_calls} failed")
            
            return {
                "success": True,
                "clients_processed": len(clients),
                "calls_initiated": successful_calls,
                "calls_failed": failed_calls,
                "results": results
            }
            
        except Exception as e:
            logger.error(f"❌ Campaign batch processing error: {e}")
            return {"error": str(e)}
    
    async def _process_single_client(self, client: Client) -> Dict[str, Any]:
        """Process a single client for calling"""
        
        try:
            logger.info(f"📞 Processing client: {client.client.full_name} ({client.client.phone})")
            
            # Check if client should be called
            if not client.should_attempt_call():
                logger.info(f"⏭️ Skipping client: {client.client.full_name} (max attempts or DNC)")
                return {
                    "client_id": client.id,
                    "client_name": client.client.full_name,
                    "skipped": True,
                    "reason": "max_attempts_or_dnc"
                }
            
            # Update client status to in_progress
            await client_repo.update_client(client.id, {
                "campaignStatus": CampaignStatus.IN_PROGRESS.value
            })
            
            # Initiate Twilio call
            call_result = await self._initiate_twilio_call(client)
            
            if call_result["success"]:
                logger.info(f"✅ Call initiated for {client.client.full_name}: {call_result['call_sid']}")
                
                # Record call attempt
                await self._record_call_attempt(client, call_result)
                
                return {
                    "client_id": client.id,
                    "client_name": client.client.full_name,
                    "call_initiated": True,
                    "call_sid": call_result["call_sid"],
                    "phone_number": client.client.phone
                }
            
            else:
                logger.error(f"❌ Call failed for {client.client.full_name}: {call_result['error']}")
                
                # Record failed attempt
                await self._record_failed_attempt(client, call_result["error"])
                
                return {
                    "client_id": client.id,
                    "client_name": client.client.full_name,
                    "call_initiated": False,
                    "error": call_result["error"]
                }
                
        except Exception as e:
            logger.error(f"❌ Error processing client {client.id}: {e}")
            return {
                "client_id": client.id,
                "error": str(e)
            }
    
    async def _initiate_twilio_call(self, client: Client) -> Dict[str, Any]:
        """Initiate a Twilio call to the client"""
        
        try:
            # Get webhook URL
            webhook_url = settings.get_webhook_url("voice")
            status_callback_url = settings.get_webhook_url("status")
            
            logger.info(f"📞 Calling {client.client.phone} with webhook: {webhook_url}")
            
            # Create Twilio call
            call = self.twilio_client.calls.create(
                to=client.client.phone,
                from_=settings.twilio_phone_number,
                url=webhook_url,
                method='POST',
                status_callback=status_callback_url,
                status_callback_event=['initiated', 'ringing', 'answered', 'completed'],
                status_callback_method='POST',
                timeout=30,  # Ring for 30 seconds
                record=False  # Don't record calls for privacy
            )
            
            return {
                "success": True,
                "call_sid": call.sid,
                "status": call.status,
                "direction": call.direction
            }
            
        except TwilioRestException as e:
            logger.error(f"Twilio error calling {client.client.phone}: {e}")
            
            # Handle specific Twilio errors
            error_message = str(e)
            if "invalid phone number" in error_message.lower():
                # Mark as invalid number
                await client_repo.add_crm_tag(client.id, CRMTag.INVALID_NUMBER)
                error_type = "invalid_number"
            elif "blacklisted" in error_message.lower():
                # Mark as DNC
                await client_repo.add_crm_tag(client.id, CRMTag.DNC_REQUESTED)
                error_type = "blacklisted"
            else:
                error_type = "twilio_error"
            
            return {
                "success": False,
                "error": error_message,
                "error_type": error_type
            }
            
        except Exception as e:
            logger.error(f"General error calling {client.client.phone}: {e}")
            return {
                "success": False,
                "error": str(e),
                "error_type": "general_error"
            }
    
    async def _record_call_attempt(self, client: Client, call_result: Dict[str, Any]):
        """Record a successful call attempt"""
        
        call_attempt = {
            "attempt_number": client.total_attempts + 1,
            "timestamp": datetime.utcnow(),
            "outcome": CallOutcome.NO_ANSWER.value,  # Will be updated by webhook
            "twilio_call_sid": call_result["call_sid"],
            "error_message": None,
            "call_initiated": True
        }
        
        await client_repo.add_call_attempt(client.id, call_attempt)
    
    async def _record_failed_attempt(self, client: Client, error_message: str):
        """Record a failed call attempt"""
        
        call_attempt = {
            "attempt_number": client.total_attempts + 1,
            "timestamp": datetime.utcnow(),
            "outcome": CallOutcome.FAILED.value,
            "twilio_call_sid": None,
            "error_message": error_message,
            "call_initiated": False
        }
        
        await client_repo.add_call_attempt(client.id, call_attempt)
        
        # If max attempts reached, mark as completed
        if client.total_attempts + 1 >= settings.max_call_attempts:
            await client_repo.update_client(client.id, {
                "campaignStatus": CampaignStatus.COMPLETED.value
            })
            await client_repo.add_crm_tag(client.id, CRMTag.NO_CONTACT)
    
    async def get_campaign_progress(self) -> Dict[str, Any]:
        """Get current campaign progress"""
        
        try:
            # Get overall statistics from database
            stats = await client_repo.get_campaign_stats()
            
            # Add processor statistics
            runtime_stats = {
                "calls_initiated": self.calls_initiated,
                "calls_failed": self.calls_failed,
                "clients_processed": self.clients_processed,
                "success_rate": (self.calls_initiated / max(self.clients_processed, 1)) * 100,
                "campaign_start_time": self.campaign_start_time.isoformat() if self.campaign_start_time else None
            }
            
            return {
                "campaign_stats": stats,
                "processor_stats": runtime_stats,
                "business_hours": settings.is_business_hours(),
                "current_time": datetime.utcnow().isoformat()
            }
            
        except Exception as e:
            logger.error(f"Error getting campaign progress: {e}")
            return {"error": str(e)}
    
    async def pause_campaign(self) -> Dict[str, Any]:
        """Pause the campaign"""
        logger.info("⏸️ Campaign paused by request")
        return {"success": True, "message": "Campaign paused"}
    
    async def resume_campaign(self) -> Dict[str, Any]:
        """Resume the campaign"""
        logger.info("▶️ Campaign resumed by request")
        if self.campaign_start_time is None:
            self.campaign_start_time = datetime.utcnow()
        return {"success": True, "message": "Campaign resumed"}
    
    def start_campaign(self):
        """Mark campaign as started"""
        self.campaign_start_time = datetime.utcnow()
        logger.info(f"🚀 Campaign started at {self.campaign_start_time}")
    
    async def cleanup_old_calls(self, hours_old: int = 24) -> int:
        """Clean up old call records and sessions"""
        
        try:
            cutoff_time = datetime.utcnow() - timedelta(hours=hours_old)
            
            # This would clean up old sessions from Redis
            # and mark very old pending calls as failed
            
            # For now, just return 0
            return 0
            
        except Exception as e:
            logger.error(f"Error cleaning up old calls: {e}")
            return 0