#!/usr/bin/env python3
"""
Simple client import for Docker environment
"""

import pandas as pd
import json
from datetime import datetime

# Read agents config
with open('/app/agents.json', 'r') as f:
    agents_config = json.load(f)

# Create agent tag mapping
agent_mapping = {}
for agent in agents_config['agents']:
    tag_id = agent.get('tag_identifier', '')
    if tag_id:
        agent_mapping[tag_id] = agent['name']

print("Agent mapping loaded:")
for tag, name in agent_mapping.items():
    print(f"  {tag} -> {name}")

# Read Excel file
print(f"\nReading Excel file...")
df = pd.read_excel('AAG-Lyzr.xlsx', sheet_name='contacts')
print(f"Found {len(df)} records")

# Show first 5 records with agent assignment
print(f"\nFirst 5 records:")
for i in range(min(5, len(df))):
    row = df.iloc[i]
    tag = str(row.get('Tags', '')).strip()
    agent = "Unassigned"
    
    # Find agent from tag
    for tag_id, agent_name in agent_mapping.items():
        if tag.startswith(tag_id):
            agent = agent_name
            break
    
    print(f"  {row['First Name']} {row['Last Name']} -> {agent}")

print(f"\n✅ Dry run completed - {len(df)} clients would be imported")
