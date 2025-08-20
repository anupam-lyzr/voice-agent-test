"""
Database Utilities
DocumentDB/MongoDB connection and operations
"""

import asyncio
import logging
from pydantic import BaseModel, Field
from typing import List, Dict, Any, Optional, Union
from datetime import datetime
from motor.motor_asyncio import AsyncIOMotorClient, AsyncIOMotorDatabase, AsyncIOMotorCollection
from pymongo.errors import DuplicateKeyError, ConnectionFailure
from bson import ObjectId
from bson.errors import InvalidId
from pydantic import Field
from shared.config.settings import settings
from shared.models.client import Client, ClientSearchFilter, CampaignStatus, CallOutcome, CRMTag
from shared.models.call_session import CallSession

logger = logging.getLogger(__name__)

class DatabaseClient:
    """MongoDB/DocumentDB client wrapper"""
    
    def __init__(self):
        self.client: Optional[AsyncIOMotorClient] = None
        self.database: Optional[AsyncIOMotorDatabase] = None
        self._connected = False
    
    async def connect(self):
        """Connect to MongoDB/DocumentDB based on the environment."""
        try:
            logger.info(f"Connecting to database: {settings.documentdb_host}:{settings.documentdb_port}")
            logger.info(f"Environment: {settings.environment}")

            client_options = {
                'serverSelectionTimeoutMS': 10000,  # Increased from 5000
                'connectTimeoutMS': 15000,  # Increased from 10000
                'socketTimeoutMS': 15000,  # Increased from 10000
                'maxPoolSize': 100,
                'minPoolSize': 5,
                'retryWrites': False,  # Disable retry writes for DocumentDB
                'retryReads': False,   # Disable retry reads for DocumentDB
            }

            if settings.is_production():
                logger.info("Applying production TLS settings for DocumentDB.")
                client_options['tls'] = True
                # Do not include tlsAllowInvalidCertificates here unless strictly necessary
                # It's already in URI if needed
            else:
                logger.info("Using non-TLS local development settings with authSource=admin.")

            # Close existing connection if any
            if self.client:
                self.client.close()
                self._connected = False

            self.client = AsyncIOMotorClient(
                settings.mongodb_uri,
                **client_options
            )

            self.database = self.client[settings.documentdb_database]

            # Test connection with retry logic
            max_retries = 3
            for attempt in range(max_retries):
                try:
                    await asyncio.wait_for(self.client.admin.command('ping'), timeout=10.0)
                    break
                except asyncio.TimeoutError:
                    if attempt < max_retries - 1:
                        logger.warning(f"⚠️ Database connection attempt {attempt + 1} timed out, retrying...")
                        await asyncio.sleep(2 ** attempt)  # Exponential backoff
                    else:
                        raise ConnectionFailure("Database connection timed out after multiple attempts")
                except Exception as e:
                    if attempt < max_retries - 1:
                        logger.warning(f"⚠️ Database connection attempt {attempt + 1} failed: {e}, retrying...")
                        await asyncio.sleep(2 ** attempt)  # Exponential backoff
                    else:
                        raise

            await self._create_indexes()

            self._connected = True
            logger.info("✅ Database connected successfully")

        except Exception as e:
            logger.error(f"❌ Database connection failed: {e}")
            self._connected = False
            raise ConnectionFailure(f"Failed to connect to database: {e}")
    
    async def disconnect(self):
        """Disconnect from database"""
        if self.client:
            self.client.close()
            self._connected = False
            logger.info("Database disconnected")
    
    async def _create_indexes(self):
        """Create necessary database indexes"""
        try:
            clients_collection = self.database.clients
            sessions_collection = self.database.call_sessions
            
            # Client indexes
            await clients_collection.create_index("client.phone", unique=True)
            await clients_collection.create_index("client.email")
            await clients_collection.create_index("client.lastAgent")
            await clients_collection.create_index("campaignStatus")
            await clients_collection.create_index("crmTags")
            await clients_collection.create_index("totalAttempts")
            await clients_collection.create_index("createdAt")
            await clients_collection.create_index("updatedAt")
            
            # Session indexes
            await sessions_collection.create_index("twilioCallSid", unique=True)
            await sessions_collection.create_index("clientId")
            await sessions_collection.create_index("callStatus")
            await sessions_collection.create_index("startedAt")
            await sessions_collection.create_index("completedAt")
            
            logger.info("✅ Database indexes created")
            
        except Exception as e:
            logger.warning(f"⚠️ Index creation warning: {e}")
    
    def is_connected(self) -> bool:
        """Check if database is connected"""
        return self._connected
    
    async def ensure_connected(self) -> bool:
        """Ensure database is connected, attempt reconnection if needed"""
        if self._connected and self.client:
            try:
                # Quick ping to verify connection is still alive
                await asyncio.wait_for(self.client.admin.command('ping'), timeout=5.0)
                return True
            except Exception:
                logger.warning("⚠️ Database connection lost, attempting to reconnect...")
                self._connected = False
        
        if not self._connected:
            try:
                await self.connect()
                return True
            except Exception as e:
                logger.error(f"❌ Failed to reconnect to database: {e}")
                return False
        
        return False
    
    @property
    def clients(self) -> AsyncIOMotorCollection:
        """Get clients collection"""
        return self.database.clients
    
    @property
    def call_sessions(self) -> AsyncIOMotorCollection:
        """Get call sessions collection"""
        return self.database.call_sessions
    
    @property
    def summaries(self) -> AsyncIOMotorCollection:
        """Get call summaries collection"""
        return self.database.call_summaries

