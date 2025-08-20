"""
CRM Integration Service
Handles Capsule CRM operations and tagging
"""

import asyncio
import httpx
import logging
from typing import Dict, Any, Optional, List
from datetime import datetime, timedelta
import base64
from shared.config.settings import settings
from shared.models.client import Client, CRMTag, CallOutcome
from shared.utils.database import client_repo

logger = logging.getLogger(__name__)

class CRMIntegration:
    """Handles integration with Capsule CRM"""
    
    def __init__(self):
        self.api_url = settings.capsule_api_url or "https://api.capsulecrm.com"
        self.api_token = settings.capsule_api_token
        
        # Initialize database client
        try:
            from shared.utils.database import get_database
            self.db_client = get_database()
        except Exception as e:
            logger.warning(f"⚠️ Could not initialize database client: {e}")
            self.db_client = None
        
        # HTTP client for API calls
        self.httpx_client = httpx.AsyncClient(
            timeout=30.0,
            headers={
                "Authorization": f"Bearer {self.api_token}" if self.api_token else "",
                "Content-Type": "application/json",
                "Accept": "application/json"
            }
        )
        
        # CRM tag mappings
        self.tag_mappings = {
            CRMTag.INTERESTED: "LYZR-UC1-INTERESTED",
            CRMTag.NOT_INTERESTED: "LYZR-UC1-NOT-INTERESTED", 
            CRMTag.DNC_REQUESTED: "LYZR-UC1-DNC-REQUESTED",
            CRMTag.NO_CONTACT: "LYZR-UC1-NO-CONTACT",
            CRMTag.INVALID_NUMBER: "LYZR-UC1-INVALID-NUMBER",
            CRMTag.INVALID_EMAIL: "LYZR-UC1-INVALID-EMAIL"
        }
        
        # Check configuration
        if not self.api_token:
            logger.warning("⚠️ Capsule CRM API token not configured - CRM operations will be mocked")
    
    def _map_outcome_to_crm_tag(self, outcome: str) -> str:
        """Map call outcome to CRM tag"""
        tag_mapping = {
            "interested": "LYZR-UC1-INTERESTED",
            "interested_no_schedule": "LYZR-UC1-INTERESTED",
            "send_email_invite": "LYZR-UC1-INTERESTED", 
            "scheduled": "LYZR-UC1-INTERESTED",
            "not_interested": "LYZR-UC1-NOT-INTERESTED",
            "dnc_requested": "LYZR-UC1-DNC-REQUESTED",
            "no_contact": "LYZR-UC1-NO-CONTACT",
            "voicemail": "LYZR-UC1-NO-CONTACT",
            "invalid_number": "LYZR-UC1-INVALID-NUMBER",
            "invalid_email": "LYZR-UC1-INVALID-EMAIL"
        }
        
        return tag_mapping.get(outcome, "LYZR-UC1-NO-CONTACT")
    
    async def update_client_record(self, client_data: Dict[str, Any], call_outcome: str, call_summary: Optional[str] = None) -> bool:
        """Update client record in CRM with call outcome and summary"""
        try:
            logger.info(f"🏷️ Updating CRM for client {client_data.get('client_id', 'unknown')} with outcome: {call_outcome}")
            
            # Map outcome to CRM tag
            crm_tag = self._map_outcome_to_crm_tag(call_outcome)
            
            # Prepare update data
            update_data = {
                "tags": crm_tag,
                "last_contact_date": datetime.utcnow().isoformat(),
                "last_contact_method": "voice_call",
                "call_outcome": call_outcome
            }
            
            # Add call summary if provided
            if call_summary:
                update_data["call_summary"] = call_summary
            
            # Update based on call outcome
            if call_outcome in ["interested", "interested_no_schedule", "send_email_invite", "scheduled"]:
                update_data["status"] = "interested"
                update_data["needs_follow_up"] = True
                update_data["follow_up_date"] = (datetime.utcnow() + timedelta(days=1)).isoformat()
            
            elif call_outcome == "not_interested":
                update_data["status"] = "not_interested"
                update_data["needs_follow_up"] = False
            
            elif call_outcome == "dnc_requested":
                update_data["status"] = "do_not_contact"
                update_data["needs_follow_up"] = False
                update_data["dnc_date"] = datetime.utcnow().isoformat()
            
            elif call_outcome in ["no_contact", "voicemail"]:
                update_data["status"] = "no_contact"
                update_data["contact_attempts"] = update_data.get("contact_attempts", 0) + 1
                
                # Check if we should mark as no-contact after 5-7 attempts
                attempts = update_data["contact_attempts"]
                if attempts >= 7:
                    update_data["tags"] = "LYZR-UC1-NO-CONTACT"
                    update_data["status"] = "no_contact_max_attempts"
                    update_data["needs_follow_up"] = False
                else:
                    update_data["needs_follow_up"] = True
                    update_data["follow_up_date"] = (datetime.utcnow() + timedelta(days=2)).isoformat()
            
            # Update in database
            if self.db_client and hasattr(self.db_client, 'is_connected') and self.db_client.is_connected():
                client_id = client_data.get("client_id")
                if client_id:
                    await self.db_client.database.clients.update_one(
                        {"client_id": client_id},
                        {"$set": update_data}
                    )
                    logger.info(f"✅ CRM updated for client {client_id} with tag: {crm_tag}")
                    return True
            
            # Log the update (for mock mode)
            logger.info(f"📝 CRM Update - Client: {client_data.get('client_id', 'unknown')}")
            logger.info(f"📝 CRM Update - Tag: {crm_tag}")
            logger.info(f"📝 CRM Update - Status: {update_data.get('status', 'unknown')}")
            
            return True
            
        except Exception as e:
            logger.error(f"❌ Error updating CRM record: {e}")
            return False
    
    async def _find_person(self, client: Client) -> Optional[int]:
        """Find person in Capsule CRM by phone or email"""
        
        try:
            # Search by phone number first
            if client.client.phone:
                phone_search = await self._search_by_phone(client.client.phone)
                if phone_search:
                    return phone_search
            
            # Search by email if phone search fails
            if client.client.email:
                email_search = await self._search_by_email(client.client.email)
                if email_search:
                    return email_search
            
            # Search by name as last resort
            name_search = await self._search_by_name(client.client.first_name, client.client.last_name)
            return name_search
            
        except Exception as e:
            logger.error(f"❌ Error finding person in CRM: {e}")
            return None
    
    async def _search_by_phone(self, phone: str) -> Optional[int]:
        """Search person by phone number"""
        
        try:
            # Clean phone number for search
            clean_phone = phone.replace("+", "").replace("-", "").replace(" ", "").replace("(", "").replace(")", "")
            
            response = await self.httpx_client.get(
                f"{self.api_url}/api/v2/parties/search",
                params={"q": clean_phone, "type": "person"}
            )
            
            if response.status_code == 200:
                data = response.json()
                parties = data.get("parties", [])
                
                if parties:
                    return parties[0]["party"]["id"]
            
            return None
            
        except Exception as e:
            logger.error(f"❌ Phone search error: {e}")
            return None
    
    async def _search_by_email(self, email: str) -> Optional[int]:
        """Search person by email address"""
        
        try:
            response = await self.httpx_client.get(
                f"{self.api_url}/api/v2/parties/search",
                params={"q": email, "type": "person"}
            )
            
            if response.status_code == 200:
                data = response.json()
                parties = data.get("parties", [])
                
                if parties:
                    return parties[0]["party"]["id"]
            
            return None
            
        except Exception as e:
            logger.error(f"❌ Email search error: {e}")
            return None
    
    async def _search_by_name(self, first_name: str, last_name: str) -> Optional[int]:
        """Search person by name"""
        
        try:
            search_query = f"{first_name} {last_name}".strip()
            
            response = await self.httpx_client.get(
                f"{self.api_url}/api/v2/parties/search",
                params={"q": search_query, "type": "person"}
            )
            
            if response.status_code == 200:
                data = response.json()
                parties = data.get("parties", [])
                
                # Look for exact name match
                for party_data in parties:
                    party = party_data["party"]
                    if (party.get("firstName", "").lower() == first_name.lower() and 
                        party.get("lastName", "").lower() == last_name.lower()):
                        return party["id"]
                
                # Return first result if no exact match
                if parties:
                    return parties[0]["party"]["id"]
            
            return None
            
        except Exception as e:
            logger.error(f"❌ Name search error: {e}")
            return None
    
    async def _update_person_tags(self, person_id: int, client: Client) -> Dict[str, Any]:
        """Update person tags based on call outcome"""
        
        try:
            # Determine which tag to add based on call outcome
            latest_outcome = await client_repo.get_latest_call_outcome(client.id)
            
            if not latest_outcome:
                return {"success": False, "error": "no_call_outcome"}
            
            # Map call outcome to CRM tag
            tag_to_add = None
            
            if latest_outcome == CallOutcome.INTERESTED:
                tag_to_add = self.tag_mappings[CRMTag.INTERESTED]
            elif latest_outcome == CallOutcome.NOT_INTERESTED:
                tag_to_add = self.tag_mappings[CRMTag.NOT_INTERESTED]
            elif latest_outcome == CallOutcome.DNC_REQUESTED:
                tag_to_add = self.tag_mappings[CRMTag.DNC_REQUESTED]
            elif latest_outcome == CallOutcome.NO_ANSWER:
                tag_to_add = self.tag_mappings[CRMTag.NO_CONTACT]
            elif latest_outcome == CallOutcome.FAILED:
                tag_to_add = self.tag_mappings[CRMTag.INVALID_NUMBER]
            
            if not tag_to_add:
                return {"success": False, "error": "no_matching_tag"}
            
            # Add tag to person
            tag_payload = {
                "tag": {
                    "name": tag_to_add,
                    "description": f"Added by LYZR voice campaign on {datetime.utcnow().strftime('%Y-%m-%d')}"
                }
            }
            
            response = await self.httpx_client.post(
                f"{self.api_url}/api/v2/parties/{person_id}/tags",
                json=tag_payload
            )
            
            if response.status_code in [200, 201]:
                logger.info(f"✅ Added tag '{tag_to_add}' to person {person_id}")
                return {"success": True, "tag": tag_to_add}
            else:
                logger.error(f"❌ Failed to add tag: {response.status_code} - {response.text}")
                return {"success": False, "error": f"api_error_{response.status_code}"}
                
        except Exception as e:
            logger.error(f"❌ Error updating person tags: {e}")
            return {"success": False, "error": str(e)}
    
    async def _add_call_notes(self, person_id: int, client: Client) -> Dict[str, Any]:
        """Add call notes to person record"""
        
        try:
            # Get call summary from latest call
            call_summary = await client_repo.get_latest_call_summary(client.id)
            
            if not call_summary:
                return {"success": False, "error": "no_call_summary"}
            
            # Create note content
            note_content = self._format_call_notes(client, call_summary)
            
            # Add note to person
            note_payload = {
                "entry": {
                    "type": "note",
                    "content": note_content,
                    "subject": f"LYZR Voice Campaign Call - {datetime.utcnow().strftime('%Y-%m-%d')}"
                }
            }
            
            response = await self.httpx_client.post(
                f"{self.api_url}/api/v2/parties/{person_id}/entries",
                json=note_payload
            )
            
            if response.status_code in [200, 201]:
                logger.info(f"✅ Added call notes to person {person_id}")
                return {"success": True}
            else:
                logger.error(f"❌ Failed to add notes: {response.status_code} - {response.text}")
                return {"success": False, "error": f"api_error_{response.status_code}"}
                
        except Exception as e:
            logger.error(f"❌ Error adding call notes: {e}")
            return {"success": False, "error": str(e)}
    
    def _format_call_notes(self, client: Client, call_summary: Dict[str, Any]) -> str:
        """Format call notes for CRM"""
        
        notes = []
        notes.append("=== LYZR VOICE CAMPAIGN CALL ===")
        notes.append(f"Date: {datetime.utcnow().strftime('%Y-%m-%d %H:%M:%S')} UTC")
        notes.append(f"Client: {client.client.full_name}")
        notes.append(f"Phone: {client.client.phone}")
        notes.append("")
        
        # Call outcome
        outcome = call_summary.get("outcome", "Unknown")
        notes.append(f"Call Outcome: {outcome}")
        
        # Call duration
        duration = call_summary.get("duration_seconds", 0)
        if duration > 0:
            minutes = duration // 60
            seconds = duration % 60
            notes.append(f"Call Duration: {minutes}m {seconds}s")
        
        # Conversation summary
        if call_summary.get("summary"):
            notes.append("")
            notes.append("Conversation Summary:")
            notes.append(call_summary["summary"])
        
        # Key points
        if call_summary.get("key_points"):
            notes.append("")
            notes.append("Key Points:")
            for point in call_summary["key_points"]:
                notes.append(f"- {point}")
        
        # Next actions
        if call_summary.get("next_actions"):
            notes.append("")
            notes.append("Next Actions:")
            for action in call_summary["next_actions"]:
                notes.append(f"- {action}")
        
        # Agent assignment
        if call_summary.get("agent_assigned"):
            notes.append("")
            notes.append(f"Assigned Agent: {call_summary['agent_assigned']}")
        
        notes.append("")
        notes.append("Generated by LYZR Voice Agent System")
        
        return "\n".join(notes)
    
    async def _mock_crm_update(self, client: Client) -> Dict[str, Any]:
        """Mock CRM update for development"""
        
        logger.info(f"🔧 Mock CRM update for {client.client.full_name}")
        
        # Simulate API delay
        await asyncio.sleep(0.5)
        
        # Mark as updated in database
        await client_repo.mark_crm_updated(client.id)
        
        return {
            "success": True,
            "person_id": "mock_person_123",
            "tags_updated": True,
            "notes_added": True,
            "client_id": client.id,
            "mock": True
        }
    
    async def bulk_update_clients(self, clients: List[Client]) -> Dict[str, Any]:
        """Bulk update multiple clients in CRM"""
        
        results = {
            "total": len(clients),
            "successful": 0,
            "failed": 0,
            "errors": []
        }
        
        for client in clients:
            try:
                result = await self.update_client_record(client)
                
                if result["success"]:
                    results["successful"] += 1
                else:
                    results["failed"] += 1
                    results["errors"].append({
                        "client_id": client.id,
                        "error": result.get("error", "unknown")
                    })
                    
            except Exception as e:
                results["failed"] += 1
                results["errors"].append({
                    "client_id": client.id,
                    "error": str(e)
                })
        
        logger.info(f"✅ Bulk CRM update completed: {results['successful']}/{results['total']} successful")
        
        return results
    
    async def add_custom_tag(self, client: Client, tag_name: str, description: str = "") -> Dict[str, Any]:
        """Add custom tag to client"""
        
        try:
            if not self.api_token:
                logger.info(f"🔧 Mock adding custom tag '{tag_name}' to {client.client.full_name}")
                return {"success": True, "mock": True}
            
            person_id = await self._find_person(client)
            
            if not person_id:
                return {"success": False, "error": "person_not_found"}
            
            tag_payload = {
                "tag": {
                    "name": tag_name,
                    "description": description or f"Custom tag added on {datetime.utcnow().strftime('%Y-%m-%d')}"
                }
            }
            
            response = await self.httpx_client.post(
                f"{self.api_url}/api/v2/parties/{person_id}/tags",
                json=tag_payload
            )
            
            if response.status_code in [200, 201]:
                return {"success": True, "tag": tag_name}
            else:
                return {"success": False, "error": f"api_error_{response.status_code}"}
                
        except Exception as e:
            logger.error(f"❌ Error adding custom tag: {e}")
            return {"success": False, "error": str(e)}
    
    async def get_client_tags(self, client: Client) -> List[str]:
        """Get existing tags for client"""
        
        try:
            if not self.api_token:
                return ["MOCK-TAG-1", "MOCK-TAG-2"]  # Mock tags for development
            
            person_id = await self._find_person(client)
            
            if not person_id:
                return []
            
            response = await self.httpx_client.get(
                f"{self.api_url}/api/v2/parties/{person_id}/tags"
            )
            
            if response.status_code == 200:
                data = response.json()
                tags = data.get("tags", [])
                return [tag["tag"]["name"] for tag in tags]
            
            return []
            
        except Exception as e:
            logger.error(f"❌ Error getting client tags: {e}")
            return []
    
    async def close(self):
        """Close HTTP client"""
        await self.httpx_client.aclose()
        logger.info("✅ CRM integration client closed")