"""
Corrected Google Calendar Integration Service
"""

import json
import logging
from datetime import datetime, timedelta
from typing import Dict, Any, List, Optional
import pytz

try:
    from google.oauth2 import service_account
    from googleapiclient.discovery import build
    from googleapiclient.errors import HttpError
    GOOGLE_CALENDAR_AVAILABLE = True
except ImportError:
    GOOGLE_CALENDAR_AVAILABLE = False

from shared.config.settings import settings
from shared.utils.database import get_database

logger = logging.getLogger(__name__)

class GoogleCalendarService:
    """Corrected Google Calendar service for agent scheduling"""
    
    def __init__(self):
        self.service = None
        self.db_client = None
        self._configured = False
        self._configure()
    
    def _configure(self):
        """Configure Google Calendar service with proper error handling"""
        try:
            if not GOOGLE_CALENDAR_AVAILABLE:
                logger.warning("⚠️ Google Calendar libraries not installed")
                return
            
            # Validate required credentials
            if not all([
                settings.google_service_account_email,
                settings.google_service_account_private_key,
                settings.google_service_account_project_id
            ]):
                logger.warning("⚠️ Google Calendar credentials incomplete")
                logger.info("Required: GOOGLE_SERVICE_ACCOUNT_EMAIL, GOOGLE_SERVICE_ACCOUNT_PRIVATE_KEY, GOOGLE_SERVICE_ACCOUNT_PROJECT_ID")
                return
            
            # Build service account credentials
            credentials_info = {
                "type": "service_account",
                "project_id": settings.google_service_account_project_id,
                "private_key_id": "",  # Not required for authentication
                "private_key": settings.google_service_account_private_key.replace('\\n', '\n'),
                "client_email": settings.google_service_account_email,
                "client_id": "",  # Not required for authentication
                "auth_uri": "https://accounts.google.com/o/oauth2/auth",
                "token_uri": "https://oauth2.googleapis.com/token",
                "auth_provider_x509_cert_url": "https://www.googleapis.com/oauth2/v1/certs"
            }
            
            # Create credentials
            credentials = service_account.Credentials.from_service_account_info(
                credentials_info,
                scopes=['https://www.googleapis.com/auth/calendar']
            )
            
            # Build service
            self.service = build('calendar', 'v3', credentials=credentials)
            self._configured = True
            
            logger.info("✅ Google Calendar service configured successfully")
            
        except Exception as e:
            logger.error(f"❌ Google Calendar configuration failed: {e}")
            self._configured = False
    
    def is_configured(self) -> bool:
        """Check if service is properly configured"""
        return self._configured and self.service is not None
    
    async def get_agent_by_name(self, agent_name: str) -> Optional[Dict]:
        """Get agent configuration by name from database or fallback to file"""
        try:
            # First try to get from database
            if not self.db_client:
                self.db_client = get_database()
            
            if await self.db_client.ensure_connected():
                # Check if we're in testing mode
                from shared.config.settings import settings
                testing_mode = getattr(settings, 'testing_mode', False)
                
                if testing_mode:
                    # In testing mode, look for test agents first
                    logger.info(f"🧪 Testing mode: Looking for test agent '{agent_name}'")
                    test_agents_collection = self.db_client.database.test_agents
                    test_agent = await test_agents_collection.find_one({"name": agent_name})
                    if test_agent:
                        logger.info(f"✅ Found test agent '{agent_name}' in database")
                        return {
                            "name": test_agent.get("name"),
                            "email": test_agent.get("email"),
                            "phone": test_agent.get("phone", ""),
                            "calendar_id": test_agent.get("google_calendar_id", test_agent.get("email")),
                            "timezone": test_agent.get("timezone", "America/New_York")
                        }
                
                # In production mode or if test agent not found, look for production agents
                logger.info(f"🔍 Looking for production agent '{agent_name}' in database")
                agents_collection = self.db_client.database.agents
                agent = await agents_collection.find_one({"name": agent_name})
                if agent:
                    logger.info(f"✅ Found production agent '{agent_name}' in database")
                    return {
                        "name": agent.get("name"),
                        "email": agent.get("email"),
                        "phone": agent.get("phone", ""),
                        "calendar_id": agent.get("google_calendar_id", agent.get("email")),
                        "timezone": agent.get("timezone", "America/New_York")
                    }
            
            # Fallback to file-based config for testing
            logger.info(f"🔍 Agent '{agent_name}' not found in database, checking file config")
            return self._get_agent_from_file(agent_name)
            
        except Exception as e:
            logger.error(f"❌ Error getting agent '{agent_name}': {e}")
            # Fallback to file-based config
            return self._get_agent_from_file(agent_name)
    
    def _get_agent_from_file(self, agent_name: str) -> Optional[Dict]:
        """Get agent configuration from file (for testing)"""
        try:
            with open('data/agents.json', 'r') as f:
                agents_config = json.load(f)
            
            for agent in agents_config.get("agents", []):
                if agent.get("name") == agent_name:
                    logger.info(f"✅ Found agent '{agent_name}' in file config")
                    return {
                        "name": agent.get("name"),
                        "email": agent.get("email"),
                        "phone": agent.get("phone"),
                        "calendar_id": agent.get("calendar_id", agent.get("email")),
                        "timezone": agent.get("timezone", "America/New_York")
                    }
            
            logger.warning(f"⚠️ Agent '{agent_name}' not found in file config")
            return None
            
        except Exception as e:
            logger.error(f"❌ Error loading agents from file: {e}")
            return None
    
    async def get_test_agent(self) -> Optional[Dict]:
        """Get a test agent for development/testing"""
        try:
            # First try to get from database
            if not self.db_client:
                self.db_client = get_database()
            
            if await self.db_client.ensure_connected():
                # Look for test agents in database
                test_agents_collection = self.db_client.database.test_agents
                test_agent = await test_agents_collection.find_one()
                if test_agent:
                    logger.info(f"✅ Found test agent '{test_agent.get('name')}' in database")
                    return {
                        "name": test_agent.get("name"),
                        "email": test_agent.get("email"),
                        "phone": test_agent.get("phone", ""),
                        "calendar_id": test_agent.get("google_calendar_id", test_agent.get("email")),
                        "timezone": test_agent.get("timezone", "America/New_York")
                    }
            
            # Try to get from file as fallback
            test_agent = self._get_agent_from_file("Test Agent")
            if test_agent:
                return test_agent
            
            # Fallback to default test agent
            logger.info("🔧 Using default test agent configuration")
            return {
                "name": "Test Agent",
                "email": "test.agent@altruisadvisor.com",
                "phone": "+1234567890",
                "calendar_id": "test.agent@altruisadvisor.com",
                "timezone": "America/New_York"
            }
            
        except Exception as e:
            logger.error(f"❌ Error getting test agent: {e}")
            return None
    
    async def test_calendar_access(self) -> Dict[str, Any]:
        """Test calendar access and return status"""
        try:
            if not self.is_configured():
                return {"success": False, "error": "Service not configured"}
            
            # Test by listing calendars
            calendar_list = self.service.calendarList().list().execute()
            calendars = calendar_list.get('items', [])
            
            return {
                "success": True,
                "calendar_count": len(calendars),
                "calendars": [{"id": cal["id"], "summary": cal.get("summary", "No title")} for cal in calendars[:5]]
            }
            
        except Exception as e:
            logger.error(f"❌ Calendar access test failed: {e}")
            return {"success": False, "error": str(e)}
    
    async def get_agent_available_slots(self, agent_email: str, days_ahead: int = 7) -> List[Dict[str, Any]]:
        """Get available time slots for an agent"""
        try:
            if not self.is_configured():
                logger.warning("⚠️ Google Calendar not configured")
                return []
            
            # Set timezone
            timezone = pytz.timezone('America/New_York')
            now = datetime.now(timezone)
            end_time = now + timedelta(days=days_ahead)
            
            # Convert to UTC for API
            time_min = now.astimezone(pytz.UTC).isoformat()
            time_max = end_time.astimezone(pytz.UTC).isoformat()
            
            # Query for busy times
            freebusy_request = {
                'timeMin': time_min,
                'timeMax': time_max,
                'items': [{'id': agent_email}]
            }
            
            freebusy_result = self.service.freebusy().query(body=freebusy_request).execute()
            
            # Check if agent calendar exists
            calendar_info = freebusy_result['calendars'].get(agent_email, {})
            if 'errors' in calendar_info:
                logger.warning(f"⚠️ Cannot access calendar for {agent_email}")
                return []
            
            busy_periods = calendar_info.get('busy', [])
            
            # Generate available slots
            available_slots = []
            current_time = now.replace(minute=0, second=0, microsecond=0)
            
            # Start from next business hour
            if current_time.hour < 9:
                current_time = current_time.replace(hour=9)
            elif current_time.hour >= 17:
                current_time = (current_time + timedelta(days=1)).replace(hour=9, minute=0)
            
            while current_time < end_time and len(available_slots) < 20:
                # Skip weekends
                if current_time.weekday() >= 5:
                    current_time = (current_time + timedelta(days=1)).replace(hour=9, minute=0)
                    continue
                
                # Skip outside business hours
                if current_time.hour < 9 or current_time.hour >= 17:
                    if current_time.hour >= 17:
                        current_time = (current_time + timedelta(days=1)).replace(hour=9, minute=0)
                    else:
                        current_time = current_time.replace(hour=9, minute=0)
                    continue
                
                slot_start = current_time
                slot_end = slot_start + timedelta(minutes=15)
                
                # Check if slot conflicts with busy times
                is_available = True
                for busy in busy_periods:
                    busy_start = datetime.fromisoformat(busy['start'].replace('Z', '+00:00'))
                    busy_end = datetime.fromisoformat(busy['end'].replace('Z', '+00:00'))
                    
                    if slot_start.astimezone(pytz.UTC) < busy_end and slot_end.astimezone(pytz.UTC) > busy_start:
                        is_available = False
                        break
                
                if is_available:
                    # Create calendar link for this slot
                    calendar_link = self._create_calendar_link(
                        start_time=slot_start,
                        end_time=slot_end,
                        agent_email=agent_email
                    )
                    
                    available_slots.append({
                        'start_time': slot_start.isoformat(),
                        'end_time': slot_end.isoformat(),
                        'display_time': slot_start.strftime('%A, %B %d at %I:%M %p'),
                        'agent_email': agent_email,
                        'calendar_link': calendar_link
                    })
                
                current_time += timedelta(minutes=15)
            
            logger.info(f"✅ Found {len(available_slots)} available slots for {agent_email}")
            return available_slots
            
        except Exception as e:
            logger.error(f"❌ Error getting availability for {agent_email}: {e}")
            return []
    
    def _create_calendar_link(self, start_time: datetime, end_time: datetime, agent_email: str) -> str:
        """Create a Google Calendar link for scheduling"""
        try:
            # Format times for URL
            start_str = start_time.strftime('%Y%m%dT%H%M%S')
            end_str = end_time.strftime('%Y%m%dT%H%M%S')
            
            # Create calendar event URL
            event_details = {
                'text': 'Discovery Call - Altruis Advisor Group',
                'dates': f'{start_str}/{end_str}',
                'details': '15-minute discovery call to review your health insurance needs and options.',
                'location': 'Phone Call',
                'add': agent_email
            }
            
            # Build URL
            base_url = 'https://calendar.google.com/calendar/render'
            params = '&'.join([f'{k}={v}' for k, v in event_details.items()])
            
            return f"{base_url}?action=TEMPLATE&{params}"
            
        except Exception as e:
            logger.error(f"❌ Error creating calendar link: {e}")
            return "#"
    
    async def schedule_discovery_call(
        self,
        client_email: str,
        agent_email: str,
        start_time: datetime,
        client_name: str,
        agent_name: str
    ) -> Dict[str, Any]:
        """Schedule a discovery call (voice call, not Google Meet)"""
        try:
            if not self.is_configured():
                return {"success": False, "error": "Google Calendar not configured"}
            
            end_time = start_time + timedelta(minutes=15)
            
            # Create event for voice call (no Google Meet)
            event = {
                'summary': f'Discovery Call - {client_name}',
                'description': f'15-minute discovery call with {client_name} to review health insurance needs.\n\nAgenda:\n• Review current policy\n• Assess insurance needs\n• Q&A session\n• Schedule follow-up\n\nFormat: Voice Call (Agent will call client)',
                'start': {
                    'dateTime': start_time.isoformat(),
                    'timeZone': 'America/New_York',
                },
                'end': {
                    'dateTime': end_time.isoformat(),
                    'timeZone': 'America/New_York',
                },
                'attendees': [
                    {'email': client_email, 'displayName': client_name},
                    {'email': agent_email, 'displayName': agent_name},
                ],
                'reminders': {
                    'useDefault': False,
                    'overrides': [
                        {'method': 'email', 'minutes': 24 * 60},
                        {'method': 'email', 'minutes': 60},
                        {'method': 'popup', 'minutes': 15},
                    ],
                }
            }
            
            # Insert event in agent's calendar
            event_result = self.service.events().insert(
                calendarId=agent_email,
                body=event,
                sendUpdates='all'
            ).execute()
            
            logger.info(f"✅ Discovery call scheduled: {event_result['id']}")
            
            return {
                "success": True,
                "event_id": event_result['id'],
                "event_link": event_result.get('htmlLink', ''),
                "start_time": start_time.isoformat(),
                "end_time": end_time.isoformat(),
                "call_type": "voice_call"
            }
            
        except Exception as e:
            logger.error(f"❌ Error scheduling discovery call: {e}")
            return {"success": False, "error": str(e)}