class ClientRepository:
    """Repository for client operations"""
    
    def __init__(self, db_client: DatabaseClient):
        self.db = db_client
    
    async def create_client(self, client: Client) -> str:
        """Create a new client record"""
        try:
            client_dict = client.model_dump(exclude={"id"})
            result = await self.db.clients.insert_one(client_dict)
            logger.info(f"Created client: {client.client.full_name} ({result.inserted_id})")
            return str(result.inserted_id)
        except DuplicateKeyError:
            logger.warning(f"Client already exists: {client.client.phone}")
            raise ValueError(f"Client with phone {client.client.phone} already exists")
        except Exception as e:
            logger.error(f"Failed to create client: {e}")
            raise
    
    async def get_client_by_id(self, client_id: str) -> Optional[Client]:
        """Get client by MongoDB ID"""
        try:
            # Handle both ObjectId and string formats
            if isinstance(client_id, str) and ObjectId.is_valid(client_id):
                object_id = ObjectId(client_id)
            else:
                logger.error(f"Invalid client_id format: {client_id}")
                return None
            
            doc = await self.db.clients.find_one({"_id": object_id})
            if doc:
                doc["id"] = str(doc["_id"])  # Convert ObjectId to string
                del doc["_id"]  # Remove original _id
                return Client(**doc)
            return None
        except Exception as e:
            logger.error(f"Failed to get client by ID {client_id}: {e}")
            return None
    
    async def get_client_by_phone(self, phone: str) -> Optional[Client]:
        """Get client by phone number with multiple format handling"""
        try:
            # First try exact match
            doc = await self.db.clients.find_one({"client.phone": phone})
            if doc:
                doc["id"] = str(doc["_id"])
                del doc["_id"]
                return Client(**doc)
            
            # If no exact match, try normalized versions
            # Remove all non-digits
            import re
            digits_only = re.sub(r'\D', '', phone)
            
            # Try different formats
            phone_formats = []
            if len(digits_only) >= 10:
                # Add +1 prefix if missing (US numbers)
                if len(digits_only) == 10:
                    phone_formats = [f"+1{digits_only}", digits_only]
                elif len(digits_only) == 11 and digits_only.startswith('1'):
                    phone_formats = [f"+{digits_only}", digits_only[1:]]
                else:
                    phone_formats = [f"+{digits_only}", digits_only]
            
            # Try each format
            for format_phone in phone_formats:
                doc = await self.db.clients.find_one({"client.phone": format_phone})
                if doc:
                    doc["id"] = str(doc["_id"])
                    del doc["_id"]
                    logger.info(f"✅ Found client with phone format: {format_phone} (original: {phone})")
                    return Client(**doc)
            
            logger.warning(f"⚠️ No client found for phone: {phone} (tried formats: {phone_formats})")
            return None
            
        except Exception as e:
            logger.error(f"Failed to get client by phone {phone}: {e}")
            return None


    
    
    async def update_client(self, client_id: str, updates: Dict[str, Any]) -> bool:
        """Update client record"""
        try:
            if not ObjectId.is_valid(client_id):
                return False
            
            updates["updatedAt"] = datetime.utcnow()
            result = await self.db.clients.update_one(
                {"_id": ObjectId(client_id)},
                {"$set": updates}
            )
            
            if result.modified_count > 0:
                logger.info(f"Updated client {client_id}")
                return True
            return False
        except Exception as e:
            logger.error(f"Failed to update client {client_id}: {e}")
            return False
    
    async def add_call_attempt(self, client_id: str, call_attempt: Dict[str, Any]) -> bool:
        """Add a call attempt to client history"""
        try:
            if not ObjectId.is_valid(client_id):
                return False
            
            result = await self.db.clients.update_one(
                {"_id": ObjectId(client_id)},
                {
                    "$push": {"callHistory": call_attempt},
                    "$inc": {"totalAttempts": 1},
                    "$set": {
                        "updatedAt": datetime.utcnow(),
                        "lastContactAttempt": call_attempt.get("timestamp", datetime.utcnow())
                    }
                }
            )
            
            return result.modified_count > 0
        except Exception as e:
            logger.error(f"Failed to add call attempt for client {client_id}: {e}")
            return False
    
    async def assign_agent(self, client_id: str, agent_id: str, agent_name: str = None) -> bool:
        """Assign agent to client"""
        try:
            if not ObjectId.is_valid(client_id):
                return False
            
            assignment = {
                "agentId": agent_id,
                "agentName": agent_name or agent_id,
                "assignedAt": datetime.utcnow(),
                "assignmentReason": "interested",
                "meetingStatus": "pending"
            }
            
            result = await self.db.clients.update_one(
                {"_id": ObjectId(client_id)},
                {
                    "$set": {
                        "agentAssignment": assignment,
                        "agentAssigned": agent_id,  # For compatibility
                        "agentName": agent_name or agent_id,  # For compatibility
                        "assignedAt": datetime.utcnow(),
                        "updatedAt": datetime.utcnow()
                    }
                }
            )
            
            return result.modified_count > 0
        except Exception as e:
            logger.error(f"Failed to assign agent to client {client_id}: {e}")
            return False
    
    async def add_crm_tag(self, client_id: str, tag: CRMTag) -> bool:
        """Add CRM tag to client"""
        try:
            if not ObjectId.is_valid(client_id):
                return False
            
            result = await self.db.clients.update_one(
                {"_id": ObjectId(client_id)},
                {
                    "$addToSet": {"crmTags": tag.value},
                    "$set": {"updatedAt": datetime.utcnow()}
                }
            )
            
            return result.modified_count > 0
        except Exception as e:
            logger.error(f"Failed to add CRM tag to client {client_id}: {e}")
            return False
    
    async def search_clients(self, filters: ClientSearchFilter, limit: int = 100, skip: int = 0) -> List[Client]:
        """Search clients with filters"""
        try:
            query = {}
            
            if filters.campaign_status:
                query["campaignStatus"] = filters.campaign_status.value
            
            if filters.crm_tags:
                query["crmTags"] = {"$in": [tag.value for tag in filters.crm_tags]}
            
            if filters.last_agent:
                query["client.lastAgent"] = filters.last_agent
            
            if filters.has_agent_assignment is not None:
                if filters.has_agent_assignment:
                    query["agentAssignment"] = {"$exists": True, "$ne": None}
                else:
                    query["agentAssignment"] = {"$exists": False}
            
            if filters.min_attempts is not None:
                query["totalAttempts"] = {"$gte": filters.min_attempts}
            
            if filters.max_attempts is not None:
                if "totalAttempts" in query:
                    query["totalAttempts"]["$lte"] = filters.max_attempts
                else:
                    query["totalAttempts"] = {"$lte": filters.max_attempts}
            
            if filters.created_after:
                query["createdAt"] = {"$gte": filters.created_after}
            
            if filters.created_before:
                if "createdAt" in query:
                    query["createdAt"]["$lte"] = filters.created_before
                else:
                    query["createdAt"] = {"$lte": filters.created_before}
            
            cursor = self.db.clients.find(query).sort("createdAt", -1).skip(skip).limit(limit)
            clients = []
            
            async for doc in cursor:
                doc["id"] = str(doc["_id"]) 
                clients.append(Client(**doc))
            
            return clients
        except Exception as e:
            logger.error(f"Failed to search clients: {e}")
            return []
    
    async def get_clients_for_campaign(self, limit: int = 100) -> List[Client]:
        """Get clients ready for campaign calls"""
        try:
            query = {
                "campaignStatus": {"$in": [CampaignStatus.PENDING.value, CampaignStatus.IN_PROGRESS.value]},
                "totalAttempts": {"$lt": settings.max_call_attempts},
                "crmTags": {"$nin": [CRMTag.DNC_REQUESTED.value]}
            }
            
            cursor = self.db.clients.find(query).sort("totalAttempts", 1).limit(limit)
            clients = []
            
            async for doc in cursor:
                doc["id"] = str(doc["_id"])
                clients.append(Client(**doc))
            
            return clients
        except Exception as e:
            logger.error(f"Failed to get campaign clients: {e}")
            return []
    
    async def get_campaign_stats(self) -> Dict[str, Any]:
        """Get campaign statistics"""
        try:
            pipeline = [
                {
                    "$group": {
                        "_id": "$campaignStatus",
                        "count": {"$sum": 1}
                    }
                }
            ]
            
            status_counts = {}
            async for doc in self.db.clients.aggregate(pipeline):
                status_counts[doc["_id"]] = doc["count"]
            
            # Get total counts
            total_clients = await self.db.clients.count_documents({})
            completed_calls = await self.db.clients.count_documents({
                "callHistory.outcome": {"$in": ["interested", "not_interested", "dnc_requested"]}
            })
            
            interested_clients = await self.db.clients.count_documents({
                "crmTags": CRMTag.INTERESTED.value
            })
            
            return {
                "total_clients": total_clients,
                "status_breakdown": status_counts,
                "completed_calls": completed_calls,
                "interested_clients": interested_clients,
                "completion_rate": (completed_calls / total_clients * 100) if total_clients > 0 else 0
            }
        except Exception as e:
            logger.error(f"Failed to get campaign stats: {e}")
            return {}
        

    async def get_clients_needing_crm_update(self, limit: int = 50) -> List[Client]:
        """Get clients that need CRM updates"""
        try:
            query = {
                "campaignStatus": CampaignStatus.COMPLETED.value,
                "crmUpdated": {"$ne": True},
                "callHistory": {"$exists": True, "$not": {"$size": 0}}
            }
            
            cursor = self.db.clients.find(query).limit(limit)
            clients = []
            
            async for doc in cursor:
                doc["id"] = str(doc["_id"])
                clients.append(Client(**doc))
            
            return clients
        except Exception as e:
            logger.error(f"Error getting clients for CRM update: {e}")
            return []

    async def get_clients_needing_assignment(self, limit: int = 20) -> List[Client]:
        """Get clients that need agent assignment"""
        try:
            query = {
                "crmTags": CRMTag.INTERESTED.value,
                "agentAssignment": {"$exists": False}
            }
            
            cursor = self.db.clients.find(query).limit(limit)
            clients = []
            
            async for doc in cursor:
                doc["id"] = str(doc["_id"])
                clients.append(Client(**doc))
            
            return clients
        except Exception as e:
            logger.error(f"Error getting clients for assignment: {e}")
            return []

    async def mark_clients_ready_for_campaign(self, batch_size: int) -> int:
        """Mark clients as ready for campaign"""
        try:
            result = await self.db.clients.update_many(
                {
                    "campaignStatus": CampaignStatus.PENDING.value,
                    "totalAttempts": {"$lt": settings.max_call_attempts}
                },
                {"$set": {"campaignStatus": CampaignStatus.IN_PROGRESS.value}},
                limit=batch_size
            )
            return result.modified_count
        except Exception as e:
            logger.error(f"Error marking clients ready: {e}")
            return 0

    async def update_client_campaign_status(self, client_id: str, status: str):
        """Update client campaign status"""
        try:
            await self.db.clients.update_one(
                {"_id": ObjectId(client_id)},
                {"$set": {"campaignStatus": status, "updatedAt": datetime.utcnow()}}
            )
        except Exception as e:
            logger.error(f"Error updating client status: {e}")

    async def get_latest_call_outcome(self, client_id: str) -> Optional[CallOutcome]:
        """Get latest call outcome for client"""
        try:
            doc = await self.db.clients.find_one(
                {"_id": ObjectId(client_id)},
                {"callHistory": {"$slice": -1}}
            )
            
            if doc and doc.get("callHistory"):
                latest_call = doc["callHistory"][-1]
                outcome_str = latest_call.get("outcome")
                if outcome_str:
                    return CallOutcome(outcome_str)
            return None
        except Exception as e:
            logger.error(f"Error getting latest call outcome: {e}")
            return None

    async def get_latest_call_summary(self, client_id: str) -> Optional[Dict[str, Any]]:
        """Get latest call summary for client"""
        try:
            doc = await self.db.clients.find_one(
                {"_id": ObjectId(client_id)},
                {"callHistory": {"$slice": -1}}
            )
            
            if doc and doc.get("callHistory"):
                latest_call = doc["callHistory"][-1]
                return {
                    "outcome": latest_call.get("outcome"),
                    "duration_seconds": latest_call.get("duration", 0),
                    "summary": latest_call.get("summary", ""),
                    "key_points": latest_call.get("keyPoints", []),
                    "next_actions": latest_call.get("nextActions", []),
                    "agent_assigned": latest_call.get("agentAssigned"),
                    "timestamp": latest_call.get("timestamp")
                }
            return None
        except Exception as e:
            logger.error(f"Error getting call summary: {e}")
            return None

    async def mark_crm_updated(self, client_id: str):
        """Mark client as CRM updated"""
        try:
            await self.db.clients.update_one(
                {"_id": ObjectId(client_id)},
                {"$set": {"crmUpdated": True, "crmUpdatedAt": datetime.utcnow(), "updatedAt": datetime.utcnow()}}
            )
        except Exception as e:
            logger.error(f"Error marking CRM updated: {e}")

    async def get_agent_assigned_count(self, agent_id: str) -> int:
        """Get number of clients assigned to agent"""
        try:
            count = await self.db.clients.count_documents({
                "agentAssignment.agentId": agent_id
            })
            return count
        except Exception as e:
            logger.error(f"Error getting agent assignment count: {e}")
            return 0

    async def update_call_outcome(self, client_id: str, outcome: CallOutcome):
        """Update call outcome for client"""
        try:
            outcome_value = outcome.value if hasattr(outcome, 'value') else str(outcome)
            
            await self.db.clients.update_one(
                {"_id": ObjectId(client_id)},
                {"$set": {"latestCallOutcome": outcome_value, "updatedAt": datetime.utcnow()}}
            )
        except Exception as e:
            logger.error(f"Error updating call outcome: {e}")


    async def get_test_clients(self, limit: int = 100) -> List[Client]:
        """Get test clients"""
        try:
            cursor = self.db.clients.find(
                {"is_test_client": True}
            ).sort("created_at", -1).limit(limit)
            
            clients = []
            async for doc in cursor:
                clients.append(Client(**doc))
            
            return clients
        except Exception as e:
            logger.error(f"Failed to get test clients: {e}")
            return []

    async def delete_client(self, client_id: str) -> bool:
        """Delete a client (only for test clients)"""
        try:
            if not ObjectId.is_valid(client_id):
                return False
            
            # Only allow deletion of test clients
            client = await self.get_client_by_id(client_id)
            if not client or not getattr(client, 'is_test_client', False):
                return False
            
            result = await self.db.clients.delete_one({"_id": ObjectId(client_id)})
            return result.deleted_count > 0
        except Exception as e:
            logger.error(f"Error deleting client: {e}")
            return False


    async def get_recent_sessions(self, limit: int = 20) -> List[CallSession]:
        """Get recent call sessions"""
        try:
            cursor = self.db.call_sessions.find().sort("startedAt", -1).limit(limit)
            sessions = []
            
            async for doc in cursor:
                sessions.append(CallSession(**doc))
            
            return sessions
        except Exception as e:
            logger.error(f"Error getting recent sessions: {e}")
            return []

    # ADD THIS TO THE Client model in shared-source/models/client.py:

    def get_latest_call_outcome(self) -> Optional[str]:
        """Get the latest call outcome"""
        if self.call_history:
            latest_call = self.call_history[-1]
            return latest_call.get("outcome")
        return None

    # ADD THIS FIELD TO Client model:
    is_test_client: bool = Field(default=False, description="Whether this is a test client")

