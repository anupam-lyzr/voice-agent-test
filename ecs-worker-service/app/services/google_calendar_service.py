"""
Google Calendar Service Account Integration
Handles agent calendar scheduling using service account authentication
"""

import asyncio
import json
import logging
from typing import Dict, Any, Optional, List
from datetime import datetime, timedelta
from pathlib import Path

import httpx
from google.oauth2.service_account import Credentials
from googleapiclient.discovery import build
from googleapiclient.errors import HttpError

from shared.config.settings import settings

logger = logging.getLogger(__name__)

class GoogleCalendarService:
    """Service for Google Calendar integration using service account"""
    
    def __init__(self):
        self.service = None
        self.credentials = None
        self.agents_config = self._load_agents_config()
        
        # Statistics
        self.events_created = 0
        self.events_failed = 0
    
    def _load_agents_config(self) -> Dict[str, Any]:
        """Load agents configuration"""
        try:
            with open("data/agents.json", 'r') as f:
                return json.load(f)
        except Exception as e:
            logger.error(f"Failed to load agents config: {e}")
            return {"agents": []}
    
    async def initialize(self) -> bool:
        """Initialize Google Calendar service with service account credentials"""
        try:
            # Check if service account credentials file exists
            credentials_path = Path("config/google-service-account.json")
            
            if not credentials_path.exists():
                logger.warning("Google Calendar service account credentials not found")
                logger.info("To enable Google Calendar integration:")
                logger.info("1. Create a service account in Google Cloud Console")
                logger.info("2. Download the JSON credentials file")
                logger.info("3. Save it as config/google-service-account.json")
                logger.info("4. Share calendars with the service account email")
                return False
            
            # Load service account credentials
            self.credentials = Credentials.from_service_account_file(
                credentials_path,
                scopes=['https://www.googleapis.com/auth/calendar']
            )
            
            # Build the service
            self.service = build('calendar', 'v3', credentials=self.credentials)
            
            logger.info("✅ Google Calendar service initialized successfully")
            return True
            
        except Exception as e:
            logger.error(f"❌ Failed to initialize Google Calendar service: {e}")
            return False
    
    def is_configured(self) -> bool:
        """Check if Google Calendar is properly configured"""
        return self.service is not None
    
    async def get_agent_availability(self, agent_email: str, start_time: datetime, end_time: datetime) -> List[Dict[str, Any]]:
        """Get agent's calendar availability for the specified time range"""
        if not self.is_configured():
            return []
        
        try:
            # Get busy times from calendar
            body = {
                "timeMin": start_time.isoformat() + 'Z',
                "timeMax": end_time.isoformat() + 'Z',
                "items": [{"id": agent_email}]
            }
            
            freebusy_result = self.service.freebusy().query(body=body).execute()
            
            busy_times = []
            calendar_data = freebusy_result.get('calendars', {}).get(agent_email, {})
            
            for busy_period in calendar_data.get('busy', []):
                busy_times.append({
                    'start': datetime.fromisoformat(busy_period['start'].replace('Z', '+00:00')),
                    'end': datetime.fromisoformat(busy_period['end'].replace('Z', '+00:00'))
                })
            
            return busy_times
            
        except HttpError as e:
            logger.error(f"Google Calendar API error for {agent_email}: {e}")
            return []
        except Exception as e:
            logger.error(f"Failed to get availability for {agent_email}: {e}")
            return []
    
    async def find_next_available_slot(self, agent_email: str, duration_minutes: int = 15) -> Optional[datetime]:
        """Find the next available time slot for an agent"""
        if not self.is_configured():
            logger.warning("Google Calendar not configured, using fallback scheduling")
            return self._fallback_scheduling()
        
        try:
            # Search for next 7 days
            start_search = datetime.now().replace(hour=9, minute=0, second=0, microsecond=0)
            
            # Ensure it's a business day
            while start_search.weekday() >= 5:  # Skip weekends
                start_search += timedelta(days=1)
            
            for day_offset in range(7):  # Search next 7 days
                current_day = start_search + timedelta(days=day_offset)
                
                # Skip weekends
                if current_day.weekday() >= 5:
                    continue
                
                # Check availability for business hours (9 AM - 5 PM)
                day_start = current_day.replace(hour=9, minute=0)
                day_end = current_day.replace(hour=17, minute=0)
                
                busy_times = await self.get_agent_availability(agent_email, day_start, day_end)
                
                # Find free slots
                available_slot = self._find_free_slot(day_start, day_end, busy_times, duration_minutes)
                if available_slot:
                    return available_slot
            
            logger.warning(f"No available slots found for {agent_email} in next 7 days")
            return None
            
        except Exception as e:
            logger.error(f"Failed to find available slot for {agent_email}: {e}")
            return self._fallback_scheduling()
    
    def _find_free_slot(self, day_start: datetime, day_end: datetime, busy_times: List[Dict], duration_minutes: int) -> Optional[datetime]:
        """Find a free slot within a day"""
        # Create 15-minute time slots
        slot_duration = timedelta(minutes=15)
        current_time = day_start
        
        while current_time + timedelta(minutes=duration_minutes) <= day_end:
            slot_end = current_time + timedelta(minutes=duration_minutes)
            
            # Check if this slot conflicts with any busy time
            is_free = True
            for busy in busy_times:
                if (current_time < busy['end'] and slot_end > busy['start']):
                    is_free = False
                    break
            
            if is_free:
                return current_time
            
            current_time += slot_duration
        
        return None
    
    def _fallback_scheduling(self) -> datetime:
        """Fallback scheduling when Google Calendar is not available"""
        # Schedule for next business day at 10 AM
        next_day = datetime.now() + timedelta(days=1)
        
        # Ensure it's a business day
        while next_day.weekday() >= 5:
            next_day += timedelta(days=1)
        
        return next_day.replace(hour=10, minute=0, second=0, microsecond=0)
    
    async def create_meeting(self, agent_email: str, client_name: str, client_email: str, meeting_time: datetime, summary: Optional[str] = None) -> Dict[str, Any]:
        """Create a calendar event for agent and client"""
        if not self.is_configured():
            logger.warning("Google Calendar not configured, logging meeting details only")
            return {
                "success": False,
                "method": "fallback",
                "meeting_time": meeting_time.isoformat(),
                "agent_email": agent_email,
                "client_email": client_email
            }
        
        try:
            # Create event details
            event = {
                'summary': f'Discovery Call - {client_name}',
                'description': self._create_event_description(client_name, summary),
                'start': {
                    'dateTime': meeting_time.isoformat(),
                    'timeZone': 'America/New_York',
                },
                'end': {
                    'dateTime': (meeting_time + timedelta(minutes=15)).isoformat(),
                    'timeZone': 'America/New_York',
                },
                'attendees': [
                    {'email': agent_email, 'responseStatus': 'accepted'},
                    {'email': client_email, 'responseStatus': 'needsAction'}
                ],
                'reminders': {
                    'useDefault': False,
                    'overrides': [
                        {'method': 'email', 'minutes': 60},
                        {'method': 'popup', 'minutes': 15},
                    ],
                },
                'conferenceData': {
                    'createRequest': {
                        'requestId': f"discovery-{client_name.replace(' ', '')}-{int(meeting_time.timestamp())}",
                        'conferenceSolutionKey': {'type': 'hangoutsMeet'}
                    }
                }
            }
            
            # Create the event
            created_event = self.service.events().insert(
                calendarId=agent_email,
                body=event,
                conferenceDataVersion=1,
                sendUpdates='all'
            ).execute()
            
            self.events_created += 1
            
            logger.info(f"✅ Calendar event created: {created_event.get('id')}")
            
            return {
                "success": True,
                "event_id": created_event.get('id'),
                "event_link": created_event.get('htmlLink'),
                "meeting_time": meeting_time.isoformat(),
                "meet_link": self._extract_meet_link(created_event)
            }
            
        except HttpError as e:
            logger.error(f"Google Calendar API error: {e}")
            self.events_failed += 1
            return {"success": False, "error": str(e)}
        except Exception as e:
            logger.error(f"Failed to create calendar event: {e}")
            self.events_failed += 1
            return {"success": False, "error": str(e)}
    
    def _create_event_description(self, client_name: str, summary: Optional[str]) -> str:
        """Create event description with call summary"""
        description = f"""Discovery Call with {client_name}

This meeting was automatically scheduled following an interested response during our voice campaign.

"""
        
        if summary:
            description += f"""Call Summary:
{summary}

"""
        
        description += """Meeting Agenda:
• Review client's insurance needs
• Discuss available options
• Answer questions and concerns
• Next steps and follow-up

Prepared by: Voice Agent Campaign System
"""
        
        return description
    
    def _extract_meet_link(self, event: Dict[str, Any]) -> Optional[str]:
        """Extract Google Meet link from event"""
        conference_data = event.get('conferenceData', {})
        entry_points = conference_data.get('entryPoints', [])
        
        for entry_point in entry_points:
            if entry_point.get('entryPointType') == 'video':
                return entry_point.get('uri')
        
        return None
    
    async def get_agent_calendar_events(self, agent_email: str, start_date: datetime, end_date: datetime) -> List[Dict[str, Any]]:
        """Get agent's calendar events for a specific date range"""
        if not self.is_configured():
            return []
        
        try:
            events_result = self.service.events().list(
                calendarId=agent_email,
                timeMin=start_date.isoformat() + 'Z',
                timeMax=end_date.isoformat() + 'Z',
                singleEvents=True,
                orderBy='startTime'
            ).execute()
            
            events = events_result.get('items', [])
            
            formatted_events = []
            for event in events:
                start = event['start'].get('dateTime', event['start'].get('date'))
                end = event['end'].get('dateTime', event['end'].get('date'))
                
                formatted_events.append({
                    'id': event['id'],
                    'summary': event.get('summary', 'No Title'),
                    'start': start,
                    'end': end,
                    'attendees': event.get('attendees', []),
                    'status': event.get('status', 'confirmed')
                })
            
            return formatted_events
            
        except Exception as e:
            logger.error(f"Failed to get calendar events for {agent_email}: {e}")
            return []
    
    async def update_meeting(self, agent_email: str, event_id: str, updates: Dict[str, Any]) -> bool:
        """Update an existing calendar event"""
        if not self.is_configured():
            return False
        
        try:
            # Get existing event
            event = self.service.events().get(
                calendarId=agent_email,
                eventId=event_id
            ).execute()
            
            # Apply updates
            for key, value in updates.items():
                event[key] = value
            
            # Update the event
            updated_event = self.service.events().update(
                calendarId=agent_email,
                eventId=event_id,
                body=event,
                sendUpdates='all'
            ).execute()
            
            logger.info(f"✅ Calendar event updated: {event_id}")
            return True
            
        except Exception as e:
            logger.error(f"Failed to update calendar event {event_id}: {e}")
            return False
    
    async def cancel_meeting(self, agent_email: str, event_id: str, reason: str = "Meeting cancelled") -> bool:
        """Cancel a calendar event"""
        if not self.is_configured():
            return False
        
        try:
            # Update event status to cancelled
            event = self.service.events().get(
                calendarId=agent_email,
                eventId=event_id
            ).execute()
            
            event['status'] = 'cancelled'
            event['description'] = event.get('description', '') + f"\n\nCancellation Reason: {reason}"
            
            self.service.events().update(
                calendarId=agent_email,
                eventId=event_id,
                body=event,
                sendUpdates='all'
            ).execute()
            
            logger.info(f"✅ Calendar event cancelled: {event_id}")
            return True
            
        except Exception as e:
            logger.error(f"Failed to cancel calendar event {event_id}: {e}")
            return False
    
    def get_agent_by_email(self, email: str) -> Optional[Dict[str, Any]]:
        """Get agent configuration by email"""
        for agent in self.agents_config.get("agents", []):
            if agent.get("email") == email:
                return agent
        return None
    
    def get_statistics(self) -> Dict[str, Any]:
        """Get calendar service statistics"""
        return {
            "configured": self.is_configured(),
            "events_created": self.events_created,
            "events_failed": self.events_failed,
            "success_rate": (self.events_created / max(1, self.events_created + self.events_failed)) * 100,
            "agents_count": len(self.agents_config.get("agents", []))
        }

