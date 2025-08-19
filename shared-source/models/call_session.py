"""
Call Session Models
Models for managing real-time call sessions and conversation state
"""

from pydantic import BaseModel, Field, validator
from typing import Optional, List, Dict, Any, Union
from datetime import datetime
from enum import Enum

class CallStatus(str, Enum):
    """Current status of a call session"""
    INITIATED = "initiated"
    RINGING = "ringing"
    ANSWERED = "answered"
    IN_PROGRESS = "in_progress"
    COMPLETED = "completed"
    FAILED = "failed"
    BUSY = "busy"
    NO_ANSWER = "no_answer"

class ConversationStage(str, Enum):
    """Current stage of the conversation"""
    GREETING = "greeting"
    INTEREST_CHECK = "interest_check"
    SCHEDULING = "scheduling"
    DNC_QUESTION = "dnc_question"
    CLOSING = "closing"
    COMPLETED = "completed"

class ResponseType(str, Enum):
    """Type of response being used"""
    STATIC_AUDIO = "static_audio"
    DYNAMIC_TTS = "dynamic_tts"
    HYBRID = "hybrid"

class ConversationTurn(BaseModel):
    """Individual turn in the conversation"""
    turn_number: int = Field(..., description="Turn number in conversation")
    timestamp: datetime = Field(default_factory=datetime.utcnow, description="When turn occurred")
    
    # Customer input
    customer_speech: Optional[str] = Field(None, description="What customer said")
    customer_speech_confidence: Optional[float] = Field(None, description="STT confidence score")
    transcription_time_ms: Optional[float] = Field(None, description="Time taken for transcription")
    
    # Agent response
    agent_response: str = Field(..., description="Agent's response text")
    response_type: ResponseType = Field(..., description="Type of response used")
    response_generation_time_ms: Optional[float] = Field(None, description="Time to generate response")
    
    # Audio details
    audio_url: Optional[str] = Field(None, description="URL to audio file")
    audio_duration_seconds: Optional[float] = Field(None, description="Audio duration")
    tts_generation_time_ms: Optional[float] = Field(None, description="Time for TTS generation")
    
    # Performance metrics
    total_turn_time_ms: Optional[float] = Field(None, description="Total time for complete turn")
    
    # Conversation context
    conversation_stage: ConversationStage = Field(..., description="Stage when turn occurred")
    customer_intent: Optional[str] = Field(None, description="Detected customer intent")
    confidence_score: Optional[float] = Field(None, description="Intent confidence")

    @validator('response_type', pre=True)
    def validate_response_type(cls, v):
        """Convert invalid response_type values to valid ones"""
        if isinstance(v, str):
            v = v.lower()
            if v == 'static':
                return ResponseType.STATIC_AUDIO
            elif v in ['dynamic', 'tts']:
                return ResponseType.DYNAMIC_TTS
            elif v in ['hybrid', 'mixed']:
                return ResponseType.HYBRID
        return v

    @validator('conversation_stage', pre=True)
    def validate_conversation_stage(cls, v):
        """Convert invalid conversation_stage values to valid ones"""
        if isinstance(v, str):
            v = v.lower()
            if v == 'goodbye':
                return ConversationStage.CLOSING
            elif v in ['greeting', 'hello']:
                return ConversationStage.GREETING
            elif v in ['interest', 'interested']:
                return ConversationStage.INTEREST_CHECK
            elif v in ['schedule', 'scheduling']:
                return ConversationStage.SCHEDULING
            elif v in ['dnc', 'do_not_call']:
                return ConversationStage.DNC_QUESTION
            elif v in ['complete', 'completed', 'done']:
                return ConversationStage.COMPLETED
        return v

