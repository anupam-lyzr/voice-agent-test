"""
Configurable Email Signature System
Allows easy management of email signatures from a single location
"""

import os
from typing import Optional, Dict, Any
from pathlib import Path

class EmailSignature:
    """Configurable email signature system"""
    
    def __init__(self):
        # Default signature configuration
        self.signature_config = {
            "contact_email": "service@altruisadvisor.com",
            "contact_phone": "833.227.8500",
            "agent_name": "Alex",
            "company_name": "Altruis Advisor Group",
            "signature_image_path": None,  # Path to signature image
            "extra_note": None,  # Additional note text
            "website": "https://altruisadvisor.com",
            "address": None,
            "social_media": None
        }
        
        # Load custom configuration if exists
        self._load_signature_config()
    
    def _load_signature_config(self):
        """Load signature configuration from environment variables or config file"""
        # Load from environment variables
        self.signature_config["contact_email"] = os.getenv("EMAIL_SIGNATURE_EMAIL", self.signature_config["contact_email"])
        self.signature_config["contact_phone"] = os.getenv("EMAIL_SIGNATURE_PHONE", self.signature_config["contact_phone"])
        self.signature_config["agent_name"] = os.getenv("EMAIL_SIGNATURE_AGENT_NAME", self.signature_config["agent_name"])
        self.signature_config["company_name"] = os.getenv("EMAIL_SIGNATURE_COMPANY", self.signature_config["company_name"])
        self.signature_config["signature_image_path"] = os.getenv("EMAIL_SIGNATURE_IMAGE", self.signature_config["signature_image_path"])
        self.signature_config["extra_note"] = os.getenv("EMAIL_SIGNATURE_NOTE", self.signature_config["extra_note"])
        self.signature_config["website"] = os.getenv("EMAIL_SIGNATURE_WEBSITE", self.signature_config["website"])
        self.signature_config["address"] = os.getenv("EMAIL_SIGNATURE_ADDRESS", self.signature_config["address"])
        self.signature_config["social_media"] = os.getenv("EMAIL_SIGNATURE_SOCIAL", self.signature_config["social_media"])
    
    def get_html_signature(self, agent_name: Optional[str] = None) -> str:
        """Get HTML formatted email signature"""
        agent = agent_name or self.signature_config["agent_name"]
        contact_email = self.signature_config["contact_email"]
        contact_phone = self.signature_config["contact_phone"]
        company = self.signature_config["company_name"]
        
        signature_html = f"""
        <div class="email-signature" style="margin-top: 30px; padding-top: 20px; border-top: 1px solid #e0e0e0;">
        """
        
        # Add signature image if available
        if self.signature_config["signature_image_path"] and os.path.exists(self.signature_config["signature_image_path"]):
            signature_html += f"""
            <div class="signature-image" style="margin-bottom: 15px;">
                <img src="{self.signature_config['signature_image_path']}" alt="{company} Signature" style="max-width: 200px; height: auto;">
            </div>
            """
        
        # Contact information
        signature_html += f"""
            <div class="contact-info" style="margin-bottom: 10px;">
                <p style="margin: 5px 0; color: #666; font-size: 14px;">
                    <strong>{contact_email}</strong> / <strong>{contact_phone}</strong>
                </p>
            </div>
        """
        
        # Extra note if provided
        if self.signature_config["extra_note"]:
            signature_html += f"""
            <div class="extra-note" style="margin-bottom: 10px;">
                <p style="margin: 5px 0; color: #666; font-size: 12px; font-style: italic;">
                    {self.signature_config["extra_note"]}
                </p>
            </div>
            """
        
        # Closing
        signature_html += f"""
            <div class="closing" style="margin-top: 15px;">
                <p style="margin: 5px 0; color: #333; font-size: 14px;">
                    Kind Regards,<br>
                    <strong>{agent}</strong>
                </p>
            </div>
        </div>
        """
        
        return signature_html
    
    def get_text_signature(self, agent_name: Optional[str] = None) -> str:
        """Get text formatted email signature"""
        agent = agent_name or self.signature_config["agent_name"]
        contact_email = self.signature_config["contact_email"]
        contact_phone = self.signature_config["contact_phone"]
        
        signature_text = f"\n{contact_email} / {contact_phone}\n"
        
        # Extra note if provided
        if self.signature_config["extra_note"]:
            signature_text += f"\n{self.signature_config['extra_note']}\n"
        
        signature_text += f"\nKind Regards,\n{agent}\n"
        
        return signature_text
    
    def update_signature_config(self, **kwargs):
        """Update signature configuration"""
        for key, value in kwargs.items():
            if key in self.signature_config:
                self.signature_config[key] = value
    
    def get_signature_config(self) -> Dict[str, Any]:
        """Get current signature configuration"""
        return self.signature_config.copy()

# Global instance
email_signature = EmailSignature()