class SessionRepository:
    """Repository for call session operations"""
    
    def __init__(self, db_client: DatabaseClient):
        self.db = db_client
    
    async def save_session(self, session: CallSession) -> bool:
        """Save or update call session"""
        try:
            session_dict = session.model_dump()
            result = await self.db.call_sessions.replace_one(
                {"sessionId": session.session_id},
                session_dict,
                upsert=True
            )
            return True
        except Exception as e:
            logger.error(f"Failed to save session {session.session_id}: {e}")
            return False
    
    async def get_session(self, session_id: str) -> Optional[CallSession]:
        """Get session by ID"""
        try:
            doc = await self.db.call_sessions.find_one({"sessionId": session_id})
            if doc:
                return CallSession(**doc)
            return None
        except Exception as e:
            logger.error(f"Failed to get session {session_id}: {e}")
            return None
    
    async def get_active_sessions(self) -> List[CallSession]:
        """Get all active call sessions"""
        try:
            query = {"callStatus": {"$in": ["initiated", "ringing", "answered", "in_progress"]}}
            cursor = self.db.call_sessions.find(query)
            sessions = []
            
            async for doc in cursor:
                sessions.append(CallSession(**doc))
            
            return sessions
        except Exception as e:
            logger.error(f"Failed to get active sessions: {e}")
            return []
    async def get_recent_sessions(self, limit: int = 20) -> List[CallSession]:
        """Get recent call sessions"""
        try:
            cursor = self.db.call_sessions.find().sort("started_at", -1).limit(limit)
            sessions = []
            
            async for doc in cursor:
                doc["session_id"] = doc.get("session_id", str(doc["_id"]))
                sessions.append(CallSession(**doc))
            
            return sessions
        except Exception as e:
            logger.error(f"Error getting recent sessions: {e}")
            return []

