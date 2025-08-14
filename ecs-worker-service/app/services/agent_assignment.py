"""
Agent Assignment Service
Handles assignment of interested clients to human agents using database
"""

import asyncio
import logging
from typing import Dict, Any, Optional, List
from datetime import datetime, timedelta

from shared.config.settings import settings
from shared.models.call_session import CallSession
from shared.models.client import Client
from shared.utils.agent_repository import agent_repo
from shared.utils.client_repository import client_repo

logger = logging.getLogger(__name__)

class AgentAssignmentService:
    """Handles assignment of clients to human agents using database"""
    
    def __init__(self):
        self.calendar_service = None
        
        # Initialize Google Calendar service if available
        try:
            from .google_calendar_service import calendar_service
            self.calendar_service = calendar_service
            logger.info("✅ Google Calendar service initialized")
        except Exception as e:
            logger.warning(f"⚠️ Google Calendar not available: {e}")
    
    async def assign_agent_to_client(self, session: CallSession) -> Dict[str, Any]:
        """Assign an agent to a client based on session data"""
        try:
            # Get client from database
            client = await self._get_client_from_session(session)
            
            if not client:
                return {
                    "success": False,
                    "error": "client_not_found",
                    "message": "Client not found in database"
                }
            
            # Check if client already has an agent assigned
            if client.assigned_agent_id:
                agent = await agent_repo.get_agent_by_id(client.assigned_agent_id)
                if agent:
                    logger.info(f"✅ Client {client.full_name} already assigned to {agent.name}")
                    return {
                        "success": True,
                        "agent": {
                            "id": agent.agent_id,
                            "name": agent.name,
                            "email": agent.email,
                            "tag_identifier": agent.tag_identifier
                        },
                        "assignment_type": "existing"
                    }
            
            # Find best agent for client
            best_agent = await self._find_best_agent(client)
            
            if not best_agent:
                return {
                    "success": False,
                    "error": "no_available_agent",
                    "message": "No available agent found"
                }
            
            # Assign agent to client
            assignment_success = await self._assign_agent_to_client(client, best_agent)
            
            if not assignment_success:
                return {
                    "success": False,
                    "error": "assignment_failed",
                    "message": "Failed to assign agent to client"
                }
            
            logger.info(f"✅ Assigned {client.full_name} to {best_agent.name}")
            
            return {
                "success": True,
                "agent": {
                    "id": best_agent.agent_id,
                    "name": best_agent.name,
                    "email": best_agent.email,
                    "tag_identifier": best_agent.tag_identifier
                },
                "assignment_type": "new"
            }
            
        except Exception as e:
            logger.error(f"❌ Error assigning agent: {e}")
            return {
                "success": False,
                "error": "assignment_error",
                "message": str(e)
            }
    
    async def _get_client_from_session(self, session: CallSession) -> Optional[Client]:
        """Get client from database based on session data"""
        try:
            # Try to find client by phone number first
            if session.phone_number:
                client = await client_repo.get_client_by_phone(session.phone_number)
                if client:
                    return client
            
            # Try to find by email if available
            if session.client_data and session.client_data.get("email"):
                client = await client_repo.get_client_by_email(session.client_data["email"])
                if client:
                    return client
            
            # Try to find by name if available
            if session.client_data and session.client_data.get("client_name"):
                # Search by name
                clients = await client_repo.search_clients(session.client_data["client_name"], limit=1)
                if clients:
                    return clients[0]
            
            logger.warning(f"⚠️ Client not found for session {session.session_id}")
            return None
            
        except Exception as e:
            logger.error(f"❌ Error getting client from session: {e}")
            return None
    
    async def _find_best_agent(self, client: Client) -> Optional[Any]:
        """Find the best agent for a client"""
        try:
            # If client has a specific agent tag, try to find that agent
            if client.assigned_agent_tag:
                agent = await agent_repo.get_agent_by_tag(client.assigned_agent_tag)
                if agent and agent.is_active:
                    logger.info(f"🎯 Found specific agent for client: {agent.name}")
                    return agent
            
            # Get agents with lowest client count (load balancing)
            agents = await agent_repo.get_agents_with_lowest_client_count(limit=5)
            
            if not agents:
                logger.warning("⚠️ No active agents found")
                return None
            
            # For now, return the first available agent
            # In the future, you could implement more sophisticated selection logic
            best_agent = agents[0]
            logger.info(f"🎯 Selected agent for load balancing: {best_agent.name}")
            return best_agent
            
        except Exception as e:
            logger.error(f"❌ Error finding best agent: {e}")
            return None
    
    async def _assign_agent_to_client(self, client: Client, agent: Any) -> bool:
        """Assign agent to client in database"""
        try:
            from shared.models.client import ClientAssignment
            
            # Create assignment
            assignment = ClientAssignment(
                client_id=client.client_id,
                agent_id=agent.agent_id,
                agent_name=agent.name,
                agent_tag=agent.tag_identifier,
                assignment_reason="voice_call_assignment"
            )
            
            # Update client with agent assignment
            success = await client_repo.assign_agent_to_client(client.client_id, assignment)
            
            if success:
                # Increment agent's client count
                await agent_repo.increment_client_count(agent.agent_id)
                logger.info(f"✅ Successfully assigned {client.full_name} to {agent.name}")
                return True
            else:
                logger.error(f"❌ Failed to assign agent to client")
                return False
                
        except Exception as e:
            logger.error(f"❌ Error assigning agent to client: {e}")
            return False
    
    async def get_agent_availability(self, agent_id: str) -> List[Dict[str, Any]]:
        """Get agent's available time slots"""
        try:
            if not self.calendar_service:
                logger.warning("⚠️ Calendar service not available, using mock slots")
                return self._generate_mock_slots()
            
            # Get agent from database
            agent = await agent_repo.get_agent_by_id(agent_id)
            if not agent:
                logger.error(f"❌ Agent not found: {agent_id}")
                return []
            
            # Get calendar availability
            available_slots = await self.calendar_service.get_agent_availability(
                agent.email, 
                datetime.now(), 
                datetime.now() + timedelta(days=7)
            )
            
            return available_slots
            
        except Exception as e:
            logger.error(f"❌ Error getting agent availability: {e}")
            return self._generate_mock_slots()
    
    def _generate_mock_slots(self) -> List[Dict[str, Any]]:
        """Generate mock time slots for testing"""
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
                    "timestamp": int(slot_time.timestamp())
                }
                
                mock_slots.append(slot_data)
                
                if len(mock_slots) >= 9:  # Max 9 mock slots
                    break
            
            if len(mock_slots) >= 9:
                break
        
        return mock_slots

