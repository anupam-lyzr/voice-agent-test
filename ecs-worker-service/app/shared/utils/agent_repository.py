"""
Agent Repository
Handles database operations for agents
"""

import logging
from typing import List, Optional, Dict, Any
from datetime import datetime
from bson import ObjectId

from shared.models.agent import Agent, AgentCreate, AgentUpdate
from shared.utils.database import get_database

logger = logging.getLogger(__name__)

class AgentRepository:
    """Repository for agent database operations"""
    
    def __init__(self):
        self.db = get_database()
        self.collection = self.db.agents
    
    async def create_agent(self, agent: AgentCreate) -> Agent:
        """Create a new agent"""
        try:
            agent_data = agent.dict()
            agent_data["created_at"] = datetime.utcnow()
            agent_data["updated_at"] = datetime.utcnow()
            
            result = await self.collection.insert_one(agent_data)
            
            # Get the created agent
            created_agent = await self.get_agent_by_id(str(result.inserted_id))
            logger.info(f"✅ Created agent: {agent.name}")
            return created_agent
            
        except Exception as e:
            logger.error(f"❌ Error creating agent: {e}")
            raise
    
    async def get_agent_by_id(self, agent_id: str) -> Optional[Agent]:
        """Get agent by ID"""
        try:
            if ObjectId.is_valid(agent_id):
                agent_data = await self.collection.find_one({"_id": ObjectId(agent_id)})
            else:
                agent_data = await self.collection.find_one({"agent_id": agent_id})
            
            if agent_data:
                return Agent(**agent_data)
            return None
            
        except Exception as e:
            logger.error(f"❌ Error getting agent by ID: {e}")
            return None
    
    async def get_agent_by_tag(self, tag_identifier: str) -> Optional[Agent]:
        """Get agent by tag identifier"""
        try:
            agent_data = await self.collection.find_one({"tag_identifier": tag_identifier})
            if agent_data:
                return Agent(**agent_data)
            return None
            
        except Exception as e:
            logger.error(f"❌ Error getting agent by tag: {e}")
            return None
    
    async def get_agent_by_email(self, email: str) -> Optional[Agent]:
        """Get agent by email"""
        try:
            agent_data = await self.collection.find_one({"email": email})
            if agent_data:
                return Agent(**agent_data)
            return None
            
        except Exception as e:
            logger.error(f"❌ Error getting agent by email: {e}")
            return None
    
    async def get_all_agents(self, active_only: bool = True) -> List[Agent]:
        """Get all agents"""
        try:
            filter_query = {"is_active": True} if active_only else {}
            cursor = self.collection.find(filter_query)
            agents = []
            
            async for agent_data in cursor:
                agents.append(Agent(**agent_data))
            
            return agents
            
        except Exception as e:
            logger.error(f"❌ Error getting all agents: {e}")
            return []
    
    async def update_agent(self, agent_id: str, updates: AgentUpdate) -> Optional[Agent]:
        """Update agent"""
        try:
            update_data = updates.dict(exclude_unset=True)
            update_data["updated_at"] = datetime.utcnow()
            
            if ObjectId.is_valid(agent_id):
                result = await self.collection.update_one(
                    {"_id": ObjectId(agent_id)},
                    {"$set": update_data}
                )
            else:
                result = await self.collection.update_one(
                    {"agent_id": agent_id},
                    {"$set": update_data}
                )
            
            if result.modified_count > 0:
                return await self.get_agent_by_id(agent_id)
            return None
            
        except Exception as e:
            logger.error(f"❌ Error updating agent: {e}")
            return None
    
    async def delete_agent(self, agent_id: str) -> bool:
        """Delete agent (soft delete by setting is_active to False)"""
        try:
            if ObjectId.is_valid(agent_id):
                result = await self.collection.update_one(
                    {"_id": ObjectId(agent_id)},
                    {"$set": {"is_active": False, "updated_at": datetime.utcnow()}}
                )
            else:
                result = await self.collection.update_one(
                    {"agent_id": agent_id},
                    {"$set": {"is_active": False, "updated_at": datetime.utcnow()}}
                )
            
            return result.modified_count > 0
            
        except Exception as e:
            logger.error(f"❌ Error deleting agent: {e}")
            return False
    
    async def increment_client_count(self, agent_id: str) -> bool:
        """Increment client count for an agent"""
        try:
            if ObjectId.is_valid(agent_id):
                result = await self.collection.update_one(
                    {"_id": ObjectId(agent_id)},
                    {"$inc": {"client_count": 1}, "$set": {"updated_at": datetime.utcnow()}}
                )
            else:
                result = await self.collection.update_one(
                    {"agent_id": agent_id},
                    {"$inc": {"client_count": 1}, "$set": {"updated_at": datetime.utcnow()}}
                )
            
            return result.modified_count > 0
            
        except Exception as e:
            logger.error(f"❌ Error incrementing client count: {e}")
            return False
    
    async def decrement_client_count(self, agent_id: str) -> bool:
        """Decrement client count for an agent"""
        try:
            if ObjectId.is_valid(agent_id):
                result = await self.collection.update_one(
                    {"_id": ObjectId(agent_id)},
                    {"$inc": {"client_count": -1}, "$set": {"updated_at": datetime.utcnow()}}
                )
            else:
                result = await self.collection.update_one(
                    {"agent_id": agent_id},
                    {"$inc": {"client_count": -1}, "$set": {"updated_at": datetime.utcnow()}}
                )
            
            return result.modified_count > 0
            
        except Exception as e:
            logger.error(f"❌ Error decrementing client count: {e}")
            return False
    
    async def get_agents_by_specialty(self, specialty: str) -> List[Agent]:
        """Get agents by specialty"""
        try:
            cursor = self.collection.find({
                "specialties": specialty,
                "is_active": True
            })
            
            agents = []
            async for agent_data in cursor:
                agents.append(Agent(**agent_data))
            
            return agents
            
        except Exception as e:
            logger.error(f"❌ Error getting agents by specialty: {e}")
            return []
    
    async def get_agents_with_lowest_client_count(self, limit: int = 5) -> List[Agent]:
        """Get agents with lowest client count (for load balancing)"""
        try:
            cursor = self.collection.find({"is_active": True}).sort("client_count", 1).limit(limit)
            
            agents = []
            async for agent_data in cursor:
                agents.append(Agent(**agent_data))
            
            return agents
            
        except Exception as e:
            logger.error(f"❌ Error getting agents with lowest client count: {e}")
            return []
    
    async def get_agent_statistics(self) -> Dict[str, Any]:
        """Get agent statistics"""
        try:
            pipeline = [
                {"$match": {"is_active": True}},
                {"$group": {
                    "_id": None,
                    "total_agents": {"$sum": 1},
                    "total_clients": {"$sum": "$client_count"},
                    "avg_clients_per_agent": {"$avg": "$client_count"},
                    "min_clients": {"$min": "$client_count"},
                    "max_clients": {"$max": "$client_count"}
                }}
            ]
            
            result = await self.collection.aggregate(pipeline).to_list(1)
            
            if result:
                stats = result[0]
                stats.pop("_id", None)
                return stats
            
            return {
                "total_agents": 0,
                "total_clients": 0,
                "avg_clients_per_agent": 0,
                "min_clients": 0,
                "max_clients": 0
            }
            
        except Exception as e:
            logger.error(f"❌ Error getting agent statistics: {e}")
            return {
                "total_agents": 0,
                "total_clients": 0,
                "avg_clients_per_agent": 0,
                "min_clients": 0,
                "max_clients": 0
            }
    
    async def bulk_create_agents(self, agents: List[AgentCreate]) -> List[Agent]:
        """Bulk create agents"""
        try:
            agent_data_list = []
            for agent in agents:
                agent_data = agent.dict()
                agent_data["created_at"] = datetime.utcnow()
                agent_data["updated_at"] = datetime.utcnow()
                agent_data_list.append(agent_data)
            
            result = await self.collection.insert_many(agent_data_list)
            
            # Get created agents
            created_agents = []
            for inserted_id in result.inserted_ids:
                agent = await self.get_agent_by_id(str(inserted_id))
                if agent:
                    created_agents.append(agent)
            
            logger.info(f"✅ Bulk created {len(created_agents)} agents")
            return created_agents
            
        except Exception as e:
            logger.error(f"❌ Error bulk creating agents: {e}")
            return []

# Global instance
agent_repo = AgentRepository()
