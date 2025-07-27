"""
CRM Integration Service
Handles Capsule CRM operations and Google Calendar scheduling
"""

import asyncio
import httpx
import json
import logging
from typing import Dict, Any, Optional, List
from datetime import datetime, timedelta

from shared.config.settings import settings
from shared.models.client import Client, CRMTag
from shared.utils.database import client_repo

logger = logging.getLogger(__name__)

class CRMIntegrationService:
    """Service for CRM operations and agent assignment"""
    
    def __init__(self):
        # HTTP clients
        self.capsule_session = httpx.AsyncClient(
            base_url=settings.capsule_api_url,
            timeout=10.0
        )
        self.google_session = httpx.AsyncClient(timeout=10.0)
        
        # Load agent configuration
        self.agents = self._load_agent_config()
        
        # Statistics
        self.crm_updates = 0
        self.agent_assignments = 0
        self.meetings_scheduled = 0
    
    def _load_agent_config(self) -> List[Dict[str, Any]]:
        """Load agent configuration from file"""
        try:
            import json
            with open("data/agents.json", "r") as f:
                config = json.load(f)
                return config.get("agents", [])
        except Exception as e:
            logger.error(f"Failed to load agent config: {e}")
            return []
    
    async def process_interested_client(
        self, 
        client: Client,
        call_summary: Optional[Dict[str, Any]] = None
    ) -> Dict[str, Any]:
        """Complete workflow for interested client"""
        
        logger.info(f"💼 Processing interested client: {client.client.full_name}")
        
        try:
            results = {}
            
            # 1. Update CRM with interested tag
            crm_result = await self._update_crm_tags(client, [CRMTag.INTERESTED])
            results["crm_update"] = crm_result
            
            # 2. Assign to agent (use last agent or round-robin)
            agent_result = await self._assign_agent(client)
            results["agent_assignment"] = agent_result
            
            if agent_result["success"]:
                # 3. Schedule discovery call
                meeting_result = await self._schedule_discovery_call(
                    client, 
                    agent_result["agent"],
                    call_summary
                )
                results["meeting_scheduling"] = meeting_result
                
                # 4. Send notifications
                notification_result = await self._send_notifications(
                    client,
                    agent_result["agent"], 
                    meeting_result.get("meeting_time"),
                    call_summary
                )
                results["notifications"] = notification_result
            
            # Update statistics
            if results["crm_update"]["success"]:
                self.crm_updates += 1
            if results["agent_assignment"]["success"]:
                self.agent_assignments += 1
            if results.get("meeting_scheduling", {}).get("success"):
                self.meetings_scheduled += 1
            
            logger.info(f"✅ Interested client processing complete: {client.client.full_name}")
            
            return {
                "success": True,
                "client_id": client.id,
                "client_name": client.client.full_name,
                "results": results
            }
            
        except Exception as e:
            logger.error(f"❌ Error processing interested client {client.id}: {e}")
            return {
                "success": False,
                "client_id": client.id,
                "error": str(e)
            }
    
    async def _update_crm_tags(self, client: Client, tags: List[CRMTag]) -> Dict[str, Any]:
        """Update CRM tags for client"""
        
        try:
            # Update local database
            for tag in tags:
                await client_repo.add_crm_tag(client.id, tag)
            
            # Update Capsule CRM if configured
            if settings.capsule_api_key and not settings.capsule_api_key.startswith("your_"):
                capsule_result = await self._update_capsule_crm(client, tags)
                
                return {
                    "success": True,
                    "local_update": True,
                    "capsule_update": capsule_result["success"],
                    "tags_added": [tag.value for tag in tags]
                }
            else:
                return {
                    "success": True,
                    "local_update": True,
                    "capsule_update": False,
                    "message": "Capsule CRM not configured",
                    "tags_added": [tag.value for tag in tags]
                }
                
        except Exception as e:
            logger.error(f"CRM tag update error: {e}")
            return {"success": False, "error": str(e)}
    
    async def _update_capsule_crm(self, client: Client, tags: List[CRMTag]) -> Dict[str, Any]:
        """Update Capsule CRM with tags"""
        
        try:
            # First, find or create person in Capsule
            person_result = await self._find_or_create_capsule_person(client)
            
            if not person_result["success"]:
                return person_result
            
            person_id = person_result["person_id"]
            
            # Add tags to person
            headers = {
                "Authorization": f"Bearer {settings.capsule_api_key}",
                "Content-Type": "application/json"
            }
            
            for tag in tags:
                tag_data = {
                    "tag": {
                        "name": tag.value,
                        "description": f"Voice Agent Campaign - {datetime.utcnow().strftime('%Y-%m-%d')}"
                    }
                }
                
                response = await self.capsule_session.post(
                    f"/api/v2/parties/{person_id}/tags",
                    headers=headers,
                    json=tag_data
                )
                
                if response.status_code not in [200, 201]:
                    logger.warning(f"Failed to add tag {tag.value}: {response.status_code}")
            
            return {"success": True, "person_id": person_id}
            
        except Exception as e:
            logger.error(f"Capsule CRM update error: {e}")
            return {"success": False, "error": str(e)}
    
    async def _find_or_create_capsule_person(self, client: Client) -> Dict[str, Any]:
        """Find or create person in Capsule CRM"""
        
        try:
            headers = {
                "Authorization": f"Bearer {settings.capsule_api_key}",
                "Content-Type": "application/json"
            }
            
            # Search for existing person by email
            search_response = await self.capsule_session.get(
                f"/api/v2/parties",
                headers=headers,
                params={"q": client.client.email, "embed": "fields"}
            )
            
            if search_response.status_code == 200:
                data = search_response.json()
                if data.get("parties"):
                    person_id = data["parties"][0]["id"]
                    logger.info(f"Found existing Capsule person: {person_id}")
                    return {"success": True, "person_id": person_id, "created": False}
            
            # Create new person
            person_data = {
                "party": {
                    "type": "person",
                    "firstName": client.client.first_name,
                    "lastName": client.client.last_name,
                    "emailAddresses": [{"address": client.client.email}],
                    "phoneNumbers": [{"number": client.client.phone}]
                }
            }
            
            create_response = await self.capsule_session.post(
                "/api/v2/parties",
                headers=headers,
                json=person_data
            )
            
            if create_response.status_code in [200, 201]:
                person_id = create_response.json()["party"]["id"]
                logger.info(f"Created new Capsule person: {person_id}")
                
                # Update client record with Capsule ID
                await client_repo.update_client(client.id, {
                    "capsule_person_id": person_id
                })
                
                return {"success": True, "person_id": person_id, "created": True}
            
            return {"success": False, "error": f"Failed to create person: {create_response.status_code}"}
            
        except Exception as e:
            return {"success": False, "error": str(e)}
    
    async def _assign_agent(self, client: Client) -> Dict[str, Any]:
        """Assign client to an agent"""
        
        try:
            # Get agent (prefer last agent, fallback to round-robin)
            agent = self._get_agent_for_client(client)
            
            if not agent:
                return {"success": False, "error": "No agents available"}
            
            # Update client record
            await client_repo.assign_agent(client.id, agent["id"])
            
            logger.info(f"👤 Assigned {client.client.full_name} to {agent['name']}")
            
            return {
                "success": True,
                "agent": agent,
                "assignment_reason": "last_agent" if agent["id"] == client.client.last_agent else "round_robin"
            }
            
        except Exception as e:
            logger.error(f"Agent assignment error: {e}")
            return {"success": False, "error": str(e)}
    
    def _get_agent_for_client(self, client: Client) -> Optional[Dict[str, Any]]:
        """Get the best agent for a client"""
        
        if not self.agents:
            return None
        
        # Try to find the client's last agent
        for agent in self.agents:
            if agent["id"] == client.client.last_agent:
                return agent
        
        # Fallback to first available agent (simple round-robin)
        return self.agents[0] if self.agents else None
    
    async def _schedule_discovery_call(
        self,
        client: Client,
        agent: Dict[str, Any],
        call_summary: Optional[Dict[str, Any]] = None
    ) -> Dict[str, Any]:
        """Schedule discovery call with agent"""
        
        try:
            # Find next available slot for agent
            meeting_time = await self._find_available_slot(agent)
            
            if not meeting_time:
                return {"success": False, "error": "No available slots found"}
            
            # Create calendar event if Google Calendar is configured
            if self._is_google_calendar_configured():
                calendar_result = await self._create_calendar_event(
                    agent, client, meeting_time, call_summary
                )
                
                return {
                    "success": True,
                    "meeting_time": meeting_time,
                    "calendar_event": calendar_result
                }
            else:
                # Just record the meeting time
                await client_repo.update_client(client.id, {
                    "agent_assignment.meeting_scheduled": meeting_time,
                    "agent_assignment.meeting_status": "scheduled"
                })
                
                return {
                    "success": True,
                    "meeting_time": meeting_time,
                    "calendar_event": {"success": False, "message": "Google Calendar not configured"}
                }
                
        except Exception as e:
            logger.error(f"Meeting scheduling error: {e}")
            return {"success": False, "error": str(e)}
    
    async def _find_available_slot(self, agent: Dict[str, Any]) -> Optional[datetime]:
        """Find next available 15-minute slot for agent"""
        
        # Simple logic: next business day at 10 AM
        # In production, this would check Google Calendar availability
        
        tomorrow = datetime.utcnow() + timedelta(days=1)
        
        # Set to 10 AM
        meeting_time = tomorrow.replace(hour=10, minute=0, second=0, microsecond=0)
        
        # Ensure it's a business day (Monday-Friday)
        while meeting_time.weekday() >= 5:  # Saturday = 5, Sunday = 6
            meeting_time += timedelta(days=1)
        
        return meeting_time
    
    def _is_google_calendar_configured(self) -> bool:
        """Check if Google Calendar is properly configured"""
        return (settings.google_calendar_client_id and 
                settings.google_calendar_client_secret and
                not settings.google_calendar_client_id.startswith("your_"))
    
    async def _create_calendar_event(
        self,
        agent: Dict[str, Any],
        client: Client,
        meeting_time: datetime,
        call_summary: Optional[Dict[str, Any]] = None
    ) -> Dict[str, Any]:
        """Create Google Calendar event"""
        
        # TODO: Implement actual Google Calendar API integration
        # This would require OAuth2 flow and proper token management
        
        logger.info(f"📅 Would create calendar event for {agent['name']} with {client.client.full_name}")
        
        return {
            "success": False,
            "message": "Google Calendar integration not implemented yet",
            "would_create": {
                "agent": agent["name"],
                "client": client.client.full_name,
                "time": meeting_time.isoformat(),
                "duration": "15 minutes"
            }
        }
    
    async def _send_notifications(
        self,
        client: Client,
        agent: Dict[str, Any],
        meeting_time: Optional[datetime],
        call_summary: Optional[Dict[str, Any]] = None
    ) -> Dict[str, Any]:
        """Send email notifications to agent and client"""
        
        try:
            notifications_sent = []
            
            # Agent notification email
            agent_email_result = await self._send_agent_notification(
                agent, client, meeting_time, call_summary
            )
            notifications_sent.append({
                "type": "agent_notification",
                "recipient": agent["email"],
                "success": agent_email_result["success"]
            })
            
            # Client confirmation email (if meeting scheduled)
            if meeting_time:
                client_email_result = await self._send_client_confirmation(
                    client, agent, meeting_time
                )
                notifications_sent.append({
                    "type": "client_confirmation", 
                    "recipient": client.client.email,
                    "success": client_email_result["success"]
                })
            
            return {
                "success": True,
                "notifications_sent": notifications_sent
            }
            
        except Exception as e:
            logger.error(f"Notification sending error: {e}")
            return {"success": False, "error": str(e)}
    
    async def _send_agent_notification(
        self,
        agent: Dict[str, Any],
        client: Client,
        meeting_time: Optional[datetime],
        call_summary: Optional[Dict[str, Any]] = None
    ) -> Dict[str, Any]:
        """Send notification email to agent about new assignment"""
        
        # TODO: Implement actual SES email sending
        # For now, just log what would be sent
        
        logger.info(f"📧 Would send agent notification to {agent['email']} about {client.client.full_name}")
        
        return {
            "success": False,
            "message": "Email sending not implemented yet",
            "would_send": {
                "to": agent["email"],
                "subject": f"New Lead Assigned - {client.client.full_name}",
                "meeting_time": meeting_time.isoformat() if meeting_time else None
            }
        }
    
    async def _send_client_confirmation(
        self,
        client: Client,
        agent: Dict[str, Any],
        meeting_time: datetime
    ) -> Dict[str, Any]:
        """Send meeting confirmation email to client"""
        
        logger.info(f"📧 Would send meeting confirmation to {client.client.email}")
        
        return {
            "success": False,
            "message": "Email sending not implemented yet",
            "would_send": {
                "to": client.client.email,
                "subject": "Discovery Call Scheduled - Altrius Advisor Group",
                "meeting_time": meeting_time.isoformat()
            }
        }
    
    def get_statistics(self) -> Dict[str, Any]:
        """Get CRM integration statistics"""
        return {
            "crm_updates": self.crm_updates,
            "agent_assignments": self.agent_assignments,
            "meetings_scheduled": self.meetings_scheduled,
            "agents_configured": len(self.agents),
            "capsule_configured": bool(settings.capsule_api_key and not settings.capsule_api_key.startswith("your_")),
            "google_calendar_configured": self._is_google_calendar_configured()
        }