# Global instance
agent_assignment_service = AgentAssignmentService()
                "timezone": "America/New_York",
                "working_hours": "9AM-5PM",
                "specialties": ["medicare", "supplements"],
                "tag_identifier": "AB - Hineth Pettway",
                "client_count": 649
            },
            {
                "id": "keith_braswell",
                "name": "Keith Braswell",
                "email": "keith@altruisadvisor.com",
                "google_calendar_id": "keith@altruisadvisor.com",
                "timezone": "America/New_York",
                "working_hours": "9AM-5PM",
                "specialties": ["auto", "commercial"],
                "tag_identifier": "AB - Keith Braswell",
                "client_count": 584
            }
        ]
        
        # Try to load from data/agents.json if it exists
        try:
            with open("data/agents.json", "r") as f:
                agents_data = json.load(f)
                if "agents" in agents_data:
                    agents_data = agents_data["agents"]
        except FileNotFoundError:
            agents_data = default_agents
        except Exception as e:
            logger.warning(f"⚠️ Error loading agents.json, using defaults: {e}")
            agents_data = default_agents
        
        # Convert to Agent objects
        agents = []
        for agent_data in agents_data:
            agents.append(Agent(**agent_data))
        
        logger.info(f"✅ Loaded {len(agents)} agents")
        return agents
    
    def _init_calendar_service(self):
        """Initialize Google Calendar service"""
        
        try:
            credentials = service_account.Credentials.from_service_account_file(
                settings.google_service_account_file,
                scopes=['https://www.googleapis.com/auth/calendar']
            )
            
            self.calendar_service = build('calendar', 'v3', credentials=credentials)
            
        except Exception as e:
            logger.error(f"❌ Failed to initialize Google Calendar: {e}")
            self.calendar_service = None
    
    async def assign_agent(self, client: Client) -> Dict[str, Any]:
        """Assign an agent to interested client"""
        
        try:
            # Find best agent for client
            best_agent = await self._find_best_agent(client)
            
            if not best_agent:
                return {
                    "success": False,
                    "error": "no_available_agent",
                    "client_id": client.id
                }
            
            # Check agent availability
            available_slots = await self._get_agent_availability(best_agent)
            
            if not available_slots:
                return {
                    "success": False,
                    "error": "no_available_slots",
                    "agent_id": best_agent.id,
                    "client_id": client.id
                }
            
            # Schedule meeting
            meeting_result = await self._schedule_meeting(best_agent, client, available_slots[0])
            
            if not meeting_result["success"]:
                return {
                    "success": False,
                    "error": "scheduling_failed",
                    "details": meeting_result.get("error"),
                    "client_id": client.id
                }
            
            # Update client record
            await client_repo.assign_agent(client.id, best_agent.id, best_agent.name)
            
            # Send notification email
            await self._send_assignment_notification(best_agent, client, meeting_result)
            
            logger.info(f"✅ Assigned {client.client.full_name} to {best_agent.name}")
            
            return {
                "success": True,
                "agent_id": best_agent.id,
                "agent_name": best_agent.name,
                "agent_email": best_agent.email,
                "meeting_scheduled": meeting_result.get("meeting_time"),
                "calendar_event_id": meeting_result.get("event_id"),
                "client_id": client.id
            }
            
        except Exception as e:
            logger.error(f"❌ Agent assignment error: {e}")
            return {
                "success": False,
                "error": str(e),
                "client_id": client.id
            }
    
    async def _find_best_agent(self, client: Client) -> Optional[Agent]:
        """Find the best agent for a client"""
        
        # Check if client has a preferred agent from their history
        preferred_agent_id = client.client.last_agent
        
        if preferred_agent_id:
            for agent in self.agents:
                if agent.id == preferred_agent_id:
                    logger.info(f"🎯 Using preferred agent: {agent.name}")
                    return agent
        
        # Find agent with lowest current workload
        available_agents = [agent for agent in self.agents]
        
        if not available_agents:
            return None
        
        # Sort by current client count (workload balancing)
        best_agent = min(available_agents, key=lambda a: a.client_count)
        
        logger.info(f"🎯 Selected agent: {best_agent.name} (workload: {best_agent.client_count})")
        return best_agent
    
    async def _get_agent_availability(self, agent: Agent) -> List[datetime]:
        """Get available time slots for agent"""
        
        if not self.calendar_service:
            # Mock availability for development
            return await self._mock_agent_availability()
        
        try:
            # Get calendar events for next 7 days
            now = datetime.utcnow()
            time_min = now.isoformat() + 'Z'
            time_max = (now + timedelta(days=7)).isoformat() + 'Z'
            
            events_result = self.calendar_service.events().list(
                calendarId=agent.google_calendar_id,
                timeMin=time_min,
                timeMax=time_max,
                singleEvents=True,
                orderBy='startTime'
            ).execute()
            
            events = events_result.get('items', [])
            
            # Find free slots (simplified - would need more complex logic for production)
            available_slots = []
            
            # Check next 5 business days
            for day_offset in range(5):
                check_date = now + timedelta(days=day_offset + 1)
                
                # Skip weekends
                if check_date.weekday() >= 5:
                    continue
                
                # Check common meeting times (10 AM, 2 PM, 4 PM)
                for hour in [10, 14, 16]:
                    slot_time = check_date.replace(hour=hour, minute=0, second=0, microsecond=0)
                    
                    # Check if slot is free
                    if not self._is_time_slot_busy(slot_time, events):
                        available_slots.append(slot_time)
                    
                    if len(available_slots) >= 3:  # Return first 3 available slots
                        break
                
                if len(available_slots) >= 3:
                    break
            
            return available_slots
            
        except HttpError as e:
            logger.error(f"❌ Google Calendar API error: {e}")
            return await self._mock_agent_availability()
        except Exception as e:
            logger.error(f"❌ Error getting agent availability: {e}")
            return await self._mock_agent_availability()
    
    def _is_time_slot_busy(self, slot_time: datetime, events: List[Dict]) -> bool:
        """Check if a time slot conflicts with existing events"""
        
        slot_end = slot_time + timedelta(minutes=30)  # 30-minute meetings
        
        for event in events:
            if 'start' not in event or 'end' not in event:
                continue
            
            # Parse event times
            event_start_str = event['start'].get('dateTime', event['start'].get('date'))
            event_end_str = event['end'].get('dateTime', event['end'].get('date'))
            
            if not event_start_str or not event_end_str:
                continue
            
            try:
                # Handle different datetime formats
                if 'T' in event_start_str:
                    event_start = datetime.fromisoformat(event_start_str.replace('Z', '+00:00'))
                    event_end = datetime.fromisoformat(event_end_str.replace('Z', '+00:00'))
                    
                    # Convert to UTC for comparison
                    event_start = event_start.replace(tzinfo=None)
                    event_end = event_end.replace(tzinfo=None)
                    
                    # Check for overlap
                    if (slot_time < event_end and slot_end > event_start):
                        return True
                        
            except Exception as e:
                logger.warning(f"⚠️ Error parsing event time: {e}")
                continue
        
        return False
    
    async def _mock_agent_availability(self) -> List[datetime]:
        """Mock agent availability for development"""
        
        now = datetime.utcnow()
        available_slots = []
        
        # Generate mock slots for next 3 business days
        for day_offset in range(1, 4):
            check_date = now + timedelta(days=day_offset)
            
            # Skip weekends
            if check_date.weekday() >= 5:
                continue
            
            # Mock available times
            for hour in [10, 14, 16]:
                slot_time = check_date.replace(hour=hour, minute=0, second=0, microsecond=0)
                available_slots.append(slot_time)
        
        return available_slots[:3]  # Return first 3 slots
    
    async def _schedule_meeting(self, agent: Agent, client: Client, meeting_time: datetime) -> Dict[str, Any]:
        """Schedule meeting with agent and client"""
        
        if not self.calendar_service:
            return await self._mock_schedule_meeting(agent, client, meeting_time)
        
        try:
            # Create calendar event
            event = {
                'summary': f'Discovery Call - {client.client.full_name}',
                'description': f'''
Discovery call with {client.client.full_name}

Client Details:
- Phone: {client.client.phone}
- Email: {client.client.email}

Call Summary:
Generated by LYZR Voice Agent System - client expressed interest during outbound campaign call.

Please review client history before the call.
                '''.strip(),
                'start': {
                    'dateTime': meeting_time.isoformat() + 'Z',
                    'timeZone': agent.timezone,
                },
                'end': {
                    'dateTime': (meeting_time + timedelta(minutes=30)).isoformat() + 'Z',
                    'timeZone': agent.timezone,
                },
                'attendees': [
                    {'email': agent.email},
                    {'email': client.client.email} if client.client.email else None
                ],
                'reminders': {
                    'useDefault': False,
                    'overrides': [
                        {'method': 'email', 'minutes': 24 * 60},  # 1 day before
                        {'method': 'popup', 'minutes': 15},       # 15 minutes before
                    ],
                },
            }
            
            # Remove None attendees
            event['attendees'] = [a for a in event['attendees'] if a is not None]
            
            # Create the event
            created_event = self.calendar_service.events().insert(
                calendarId=agent.google_calendar_id,
                body=event
            ).execute()
            
            logger.info(f"✅ Meeting scheduled: {meeting_time} - {agent.name} & {client.client.full_name}")
            
            return {
                "success": True,
                "event_id": created_event['id'],
                "meeting_time": meeting_time.isoformat(),
                "calendar_link": created_event.get('htmlLink')
            }
            
        except HttpError as e:
            logger.error(f"❌ Calendar scheduling error: {e}")
            return {"success": False, "error": f"calendar_error: {e}"}
        except Exception as e:
            logger.error(f"❌ Meeting scheduling error: {e}")
            return {"success": False, "error": str(e)}
    
    async def _mock_schedule_meeting(self, agent: Agent, client: Client, meeting_time: datetime) -> Dict[str, Any]:
        """Mock meeting scheduling for development"""
        
        logger.info(f"🔧 Mock scheduling meeting: {meeting_time} - {agent.name} & {client.client.full_name}")
        
        return {
            "success": True,
            "event_id": f"mock_event_{int(meeting_time.timestamp())}",
            "meeting_time": meeting_time.isoformat(),
            "calendar_link": "https://calendar.google.com/mock-event",
            "mock": True
        }
    
    async def _send_assignment_notification(self, agent: Agent, client: Client, meeting_result: Dict[str, Any]):
        """Send email notification to agent about new assignment"""
        
        # This would integrate with SES to send actual emails
        # For now, just log the notification
        
        logger.info(f"📧 Sending assignment notification to {agent.email}")
        logger.info(f"   Client: {client.client.full_name} ({client.client.phone})")
        logger.info(f"   Meeting: {meeting_result.get('meeting_time')}")
        
        # TODO: Implement actual email sending using SES
        
    async def get_agent_workload(self) -> Dict[str, Any]:
        """Get current workload for all agents"""
        
        workload = {}
        
        for agent in self.agents:
            # Get assigned clients count from database
            assigned_count = await client_repo.get_agent_assigned_count(agent.id)
            
            workload[agent.id] = {
                "name": agent.name,
                "email": agent.email,
                "current_assignments": assigned_count,
                "base_client_count": agent.client_count,
                "specialties": agent.specialties
            }
        
        return workload
    
    async def reassign_client(self, client_id: str, new_agent_id: str) -> Dict[str, Any]:
        """Reassign client to different agent"""
        
        try:
            # Find new agent
            new_agent = None
            for agent in self.agents:
                if agent.id == new_agent_id:
                    new_agent = agent
                    break
            
            if not new_agent:
                return {"success": False, "error": "agent_not_found"}
            
            # Update client assignment
            await client_repo.assign_agent(client_id, new_agent.id, new_agent.name)
            
            logger.info(f"✅ Client {client_id} reassigned to {new_agent.name}")
            
            return {
                "success": True,
                "new_agent_id": new_agent.id,
                "new_agent_name": new_agent.name
            }
            
        except Exception as e:
            logger.error(f"❌ Reassignment error: {e}")
            return {"success": False, "error": str(e)}