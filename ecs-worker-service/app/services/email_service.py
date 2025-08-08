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

    def is_configured(self) -> bool:
        """Check if email service is properly configured"""
        return self.ses_client is not None

    async def send_conversation_stage_email(self, client_email: str, client_name: str, stage: str, call_summary: Dict[str, Any]) -> bool:
        """Send email based on conversation stage"""
        try:
            email_templates = {
                "interested": {
                    "subject": "Thank you for your interest in our services!",
                    "body": f"""
Dear {client_name},

Thank you for your interest in our services! We're excited to work with you.

Based on our conversation, here are the key points we discussed:
{self._format_key_points(call_summary.get('key_points', []))}

Next Steps:
- Our team will review your requirements
- We'll schedule a follow-up call within 24-48 hours
- You'll receive calendar invites for available time slots

If you have any immediate questions, please don't hesitate to reach out.

Best regards,
The Altruis Team
                    """.strip()
                },
                "not_interested": {
                    "subject": "Thank you for your time",
                    "body": f"""
Dear {client_name},

Thank you for taking the time to speak with us today. We appreciate your consideration.

We understand that our services may not be the right fit for you at this time. If your circumstances change in the future, we'd be happy to hear from you.

We've noted your preferences and will respect your decision.

Best regards,
The Altruis Team
                    """.strip()
                },
                "follow_up": {
                    "subject": "Follow-up on our conversation",
                    "body": f"""
Dear {client_name},

Thank you for our recent conversation. We wanted to follow up on the points we discussed.

Key Discussion Points:
{self._format_key_points(call_summary.get('key_points', []))}

Customer Concerns Addressed:
{self._format_concerns(call_summary.get('customer_concerns', []))}

We're here to help address any questions you may have. Please feel free to reach out if you'd like to discuss further.

Best regards,
The Altruis Team
                    """.strip()
                },
                "meeting_scheduled": {
                    "subject": "Meeting Confirmation - Discovery Call",
                    "body": f"""
Dear {client_name},

Your discovery call has been scheduled successfully!

Meeting Details:
- Date: {call_summary.get('meeting_time', 'TBD')}
- Duration: 30 minutes
- Format: Video call (link will be sent separately)

What to expect:
- Detailed discussion of your needs
- Custom solution recommendations
- Q&A session
- Next steps planning

Please let us know if you need to reschedule or have any questions.

Best regards,
The Altruis Team
                    """.strip()
                }
            }

            template = email_templates.get(stage)
            if not template:
                logger.warning(f"Unknown conversation stage: {stage}")
                return False

            success = await self._send_email(
                to_email=client_email,
                subject=template["subject"],
                body=template["body"]
            )

            if success:
                logger.info(f"✅ {stage} email sent to {client_email}")
                self.emails_sent += 1
            else:
                logger.error(f"❌ Failed to send {stage} email to {client_email}")
                self.emails_failed += 1

            return success

        except Exception as e:
            logger.error(f"❌ Error sending conversation stage email: {e}")
            self.emails_failed += 1
            return False

    async def send_agent_assignment_email(self, agent_email: str, agent_name: str, client_info: Dict[str, Any], call_summary: Dict[str, Any]) -> bool:
        """Send email notification to agent about new assignment"""
        try:
            subject = f"New Client Assignment - {client_info.get('client_name', 'Unknown Client')}"
            
            body = f"""
Dear {agent_name},

You have been assigned a new client based on their recent conversation with our AI system.

Client Information:
- Name: {client_info.get('client_name', 'N/A')}
- Phone: {client_info.get('phone', 'N/A')}
- Email: {client_info.get('email', 'N/A')}

Call Summary:
- Outcome: {call_summary.get('outcome', 'N/A')}
- Sentiment: {call_summary.get('sentiment', 'N/A')}
- Key Points: {', '.join(call_summary.get('key_points', [])[:3])}

Customer Concerns:
{self._format_concerns(call_summary.get('customer_concerns', []))}

Recommended Actions:
{self._format_actions(call_summary.get('recommended_actions', []))}

Please review the client's information and prepare for the follow-up call.

Best regards,
The Altruis Team
            """.strip()

            success = await self._send_email(
                to_email=agent_email,
                subject=subject,
                body=body
            )

            if success:
                logger.info(f"✅ Agent assignment email sent to {agent_email}")
                self.emails_sent += 1
            else:
                logger.error(f"❌ Failed to send agent assignment email to {agent_email}")
                self.emails_failed += 1

            return success

        except Exception as e:
            logger.error(f"❌ Error sending agent assignment email: {e}")
            self.emails_failed += 1
            return False

    async def send_meeting_confirmation_email(self, client_email: str, client_name: str, agent_name: str, meeting_details: Dict[str, Any]) -> bool:
        """Send meeting confirmation email to client and agent"""
        try:
            subject = f"Meeting Confirmation - {meeting_details.get('meeting_time', 'Discovery Call')}"
            
            body = f"""
Dear {client_name},

Your discovery call has been confirmed!

Meeting Details:
- Date: {meeting_details.get('meeting_time', 'TBD')}
- Duration: 30 minutes
- Agent: {agent_name}
- Format: Video call

Calendar Link: {meeting_details.get('calendar_link', 'Will be sent separately')}

What to expect:
- Detailed discussion of your needs and requirements
- Custom solution recommendations
- Q&A session
- Next steps planning

Please let us know if you need to reschedule or have any questions.

Best regards,
{agent_name}
The Altruis Team
            """.strip()

            success = await self._send_email(
                to_email=client_email,
                subject=subject,
                body=body
            )

            if success:
                logger.info(f"✅ Meeting confirmation email sent to {client_email}")
                self.emails_sent += 1
            else:
                logger.error(f"❌ Failed to send meeting confirmation email to {client_email}")
                self.emails_failed += 1

            return success

        except Exception as e:
            logger.error(f"❌ Error sending meeting confirmation email: {e}")
            self.emails_failed += 1
            return False

    async def _send_email(self, to_email: str, subject: str, body: str) -> bool:
        """Send email via SES or log in mock mode"""
        if not self.is_configured():
            # Mock mode - just log the email
            logger.info(f"📧 MOCK EMAIL - To: {to_email}")
            logger.info(f"📧 MOCK EMAIL - Subject: {subject}")
            logger.info(f"📧 MOCK EMAIL - Body: {body[:200]}...")
            return True

        try:
            response = self.ses_client.send_email(
                Source=self.from_email,
                Destination={'ToAddresses': [to_email]},
                Message={
                    'Subject': {'Data': subject, 'Charset': 'UTF-8'},
                    'Body': {'Text': {'Data': body, 'Charset': 'UTF-8'}}
                }
            )
            logger.info(f"✅ Email sent successfully: {response['MessageId']}")
            return True

        except ClientError as e:
            logger.error(f"❌ SES error: {e.response['Error']['Message']}")
            return False
        except Exception as e:
            logger.error(f"❌ Email sending error: {e}")
            return False

    def _format_key_points(self, points: List[str]) -> str:
        """Format key points for email"""
        if not points:
            return "- No specific points discussed"
        return "\n".join([f"- {point}" for point in points[:5]])  # Limit to 5 points

    def _format_concerns(self, concerns: List[str]) -> str:
        """Format customer concerns for email"""
        if not concerns:
            return "- No specific concerns raised"
        return "\n".join([f"- {concern}" for concern in concerns[:3]])  # Limit to 3 concerns

    def _format_actions(self, actions: List[str]) -> str:
        """Format recommended actions for email"""
        if not actions:
            return "- No specific actions recommended"
        return "\n".join([f"- {action}" for action in actions[:3]])  # Limit to 3 actions

    def get_stats(self) -> Dict[str, Any]:
        """Get email service statistics"""
        return {
            "emails_sent": self.emails_sent,
            "emails_failed": self.emails_failed,
            "success_rate": self.emails_sent / (self.emails_sent + self.emails_failed) * 100 if (self.emails_sent + self.emails_failed) > 0 else 0,
            "configured": self.is_configured()
        }