# Add to database.py - create TestAgentRepository:

class TestAgent(BaseModel):
    """Test agent model"""
    id: Optional[str] = Field(None, description="Agent ID")
    name: str
    email: str
    google_calendar_id: Optional[str] = None
    timezone: str = "America/New_York"
    specialties: List[str] = Field(default_factory=list)
    working_hours: str = "9AM-5PM"
    created_at: datetime = Field(default_factory=datetime.utcnow)
    updated_at: datetime = Field(default_factory=datetime.utcnow)

class TestAgentRepository:
    """Repository for test agent operations"""
    
    def __init__(self, db_client: DatabaseClient):
        self.db = db_client
    
    async def create_test_agent(self, agent: TestAgent) -> str:
        """Create a new test agent"""
        try:
            agent_dict = agent.model_dump(exclude={"id"})
            result = await self.db.database.test_agents.insert_one(agent_dict)
            logger.info(f"Created test agent: {agent.name} ({result.inserted_id})")
            return str(result.inserted_id)
        except Exception as e:
            logger.error(f"Failed to create test agent: {e}")
            raise
    
    async def get_all_test_agents(self) -> List[TestAgent]:
        """Get all test agents"""
        try:
            cursor = self.db.database.test_agents.find().sort("created_at", -1)
            agents = []
            
            async for doc in cursor:
                # Convert ObjectId to string and set as id field
                agent_data = {
                    "id": str(doc["_id"]),
                    "name": doc["name"],
                    "email": doc["email"],
                    "google_calendar_id": doc.get("google_calendar_id", ""),
                    "timezone": doc.get("timezone", "America/New_York"),
                    "specialties": doc.get("specialties", []),
                    "working_hours": doc.get("working_hours", "9AM-5PM"),
                    "created_at": doc.get("created_at"),
                    "updated_at": doc.get("updated_at")
                }
                agents.append(TestAgent(**agent_data))
            
            return agents
        except Exception as e:
            logger.error(f"Error getting test agents: {e}")
            return []
    
    async def get_test_agent_by_id(self, agent_id: str) -> Optional[TestAgent]:
        """Get test agent by ID"""
        try:
            if not ObjectId.is_valid(agent_id):
                return None
            
            doc = await self.db.database.test_agents.find_one({"_id": ObjectId(agent_id)})
            if doc:
                # Convert ObjectId to string
                agent_data = {
                    "id": str(doc["_id"]),
                    "name": doc["name"],
                    "email": doc["email"],
                    "google_calendar_id": doc.get("google_calendar_id", ""),
                    "timezone": doc.get("timezone", "America/New_York"),
                    "specialties": doc.get("specialties", []),
                    "working_hours": doc.get("working_hours", "9AM-5PM"),
                    "created_at": doc.get("created_at"),
                    "updated_at": doc.get("updated_at")
                }
                return TestAgent(**agent_data)
            return None
        except Exception as e:
            logger.error(f"Failed to get test agent {agent_id}: {e}")
            return None

# Add test_agent_repo to global instances
test_agent_repo: Optional[TestAgentRepository] = None

async def init_database():
    """Initialize database connection and repositories"""
    global client_repo, session_repo, test_agent_repo
    
    await db_client.connect()
    client_repo = ClientRepository(db_client)
    session_repo = SessionRepository(db_client)
    test_agent_repo = TestAgentRepository(db_client)  # Add this
    
    logger.info("✅ Database repositories initialized")


# Global database client instance
db_client = DatabaseClient()

# Repository instances
client_repo: Optional[ClientRepository] = None
session_repo: Optional[SessionRepository] = None


async def close_database():
    """Close database connection"""
    await db_client.disconnect()
    logger.info("Database connection closed")

# Utility functions for easy access
def get_database() -> DatabaseClient:
    """Get database client instance"""
    return db_client

async def get_client_by_phone(phone: str) -> Optional[Client]:
    """Get client by phone number"""
    if not client_repo:
        await init_database()
    return await client_repo.get_client_by_phone(phone)

async def save_call_session(session: CallSession) -> bool:
    """Save call session"""
    if not session_repo:
        await init_database()
    return await session_repo.save_session(session)