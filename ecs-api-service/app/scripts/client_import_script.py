#!/usr/bin/env python3
"""
Client Data Import Script
Imports clients from Excel file with correct agent assignment from Tags column
"""

import asyncio
import sys
import os
import json
import logging
import pandas as pd
import re
from datetime import datetime
from typing import Dict, List, Optional, Any
from pathlib import Path

# Add the project root to Python path
sys.path.append(str(Path(__file__).parent.parent))

# Import shared modules (adjust paths based on where script runs)
try:
    from shared.config.settings import settings
    from shared.models.client import Client, ClientInfo, CampaignStatus
    from shared.utils.database import init_database, client_repo
except ImportError:
    print("❌ Cannot import shared modules. Make sure you're running from project root.")
    print("Usage: python scripts/setup/import-client-data.py")
    sys.exit(1)

# Configure logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

class ClientImporter:
    """Handles client data import with agent assignment"""
    
    def __init__(self):
        self.agents_config = self.load_agents_config()
        self.agent_tag_mapping = self.create_agent_tag_mapping()
        
        # Statistics
        self.imported_count = 0
        self.error_count = 0
        self.agent_assignment_stats = {}
    
    def load_agents_config(self) -> Dict[str, Any]:
        """Load agents configuration from file"""
        try:
            agents_file = Path("data/agents.json")
            if not agents_file.exists():
                logger.error("❌ agents.json not found. Run system-startup.sh first.")
                return {"agents": []}
            
            with open(agents_file, 'r') as f:
                config = json.load(f)
                logger.info(f"✅ Loaded {len(config.get('agents', []))} agents from config")
                return config
        except Exception as e:
            logger.error(f"❌ Failed to load agents config: {e}")
            return {"agents": []}
    
    def create_agent_tag_mapping(self) -> Dict[str, Dict[str, Any]]:
        """Create mapping from tag identifier to agent info"""
        mapping = {}
        
        for agent in self.agents_config.get("agents", []):
            tag_id = agent.get("tag_identifier", "")
            if tag_id:
                mapping[tag_id] = agent
                logger.info(f"📋 Mapped tag '{tag_id}' to agent {agent['name']}")
        
        logger.info(f"✅ Created mapping for {len(mapping)} agent tags")
        return mapping
    
    def extract_agent_from_tag(self, tag: str) -> Optional[Dict[str, Any]]:
        """Extract agent information from tag string"""
        if not tag:
            return None
        
        # Try exact match first
        if tag in self.agent_tag_mapping:
            return self.agent_tag_mapping[tag]
        
        # Try partial match for tags with additional info (e.g., "AB - Anthony Fracchia, AAG - Medicare Client")
        for tag_identifier, agent_info in self.agent_tag_mapping.items():
            if tag.startswith(tag_identifier):
                return agent_info
        
        # Extract agent name using regex pattern "AB - [Name]"
        match = re.match(r"AB - ([^,]+)", tag)
        if match:
            agent_name = match.group(1).strip()
            # Try to find agent by name
            for agent_info in self.agents_config.get("agents", []):
                if agent_info["name"] == agent_name:
                    return agent_info
        
        logger.warning(f"⚠️ Could not map tag to agent: {tag}")
        return None
    
    def read_excel_file(self, file_path: str) -> pd.DataFrame:
        """Read the Excel file and return DataFrame"""
        try:
            logger.info(f"📖 Reading Excel file: {file_path}")
            
            # Read the Excel file
            df = pd.read_excel(file_path, sheet_name='contacts')
            
            logger.info(f"✅ Successfully read {len(df)} records from Excel file")
            logger.info(f"📊 Columns: {list(df.columns)}")
            
            return df
            
        except Exception as e:
            logger.error(f"❌ Failed to read Excel file: {e}")
            raise
    
    def read_csv_file(self, file_path: str) -> pd.DataFrame:
        """Read CSV file for testing"""
        try:
            logger.info(f"📖 Reading CSV file: {file_path}")
            df = pd.read_csv(file_path)
            logger.info(f"✅ Successfully read {len(df)} records from CSV file")
            return df
        except Exception as e:
            logger.error(f"❌ Failed to read CSV file: {e}")
            raise
    
    def clean_phone_number(self, phone: Any) -> str:
        """Clean and format phone number"""
        if pd.isna(phone):
            return ""
        
        # Convert to string and remove all non-digits
        phone_str = str(phone)
        digits_only = re.sub(r'\D', '', phone_str)
        
        # Add country code if not present
        if len(digits_only) == 10:
            return f"+1{digits_only}"
        elif len(digits_only) == 11 and digits_only.startswith('1'):
            return f"+{digits_only}"
        else:
            return f"+1{digits_only}" if digits_only else ""
    
    def create_client_from_row(self, row: pd.Series, is_test: bool = False) -> Optional[Client]:
        """Create Client object from DataFrame row"""
        try:
            # Extract basic info
            first_name = str(row.get('First Name', row.get('first_name', ''))).strip()
            last_name = str(row.get('Last Name', row.get('last_name', ''))).strip()
            email = str(row.get('Email', row.get('email', ''))).strip()
            phone = self.clean_phone_number(row.get('Phone', row.get('phone', '')))
            tags = str(row.get('Tags', row.get('tags', ''))).strip()
            
            # Skip if missing required fields
            if not first_name or not last_name or not phone:
                logger.warning(f"⚠️ Skipping row with missing required fields: {first_name} {last_name}")
                return None
            
            # Get agent assignment
            agent_info = self.extract_agent_from_tag(tags)
            last_agent = agent_info['name'] if agent_info else "Unassigned"
            
            # Update agent stats
            if last_agent not in self.agent_assignment_stats:
                self.agent_assignment_stats[last_agent] = 0
            self.agent_assignment_stats[last_agent] += 1
            
            # Create client info
            client_info = ClientInfo(
                first_name=first_name,
                last_name=last_name,
                phone=phone,
                email=email if email and '@' in email else "",
                last_agent=last_agent,
                tags=[tags] if tags else [],
                is_test_client=is_test
            )
            
            # Create client with campaign status
            client = Client(
                client=client_info,
                campaign_status=CampaignStatus.PENDING,
                total_attempts=0,
                call_history=[],
                crm_tags=[],
                agent_assignment=None,
                meeting_scheduled=None,
                emails_sent=[]
            )
            
            return client
            
        except Exception as e:
            logger.error(f"❌ Failed to create client from row: {e}")
            self.error_count += 1
            return None
    
    async def import_clients(self, file_path: str, is_test: bool = False, limit: Optional[int] = None) -> bool:
        """Import clients from file"""
        try:
            # Determine file type and read
            if file_path.endswith('.xlsx'):
                df = self.read_excel_file(file_path)
            elif file_path.endswith('.csv'):
                df = self.read_csv_file(file_path)
            else:
                raise ValueError("Unsupported file format. Use .xlsx or .csv")
            
            # Apply limit if specified
            if limit:
                df = df.head(limit)
                logger.info(f"🔢 Limited import to {limit} records")
            
            # Process each row
            clients_to_import = []
            
            for index, row in df.iterrows():
                client = self.create_client_from_row(row, is_test=is_test)
                if client:
                    clients_to_import.append(client)
                
                # Log progress every 100 records
                if (index + 1) % 100 == 0:
                    logger.info(f"⚡ Processed {index + 1}/{len(df)} records...")
            
            # Import to database
            logger.info(f"💾 Importing {len(clients_to_import)} clients to database...")
            
            for client in clients_to_import:
                try:
                    # Check if client already exists
                    existing = await client_repo.get_client_by_phone(client.client.phone)
                    if existing:
                        logger.debug(f"📱 Client already exists: {client.client.phone}")
                        continue
                    
                    # Save new client
                    await client_repo.create_client(client)
                    self.imported_count += 1
                    
                except Exception as e:
                    logger.error(f"❌ Failed to import client {client.client.full_name}: {e}")
                    self.error_count += 1
            
            return True
            
        except Exception as e:
            logger.error(f"❌ Import failed: {e}")
            return False
    
    def print_statistics(self):
        """Print import statistics"""
        logger.info("📊 Import Statistics:")
        logger.info(f"   ✅ Successfully imported: {self.imported_count}")
        logger.info(f"   ❌ Errors: {self.error_count}")
        logger.info(f"   📋 Agent assignments:")
        
        for agent, count in sorted(self.agent_assignment_stats.items()):
            logger.info(f"      {agent}: {count} clients")

