"""
Slot Selection Service
Handles fetching agent availability and generating slot selection emails
"""

import asyncio
import logging
from typing import Dict, Any, List, Optional
from datetime import datetime, timedelta
from urllib.parse import urlencode
import json

from .google_calendar_service import calendar_service
from .agent_assignment import agent_assignment_service
from .email_service import EmailService
from shared.models.call_session import CallSession

logger = logging.getLogger(__name__)

class SlotSelectionService:
    """Service for handling slot selection and scheduling"""
    
    def __init__(self):
        self.agent_assignment = agent_assignment_service
        self.email_service = EmailService()
        
        # Configuration
        self.slot_duration_minutes = 30
        self.business_hours = {
            'start': 9,  # 9 AM
            'end': 17    # 5 PM
        }
        self.days_to_check = 7
        self.slots_per_day = 3  # Number of slots to offer per day
    
    async def generate_slot_selection_email(self, session: CallSession) -> Dict[str, Any]:
        """Generate slot selection email with real calendar availability"""
        try:
            # Get assigned agent
            agent_result = await self.agent_assignment.assign_agent_to_client(session)
            
            if not agent_result.get("success"):
                logger.error(f"❌ Failed to assign agent: {agent_result.get('error')}")
                return {
                    "success": False,
                    "error": "Failed to assign agent",
                    "fallback": True
                }
            
            agent = agent_result.get("agent")
            agent_email = agent.get("email")
            
            # Get available slots
            available_slots = await self._get_available_slots(agent_email)
            
            if not available_slots:
                logger.warning(f"⚠️ No available slots found for {agent_email}")
                return {
                    "success": False,
                    "error": "No available slots",
                    "fallback": True
                }
            
            # Generate slot selection links
            slot_links = await self._generate_slot_links(session, agent, available_slots)
            
            # Send slot selection email
            email_result = await self._send_slot_selection_email(
                session, agent, slot_links
            )
            
            if email_result.get("success"):
                logger.info(f"✅ Slot selection email sent to {session.client_data.get('email')}")
                
                # Update session with slot selection info
                session.client_data.update({
                    "slot_selection_sent": True,
                    "agent_assigned": agent.get("name"),
                    "agent_email": agent_email,
                    "available_slots_count": len(available_slots)
                })
                
                return {
                    "success": True,
                    "agent": agent,
                    "slots_count": len(available_slots),
                    "email_sent": True
                }
            else:
                logger.error(f"❌ Failed to send slot selection email: {email_result.get('error')}")
                return {
                    "success": False,
                    "error": "Failed to send email",
                    "fallback": True
                }
                
        except Exception as e:
            logger.error(f"❌ Error in slot selection: {e}")
            return {
                "success": False,
                "error": str(e),
                "fallback": True
            }
    
    async def _get_available_slots(self, agent_email: str) -> List[Dict[str, Any]]:
        """Get available time slots for an agent"""
        try:
            # Initialize calendar service if needed
            if not calendar_service.is_configured():
                await calendar_service.initialize()
            
            if not calendar_service.is_configured():
                logger.warning("⚠️ Calendar service not configured, using mock slots")
                return self._generate_mock_slots()
            
            # Get agent's calendar events for next 7 days
            now = datetime.now()
            end_date = now + timedelta(days=self.days_to_check)
            
            events = await calendar_service.get_agent_calendar_events(
                agent_email, now, end_date
            )
            
            # Generate available slots
            available_slots = []
            
            for day_offset in range(self.days_to_check):
                check_date = now + timedelta(days=day_offset)
                
                # Skip weekends
                if check_date.weekday() >= 5:
                    continue
                
                # Generate slots for business hours
                day_slots = self._generate_day_slots(check_date, events)
                available_slots.extend(day_slots)
                
                # Limit total slots
                if len(available_slots) >= 12:  # Max 12 slots total
                    break
            
            return available_slots[:12]  # Return max 12 slots
            
        except Exception as e:
            logger.error(f"❌ Error getting available slots: {e}")
            return self._generate_mock_slots()
    
    def _generate_day_slots(self, date: datetime, events: List[Dict]) -> List[Dict[str, Any]]:
        """Generate available slots for a specific day"""
        slots = []
        
        # Generate time slots for business hours
        for hour in range(self.business_hours['start'], self.business_hours['end']):
            for minute in [0, 30]:  # 30-minute intervals
                slot_time = date.replace(hour=hour, minute=minute, second=0, microsecond=0)
                
                # Skip past times
                if slot_time <= datetime.now():
                    continue
                
                # Check if slot conflicts with existing events
                if not self._is_slot_available(slot_time, events):
                    continue
                
                slot_data = {
                    "time": slot_time,
                    "formatted_time": slot_time.strftime("%A, %B %d at %I:%M %p"),
                    "date": slot_time.strftime("%Y-%m-%d"),
                    "hour": slot_time.hour,
                    "minute": slot_time.minute,
                    "timestamp": int(slot_time.timestamp())
                }
                
                slots.append(slot_data)
                
                if len(slots) >= self.slots_per_day:
                    break
            
            if len(slots) >= self.slots_per_day:
                break
        
        return slots
    
    def _is_slot_available(self, slot_time: datetime, events: List[Dict]) -> bool:
        """Check if a time slot is available (not conflicting with events)"""
        slot_end = slot_time + timedelta(minutes=self.slot_duration_minutes)
        
        for event in events:
            try:
                # Parse event start and end times
                event_start_str = event.get('start', '')
                event_end_str = event.get('end', '')
                
                if not event_start_str or not event_end_str:
                    continue
                
                # Handle different datetime formats
                if 'T' in event_start_str:
                    event_start = datetime.fromisoformat(event_start_str.replace('Z', '+00:00'))
                    event_end = datetime.fromisoformat(event_end_str.replace('Z', '+00:00'))
                    
                    # Remove timezone info for comparison
                    event_start = event_start.replace(tzinfo=None)
                    event_end = event_end.replace(tzinfo=None)
                    
                    # Check for overlap
                    if (slot_time < event_end and slot_end > event_start):
                        return False
                        
            except Exception as e:
                logger.warning(f"⚠️ Error parsing event time: {e}")
                continue
        
        return True
    
    async def _generate_slot_links(self, session: CallSession, agent: Dict, slots: List[Dict]) -> List[Dict[str, Any]]:
        """Generate clickable links for slot selection"""
        slot_links = []
        
        for slot in slots:
            # Create slot selection link
            selection_data = {
                "session_id": session.session_id,
                "agent_email": agent.get("email"),
                "agent_name": agent.get("name"),
                "slot_time": slot["timestamp"],
                "client_name": session.client_data.get("client_name", "Client"),
                "client_email": session.client_data.get("email", ""),
                "client_phone": session.phone_number
            }
            
            # Create selection URL (this would be handled by your webhook endpoint)
            selection_url = f"/api/slot-selection?{urlencode(selection_data)}"
            
            slot_with_link = {
                **slot,
                "selection_url": selection_url,
                "agent_name": agent.get("name")
            }
            
            slot_links.append(slot_with_link)
        
        return slot_links
    
    async def _send_slot_selection_email(self, session: CallSession, agent: Dict, slot_links: List[Dict]) -> Dict[str, Any]:
        """Send slot selection email to client"""
        try:
            client_email = session.client_data.get("email")
            client_name = session.client_data.get("client_name", "there")
            
            if not client_email:
                return {
                    "success": False,
                    "error": "No client email available"
                }
            
            # Send email using the email service
            email_result = await self.email_service.send_slot_selection_email(
                client_email=client_email,
                client_name=client_name,
                agent_name=agent.get("name"),
                available_slots=slot_links
            )
            
            return email_result
            
        except Exception as e:
            logger.error(f"❌ Error sending slot selection email: {e}")
            return {
                "success": False,
                "error": str(e)
            }
    
    def _generate_mock_slots(self) -> List[Dict[str, Any]]:
        """Generate mock slots for development/testing"""
        mock_slots = []
        now = datetime.now()
        
        # Generate slots for next 3 business days
        for day_offset in range(1, 4):
            check_date = now + timedelta(days=day_offset)
            
            # Skip weekends
            if check_date.weekday() >= 5:
                continue
            
            # Generate 3 slots per day
            for hour in [10, 14, 16]:  # 10 AM, 2 PM, 4 PM
                slot_time = check_date.replace(hour=hour, minute=0, second=0, microsecond=0)
                
                slot_data = {
                    "time": slot_time,
                    "formatted_time": slot_time.strftime("%A, %B %d at %I:%M %p"),
                    "date": slot_time.strftime("%Y-%m-%d"),
                    "hour": slot_time.hour,
                    "minute": slot_time.minute,
                    "timestamp": int(slot_time.timestamp())
                }
                
                mock_slots.append(slot_data)
                
                if len(mock_slots) >= 9:  # Max 9 mock slots
                    break
            
            if len(mock_slots) >= 9:
                break
        
        return mock_slots
    
    async def handle_slot_selection(self, selection_data: Dict[str, Any]) -> Dict[str, Any]:
        """Handle slot selection from client"""
        try:
            session_id = selection_data.get("session_id")
            agent_email = selection_data.get("agent_email")
            slot_timestamp = selection_data.get("slot_time")
            client_name = selection_data.get("client_name")
            client_email = selection_data.get("client_email")
            
            # Convert timestamp back to datetime
            slot_time = datetime.fromtimestamp(slot_timestamp)
            
            # Create the meeting
            meeting_result = await calendar_service.create_meeting(
                agent_email=agent_email,
                client_name=client_name,
                client_email=client_email,
                meeting_time=slot_time
            )
            
            if meeting_result.get("success"):
                # Send confirmation email
                confirmation_result = await self.email_service.send_meeting_confirmation_email(
                    client_email=client_email,
                    client_name=client_name,
                    agent_name=selection_data.get("agent_name"),
                    meeting_details=meeting_result
                )
                
                logger.info(f"✅ Meeting scheduled successfully: {meeting_result.get('event_id')}")
                
                return {
                    "success": True,
                    "meeting_id": meeting_result.get("event_id"),
                    "meeting_time": slot_time.isoformat(),
                    "meet_link": meeting_result.get("meet_link"),
                    "confirmation_sent": confirmation_result.get("success")
                }
            else:
                logger.error(f"❌ Failed to create meeting: {meeting_result.get('error')}")
                return {
                    "success": False,
                    "error": meeting_result.get("error")
                }
                
        except Exception as e:
            logger.error(f"❌ Error handling slot selection: {e}")
            return {
                "success": False,
                "error": str(e)
            }

# Global instance
slot_selection_service = SlotSelectionService()
