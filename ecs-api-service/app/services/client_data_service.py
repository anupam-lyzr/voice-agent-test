"""
Client Data Service - Enhanced with Medicare/Non-Medicare Detection
Handles client data from Excel file and determines appropriate scripts
"""

import logging
from typing import Dict, Any, Optional, Tuple
from enum import Enum

logger = logging.getLogger(__name__)

class ClientType(str, Enum):
    """Type of client based on tags"""
    MEDICARE = "medicare"
    NON_MEDICARE = "non_medicare"
    UNKNOWN = "unknown"

class AgentInfo:
    """Agent information extracted from tags"""
    
    def __init__(self, full_name: str, client_type: ClientType):
        self.full_name = full_name
        self.client_type = client_type
        
        # Extract first/last name
        name_parts = full_name.split()
        if len(name_parts) >= 2:
            self.first_name = name_parts[0]
            self.last_name = " ".join(name_parts[1:])
        else:
            self.first_name = full_name
            self.last_name = ""

class ClientDataService:
    """Service for handling client data and determining script types"""
    
    def __init__(self):
        # Agent name mappings from tags
        self.agent_mappings = {
            "AB - Anthony Fracchia": "Anthony Fracchia",
            "AB - Hineth Pettway": "Hineth Pettway", 
            "AB - India Watson": "India Watson",
            "AB - Keith Braswell": "Keith Braswell",
            "AB - LaShawn Boyd": "LaShawn Boyd"
        }
    
    def analyze_client_data(self, client_data: Dict[str, Any]) -> Dict[str, Any]:
        """Analyze client data to determine type and appropriate script"""
        
        try:
            # Extract basic info
            first_name = client_data.get("first_name", "")
            last_name = client_data.get("last_name", "")
            phone = client_data.get("phone", "")
            email = client_data.get("email", "")
            tags = client_data.get("tags", "")
            
            # Determine client type and agent
            client_type, agent_info = self._analyze_tags(tags)
            
            # Create enhanced client data
            enhanced_data = {
                "first_name": first_name,
                "last_name": last_name,
                "full_name": f"{first_name} {last_name}".strip(),
                "phone": phone,
                "email": email,
                "tags": tags,
                "client_type": client_type,
                "is_medicare_client": client_type == ClientType.MEDICARE,
                "is_non_medicare_client": client_type == ClientType.NON_MEDICARE,
                "agent_info": {
                    "full_name": agent_info.full_name if agent_info else "our team",
                    "first_name": agent_info.first_name if agent_info else "",
                    "last_name": agent_info.last_name if agent_info else "",
                } if agent_info else None,
                "script_type": self._determine_script_type(client_type),
                "greeting_template": self._get_greeting_template(client_type),
                "voicemail_template": self._get_voicemail_template(client_type)
            }
            
            return enhanced_data
            
        except Exception as e:
            logger.error(f"❌ Error analyzing client data: {e}")
            return self._get_fallback_client_data(client_data)
    
    def _analyze_tags(self, tags: str) -> Tuple[ClientType, Optional[AgentInfo]]:
        """Analyze tags to determine client type and agent"""
        
        if not tags:
            return ClientType.UNKNOWN, None
        
        tags_lower = tags.lower().strip()
        
        # Determine client type
        if "aag - medicare client" in tags_lower:
            client_type = ClientType.MEDICARE
        elif any(agent_prefix in tags_lower for agent_prefix in ["ab - anthony", "ab - hineth", "ab - india", "ab - keith", "ab - lashawn"]):
            client_type = ClientType.NON_MEDICARE
        else:
            client_type = ClientType.UNKNOWN
        
        # Extract agent information
        agent_info = None
        for tag_prefix, agent_name in self.agent_mappings.items():
            if tag_prefix.lower() in tags_lower:
                agent_info = AgentInfo(agent_name, client_type)
                break
        
        return client_type, agent_info
    
    def _determine_script_type(self, client_type: ClientType) -> str:
        """Determine which script type to use"""
        
        if client_type == ClientType.NON_MEDICARE:
            return "non_medicare_script"
        elif client_type == ClientType.MEDICARE:
            return "medicare_script"  # For future use
        else:
            return "default_script"
    
    def _get_greeting_template(self, client_type: ClientType) -> str:
        """Get the appropriate greeting template"""
        
        if client_type == ClientType.NON_MEDICARE:
            return "non_medicare_greeting"
        elif client_type == ClientType.MEDICARE:
            return "medicare_greeting"  # For future use
        else:
            return "default_greeting"
    
    def _get_voicemail_template(self, client_type: ClientType) -> str:
        """Get the appropriate voicemail template"""
        
        if client_type == ClientType.NON_MEDICARE:
            return "non_medicare_voicemail"
        elif client_type == ClientType.MEDICARE:
            return "medicare_voicemail"  # For future use
        else:
            return "default_voicemail"
    
    def _get_fallback_client_data(self, original_data: Dict[str, Any]) -> Dict[str, Any]:
        """Provide fallback client data structure"""
        
        return {
            "first_name": original_data.get("first_name", ""),
            "last_name": original_data.get("last_name", ""),
            "full_name": f"{original_data.get('first_name', '')} {original_data.get('last_name', '')}".strip(),
            "phone": original_data.get("phone", ""),
            "email": original_data.get("email", ""),
            "tags": original_data.get("tags", ""),
            "client_type": ClientType.UNKNOWN,
            "is_medicare_client": False,
            "is_non_medicare_client": False,
            "agent_info": None,
            "script_type": "default_script",
            "greeting_template": "default_greeting", 
            "voicemail_template": "default_voicemail"
        }
    
    def get_scripts_for_client_type(self, client_type: ClientType) -> Dict[str, str]:
        """Get all scripts for a specific client type"""
        
        if client_type == ClientType.NON_MEDICARE:
            return {
                "greeting": "Hello {client_name}, Alex calling on behalf of Anthony Fracchia and Altruis Advisor Group, we've helped you with your health insurance needs in the past and I'm reaching out to see if we can be of service to you this year during Open Enrollment? A simple 'Yes' or 'No' is fine, and remember, our services are completely free of charge.",
                
                "agent_intro": "Great, looks like {agent_name} was the last agent you worked with here at Altruis. Would you like to schedule a quick 15-minute discovery call with them to get reacquainted? A simple Yes or No will do!",
                
                "schedule_confirmation": "Perfect! I'll send you an email shortly with {agent_name}'s available time slots. You can review the calendar and choose a time that works best for your schedule. Thank you so much for your time today, and have a wonderful day!",
                
                "no_schedule_followup": "No problem, {agent_name} will reach out to you and the two of you can work together to determine the best next steps. We look forward to servicing you, have a wonderful day!",
                
                "not_interested": "No problem, would you like to continue receiving general health insurance communications from our team? Again, a simple Yes or No will do!",
                
                "dnc_confirmation": "Understood, we will make sure you are removed from all future communications and send you a confirmation email once that is done. If you'd like to connect with one of our insurance experts in the future please feel free to reach out — we are always here to help and our service is always free of charge. Have a wonderful day!",
                
                "keep_communications": "Great! We'll keep you in the loop with helpful health insurance updates throughout the year. If you ever need assistance, just reach out - we're always here to help, and our service is always free. Thank you for your time today!",
                
                "voicemail": "Hello {client_name}, Alex calling on behalf of Anthony Fracchia and Altruis Advisor Group. We've helped with your health insurance needs in the past and we wanted to reach out to see if we could be of assistance this year during Open Enrollment. There have been a number of important changes to the Affordable Care Act that may impact your situation - so it may make sense to do a quick policy review. As always, our services are completely free of charge - if you'd like to review your policy please call us at 8-3-3, 2-2-7, 8-5-0-0. We look forward to hearing from you - take care!"
            }
        
        elif client_type == ClientType.MEDICARE:
            # Future Medicare scripts can go here
            return {
                "greeting": "Hello {client_name}, this is Alex from Altruis Advisor Group. We've helped you with your Medicare needs in the past and I just wanted to reach out to see if we can be of service to you this year during Open Enrollment? A simple Yes or No is fine, and remember, our services are completely free of charge.",
                
                "voicemail": "Hello {client_name}, Alex here from Altruis Advisor Group. We've helped with your Medicare needs in the past and we wanted to reach out to see if we could be of assistance this year during Open Enrollment. Please call us at 8-3-3, 2-2-7, 8-5-0-0. We look forward to hearing from you - take care!"
            }
        
        else:
            # Default/fallback scripts
            return {
                "greeting": "Hello {client_name}, this is Alex from Altruis Advisor Group. We've helped you with your insurance needs in the past and I just wanted to reach out to see if we can be of service to you this year during Open Enrollment? A simple Yes or No is fine, and remember, our services are completely free of charge.",
                
                "voicemail": "Hello {client_name}, Alex here from Altruis Advisor Group. We've helped with your insurance needs in the past and we wanted to reach out to see if we could be of assistance this year during Open Enrollment. Please call us at 8-3-3, 2-2-7, 8-5-0-0. We look forward to hearing from you - take care!"
            }
    
    def format_script_with_data(self, script_template: str, client_data: Dict[str, Any]) -> str:
        """Format script template with actual client data"""
        
        try:
            # Prepare replacement values
            replacements = {
                "client_name": client_data.get("first_name", ""),
                "full_client_name": client_data.get("full_name", ""),
                "agent_name": client_data.get("agent_info", {}).get("full_name", "our team") if client_data.get("agent_info") else "our team",
                "agent_first_name": client_data.get("agent_info", {}).get("first_name", "") if client_data.get("agent_info") else ""
            }
            
            # Format the script
            formatted_script = script_template.format(**replacements)
            return formatted_script
            
        except Exception as e:
            logger.error(f"❌ Error formatting script: {e}")
            return script_template  # Return unformatted if error
    
    def get_formatted_scripts_for_client(self, client_data: Dict[str, Any]) -> Dict[str, str]:
        """Get all formatted scripts for a specific client"""
        
        # Analyze client data first
        enhanced_data = self.analyze_client_data(client_data)
        
        # Get script templates
        scripts = self.get_scripts_for_client_type(enhanced_data["client_type"])
        
        # Format all scripts with client data
        formatted_scripts = {}
        for script_name, script_template in scripts.items():
            formatted_scripts[script_name] = self.format_script_with_data(script_template, enhanced_data)
        
        return formatted_scripts