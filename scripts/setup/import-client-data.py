#!/usr/bin/env python3
"""
Import client data from CSV to DocumentDB
"""

import csv
import os
import sys
from pymongo import MongoClient
from datetime import datetime

def import_clients():
    # Database connection
    mongo_uri = f"mongodb://{os.getenv('DOCUMENTDB_USERNAME', 'admin')}:{os.getenv('DOCUMENTDB_PASSWORD', 'password123')}@{os.getenv('DOCUMENTDB_HOST', 'localhost')}:{os.getenv('DOCUMENTDB_PORT', '27017')}/{os.getenv('DOCUMENTDB_DATABASE', 'voice_agent')}"
    
    client = MongoClient(mongo_uri)
    db = client[os.getenv('DOCUMENTDB_DATABASE', 'voice_agent')]
    collection = db.clients
    
    # Clear existing data
    collection.delete_many({})
    print("Cleared existing client data")
    
    # Import from CSV
    csv_file = 'data/clients-14k.csv'
    if not os.path.exists(csv_file):
        print(f"CSV file not found: {csv_file}")
        sys.exit(1)
    
    clients = []
    with open(csv_file, 'r') as file:
        reader = csv.DictReader(file)
        for row in reader:
            client_doc = {
                'client': {
                    'firstName': row['first_name'],
                    'lastName': row['last_name'],
                    'phone': row['phone'],
                    'email': row['email'],
                    'lastAgent': row['last_agent']
                },
                'campaignStatus': 'pending',
                'callHistory': [],
                'crmTags': [],
                'agentAssigned': None,
                'meetingScheduled': None,
                'createdAt': datetime.utcnow(),
                'updatedAt': datetime.utcnow()
            }
            clients.append(client_doc)
    
    # Bulk insert
    result = collection.insert_many(clients)
    print(f"Imported {len(result.inserted_ids)} clients successfully")
    
    client.close()

if __name__ == '__main__':
    import_clients()
