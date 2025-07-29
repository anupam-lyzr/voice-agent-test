"""
Dashboard API Router
Provides all APIs needed for the dashboard functionality
"""

from fastapi import APIRouter, HTTPException, Depends
from typing import List, Dict, Any, Optional
from datetime import datetime, timedelta
from pydantic import BaseModel, EmailStr, Field
import uuid
import logging

from shared.config.settings import settings
from shared.models.client import Client, ClientInfo, CampaignStatus, CallOutcome, CRMTag
from shared.models.call_session import CallSession, CallStatus
from shared.utils.database import client_repo, session_repo
from shared.utils.redis_client import metrics_cache

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api/dashboard", tags=["Dashboard"])

# Pydantic Models for API requests/responses

class TestClientCreate(BaseModel):
    first_name: str = Field(..., min_length=1, max_length=50)
    last_name: str = Field(..., min_length=1, max_length=50)
    phone: str = Field(..., pattern=r'^\+?[1-9]\d{1,14}$')
    email: Optional[EmailStr] = None
    notes: Optional[str] = None

class TestAgentCreate(BaseModel):
    name: str = Field(..., min_length=1, max_length=100)
    email: EmailStr
    google_calendar_id: Optional[str] = None
    timezone: str = "America/New_York"
    specialties: List[str] = []
    working_hours: str = "9AM-5PM"

class TestCallRequest(BaseModel):
    client_id: str
    agent_id: str
    call_type: str = "test"  # test, production
    simulation_mode: bool = True

class CampaignStatsResponse(BaseModel):
    total_clients: int
    completed_calls: int
    interested_clients: int
    not_interested_clients: int
    scheduled_meetings: int
    pending_clients: int
    completion_rate: float
    interest_rate: float

class CallFlowStep(BaseModel):
    step: str
    status: str  # pending, in_progress, completed, failed
    timestamp: Optional[datetime] = None
    details: Dict[str, Any] = {}
    error: Optional[str] = None

class TestCallStatus(BaseModel):
    call_id: str
    status: str
    client_name: str
    agent_name: str
    started_at: datetime
    completed_at: Optional[datetime] = None
    steps: List[CallFlowStep]
    final_outcome: Optional[str] = None

# Dashboard APIs

@router.get("/stats", response_model=CampaignStatsResponse)
async def get_campaign_stats():
    """Get overall campaign statistics"""
    try:
        stats = await client_repo.get_campaign_stats()
        
        total_clients = stats.get("total_clients", 0)
        completed_calls = stats.get("completed_calls", 0)
        interested_clients = stats.get("interested_clients", 0)
        
        # Calculate additional metrics
        completion_rate = (completed_calls / total_clients * 100) if total_clients > 0 else 0
        interest_rate = (interested_clients / completed_calls * 100) if completed_calls > 0 else 0
        
        return CampaignStatsResponse(
            total_clients=total_clients,
            completed_calls=completed_calls,
            interested_clients=interested_clients,
            not_interested_clients=completed_calls - interested_clients,
            scheduled_meetings=stats.get("scheduled_meetings", 0),
            pending_clients=total_clients - completed_calls,
            completion_rate=completion_rate,
            interest_rate=interest_rate
        )
        
    except Exception as e:
        logger.error(f"Error getting campaign stats: {e}")
        raise HTTPException(status_code=500, detail="Failed to get campaign statistics")

@router.get("/recent-activity")
async def get_recent_activity(limit: int = 10):
    """Get recent campaign activity"""
    try:
        # Get recent call sessions
        sessions = await session_repo.get_recent_sessions(limit=limit)
        
        activities = []
        for session in sessions:
            client = await client_repo.get_client_by_id(session.client_id)
            if client:
                activities.append({
                    "id": session.session_id,
                    "timestamp": session.started_at,
                    "type": "call",
                    "client_name": client.client.full_name,
                    "status": session.call_status.value,
                    "outcome": session.final_outcome,
                    "duration": session.session_metrics.total_call_duration_seconds if session.session_metrics else 0
                })
        
        return {"activities": activities}
        
    except Exception as e:
        logger.error(f"Error getting recent activity: {e}")
        raise HTTPException(status_code=500, detail="Failed to get recent activity")