class SessionMetrics(BaseModel):
    """Performance metrics for the call session"""
    # Timing metrics
    total_call_duration_seconds: Optional[float] = Field(None, description="Total call duration")
    avg_response_time_ms: float = Field(default=0.0, description="Average response time")
    fastest_response_ms: Optional[float] = Field(None, description="Fastest response time")
    slowest_response_ms: Optional[float] = Field(None, description="Slowest response time")
    
    # Conversation metrics
    total_turns: int = Field(default=0, description="Total conversation turns")
    static_responses_used: int = Field(default=0, description="Static audio responses used")
    dynamic_responses_used: int = Field(default=0, description="Dynamic TTS responses used")
    
    # Quality metrics
    avg_transcription_confidence: Optional[float] = Field(None, description="Average STT confidence")
    conversation_completion_rate: float = Field(default=0.0, description="How much of conversation completed")
    
    # Technical metrics
    transcription_errors: int = Field(default=0, description="Number of transcription errors")
    tts_failures: int = Field(default=0, description="Number of TTS failures")
    agent_api_failures: int = Field(default=0, description="Number of agent API failures")

class CallSession(BaseModel):
    """Real-time call session state"""
    # Session identification
    session_id: str = Field(..., description="Unique session identifier")
    twilio_call_sid: str = Field(..., description="Twilio call SID")
    client_id: str = Field(..., description="Client MongoDB ID")
    
    # Call details
    call_status: CallStatus = Field(default=CallStatus.INITIATED, description="Current call status")
    phone_number: str = Field(..., description="Client phone number")
    direction: str = Field(default="outbound", description="Call direction")
    
    # Conversation state
    conversation_stage: ConversationStage = Field(default=ConversationStage.GREETING, description="Current conversation stage")

    @validator('conversation_stage', pre=True)
    def validate_session_conversation_stage(cls, v):
        """Convert invalid conversation_stage values to valid ones"""
        if isinstance(v, str):
            v = v.lower()
            if v == 'goodbye':
                return ConversationStage.CLOSING
            elif v in ['greeting', 'hello']:
                return ConversationStage.GREETING
            elif v in ['interest', 'interested']:
                return ConversationStage.INTEREST_CHECK
            elif v in ['schedule', 'scheduling']:
                return ConversationStage.SCHEDULING
            elif v in ['dnc', 'do_not_call']:
                return ConversationStage.DNC_QUESTION
            elif v in ['complete', 'completed', 'done']:
                return ConversationStage.COMPLETED
        return v
    conversation_turns: List[ConversationTurn] = Field(default_factory=list, description="All conversation turns")
    current_turn_number: int = Field(default=0, description="Current turn number")
    
    # Context and memory
    conversation_context: Dict[str, Any] = Field(default_factory=dict, description="Conversation context")
    customer_preferences: Dict[str, Any] = Field(default_factory=dict, description="Customer preferences discovered")
    detected_intents: List[str] = Field(default_factory=list, description="All detected customer intents")
    
    # LYZR Agent details
    lyzr_agent_id: str = Field(..., description="LYZR conversation agent ID")
    lyzr_session_id: str = Field(..., description="LYZR session ID")
    
    # Performance tracking
    session_metrics: SessionMetrics = Field(default_factory=SessionMetrics, description="Session performance metrics")
    
    # Timing
    started_at: datetime = Field(default_factory=datetime.utcnow, description="Session start time")
    answered_at: Optional[datetime] = Field(None, description="When call was answered")
    completed_at: Optional[datetime] = Field(None, description="When call completed")
    
    # Results
    final_outcome: Optional[str] = Field(None, description="Final call outcome")
    customer_interested: Optional[bool] = Field(None, description="Customer interest determination")
    agent_assigned: Optional[str] = Field(None, description="Agent assigned if interested")
    meeting_scheduled: Optional[datetime] = Field(None, description="Meeting scheduled time")
    
    # Error tracking
    errors: List[Dict[str, Any]] = Field(default_factory=list, description="Errors during session")
    
    def add_conversation_turn(self, turn: ConversationTurn):
        """Add a new conversation turn"""
        turn.turn_number = len(self.conversation_turns) + 1
        self.conversation_turns.append(turn)
        self.current_turn_number = turn.turn_number
        
        # Update metrics
        self._update_metrics(turn)
    
    def _update_metrics(self, turn: ConversationTurn):
        """Update session metrics with new turn data"""
        self.session_metrics.total_turns = len(self.conversation_turns)
        
        # Update response type counts
        if turn.response_type == ResponseType.STATIC_AUDIO:
            self.session_metrics.static_responses_used += 1
        elif turn.response_type == ResponseType.DYNAMIC_TTS:
            self.session_metrics.dynamic_responses_used += 1
        
        # Update timing metrics
        if turn.total_turn_time_ms:
            response_times = [t.total_turn_time_ms for t in self.conversation_turns if t.total_turn_time_ms]
            if response_times:
                self.session_metrics.avg_response_time_ms = sum(response_times) / len(response_times)
                self.session_metrics.fastest_response_ms = min(response_times)
                self.session_metrics.slowest_response_ms = max(response_times)
        
        # Update transcription confidence
        confidences = [t.customer_speech_confidence for t in self.conversation_turns 
                      if t.customer_speech_confidence is not None]
        if confidences:
            self.session_metrics.avg_transcription_confidence = sum(confidences) / len(confidences)
    
    def update_conversation_stage(self, stage: ConversationStage):
        """Update the current conversation stage"""
        self.conversation_stage = stage
        
        # Update context based on stage
        self.conversation_context["current_stage"] = stage.value
        self.conversation_context["stage_changed_at"] = datetime.utcnow().isoformat()
    
    def set_customer_interest(self, interested: bool, reason: str = ""):
        """Set customer interest determination"""
        self.customer_interested = interested
        self.conversation_context["interest_reason"] = reason
        self.conversation_context["interest_determined_at"] = datetime.utcnow().isoformat()
    
    def assign_agent(self, agent_id: str):
        """Assign an agent to this customer"""
        self.agent_assigned = agent_id
        self.conversation_context["agent_assigned_at"] = datetime.utcnow().isoformat()
    
    def schedule_meeting(self, meeting_time: datetime):
        """Schedule a meeting with the assigned agent"""
        self.meeting_scheduled = meeting_time
        self.conversation_context["meeting_scheduled_at"] = datetime.utcnow().isoformat()
    
    def add_error(self, error_type: str, error_message: str, context: Dict[str, Any] = None):
        """Add an error to the session"""
        error_entry = {
            "type": error_type,
            "message": error_message,
            "timestamp": datetime.utcnow().isoformat(),
            "context": context or {}
        }
        self.errors.append(error_entry)
        
        # Update metrics based on error type
        if error_type == "transcription":
            self.session_metrics.transcription_errors += 1
        elif error_type == "tts":
            self.session_metrics.tts_failures += 1
        elif error_type == "agent_api":
            self.session_metrics.agent_api_failures += 1
    
    def complete_call(self, outcome: str):
        """Mark the call as completed"""
        self.call_status = CallStatus.COMPLETED
        self.final_outcome = outcome
        self.completed_at = datetime.utcnow()
        
        # Calculate final metrics
        if self.started_at and self.completed_at:
            duration = (self.completed_at - self.started_at).total_seconds()
            self.session_metrics.total_call_duration_seconds = duration
        
        # Calculate completion rate based on conversation stage
        stage_completion = {
            ConversationStage.GREETING: 0.2,
            ConversationStage.INTEREST_CHECK: 0.5,
            ConversationStage.SCHEDULING: 0.8,
            ConversationStage.DNC_QUESTION: 0.8,
            ConversationStage.CLOSING: 0.9,
            ConversationStage.COMPLETED: 1.0
        }
        self.session_metrics.conversation_completion_rate = stage_completion.get(self.conversation_stage, 0.0)
    
    def get_conversation_summary(self) -> Dict[str, Any]:
        """Get a summary of the conversation for logging/analysis"""
        return {
            "session_id": self.session_id,
            "call_sid": self.twilio_call_sid,
            "phone_number": self.phone_number,
            "duration_seconds": self.session_metrics.total_call_duration_seconds,
            "total_turns": self.session_metrics.total_turns,
            "final_outcome": self.final_outcome,
            "customer_interested": self.customer_interested,
            "conversation_stage": self.conversation_stage.value if hasattr(self.conversation_stage, 'value') else self.conversation_stage,
            "avg_response_time_ms": self.session_metrics.avg_response_time_ms,
            "static_responses": self.session_metrics.static_responses_used,
            "dynamic_responses": self.session_metrics.dynamic_responses_used,
            "errors": len(self.errors),
            "completed_at": self.completed_at.isoformat() if self.completed_at else None
        }
    
    def get_transcript(self) -> str:
        """Get full conversation transcript"""
        transcript_lines = []
        
        for turn in self.conversation_turns:
            if turn.customer_speech:
                transcript_lines.append(f"Customer: {turn.customer_speech}")
            transcript_lines.append(f"Agent: {turn.agent_response}")
        
        return "\n".join(transcript_lines)
    
    def is_performing_well(self) -> bool:
        """Check if the session is performing within acceptable parameters"""
        # Check average response time (target: < 2500ms)
        if self.session_metrics.avg_response_time_ms > 2500:
            return False
        
        # Check error rate (should be < 20% of turns)
        total_errors = (self.session_metrics.transcription_errors + 
                       self.session_metrics.tts_failures + 
                       self.session_metrics.agent_api_failures)
        if self.session_metrics.total_turns > 0:
            error_rate = total_errors / self.session_metrics.total_turns
            if error_rate > 0.2:
                return False
        
        # Check transcription confidence (should be > 0.7)
        if (self.session_metrics.avg_transcription_confidence and 
            self.session_metrics.avg_transcription_confidence < 0.7):
            return False
        
        return True
    
    class Config:
        json_encoders = {
            datetime: lambda v: v.isoformat()
        }

