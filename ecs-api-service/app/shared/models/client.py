"""
Client Data Models
Pydantic models for client information and call history
"""

from pydantic import BaseModel, Field
from typing import Optional, List, Dict, Any
from datetime import datetime
from enum import Enum
from .custom_types import PyObjectId
class CampaignStatus(str, Enum):
    """Campaign status for each client"""
    PENDING = "pending"
    IN_PROGRESS = "in_progress"
    COMPLETED = "completed"
    FAILED = "failed"
    PAUSED = "paused"

class CallOutcome(str, Enum):
    """Possible outcomes for a call attempt"""
    NO_ANSWER = "no_answer"
    BUSY = "busy"
    VOICEMAIL = "voicemail"
    ANSWERED = "answered"
    INTERESTED = "interested"
    NOT_INTERESTED = "not_interested"
    DNC_REQUESTED = "dnc_requested"
    INVALID_NUMBER = "invalid_number"
    FAILED = "failed"

class CRMTag(str, Enum):
    """CRM tags for client categorization"""
    INTERESTED = "LYZR-UC1-INTERESTED"
    NOT_INTERESTED = "LYZR-UC1-NOT-INTERESTED"
    DNC_REQUESTED = "LYZR-UC1-DNC-REQUESTED"
    NO_CONTACT = "LYZR-UC1-NO-CONTACT"
    INVALID_NUMBER = "LYZR-UC1-INVALID-NUMBER"
    INVALID_EMAIL = "LYZR-UC1-INVALID-EMAIL"
    AAG_MEDICARE_CLIENT = "AAG - Medicare Client"
    AB_ANTHONY_FRACCHIA = "AB - Anthony Fracchia"

class AudioType(str, Enum):
    """Type of audio used in the call"""
    STATIC = "static"        # Pre-generated audio
    DYNAMIC = "dynamic"      # Real-time TTS
    HYBRID = "hybrid"        # Mix of both

class ClientInfo(BaseModel):
    """Basic client information from CSV"""
    first_name: str = Field(..., description="Client's first name")
    last_name: str = Field(..., description="Client's last name")
    phone: str = Field(..., description="Client's phone number")
    email: str = Field(..., description="Client's email address")
    last_agent: str = Field(..., description="ID of the last agent who handled this client")
    
    @property
    def full_name(self) -> str:
        """Get client's full name"""
        return f"{self.first_name} {self.last_name}"
    
    def model_dump_for_greeting(self) -> dict:
        """Get data formatted for greeting personalization"""
        return {
            "client_name": self.full_name,
            "first_name": self.first_name,
            "last_agent": self.last_agent
        }

class CallAttempt(BaseModel):
    """Individual call attempt record"""
    attempt_number: int = Field(..., description="Attempt number (1-6)")
    timestamp: datetime = Field(default_factory=datetime.utcnow, description="When the attempt was made")
    outcome: CallOutcome = Field(..., description="Result of the call attempt")
    duration_seconds: Optional[int] = Field(None, description="Call duration in seconds")
    twilio_call_sid: Optional[str] = Field(None, description="Twilio call SID")
    
    # Audio and conversation details
    audio_type: Optional[AudioType] = Field(None, description="Type of audio used")
    transcript: Optional[str] = Field(None, description="Full conversation transcript")
    agent_responses: List[str] = Field(default_factory=list, description="Agent responses during call")
    
    # Technical details
    error_message: Optional[str] = Field(None, description="Error message if call failed")
    response_times: Dict[str, float] = Field(default_factory=dict, description="Performance metrics")
    
    # Conversation analysis
    conversation_turns: int = Field(default=0, description="Number of conversation turns")
    static_responses_used: int = Field(default=0, description="Number of pre-generated responses used")
    dynamic_responses_used: int = Field(default=0, description="Number of real-time responses used")

class CallSummary(BaseModel):
    """LYZR-generated call summary"""
    summary_id: str = Field(..., description="Unique summary ID")
    generated_at: datetime = Field(default_factory=datetime.utcnow, description="When summary was generated")
    
    # Core summary data
    outcome: CallOutcome = Field(..., description="Call outcome")
    sentiment: str = Field(..., description="Customer sentiment (positive/neutral/negative)")
    key_points: List[str] = Field(default_factory=list, description="Key conversation points")
    customer_concerns: List[str] = Field(default_factory=list, description="Customer concerns mentioned")
    
    # Actionable insights
    recommended_actions: List[str] = Field(default_factory=list, description="Recommended next actions")
    agent_notes: str = Field(default="", description="Notes for assigned agent")
    urgency: str = Field(default="medium", description="Urgency level (high/medium/low)")
    follow_up_timeframe: str = Field(default="within_week", description="Recommended follow-up timing")
    
    # Interest analysis
    interest_level: str = Field(default="unknown", description="Customer interest level")
    services_mentioned: List[str] = Field(default_factory=list, description="Insurance services discussed")
    objections_raised: List[str] = Field(default_factory=list, description="Customer objections")
    
    # Quality metrics
    conversation_quality: str = Field(default="good", description="Overall conversation quality")
    agent_performance: str = Field(default="good", description="AI agent performance assessment")

class AgentAssignment(BaseModel):
    """Agent assignment details"""
    agent_id: str = Field(..., description="Assigned agent ID")
    assigned_at: datetime = Field(default_factory=datetime.utcnow, description="When agent was assigned")
    assignment_reason: str = Field(default="interested", description="Reason for assignment")
    
    # Meeting scheduling
    meeting_scheduled: Optional[datetime] = Field(None, description="Scheduled meeting time")
    meeting_status: str = Field(default="pending", description="Meeting status")
    calendar_event_id: Optional[str] = Field(None, description="Google Calendar event ID")
    
    # Communication history
    emails_sent: List[str] = Field(default_factory=list, description="Emails sent to client/agent")
    last_contact_attempt: Optional[datetime] = Field(None, description="Last contact attempt")