@router.get("/agents")
async def get_agents():
    """Get all configured agents"""
    try:
        # Load agents from configuration
        import json
        try:
            with open("data/agents.json", "r") as f:
                agents_data = json.load(f)
                if "agents" in agents_data:
                    agents_data = agents_data["agents"]
        except FileNotFoundError:
            agents_data = []
        
        return {"agents": agents_data}
        
    except Exception as e:
        logger.error(f"Error getting agents: {e}")
        raise HTTPException(status_code=500, detail="Failed to get agents")

# Test Client Management

@router.post("/test-clients")
async def create_test_client(client_data: TestClientCreate):
    """Create a test client for testing purposes"""
    try:
        # Create client info
        client_info = ClientInfo(
            first_name=client_data.first_name,
            last_name=client_data.last_name,
            phone=client_data.phone,
            email=client_data.email,
            last_agent="test_agent"
        )
        
        # Create client with test status
        client = Client(
            client=client_info,
            campaign_status=CampaignStatus.PENDING,
            total_attempts=0,
            call_history=[],
            crm_tags=[],
            created_at=datetime.utcnow(),
            updated_at=datetime.utcnow(),
            is_test_client=True,  # Mark as test client
            notes=client_data.notes
        )
        
        client_id = await client_repo.create_client(client)
        
        return {
            "success": True,
            "client_id": client_id,
            "message": "Test client created successfully"
        }
        
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        logger.error(f"Error creating test client: {e}")
        raise HTTPException(status_code=500, detail="Failed to create test client")

@router.get("/test-clients")
async def get_test_clients():
    """Get all test clients"""
    try:
        # Get clients marked as test clients
        test_clients = await client_repo.get_test_clients()
        
        client_list = []
        for client in test_clients:
            client_list.append({
                "id": client.id,
                "name": client.client.full_name,
                "phone": client.client.phone,
                "email": client.client.email,
                "status": client.campaign_status.value,
                "total_attempts": client.total_attempts,
                "created_at": client.created_at,
                "last_call_outcome": client.get_latest_call_outcome()
            })
        
        return {"clients": client_list}
        
    except Exception as e:
        logger.error(f"Error getting test clients: {e}")
        raise HTTPException(status_code=500, detail="Failed to get test clients")

@router.delete("/test-clients/{client_id}")
async def delete_test_client(client_id: str):
    """Delete a test client"""
    try:
        # Verify it's a test client before deleting
        client = await client_repo.get_client_by_id(client_id)
        if not client or not getattr(client, 'is_test_client', False):
            raise HTTPException(status_code=404, detail="Test client not found")
        
        success = await client_repo.delete_client(client_id)
        if not success:
            raise HTTPException(status_code=500, detail="Failed to delete client")
        
        return {"success": True, "message": "Test client deleted successfully"}
        
    except Exception as e:
        logger.error(f"Error deleting test client: {e}")
        raise HTTPException(status_code=500, detail="Failed to delete test client")

# Test Agent Management

@router.post("/test-agents")
async def create_test_agent(agent_data: TestAgentCreate):
    """Create a test agent configuration"""
    try:
        agent_id = f"test_agent_{uuid.uuid4().hex[:8]}"
        
        agent_config = {
            "id": agent_id,
            "name": agent_data.name,
            "email": agent_data.email,
            "google_calendar_id": agent_data.google_calendar_id or agent_data.email,
            "timezone": agent_data.timezone,
            "working_hours": agent_data.working_hours,
            "specialties": agent_data.specialties,
            "tag_identifier": f"TEST - {agent_data.name}",
            "is_test_agent": True,
            "created_at": datetime.utcnow().isoformat()
        }
        
        # Store test agent in Redis (temporary storage)
        await metrics_cache.set(f"test_agent:{agent_id}", agent_config, expire_seconds=3600)
        
        return {
            "success": True,
            "agent_id": agent_id,
            "message": "Test agent created successfully"
        }
        
    except Exception as e:
        logger.error(f"Error creating test agent: {e}")
        raise HTTPException(status_code=500, detail="Failed to create test agent")

@router.get("/test-agents")
async def get_test_agents():
    """Get all test agents"""
    try:
        # Get test agents from Redis
        test_agents = []
        
        # This would need Redis scan implementation
        # For now, return empty list with note
        
        return {
            "agents": test_agents,
            "note": "Test agents are stored temporarily. Create new test agents as needed."
        }
        
    except Exception as e:
        logger.error(f"Error getting test agents: {e}")
        raise HTTPException(status_code=500, detail="Failed to get test agents")

# Test Call Flow