class SessionCache(BaseModel):
    """Redis cache entry for session data"""
    session_id: str = Field(..., description="Session identifier")
    data: Dict[str, Any] = Field(..., description="Cached session data")
    expires_at: datetime = Field(..., description="Cache expiration time")
    
    def is_expired(self) -> bool:
        """Check if cache entry is expired"""
        return datetime.utcnow() > self.expires_at
    
    @classmethod
    def create(cls, session_id: str, data: Dict[str, Any], ttl_seconds: int = 1800):
        """Create a new cache entry with TTL"""
        expires_at = datetime.utcnow()
        expires_at = expires_at.replace(second=expires_at.second + ttl_seconds)
        
        return cls(
            session_id=session_id,
            data=data,
            expires_at=expires_at
        )

class WebSocketMessage(BaseModel):
    """WebSocket message structure for real-time communication"""
    type: str = Field(..., description="Message type")
    session_id: str = Field(..., description="Session identifier")
    timestamp: datetime = Field(default_factory=datetime.utcnow, description="Message timestamp")
    data: Dict[str, Any] = Field(default_factory=dict, description="Message data")
    
    @classmethod
    def transcript_message(cls, session_id: str, text: str, confidence: float = None):
        """Create a transcript message"""
        return cls(
            type="transcript",
            session_id=session_id,
            data={
                "text": text,
                "confidence": confidence,
                "speaker": "customer"
            }
        )
    
    @classmethod
    def agent_response_message(cls, session_id: str, text: str, response_type: str):
        """Create an agent response message"""
        return cls(
            type="agent_response",
            session_id=session_id,
            data={
                "text": text,
                "response_type": response_type,
                "speaker": "agent"
            }
        )
    
    @classmethod
    def audio_message(cls, session_id: str, audio_url: str, duration: float = None):
        """Create an audio message"""
        return cls(
            type="audio",
            session_id=session_id,
            data={
                "audio_url": audio_url,
                "duration": duration
            }
        )
    
    @classmethod
    def status_message(cls, session_id: str, status: str, details: Dict[str, Any] = None):
        """Create a status message"""
        return cls(
            type="status",
            session_id=session_id,
            data={
                "status": status,
                "details": details or {}
            }
        )
    
    @classmethod
    def error_message(cls, session_id: str, error: str, error_type: str = "general"):
        """Create an error message"""
        return cls(
            type="error",
            session_id=session_id,
            data={
                "error": error,
                "error_type": error_type
            }
        )