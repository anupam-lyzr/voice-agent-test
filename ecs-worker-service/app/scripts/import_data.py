"""
Data Import Script
Imports client and agent data from Excel files into the database
"""

import asyncio
import logging
import sys
from pathlib import Path

# Add the parent directory to the Python path
sys.path.insert(0, str(Path(__file__).parent.parent))

from services.data_import_service import data_import_service
from shared.utils.database import init_database, close_database

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

async def main():
    """Main import function"""
    try:
        logger.info("🚀 Starting data import process...")
        
        # Initialize database connection
        logger.info("🔌 Initializing database connection...")
        await init_database()
        
        # Import all data
        logger.info("📊 Importing data from Excel files...")
        results = await data_import_service.import_all_data()
        
        if "error" in results:
            logger.error(f"❌ Import failed: {results['error']}")
            return
        
        # Print results
        logger.info("📈 Import Results:")
        logger.info(f"   Agents: {results.get('agents', {})}")
        logger.info(f"   Clients: {results.get('clients', {})}")
        
        # Assign clients to agents
        logger.info("🔄 Assigning clients to agents...")
        assignment_results = await data_import_service.assign_clients_to_agents()
        
        if assignment_results.get("success"):
            logger.info(f"✅ Successfully assigned {assignment_results['assigned_clients']} clients to agents")
        else:
            logger.error(f"❌ Assignment failed: {assignment_results.get('error')}")
        
        # Get final statistics
        logger.info("📊 Getting final statistics...")
        stats = await data_import_service.get_import_statistics()
        
        logger.info("📈 Final Statistics:")
        logger.info(f"   Agents: {stats.get('agents', {})}")
        logger.info(f"   Clients: {stats.get('clients', {})}")
        
        logger.info("✅ Data import completed successfully!")
        
    except Exception as e:
        logger.error(f"❌ Error during data import: {e}")
        raise
    finally:
        # Close database connection
        logger.info("🔌 Closing database connection...")
        await close_database()

if __name__ == "__main__":
    asyncio.run(main())
