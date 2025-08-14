"""
Client Repository
Handles database operations for clients
"""

import logging
from typing import List, Optional, Dict, Any
from datetime import datetime
from bson import ObjectId

from shared.models.client import Client, ClientCreate, ClientUpdate, ClientAssignment
from shared.utils.database import get_database

logger = logging.getLogger(__name__)

class ClientRepository:
    """Repository for client database operations"""
    
    def __init__(self):
        self.db = get_database()
        self.collection = self.db.clients
    
    async def create_client(self, client: ClientCreate) -> Client:
        """Create a new client"""
        try:
            client_data = client.dict()
            client_data["created_at"] = datetime.utcnow()
            client_data["updated_at"] = datetime.utcnow()
            
            result = await self.collection.insert_one(client_data)
            
            # Get the created client
            created_client = await self.get_client_by_id(str(result.inserted_id))
            logger.info(f"✅ Created client: {client.full_name}")
            return created_client
            
        except Exception as e:
            logger.error(f"❌ Error creating client: {e}")
            raise
    
    async def get_client_by_id(self, client_id: str) -> Optional[Client]:
        """Get client by ID"""
        try:
            if ObjectId.is_valid(client_id):
                client_data = await self.collection.find_one({"_id": ObjectId(client_id)})
            else:
                client_data = await self.collection.find_one({"client_id": client_id})
            
            if client_data:
                return Client(**client_data)
            return None
            
        except Exception as e:
            logger.error(f"❌ Error getting client by ID: {e}")
            return None
    
    async def get_client_by_phone(self, phone_number: str) -> Optional[Client]:
        """Get client by phone number"""
        try:
            client_data = await self.collection.find_one({"phone_number": phone_number})
            if client_data:
                return Client(**client_data)
            return None
            
        except Exception as e:
            logger.error(f"❌ Error getting client by phone: {e}")
            return None
    
    async def get_client_by_email(self, email: str) -> Optional[Client]:
        """Get client by email"""
        try:
            client_data = await self.collection.find_one({"email": email})
            if client_data:
                return Client(**client_data)
            return None
            
        except Exception as e:
            logger.error(f"❌ Error getting client by email: {e}")
            return None
    
    async def get_clients_by_agent(self, agent_id: str) -> List[Client]:
        """Get all clients assigned to an agent"""
        try:
            cursor = self.collection.find({"assigned_agent_id": agent_id, "is_active": True})
            clients = []
            
            async for client_data in cursor:
                clients.append(Client(**client_data))
            
            return clients
            
        except Exception as e:
            logger.error(f"❌ Error getting clients by agent: {e}")
            return []
    
    async def get_clients_by_status(self, call_status: str) -> List[Client]:
        """Get clients by call status"""
        try:
            cursor = self.collection.find({"call_status": call_status, "is_active": True})
            clients = []
            
            async for client_data in cursor:
                clients.append(Client(**client_data))
            
            return clients
            
        except Exception as e:
            logger.error(f"❌ Error getting clients by status: {e}")
            return []
    
    async def get_pending_clients(self, limit: int = 100) -> List[Client]:
        """Get clients pending calls"""
        try:
            cursor = self.collection.find({
                "call_status": "pending",
                "is_active": True,
                "call_attempts": {"$lt": "$max_call_attempts"}
            }).limit(limit)
            
            clients = []
            async for client_data in cursor:
                clients.append(Client(**client_data))
            
            return clients
            
        except Exception as e:
            logger.error(f"❌ Error getting pending clients: {e}")
            return []
    
    async def update_client(self, client_id: str, updates: ClientUpdate) -> Optional[Client]:
        """Update client"""
        try:
            update_data = updates.dict(exclude_unset=True)
            update_data["updated_at"] = datetime.utcnow()
            
            if ObjectId.is_valid(client_id):
                result = await self.collection.update_one(
                    {"_id": ObjectId(client_id)},
                    {"$set": update_data}
                )
            else:
                result = await self.collection.update_one(
                    {"client_id": client_id},
                    {"$set": update_data}
                )
            
            if result.modified_count > 0:
                return await self.get_client_by_id(client_id)
            return None
            
        except Exception as e:
            logger.error(f"❌ Error updating client: {e}")
            return None
    
    async def assign_agent_to_client(self, client_id: str, assignment: ClientAssignment) -> bool:
        """Assign agent to client"""
        try:
            update_data = {
                "assigned_agent_id": assignment.agent_id,
                "assigned_agent_name": assignment.agent_name,
                "assigned_agent_tag": assignment.agent_tag,
                "assignment_date": assignment.assigned_at,
                "updated_at": datetime.utcnow()
            }
            
            if ObjectId.is_valid(client_id):
                result = await self.collection.update_one(
                    {"_id": ObjectId(client_id)},
                    {"$set": update_data}
                )
            else:
                result = await self.collection.update_one(
                    {"client_id": client_id},
                    {"$set": update_data}
                )
            
            return result.modified_count > 0
            
        except Exception as e:
            logger.error(f"❌ Error assigning agent to client: {e}")
            return False
    
    async def update_call_status(self, client_id: str, status: str, outcome: Optional[str] = None, notes: Optional[str] = None) -> bool:
        """Update client call status"""
        try:
            update_data = {
                "call_status": status,
                "last_call_date": datetime.utcnow(),
                "call_attempts": {"$inc": 1},
                "updated_at": datetime.utcnow()
            }
            
            if outcome:
                update_data["call_outcome"] = outcome
            if notes:
                update_data["call_notes"] = notes
            
            if ObjectId.is_valid(client_id):
                result = await self.collection.update_one(
                    {"_id": ObjectId(client_id)},
                    {"$set": update_data}
                )
            else:
                result = await self.collection.update_one(
                    {"client_id": client_id},
                    {"$set": update_data}
                )
            
            return result.modified_count > 0
            
        except Exception as e:
            logger.error(f"❌ Error updating call status: {e}")
            return False
    
    async def mark_dnc(self, client_id: str, reason: Optional[str] = None) -> bool:
        """Mark client as Do Not Call"""
        try:
            update_data = {
                "dnc_requested": True,
                "dnc_date": datetime.utcnow(),
                "call_status": "dnc",
                "updated_at": datetime.utcnow()
            }
            
            if reason:
                update_data["call_notes"] = reason
            
            if ObjectId.is_valid(client_id):
                result = await self.collection.update_one(
                    {"_id": ObjectId(client_id)},
                    {"$set": update_data}
                )
            else:
                result = await self.collection.update_one(
                    {"client_id": client_id},
                    {"$set": update_data}
                )
            
            return result.modified_count > 0
            
        except Exception as e:
            logger.error(f"❌ Error marking DNC: {e}")
            return False
    
    async def schedule_meeting(self, client_id: str, meeting_date: datetime) -> bool:
        """Schedule meeting for client"""
        try:
            update_data = {
                "meeting_scheduled": True,
                "meeting_date": meeting_date,
                "call_status": "scheduled",
                "updated_at": datetime.utcnow()
            }
            
            if ObjectId.is_valid(client_id):
                result = await self.collection.update_one(
                    {"_id": ObjectId(client_id)},
                    {"$set": update_data}
                )
            else:
                result = await self.collection.update_one(
                    {"client_id": client_id},
                    {"$set": update_data}
                )
            
            return result.modified_count > 0
            
        except Exception as e:
            logger.error(f"❌ Error scheduling meeting: {e}")
            return False
    
    async def get_client_statistics(self) -> Dict[str, Any]:
        """Get client statistics"""
        try:
            pipeline = [
                {"$match": {"is_active": True}},
                {"$group": {
                    "_id": None,
                    "total_clients": {"$sum": 1},
                    "pending_calls": {"$sum": {"$cond": [{"$eq": ["$call_status", "pending"]}, 1, 0]}},
                    "called": {"$sum": {"$cond": [{"$eq": ["$call_status", "called"]}, 1, 0]}},
                    "interested": {"$sum": {"$cond": [{"$eq": ["$call_status", "interested"]}, 1, 0]}},
                    "not_interested": {"$sum": {"$cond": [{"$eq": ["$call_status", "not_interested"]}, 1, 0]}},
                    "scheduled": {"$sum": {"$cond": [{"$eq": ["$call_status", "scheduled"]}, 1, 0]}},
                    "dnc": {"$sum": {"$cond": [{"$eq": ["$call_status", "dnc"]}, 1, 0]}},
                    "avg_call_attempts": {"$avg": "$call_attempts"}
                }}
            ]
            
            result = await self.collection.aggregate(pipeline).to_list(1)
            
            if result:
                stats = result[0]
                stats.pop("_id", None)
                return stats
            
            return {
                "total_clients": 0,
                "pending_calls": 0,
                "called": 0,
                "interested": 0,
                "not_interested": 0,
                "scheduled": 0,
                "dnc": 0,
                "avg_call_attempts": 0
            }
            
        except Exception as e:
            logger.error(f"❌ Error getting client statistics: {e}")
            return {
                "total_clients": 0,
                "pending_calls": 0,
                "called": 0,
                "interested": 0,
                "not_interested": 0,
                "scheduled": 0,
                "dnc": 0,
                "avg_call_attempts": 0
            }
    
    async def bulk_create_clients(self, clients: List[ClientCreate]) -> List[Client]:
        """Bulk create clients"""
        try:
            client_data_list = []
            for client in clients:
                client_data = client.dict()
                client_data["created_at"] = datetime.utcnow()
                client_data["updated_at"] = datetime.utcnow()
                client_data_list.append(client_data)
            
            result = await self.collection.insert_many(client_data_list)
            
            # Get created clients
            created_clients = []
            for inserted_id in result.inserted_ids:
                client = await self.get_client_by_id(str(inserted_id))
                if client:
                    created_clients.append(client)
            
            logger.info(f"✅ Bulk created {len(created_clients)} clients")
            return created_clients
            
        except Exception as e:
            logger.error(f"❌ Error bulk creating clients: {e}")
            return []
    
    async def search_clients(self, search_term: str, limit: int = 50) -> List[Client]:
        """Search clients by name, email, or phone"""
        try:
            # Create regex pattern for case-insensitive search
            import re
            pattern = re.compile(search_term, re.IGNORECASE)
            
            cursor = self.collection.find({
                "$or": [
                    {"full_name": pattern},
                    {"email": pattern},
                    {"phone_number": pattern}
                ],
                "is_active": True
            }).limit(limit)
            
            clients = []
            async for client_data in cursor:
                clients.append(Client(**client_data))
            
            return clients
            
        except Exception as e:
            logger.error(f"❌ Error searching clients: {e}")
            return []

# Global instance
client_repo = ClientRepository()
