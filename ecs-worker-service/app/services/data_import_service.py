"""
Data Import Service
Handles importing client and agent data from Excel files
"""

import asyncio
import logging
import pandas as pd
from typing import List, Dict, Any, Optional
from datetime import datetime
from pathlib import Path

from shared.models.agent import AgentCreate
from shared.models.client import ClientCreate
from shared.utils.agent_repository import agent_repo
from shared.utils.client_repository import client_repo

logger = logging.getLogger(__name__)

class DataImportService:
    """Service for importing data from Excel files"""
    
    def __init__(self):
        self.temp_dir = Path("temp")
        self.data_dir = Path("data")
    
    async def import_all_data(self) -> Dict[str, Any]:
        """Import all data (agents and clients)"""
        try:
            results = {}
            
            # Import agents first
            logger.info("🔄 Starting agent import...")
            agent_result = await self.import_agents()
            results["agents"] = agent_result
            
            # Import clients
            logger.info("🔄 Starting client import...")
            client_result = await self.import_clients()
            results["clients"] = client_result
            
            logger.info("✅ Data import completed successfully")
            return results
            
        except Exception as e:
            logger.error(f"❌ Error importing data: {e}")
            return {"error": str(e)}
    
    async def import_agents(self) -> Dict[str, Any]:
        """Import agents from the AAG-Lyzr.xlsx file"""
        try:
            excel_file = self.temp_dir / "AAG-Lyzr.xlsx"
            
            if not excel_file.exists():
                logger.warning(f"⚠️ Agent Excel file not found: {excel_file}")
                return {"success": False, "error": "Agent Excel file not found"}
            
            # Read Excel file
            df = pd.read_excel(excel_file)
            logger.info(f"📊 Loaded {len(df)} rows from agent Excel file")
            
            # Extract unique agent tags from the last column
            agent_tags = self._extract_agent_tags(df)
            logger.info(f"👥 Found {len(agent_tags)} unique agent tags")
            
            # Create agent records
            agents_to_create = []
            for tag in agent_tags:
                agent_data = self._parse_agent_tag(tag)
                if agent_data:
                    agent_create = AgentCreate(**agent_data)
                    agents_to_create.append(agent_create)
            
            # Bulk create agents
            if agents_to_create:
                created_agents = await agent_repo.bulk_create_agents(agents_to_create)
                logger.info(f"✅ Created {len(created_agents)} agents")
                
                return {
                    "success": True,
                    "total_agents": len(agents_to_create),
                    "created_agents": len(created_agents),
                    "agent_tags": agent_tags
                }
            else:
                logger.warning("⚠️ No valid agent data found")
                return {"success": False, "error": "No valid agent data found"}
                
        except Exception as e:
            logger.error(f"❌ Error importing agents: {e}")
            return {"success": False, "error": str(e)}
    
    async def import_clients(self) -> Dict[str, Any]:
        """Import clients from the reconciled Excel file"""
        try:
            excel_file = self.temp_dir / "File 1 - Reconciled - FINAL.xlsx"
            
            if not excel_file.exists():
                logger.warning(f"⚠️ Client Excel file not found: {excel_file}")
                return {"success": False, "error": "Client Excel file not found"}
            
            # Read Excel file
            df = pd.read_excel(excel_file)
            logger.info(f"📊 Loaded {len(df)} rows from client Excel file")
            
            # Process client data
            clients_to_create = []
            for index, row in df.iterrows():
                try:
                    client_data = self._parse_client_row(row, index + 1)
                    if client_data:
                        client_create = ClientCreate(**client_data)
                        clients_to_create.append(client_create)
                except Exception as e:
                    logger.warning(f"⚠️ Error parsing row {index + 1}: {e}")
                    continue
            
            # Bulk create clients
            if clients_to_create:
                created_clients = await client_repo.bulk_create_clients(clients_to_create)
                logger.info(f"✅ Created {len(created_clients)} clients")
                
                return {
                    "success": True,
                    "total_clients": len(clients_to_create),
                    "created_clients": len(created_clients),
                    "source_file": excel_file.name
                }
            else:
                logger.warning("⚠️ No valid client data found")
                return {"success": False, "error": "No valid client data found"}
                
        except Exception as e:
            logger.error(f"❌ Error importing clients: {e}")
            return {"success": False, "error": str(e)}
    
    def _extract_agent_tags(self, df: pd.DataFrame) -> List[str]:
        """Extract unique agent tags from the last column"""
        try:
            # Get the last column (agent tags)
            last_column = df.columns[-1]
            agent_tags = df[last_column].dropna().unique().tolist()
            
            # Clean and filter tags
            cleaned_tags = []
            for tag in agent_tags:
                if isinstance(tag, str) and tag.strip():
                    cleaned_tag = tag.strip()
                    if cleaned_tag.startswith("AB - "):
                        cleaned_tags.append(cleaned_tag)
            
            return list(set(cleaned_tags))  # Remove duplicates
            
        except Exception as e:
            logger.error(f"❌ Error extracting agent tags: {e}")
            return []
    
    def _parse_agent_tag(self, tag: str) -> Optional[Dict[str, Any]]:
        """Parse agent tag to create agent data"""
        try:
            # Expected format: "AB - FirstName LastName"
            if not tag.startswith("AB - "):
                return None
            
            name_part = tag[5:]  # Remove "AB - " prefix
            name_parts = name_part.split()
            
            if len(name_parts) < 2:
                logger.warning(f"⚠️ Invalid agent name format: {tag}")
                return None
            
            first_name = name_parts[0]
            last_name = " ".join(name_parts[1:])
            full_name = f"{first_name} {last_name}"
            
            # Create email from name
            email = f"{first_name.lower()}.{last_name.lower().replace(' ', '')}@altruisadvisor.com"
            
            # Create agent ID
            agent_id = f"{first_name.lower()}_{last_name.lower().replace(' ', '_')}"
            
            return {
                "agent_id": agent_id,
                "name": full_name,
                "email": email,
                "google_calendar_id": email,
                "timezone": "America/New_York",
                "working_hours": "9AM-5PM",
                "specialties": ["health", "medicare"],  # Default specialties
                "tag_identifier": tag,
                "is_active": True
            }
            
        except Exception as e:
            logger.error(f"❌ Error parsing agent tag {tag}: {e}")
            return None
    
    def _parse_client_row(self, row: pd.Series, row_number: int) -> Optional[Dict[str, Any]]:
        """Parse a client row from the Excel file"""
        try:
            # Map Excel columns to client fields
            # You'll need to adjust these based on the actual Excel structure
            
            # Basic client info
            full_name = str(row.get('Full Name', '')).strip()
            if not full_name or full_name == 'nan':
                return None
            
            # Split name into first and last
            name_parts = full_name.split()
            first_name = name_parts[0] if name_parts else ""
            last_name = " ".join(name_parts[1:]) if len(name_parts) > 1 else ""
            
            # Phone number
            phone = str(row.get('Phone', '')).strip()
            if not phone or phone == 'nan':
                phone = "(555) 123-4567"  # Default phone if missing
            
            # Email
            email = str(row.get('Email', '')).strip()
            if email == 'nan':
                email = None
            
            # Address info
            address = str(row.get('Address', '')).strip()
            if address == 'nan':
                address = None
            
            city = str(row.get('City', '')).strip()
            if city == 'nan':
                city = None
            
            state = str(row.get('State', '')).strip()
            if state == 'nan':
                state = None
            
            zip_code = str(row.get('Zip', '')).strip()
            if zip_code == 'nan':
                zip_code = None
            
            # Agent assignment
            agent_tag = str(row.get('Agent', '')).strip()
            if agent_tag == 'nan':
                agent_tag = None
            
            # Policy info
            policy_type = str(row.get('Policy Type', '')).strip()
            if policy_type == 'nan':
                policy_type = None
            
            policy_number = str(row.get('Policy Number', '')).strip()
            if policy_number == 'nan':
                policy_number = None
            
            # Premium amount
            premium = row.get('Premium', None)
            if pd.isna(premium):
                premium = None
            
            # Create client ID
            client_id = f"client_{row_number:06d}"
            
            return {
                "client_id": client_id,
                "full_name": full_name,
                "first_name": first_name,
                "last_name": last_name,
                "email": email,
                "phone_number": phone,
                "address": address,
                "city": city,
                "state": state,
                "zip_code": zip_code,
                "assigned_agent_tag": agent_tag,
                "policy_type": policy_type,
                "policy_number": policy_number,
                "premium_amount": premium,
                "excel_row_id": row_number,
                "source_file": "File 1 - Reconciled - FINAL.xlsx"
            }
            
        except Exception as e:
            logger.error(f"❌ Error parsing client row {row_number}: {e}")
            return None
    
    async def assign_clients_to_agents(self) -> Dict[str, Any]:
        """Assign clients to agents based on agent tags"""
        try:
            # Get all clients without agent assignment
            clients = await client_repo.get_clients_by_status("pending")
            logger.info(f"🔄 Assigning {len(clients)} clients to agents...")
            
            assigned_count = 0
            for client in clients:
                if client.assigned_agent_tag:
                    # Find agent by tag
                    agent = await agent_repo.get_agent_by_tag(client.assigned_agent_tag)
                    if agent:
                        # Create assignment
                        assignment = ClientAssignment(
                            client_id=client.client_id,
                            agent_id=agent.agent_id,
                            agent_name=agent.name,
                            agent_tag=agent.tag_identifier,
                            assignment_reason="Excel import"
                        )
                        
                        # Assign agent to client
                        success = await client_repo.assign_agent_to_client(client.client_id, assignment)
                        if success:
                            # Increment agent's client count
                            await agent_repo.increment_client_count(agent.agent_id)
                            assigned_count += 1
                
                # Process in batches to avoid overwhelming the database
                if assigned_count % 100 == 0:
                    logger.info(f"📊 Assigned {assigned_count} clients so far...")
                    await asyncio.sleep(0.1)  # Small delay
            
            logger.info(f"✅ Successfully assigned {assigned_count} clients to agents")
            return {
                "success": True,
                "total_clients": len(clients),
                "assigned_clients": assigned_count
            }
            
        except Exception as e:
            logger.error(f"❌ Error assigning clients to agents: {e}")
            return {"success": False, "error": str(e)}
    
    async def get_import_statistics(self) -> Dict[str, Any]:
        """Get statistics about imported data"""
        try:
            agent_stats = await agent_repo.get_agent_statistics()
            client_stats = await client_repo.get_client_statistics()
            
            return {
                "agents": agent_stats,
                "clients": client_stats,
                "timestamp": datetime.utcnow().isoformat()
            }
            
        except Exception as e:
            logger.error(f"❌ Error getting import statistics: {e}")
            return {"error": str(e)}

# Global instance
data_import_service = DataImportService()
