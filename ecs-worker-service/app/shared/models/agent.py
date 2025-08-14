"""
Agent Database Model
Handles agent data storage and retrieval
"""

from typing import Optional, List, Dict, Any
from datetime import datetime
from pydantic import BaseModel, Field
from bson import ObjectId

class Agent(BaseModel):
    """Agent database model"""
    
    id: Optional[str] = Field(default=None, alias="_id")
    agent_id: str = Field(..., description="Unique agent identifier")
    name: str = Field(..., description="Agent full name")
    email: str = Field(..., description="Agent email address")
    google_calendar_id: str = Field(..., description="Google Calendar ID")
    timezone: str = Field(default="America/New_York", description="Agent timezone")
    working_hours: str = Field(default="9AM-5PM", description="Working hours")
    specialties: List[str] = Field(default=[], description="Agent specialties")
    tag_identifier: str = Field(..., description="Tag identifier from Excel (e.g., 'AB - Anthony Fracchia')")
    client_count: int = Field(default=0, description="Number of clients assigned")
    is_active: bool = Field(default=True, description="Whether agent is active")
    created_at: datetime = Field(default_factory=datetime.utcnow)
    updated_at: datetime = Field(default_factory=datetime.utcnow)
    
    class Config:
        allow_population_by_field_name = True
        schema_extra = {
            "example": {
                "agent_id": "anthony_fracchia",
                "name": "Anthony Fracchia",
                "email": "anthony@altruisadvisor.com",
                "google_calendar_id": "anthony@altruisadvisor.com",
                "timezone": "America/New_York",
                "working_hours": "9AM-5PM",
                "specialties": ["health", "medicare"],
                "tag_identifier": "AB - Anthony Fracchia",
                "client_count": 1861,
                "is_active": True
            }
        }

class AgentCreate(BaseModel):
    """Model for creating new agents"""
    agent_id: str
    name: str
    email: str
    google_calendar_id: str
    timezone: str = "America/New_York"
    working_hours: str = "9AM-5PM"
    specialties: List[str] = []
    tag_identifier: str
    is_active: bool = True

class AgentUpdate(BaseModel):
    """Model for updating agents"""
    name: Optional[str] = None
    email: Optional[str] = None
    google_calendar_id: Optional[str] = None
    timezone: Optional[str] = None
    working_hours: Optional[str] = None
    specialties: Optional[List[str]] = None
    tag_identifier: Optional[str] = None
    is_active: Optional[bool] = None
    client_count: Optional[int] = None

class AgentAssignment(BaseModel):
    """Model for agent assignment to clients"""
    agent_id: str
    client_id: str
    assigned_at: datetime = Field(default_factory=datetime.utcnow)
    assignment_reason: Optional[str] = None
    is_active: bool = True