async def main():
    """Main import function"""
    import argparse
    
    parser = argparse.ArgumentParser(description='Import client data with agent assignment')
    parser.add_argument('--file', required=True, help='Path to Excel or CSV file')
    parser.add_argument('--test', action='store_true', help='Mark as test clients')
    parser.add_argument('--limit', type=int, help='Limit number of records to import')
    parser.add_argument('--dry-run', action='store_true', help='Preview import without saving')
    
    args = parser.parse_args()
    
    # Check if file exists
    if not os.path.exists(args.file):
        logger.error(f"❌ File not found: {args.file}")
        sys.exit(1)
    
    logger.info("🚀 Starting client data import...")
    logger.info(f"📁 File: {args.file}")
    logger.info(f"🧪 Test mode: {args.test}")
    logger.info(f"🔢 Limit: {args.limit if args.limit else 'None'}")
    logger.info(f"👁️ Dry run: {args.dry_run}")
    
    try:
        # Initialize database
        if not args.dry_run:
            await init_database()
            logger.info("✅ Database connection established")
        
        # Create importer and run
        importer = ClientImporter()
        
        if args.dry_run:
            logger.info("👁️ DRY RUN MODE - No data will be saved")
            # Just test reading the file
            if args.file.endswith('.xlsx'):
                df = importer.read_excel_file(args.file)
            else:
                df = importer.read_csv_file(args.file)
            
            logger.info(f"✅ File successfully read: {len(df)} records")
            logger.info("Sample records:")
            for i in range(min(5, len(df))):
                row = df.iloc[i]
                client = importer.create_client_from_row(row, args.test)
                if client:
                    logger.info(f"  {client.client.full_name} -> {client.client.last_agent}")
        else:
            success = await importer.import_clients(args.file, args.test, args.limit)
            
            if success:
                importer.print_statistics()
                logger.info("✅ Client import completed successfully!")
            else:
                logger.error("❌ Client import failed!")
                sys.exit(1)
    
    except Exception as e:
        logger.error(f"❌ Import failed with error: {e}")
        sys.exit(1)

if __name__ == "__main__":
    asyncio.run(main())