# Global calendar service instance
calendar_service = GoogleCalendarService()

async def init_calendar_service():
    """Initialize the calendar service"""
    return await calendar_service.initialize()

# Utility functions for easy access
async def schedule_discovery_call(agent_email: str, client_name: str, client_email: str, call_summary: Optional[str] = None) -> Dict[str, Any]:
    """Schedule a discovery call for an interested client"""
    try:
        # Find next available slot
        meeting_time = await calendar_service.find_next_available_slot(agent_email)
        
        if not meeting_time:
            return {
                "success": False,
                "error": "No available time slots found"
            }
        
        # Create the meeting
        result = await calendar_service.create_meeting(
            agent_email=agent_email,
            client_name=client_name,
            client_email=client_email,
            meeting_time=meeting_time,
            summary=call_summary
        )
        
        return result
        
    except Exception as e:
        logger.error(f"Failed to schedule discovery call: {e}")
        return {"success": False, "error": str(e)}

async def get_agent_schedule(agent_email: str, days_ahead: int = 7) -> List[Dict[str, Any]]:
    """Get agent's schedule for the next N days"""
    start_date = datetime.now()
    end_date = start_date + timedelta(days=days_ahead)
    
    return await calendar_service.get_agent_calendar_events(agent_email, start_date, end_date)

# Setup instructions for Google Calendar integration
SETUP_INSTRUCTIONS = """
Google Calendar Service Account Setup:

1. Go to Google Cloud Console (https://console.cloud.google.com/)
2. Create a new project or select existing project
3. Enable the Google Calendar API
4. Create a service account:
   - Go to IAM & Admin > Service Accounts
   - Click "Create Service Account"
   - Enter name: "voice-agent-calendar"
   - Grant role: "Editor" or custom role with calendar permissions
5. Create and download JSON key file
6. Save the file as: config/google-service-account.json
7. Share each agent's calendar with the service account email
8. Grant "Make changes to events" permission

Example service account email: 
voice-agent-calendar@your-project.iam.gserviceaccount.com

Agent Calendar Sharing:
- Each agent must share their calendar with the service account
- Permission level: "Make changes to events"
- This allows the system to read availability and create meetings

Testing:
- Run: python -c "from services.google_calendar import init_calendar_service; import asyncio; asyncio.run(init_calendar_service())"
"""