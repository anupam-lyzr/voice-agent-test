"""
Database Utilities
DocumentDB/MongoDB connection and operations
"""

import asyncio
import logging
from typing import List, Dict, Any, Optional, Union
from datetime import datetime
from motor.motor_asyncio import AsyncIOMotorClient, AsyncIOMotorDatabase, AsyncIOMotorCollection
from pymongo.errors import DuplicateKeyError, ConnectionFailure
from bson import ObjectId
from bson.errors import InvalidId

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
        """Connect to MongoDB/DocumentDB"""
        try:
            logger.info(f"Connecting to database: {settings.documentdb_host}:{settings.documentdb_port}")
            
            self.client = AsyncIOMotorClient(
                settings.mongodb_uri,
                serverSelectionTimeoutMS=5000,
                connectTimeoutMS=10000,
                socketTimeoutMS=10000,
                maxPoolSize=10,
                minPoolSize=2
            )
            
            self.database = self.client[settings.documentdb_database]
            
            # Test connection
            await self.client.admin.command('ping')
            
            # Create indexes
            await self._create_indexes()
            
            self._connected = True
            logger.info("✅ Database connected successfully")
            
        except Exception as e:
            logger.error(f"❌ Database connection failed: {e}")
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
            if not ObjectId.is_valid(client_id):
                return None
            
            doc = await self.db.clients.find_one({"_id": ObjectId(client_id)})
            if doc:
                doc["id"] = str(doc["_id"])
                return Client(**doc)
            return None
        except Exception as e:
            logger.error(f"Failed to get client by ID {client_id}: {e}")
            return None
    
    async def get_client_by_phone(self, phone: str) -> Optional[Client]:
        """Get client by phone number"""
        try:
            doc = await self.db.clients.find_one({"client.phone": phone})
            if doc:
                doc["id"] = str(doc["_id"])
                return Client(**doc)
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
    
    async def assign_agent(self, client_id: str, agent_id: str, meeting_time: Optional[datetime] = None) -> bool:
        """Assign agent to client"""
        try:
            if not ObjectId.is_valid(client_id):
                return False
            
            assignment = {
                "agentId": agent_id,
                "assignedAt": datetime.utcnow(),
                "assignmentReason": "interested",
                "meetingScheduled": meeting_time,
                "meetingStatus": "pending" if meeting_time else "not_scheduled"
            }
            
            result = await self.db.clients.update_one(
                {"_id": ObjectId(client_id)},
                {
                    "$set": {
                        "agentAssignment": assignment,
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

# Global database client instance
db_client = DatabaseClient()

# Repository instances
client_repo: Optional[ClientRepository] = None
session_repo: Optional[SessionRepository] = None

async def init_database():
    """Initialize database connection and repositories"""
    global client_repo, session_repo
    
    await db_client.connect()
    client_repo = ClientRepository(db_client)
    session_repo = SessionRepository(db_client)
    
    logger.info("✅ Database repositories initialized")

async def close_database():
    """Close database connection"""
    await db_client.disconnect()
    logger.info("Database connection closed")

# Utility functions for easy access
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