class Client(BaseModel):
    """Complete client record with call history"""
    # MongoDB document ID
    # id: Optional[str] = Field(None, alias="_id", description="MongoDB document ID")
    id: PyObjectId = Field(default_factory=PyObjectId, alias="_id")
    # Core client information
    client: ClientInfo = Field(..., description="Basic client information")
    
    # Campaign tracking
    campaign_status: CampaignStatus = Field(default=CampaignStatus.PENDING, description="Current campaign status")
    total_attempts: int = Field(default=0, description="Total number of call attempts")
    
    # Call history
    call_history: List[CallAttempt] = Field(default_factory=list, description="All call attempts")
    
    # Current call summary (latest)
    current_summary: Optional[CallSummary] = Field(None, description="Most recent call summary")
    
    # CRM integration
    crm_tags: List[CRMTag] = Field(default_factory=list, description="Applied CRM tags")
    capsule_person_id: Optional[str] = Field(None, description="Capsule CRM person ID")
    
    # Agent assignment
    agent_assignment: Optional[AgentAssignment] = Field(None, description="Current agent assignment")
    
    # Timestamps
    created_at: datetime = Field(default_factory=datetime.utcnow, description="When record was created")
    updated_at: datetime = Field(default_factory=datetime.utcnow, description="Last update time")
    last_contact_attempt: Optional[datetime] = Field(None, description="Last contact attempt")
    
    # Metadata
    metadata: Dict[str, Any] = Field(default_factory=dict, description="Additional metadata")
    
    is_test_client: bool = Field(default=False, description="Whether this is a test client")
    
    def add_call_attempt(self, attempt: CallAttempt):
        """Add a new call attempt to history"""
        self.call_history.append(attempt)
        self.total_attempts = len(self.call_history)
        self.last_contact_attempt = attempt.timestamp
        self.updated_at = datetime.utcnow()
        
        # Update campaign status based on outcome
        if attempt.outcome in [CallOutcome.INTERESTED, CallOutcome.NOT_INTERESTED, CallOutcome.DNC_REQUESTED]:
            self.campaign_status = CampaignStatus.COMPLETED
        elif self.total_attempts >= 6:  # Max attempts reached
            self.campaign_status = CampaignStatus.COMPLETED
        else:
            self.campaign_status = CampaignStatus.IN_PROGRESS
    
    def assign_agent(self, agent_id: str, meeting_time: Optional[datetime] = None):
        """Assign client to an agent"""
        self.agent_assignment = AgentAssignment(
            agent_id=agent_id,
            assignment_reason="interested" if self.is_interested() else "follow_up",
            meeting_scheduled=meeting_time
        )
        self.updated_at = datetime.utcnow()
    
    def add_crm_tag(self, tag: CRMTag):
        """Add CRM tag if not already present"""
        if tag not in self.crm_tags:
            self.crm_tags.append(tag)
            self.updated_at = datetime.utcnow()
    
    def is_interested(self) -> bool:
        """Check if client has shown interest"""
        if self.call_history:
            latest_attempt = self.call_history[-1]
            return latest_attempt.outcome == CallOutcome.INTERESTED
        return False
    
    def should_attempt_call(self) -> bool:
        """Check if we should attempt another call"""
        if self.campaign_status == CampaignStatus.COMPLETED:
            return False
        if self.total_attempts >= 6:  # Max attempts
            return False
        if CRMTag.DNC_REQUESTED in self.crm_tags:
            return False
        return True
    
    def get_latest_summary(self) -> Optional[CallSummary]:
        """Get the most recent call summary"""
        return self.current_summary
    
    def get_success_rate(self) -> float:
        """Get success rate (answered calls / total attempts)"""
        if not self.call_history:
            return 0.0
        
        answered_calls = sum(1 for attempt in self.call_history 
                           if attempt.outcome in [CallOutcome.ANSWERED, CallOutcome.INTERESTED, CallOutcome.NOT_INTERESTED])
        return answered_calls / len(self.call_history)

    def get_latest_call_outcome(self) -> Optional[str]:
        """Get the latest call outcome"""
        if self.call_history:
            latest_call = self.call_history[-1]
            return latest_call.get("outcome")
        return None
      
    class Config:
        populate_by_name = True
        json_encoders = {
            datetime: lambda v: v.isoformat()
        }

class ClientSearchFilter(BaseModel):
    """Filters for searching clients"""
    campaign_status: Optional[CampaignStatus] = None
    crm_tags: Optional[List[CRMTag]] = None
    last_agent: Optional[str] = None
    has_agent_assignment: Optional[bool] = None
    min_attempts: Optional[int] = None
    max_attempts: Optional[int] = None
    created_after: Optional[datetime] = None
    created_before: Optional[datetime] = None

class ClientBatch(BaseModel):
    """Batch of clients for processing"""
    clients: List[Client] = Field(..., description="List of clients in batch")
    batch_id: str = Field(..., description="Unique batch identifier")
    created_at: datetime = Field(default_factory=datetime.utcnow, description="Batch creation time")
    total_count: int = Field(..., description="Total number of clients in batch")
    processed_count: int = Field(default=0, description="Number of clients processed")
    
    def mark_processed(self, client_id: str):
        """Mark a client as processed"""
        self.processed_count += 1
    
    def is_complete(self) -> bool:
        """Check if batch is complete"""
        return self.processed_count >= self.total_count