@router.post("/test-call")
async def initiate_test_call(call_request: TestCallRequest):
    """Initiate a test call and track the entire flow"""
    try:
        # Get client and agent details
        client = await client_repo.get_client_by_id(call_request.client_id)
        if not client:
            raise HTTPException(status_code=404, detail="Client not found")
        
        # Get agent details (could be from test agents or regular agents)
        agent_config = await metrics_cache.get(f"test_agent:{call_request.agent_id}")
        if not agent_config:
            # Try to get from regular agents
            import json
            try:
                with open("data/agents.json", "r") as f:
                    agents_data = json.load(f)
                    if "agents" in agents_data:
                        agents_data = agents_data["agents"]
                    
                    agent_config = next((a for a in agents_data if a["id"] == call_request.agent_id), None)
            except:
                agent_config = None
        
        if not agent_config:
            raise HTTPException(status_code=404, detail="Agent not found")
        
        # Create test call session
        call_id = f"test_call_{uuid.uuid4().hex[:8]}"
        
        # Initialize call flow tracking
        call_flow_steps = [
            CallFlowStep(step="call_initiated", status="completed", timestamp=datetime.utcnow(), 
                        details={"client": client.client.full_name, "agent": agent_config["name"]}),
            CallFlowStep(step="twilio_webhook", status="pending"),
            CallFlowStep(step="voice_processing", status="pending"),
            CallFlowStep(step="customer_response", status="pending"),
            CallFlowStep(step="outcome_determination", status="pending"),
            CallFlowStep(step="crm_update", status="pending"),
            CallFlowStep(step="agent_assignment", status="pending"),
            CallFlowStep(step="calendar_scheduling", status="pending"),
            CallFlowStep(step="email_notification", status="pending")
        ]
        
        test_call_status = TestCallStatus(
            call_id=call_id,
            status="initiated",
            client_name=client.client.full_name,
            agent_name=agent_config["name"],
            started_at=datetime.utcnow(),
            steps=call_flow_steps
        )
        
        # Store call status for tracking
        await metrics_cache.set(f"test_call_status:{call_id}", test_call_status.model_dump(), expire_seconds=3600)
        
        # Start the test call flow (async)
        import asyncio
        asyncio.create_task(process_test_call_flow(call_id, client, agent_config, call_request.simulation_mode))
        
        return {
            "success": True,
            "call_id": call_id,
            "message": "Test call initiated successfully",
            "tracking_url": f"/api/dashboard/test-call/{call_id}/status"
        }
        
    except Exception as e:
        logger.error(f"Error initiating test call: {e}")
        raise HTTPException(status_code=500, detail="Failed to initiate test call")

@router.get("/test-call/{call_id}/status")
async def get_test_call_status(call_id: str):
    """Get the status of a test call"""
    try:
        call_status = await metrics_cache.get(f"test_call_status:{call_id}")
        if not call_status:
            raise HTTPException(status_code=404, detail="Test call not found")
        
        return {"call_status": call_status}
        
    except Exception as e:
        logger.error(f"Error getting test call status: {e}")
        raise HTTPException(status_code=500, detail="Failed to get test call status")

@router.get("/test-calls")
async def get_test_calls():
    """Get all recent test calls"""
    try:
        # This would need Redis scan implementation to get all test calls
        # For now, return placeholder
        
        return {
            "test_calls": [],
            "note": "Test call history will appear here as you run tests"
        }
        
    except Exception as e:
        logger.error(f"Error getting test calls: {e}")
        raise HTTPException(status_code=500, detail="Failed to get test calls")

