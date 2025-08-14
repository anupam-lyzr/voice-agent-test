"""
Client Database Model
Handles client data storage and retrieval
"""

from typing import Optional, List, Dict, Any
from datetime import datetime
from pydantic import BaseModel, Field, validator
from bson import ObjectId

class Client(BaseModel):
    """Client database model"""
    
    id: Optional[str] = Field(default=None, alias="_id")
    client_id: str = Field(..., description="Unique client identifier")
    full_name: str = Field(..., description="Client full name")
    first_name: Optional[str] = Field(None, description="Client first name")
    last_name: Optional[str] = Field(None, description="Client last name")
    email: Optional[str] = Field(None, description="Client email address")
    phone_number: str = Field(..., description="Client phone number")
    
    # Address information
    address: Optional[str] = Field(None, description="Client address")
    city: Optional[str] = Field(None, description="Client city")
    state: Optional[str] = Field(None, description="Client state")
    zip_code: Optional[str] = Field(None, description="Client zip code")
    
    # Agent assignment
    assigned_agent_id: Optional[str] = Field(None, description="Assigned agent ID")
    assigned_agent_name: Optional[str] = Field(None, description="Assigned agent name")
    assigned_agent_tag: Optional[str] = Field(None, description="Agent tag identifier from Excel")
    assignment_date: Optional[datetime] = Field(None, description="Date when agent was assigned")
    
    # Call status
    call_status: str = Field(default="pending", description="Call status: pending, called, interested, not_interested, scheduled")
    last_call_date: Optional[datetime] = Field(None, description="Date of last call attempt")
    call_attempts: int = Field(default=0, description="Number of call attempts")
    max_call_attempts: int = Field(default=3, description="Maximum call attempts allowed")
    
    # Call outcomes
    call_outcome: Optional[str] = Field(None, description="Outcome of last call")
    call_notes: Optional[str] = Field(None, description="Notes from call")
    call_summary: Optional[Dict[str, Any]] = Field(None, description="Detailed call summary")
    
    # Scheduling
    meeting_scheduled: bool = Field(default=False, description="Whether meeting is scheduled")
    meeting_date: Optional[datetime] = Field(None, description="Scheduled meeting date")
    meeting_confirmed: bool = Field(default=False, description="Whether meeting is confirmed")
    
    # DNC (Do Not Call)
    dnc_requested: bool = Field(default=False, description="Whether client requested DNC")
    dnc_date: Optional[datetime] = Field(None, description="Date when DNC was requested")
    
    # Excel data fields
    excel_row_id: Optional[int] = Field(None, description="Row ID from Excel file")
    source_file: Optional[str] = Field(None, description="Source Excel file name")
    import_date: Optional[datetime] = Field(None, description="Date when imported from Excel")
    
    # Additional fields from Excel
    policy_type: Optional[str] = Field(None, description="Type of insurance policy")
    policy_number: Optional[str] = Field(None, description="Policy number")
    premium_amount: Optional[float] = Field(None, description="Premium amount")
    effective_date: Optional[datetime] = Field(None, description="Policy effective date")
    expiration_date: Optional[datetime] = Field(None, description="Policy expiration date")
    
    # Metadata
    is_active: bool = Field(default=True, description="Whether client is active")
    created_at: datetime = Field(default_factory=datetime.utcnow)
    updated_at: datetime = Field(default_factory=datetime.utcnow)
    
    @validator('phone_number')
    def validate_phone_number(cls, v):
        """Clean and validate phone number"""
        if v:
            # Remove all non-digit characters
            cleaned = ''.join(filter(str.isdigit, str(v)))
            if len(cleaned) == 10:
                return f"({cleaned[:3]}) {cleaned[3:6]}-{cleaned[6:]}"
            elif len(cleaned) == 11 and cleaned[0] == '1':
                return f"({cleaned[1:4]}) {cleaned[4:7]}-{cleaned[7:]}"
            else:
                return v  # Return original if can't format
        return v
    
    class Config:
        allow_population_by_field_name = True
        schema_extra = {
            "example": {
                "client_id": "client_001",
                "full_name": "John Doe",
                "first_name": "John",
                "last_name": "Doe",
                "email": "john.doe@email.com",
                "phone_number": "(555) 123-4567",
                "address": "123 Main St",
                "city": "Anytown",
                "state": "CA",
                "zip_code": "12345",
                "assigned_agent_id": "anthony_fracchia",
                "assigned_agent_name": "Anthony Fracchia",
                "assigned_agent_tag": "AB - Anthony Fracchia",
                "call_status": "pending",
                "call_attempts": 0,
                "is_active": True
            }
        }

class ClientCreate(BaseModel):
    """Model for creating new clients"""
    client_id: str
    full_name: str
    first_name: Optional[str] = None
    last_name: Optional[str] = None
    email: Optional[str] = None
    phone_number: str
    address: Optional[str] = None
    city: Optional[str] = None
    state: Optional[str] = None
    zip_code: Optional[str] = None
    assigned_agent_tag: Optional[str] = None
    policy_type: Optional[str] = None
    policy_number: Optional[str] = None
    premium_amount: Optional[float] = None
    effective_date: Optional[datetime] = None
    expiration_date: Optional[datetime] = None
    excel_row_id: Optional[int] = None
    source_file: Optional[str] = None

class ClientUpdate(BaseModel):
    """Model for updating clients"""
    full_name: Optional[str] = None
    first_name: Optional[str] = None
    last_name: Optional[str] = None
    email: Optional[str] = None
    phone_number: Optional[str] = None
    address: Optional[str] = None
    city: Optional[str] = None
    state: Optional[str] = None
    zip_code: Optional[str] = None
    assigned_agent_id: Optional[str] = None
    assigned_agent_name: Optional[str] = None
    assigned_agent_tag: Optional[str] = None
    assignment_date: Optional[datetime] = None
    call_status: Optional[str] = None
    last_call_date: Optional[datetime] = None
    call_attempts: Optional[int] = None
    call_outcome: Optional[str] = None
    call_notes: Optional[str] = None
    call_summary: Optional[Dict[str, Any]] = None
    meeting_scheduled: Optional[bool] = None
    meeting_date: Optional[datetime] = None
    meeting_confirmed: Optional[bool] = None
    dnc_requested: Optional[bool] = None
    dnc_date: Optional[datetime] = None
    is_active: Optional[bool] = None

class ClientAssignment(BaseModel):
    """Model for assigning clients to agents"""
    client_id: str
    agent_id: str
    agent_name: str
    agent_tag: str
    assignment_reason: Optional[str] = None
    assigned_at: datetime = Field(default_factory=datetime.utcnow)