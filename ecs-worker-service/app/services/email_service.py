"""
Email Service for SES Integration
Handles email notifications for agent assignments and meeting confirmations
"""

import asyncio
import logging
from typing import Dict, Any, Optional, List
from datetime import datetime

# For local development without AWS SES
try:
    import boto3
    from botocore.exceptions import ClientError, NoCredentialsError
    AWS_SES_AVAILABLE = True
except ImportError:
    AWS_SES_AVAILABLE = False

from shared.config.settings import settings

logger = logging.getLogger(__name__)

class EmailService:
    """Service for sending emails via AWS SES"""
    
    def __init__(self):
        self.ses_client = None
        self.from_email = getattr(settings, 'from_email', 'noreply@altruisadvisor.com')
        
        # Initialize SES client if available
        if AWS_SES_AVAILABLE and hasattr(settings, 'aws_region'):
            try:
                self.ses_client = boto3.client('ses', region_name=settings.aws_region)
                logger.info("✅ SES client initialized")
            except (NoCredentialsError, Exception) as e:
                logger.warning(f"⚠️ SES not available: {e}")
                self.ses_client = None
        else:
            logger.info("🔧 Running in mock mode - emails will be logged only")
        
        # Email statistics
        self.emails_sent = 0
        self.emails_failed = 0
    
    async def send_agent_assignment_email(
        self, 
        agent_email: str, 
        agent_name: str, 
        client_info: Dict[str, Any], 
        call_summary: Dict[str, Any]
    ) -> bool:
        """Send email notification to agent about new client assignment"""
        
        subject = f"New Lead Assigned - {client_info.get('name', 'Unknown Client')}"
        
        # Create email content
        html_content = self._create_assignment_email_html(agent_name, client_info, call_summary)
        text_content = self._create_assignment_email_text(agent_name, client_info, call_summary)
        
        return await self._send_email(
            to_email=agent_email,
            subject=subject,
            html_content=html_content,
            text_content=text_content
        )
    
    async def send_meeting_confirmation_email(
        self,
        client_email: str,
        client_name: str,
        agent_name: str,
        meeting_details: Dict[str, Any]
    ) -> bool:
        """Send meeting confirmation email to client"""
        
        subject = f"Discovery Call Scheduled - {agent_name} from Altrius Advisor Group"
        
        # Create email content
        html_content = self._create_confirmation_email_html(client_name, agent_name, meeting_details)
        text_content = self._create_confirmation_email_text(client_name, agent_name, meeting_details)
        
        return await self._send_email(
            to_email=client_email,
            subject=subject,
            html_content=html_content,
            text_content=text_content
        )
    
    async def send_no_contact_followup_email(
        self,
        client_email: str,
        client_name: str
    ) -> bool:
        """Send follow-up email when client couldn't be reached"""
        
        subject = "We Tried to Reach You - Altrius Advisor Group"
        
        html_content = f"""
        <html>
        <body>
            <h2>Hello {client_name},</h2>
            
            <p>We recently attempted to contact you regarding your insurance coverage options during Open Enrollment, but we weren't able to reach you.</p>
            
            <p>We'd still love to help you find the best insurance options for your needs. If you're interested in learning more about:</p>
            
            <ul>
                <li>Health Insurance Plans</li>
                <li>Medicare Options</li>
                <li>Dental and Vision Coverage</li>
                <li>Life Insurance</li>
            </ul>
            
            <p>Please reply to this email or call us at <strong>{getattr(settings, 'twilio_phone_number', '(555) 123-4567')}</strong></p>
            
            <p>Best regards,<br>
            The Altrius Advisor Group Team</p>
            
            <hr>
            <p style="font-size: 12px; color: #666;">
                If you no longer wish to receive communications from us, please reply with "UNSUBSCRIBE" in the subject line.
            </p>
        </body>
        </html>
        """
        
        text_content = f"""
        Hello {client_name},

        We recently attempted to contact you regarding your insurance coverage options during Open Enrollment, but we weren't able to reach you.

        We'd still love to help you find the best insurance options for your needs. If you're interested in learning more about Health Insurance Plans, Medicare Options, Dental and Vision Coverage, or Life Insurance, please reply to this email or call us at {getattr(settings, 'twilio_phone_number', '(555) 123-4567')}.

        Best regards,
        The Altrius Advisor Group Team

        If you no longer wish to receive communications from us, please reply with "UNSUBSCRIBE" in the subject line.
        """
        
        return await self._send_email(
            to_email=client_email,
            subject=subject,
            html_content=html_content,
            text_content=text_content
        )
    
    def _create_assignment_email_html(self, agent_name: str, client_info: Dict, call_summary: Dict) -> str:
        """Create HTML content for agent assignment email"""
        
        meeting_time = call_summary.get('meeting_time', 'Not scheduled')
        
        return f"""
        <html>
        <body>
            <h2>New Lead Assignment</h2>
            
            <p>Hello {agent_name},</p>
            
            <p>A new interested client has been assigned to you from our voice campaign:</p>
            
            <div style="background-color: #f5f5f5; padding: 15px; margin: 10px 0; border-radius: 5px;">
                <h3>Client Information:</h3>
                <p><strong>Name:</strong> {client_info.get('name', 'N/A')}</p>
                <p><strong>Phone:</strong> {client_info.get('phone', 'N/A')}</p>
                <p><strong>Email:</strong> {client_info.get('email', 'N/A')}</p>
                <p><strong>Assigned:</strong> {datetime.utcnow().strftime('%Y-%m-%d %H:%M:%S')} UTC</p>
            </div>
            
            <div style="background-color: #e8f4fd; padding: 15px; margin: 10px 0; border-radius: 5px;">
                <h3>Call Summary:</h3>
                <p><strong>Outcome:</strong> {call_summary.get('outcome', 'Interested')}</p>
                <p><strong>Call Duration:</strong> {call_summary.get('duration', 'N/A')}</p>
                <p><strong>Key Points:</strong></p>
                <ul>
                    {''.join([f'<li>{point}</li>' for point in call_summary.get('key_points', ['Client expressed interest in insurance options'])])}
                </ul>
                <p><strong>Next Actions:</strong></p>
                <ul>
                    {''.join([f'<li>{action}</li>' for action in call_summary.get('next_actions', ['Schedule discovery call', 'Discuss insurance options'])])}
                </ul>
            </div>
            
            <div style="background-color: #fff3cd; padding: 15px; margin: 10px 0; border-radius: 5px;">
                <h3>Meeting Details:</h3>
                <p><strong>Scheduled Time:</strong> {meeting_time}</p>
                <p><strong>Calendar Event:</strong> A calendar invite has been sent to your email</p>
            </div>
            
            <p>Please review the client information and prepare for your discovery call. The client has already expressed interest, so focus on understanding their specific needs and presenting appropriate options.</p>
            
            <p>Best regards,<br>
            Voice Agent Campaign System</p>
        </body>
        </html>
        """
    
    def _create_assignment_email_text(self, agent_name: str, client_info: Dict, call_summary: Dict) -> str:
        """Create text content for agent assignment email"""
        
        return f"""
        New Lead Assignment

        Hello {agent_name},

        A new interested client has been assigned to you from our voice campaign:

        CLIENT INFORMATION:
        - Name: {client_info.get('name', 'N/A')}
        - Phone: {client_info.get('phone', 'N/A')}
        - Email: {client_info.get('email', 'N/A')}
        - Assigned: {datetime.utcnow().strftime('%Y-%m-%d %H:%M:%S')} UTC

        CALL SUMMARY:
        - Outcome: {call_summary.get('outcome', 'Interested')}
        - Duration: {call_summary.get('duration', 'N/A')}
        - Key Points: {', '.join(call_summary.get('key_points', ['Client expressed interest']))}
        - Next Actions: {', '.join(call_summary.get('next_actions', ['Schedule discovery call']))}

        MEETING DETAILS:
        - Scheduled Time: {call_summary.get('meeting_time', 'Not scheduled')}
        - Calendar Event: A calendar invite has been sent to your email

        Please review the client information and prepare for your discovery call.

        Best regards,
        Voice Agent Campaign System
        """
    
    def _create_confirmation_email_html(self, client_name: str, agent_name: str, meeting_details: Dict) -> str:
        """Create HTML content for meeting confirmation email"""
        
        meeting_time = meeting_details.get('meeting_time', 'TBD')
        meet_link = meeting_details.get('meet_link', '')
        
        return f"""
        <html>
        <body>
            <h2>Discovery Call Confirmed</h2>
            
            <p>Hello {client_name},</p>
            
            <p>Thank you for your interest in our insurance services! Your discovery call has been scheduled with one of our specialists.</p>
            
            <div style="background-color: #e8f4fd; padding: 15px; margin: 10px 0; border-radius: 5px;">
                <h3>Meeting Details:</h3>
                <p><strong>Date & Time:</strong> {meeting_time}</p>
                <p><strong>With:</strong> {agent_name}</p>
                <p><strong>Duration:</strong> 15-30 minutes</p>
                {f'<p><strong>Join Link:</strong> <a href="{meet_link}">Click here to join</a></p>' if meet_link else ''}
            </div>
            
            <div style="background-color: #f5f5f5; padding: 15px; margin: 10px 0; border-radius: 5px;">
                <h3>What to Expect:</h3>
                <ul>
                    <li>Review of your current insurance needs</li>
                    <li>Discussion of available options</li>
                    <li>Personalized recommendations</li>
                    <li>Q&A session for any concerns</li>
                </ul>
            </div>
            
            <p>If you need to reschedule or have any questions, please call us at <strong>{getattr(settings, 'twilio_phone_number', '(555) 123-4567')}</strong></p>
            
            <p>We look forward to helping you find the perfect insurance solution!</p>
            
            <p>Best regards,<br>
            {agent_name}<br>
            Altrius Advisor Group</p>
        </body>
        </html>
        """
    
    def _create_confirmation_email_text(self, client_name: str, agent_name: str, meeting_details: Dict) -> str:
        """Create text content for meeting confirmation email"""
        
        return f"""
        Discovery Call Confirmed

        Hello {client_name},

        Thank you for your interest in our insurance services! Your discovery call has been scheduled with one of our specialists.

        MEETING DETAILS:
        - Date & Time: {meeting_details.get('meeting_time', 'TBD')}
        - With: {agent_name}
        - Duration: 15-30 minutes
        {f"- Join Link: {meeting_details.get('meet_link', '')}" if meeting_details.get('meet_link') else ''}

        WHAT TO EXPECT:
        - Review of your current insurance needs
        - Discussion of available options
        - Personalized recommendations
        - Q&A session for any concerns

        If you need to reschedule or have any questions, please call us at {getattr(settings, 'twilio_phone_number', '(555) 123-4567')}.

        We look forward to helping you find the perfect insurance solution!

        Best regards,
        {agent_name}
        Altrius Advisor Group
        """
    
    async def _send_email(self, to_email: str, subject: str, html_content: str, text_content: str) -> bool:
        """Send email via SES or mock"""
        
        if not self.ses_client:
            # Mock email sending for development
            logger.info(f"📧 Mock email sent to {to_email}")
            logger.info(f"   Subject: {subject}")
            self.emails_sent += 1
            return True
        
        try:
            response = self.ses_client.send_email(
                Source=self.from_email,
                Destination={'ToAddresses': [to_email]},
                Message={
                    'Subject': {'Data': subject, 'Charset': 'UTF-8'},
                    'Body': {
                        'Html': {'Data': html_content, 'Charset': 'UTF-8'},
                        'Text': {'Data': text_content, 'Charset': 'UTF-8'}
                    }
                }
            )
            
            self.emails_sent += 1
            logger.info(f"✅ Email sent to {to_email}: {response['MessageId']}")
            return True
            
        except ClientError as e:
            logger.error(f"❌ SES error sending email to {to_email}: {e}")
            self.emails_failed += 1
            return False
        except Exception as e:
            logger.error(f"❌ Error sending email to {to_email}: {e}")
            self.emails_failed += 1
            return False
    
    def get_statistics(self) -> Dict[str, Any]:
        """Get email service statistics"""
        total_attempts = self.emails_sent + self.emails_failed
        success_rate = (self.emails_sent / total_attempts * 100) if total_attempts > 0 else 0
        
        return {
            "emails_sent": self.emails_sent,
            "emails_failed": self.emails_failed,
            "total_attempts": total_attempts,
            "success_rate": success_rate,
            "ses_configured": self.ses_client is not None
        }
    
    async def close(self):
        """Close email service"""
        if self.ses_client:
            # SES client doesn't need explicit closing
            logger.info("✅ Email service closed")
        else:
            logger.info("✅ Mock email service closed")