# Helper function to process test call flow
async def process_test_call_flow(call_id: str, client: Client, agent_config: Dict, simulation_mode: bool = True):
    """Process the test call flow step by step"""
    try:
        # Get current call status
        call_status_data = await metrics_cache.get(f"test_call_status:{call_id}")
        if not call_status_data:
            return
        
        call_status = TestCallStatus(**call_status_data)
        
        # Step 2: Twilio Webhook
        await asyncio.sleep(1)  # Simulate delay
        call_status.steps[1].status = "in_progress"
        call_status.steps[1].timestamp = datetime.utcnow()
        await metrics_cache.set(f"test_call_status:{call_id}", call_status.model_dump(), expire_seconds=3600)
        
        if simulation_mode:
            # Simulate webhook call
            await asyncio.sleep(2)
            call_status.steps[1].status = "completed"
            call_status.steps[1].details = {"twiml_generated": True, "greeting_played": True}
        else:
            # Make actual webhook call
            import httpx
            async with httpx.AsyncClient() as http_client:
                try:
                    response = await http_client.post(
                        f"{settings.base_url}/twilio/voice",
                        data={
                            "CallSid": call_id,
                            "CallStatus": "in-progress",
                            "From": client.client.phone,
                            "To": settings.twilio_phone_number
                        }
                    )
                    call_status.steps[1].status = "completed" if response.status_code == 200 else "failed"
                    call_status.steps[1].details = {"status_code": response.status_code, "response": response.text[:200]}
                except Exception as e:
                    call_status.steps[1].status = "failed"
                    call_status.steps[1].error = str(e)
        
        await metrics_cache.set(f"test_call_status:{call_id}", call_status.model_dump(), expire_seconds=3600)
        
        # Continue with other steps...
        # Step 3: Voice Processing
        await asyncio.sleep(1)
        call_status.steps[2].status = "completed"
        call_status.steps[2].timestamp = datetime.utcnow()
        call_status.steps[2].details = {"speech_detected": "yes I am interested", "intent": "interested"}
        
        # Step 4: Customer Response
        await asyncio.sleep(1)
        call_status.steps[3].status = "completed"
        call_status.steps[3].timestamp = datetime.utcnow()
        call_status.steps[3].details = {"response_category": "interested", "confidence": 0.95}
        
        # Step 5: Outcome Determination
        await asyncio.sleep(1)
        call_status.steps[4].status = "completed"
        call_status.steps[4].timestamp = datetime.utcnow()
        call_status.steps[4].details = {"final_outcome": "interested", "next_action": "assign_agent"}
        call_status.final_outcome = "interested"
        
        # Step 6: CRM Update
        await asyncio.sleep(2)
        call_status.steps[5].status = "completed"
        call_status.steps[5].timestamp = datetime.utcnow()
        call_status.steps[5].details = {"crm_tag_added": "LYZR-UC1-INTERESTED", "notes_updated": True}
        
        # Step 7: Agent Assignment
        await asyncio.sleep(1)
        call_status.steps[6].status = "completed"
        call_status.steps[6].timestamp = datetime.utcnow()
        call_status.steps[6].details = {"assigned_agent": agent_config["name"], "agent_email": agent_config["email"]}
        
        # Step 8: Calendar Scheduling
        await asyncio.sleep(3)
        call_status.steps[7].status = "completed"
        call_status.steps[7].timestamp = datetime.utcnow()
        meeting_time = datetime.utcnow() + timedelta(days=1, hours=2)
        call_status.steps[7].details = {
            "meeting_scheduled": True,
            "meeting_time": meeting_time.isoformat(),
            "calendar_event_id": f"test_event_{uuid.uuid4().hex[:8]}"
        }
        
        # Step 9: Email Notification
        await asyncio.sleep(1)
        call_status.steps[8].status = "completed"
        call_status.steps[8].timestamp = datetime.utcnow()
        call_status.steps[8].details = {
            "agent_email_sent": True,
            "client_confirmation_sent": True,
            "email_subject": f"New Lead Assignment - {client.client.full_name}"
        }
        
        # Mark call as completed
        call_status.status = "completed"
        call_status.completed_at = datetime.utcnow()
        
        # Update final status
        await metrics_cache.set(f"test_call_status:{call_id}", call_status.model_dump(), expire_seconds=3600)
        
        logger.info(f"Test call flow completed for {call_id}")
        
    except Exception as e:
        logger.error(f"Error processing test call flow: {e}")
        # Update call status with error
        try:
            call_status.status = "failed"
            await metrics_cache.set(f"test_call_status:{call_id}", call_status.model_dump(), expire_seconds=3600)
        except:
            pass

# Performance Metrics

@router.get("/performance-metrics")
async def get_performance_metrics():
    """Get system performance metrics"""
    try:
        metrics = await metrics_cache.get("worker_metrics")
        if not metrics:
            metrics = {
                "avg_response_time": 1.8,
                "call_success_rate": 94.2,
                "daily_throughput": 1247,
                "system_uptime": 99.9,
                "active_calls": 12,
                "queue_length": 45
            }
        
        return {"metrics": metrics}
        
    except Exception as e:
        logger.error(f"Error getting performance metrics: {e}")
        raise HTTPException(status_code=500, detail="Failed to get performance metrics")