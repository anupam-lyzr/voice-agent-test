"""
Email Service for SES Integration - Production Ready
Handles email notifications for agent assignments and meeting confirmations
"""

import asyncio
import logging
from typing import Dict, Any, Optional, List
from datetime import datetime, timedelta

# For local development without AWS SES
try:
    import boto3
    from botocore.exceptions import ClientError, NoCredentialsError
    AWS_SES_AVAILABLE = True
except ImportError:
    AWS_SES_AVAILABLE = False

# SMTP support
try:
    import smtplib
    from email.mime.text import MIMEText
    from email.mime.multipart import MIMEMultipart
    SMTP_AVAILABLE = True
except ImportError:
    SMTP_AVAILABLE = False

from shared.config.settings import settings

logger = logging.getLogger(__name__)

class EmailService:
    """Service for sending emails via AWS SES - Production Ready"""
    
    def __init__(self):
        self.ses_client = None
        self.smtp_config = None
        
        # Check for SMTP configuration first (preferred method)
        smtp_host = getattr(settings, 'smtp_host', None)
        smtp_username = getattr(settings, 'smtp_username', None)
        smtp_password = getattr(settings, 'smtp_password', None)
        
        if all([smtp_host, smtp_username, smtp_password]) and SMTP_AVAILABLE:
            # Use SMTP method
            self.smtp_config = {
                'host': smtp_host,
                'port': getattr(settings, 'smtp_port', 587),
                'username': smtp_username,
                'password': smtp_password,
                'sender_email': getattr(settings, 'smtp_sender_email', 'aag@ca.lyzr.app'),
                'reply_to': getattr(settings, 'smtp_reply_to_email', 'aag@ca.lyzr.app')
            }
            
            # Set the from_email to use SMTP sender email
            self.from_email = self.smtp_config['sender_email']
            logger.info(f"✅ SMTP client configured: {smtp_host}:{self.smtp_config['port']}")
            logger.info(f"✅ Using SMTP sender email: {self.from_email}")
        elif AWS_SES_AVAILABLE:
            # Fallback to AWS SDK method
            try:
                region_name = getattr(settings, 'aws_region', 'us-east-1')
                
                # Use real AWS SES with session token support
                ses_kwargs = {
                    'service_name': 'ses',
                    'region_name': region_name
                }
                
                # Add session token if available (required for temporary credentials)
                aws_session_token = getattr(settings, 'aws_session_token', None)
                if aws_session_token:
                    ses_kwargs['aws_session_token'] = aws_session_token
                    logger.info("✅ Using AWS session token (temporary credentials)")
                
                self.ses_client = boto3.client(**ses_kwargs)
                logger.info("✅ SES client initialized with AWS SDK")
                
                # Set from_email for SES
                self.from_email = getattr(settings, 'from_email', 'aag@ca.lyzr.app')
                
            except (NoCredentialsError, Exception) as e:
                logger.warning(f"⚠️ SES not available: {e}")
                self.ses_client = None
        else:
            logger.info("🔧 Running in mock mode - emails will be logged only")
            # Set from_email for mock mode
            self.from_email = getattr(settings, 'from_email', 'aag@ca.lyzr.app')
        
        # Email statistics
        self.emails_sent = 0
        self.emails_failed = 0

    def is_configured(self) -> bool:
        """Check if email service is properly configured"""
        return self.ses_client is not None or self.smtp_config is not None

    async def send_conversation_stage_email(self, client_email: str, client_name: str, stage: str, call_summary: Dict[str, Any]) -> bool:
        """Send email based on conversation stage with proper timing"""
        try:
            # Determine email template based on stage
            email_templates = {
                "interested": {
                    "subject": "Thank you for your interest in our services! 🎉",
                    "html": self._get_interested_email_html(client_name, call_summary),
                    "text": self._get_interested_email_text(client_name, call_summary)
                },
                "not_interested": {
                    "subject": "Thank you for your time 🙏",
                    "html": self._get_not_interested_email_html(client_name, call_summary),
                    "text": self._get_not_interested_email_text(client_name, call_summary)
                },
                "follow_up": {
                    "subject": "Follow-up on our conversation 📞",
                    "html": self._get_follow_up_email_html(client_name, call_summary),
                    "text": self._get_follow_up_email_text(client_name, call_summary)
                },
                "meeting_scheduled": {
                    "subject": "Meeting Confirmation - Discovery Call 📅",
                    "html": self._get_meeting_scheduled_email_html(client_name, call_summary),
                    "text": self._get_meeting_scheduled_email_text(client_name, call_summary)
                },
                "agent_assignment": {
                    "subject": "New Client Assignment - Action Required 👨‍💼",
                    "html": self._get_agent_assignment_email_html(client_name, call_summary),
                    "text": self._get_agent_assignment_email_text(client_name, call_summary)
                }
            }

            template = email_templates.get(stage)
            if not template:
                logger.warning(f"Unknown conversation stage: {stage}")
                return False

            success = await self._send_email(
                to_email=client_email,
                subject=template["subject"],
                html_body=template["html"],
                text_body=template["text"]
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
            subject = f"New Client Assignment - {client_info.get('client_name', 'Unknown Client')} 👨‍💼"
            
            html_body = self._get_agent_assignment_email_html(agent_name, client_info, call_summary)
            text_body = self._get_agent_assignment_email_text(agent_name, client_info, call_summary)

            success = await self._send_email(
                to_email=agent_email,
                subject=subject,
                html_body=html_body,
                text_body=text_body
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
            subject = f"Meeting Confirmation - {meeting_details.get('meeting_time', 'Discovery Call')} 📅"
            
            html_body = self._get_meeting_confirmation_email_html(client_name, agent_name, meeting_details)
            text_body = self._get_meeting_confirmation_email_text(client_name, agent_name, meeting_details)

            success = await self._send_email(
                to_email=client_email,
                subject=subject,
                html_body=html_body,
                text_body=text_body
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

    async def _send_email(self, to_email: str, subject: str, html_body: str, text_body: str) -> bool:
        """Send email via SMTP (preferred) or SES with HTML and text versions"""
        if not self.is_configured():
            # Mock mode - just log the email
            logger.info(f"📧 MOCK EMAIL - To: {to_email}")
            logger.info(f"📧 MOCK EMAIL - Subject: {subject}")
            logger.info(f"📧 MOCK EMAIL - HTML Body: {html_body[:200]}...")
            return True

        # Try SMTP first (preferred method)
        if self.smtp_config:
            return await self._send_email_smtp(to_email, subject, html_body, text_body)
        
        # Fallback to SES SDK
        elif self.ses_client:
            return await self._send_email_ses(to_email, subject, html_body, text_body)
        
        return False

    async def _send_email_smtp(self, to_email: str, subject: str, html_body: str, text_body: str) -> bool:
        """Send email via SMTP"""
        try:
            # Create message
            msg = MIMEMultipart('alternative')
            msg['Subject'] = subject
            msg['From'] = self.smtp_config['sender_email']
            msg['To'] = to_email
            msg['Reply-To'] = self.smtp_config['reply_to']
            
            # Attach text and HTML parts
            text_part = MIMEText(text_body, 'plain', 'utf-8')
            html_part = MIMEText(html_body, 'html', 'utf-8')
            
            msg.attach(text_part)
            msg.attach(html_part)
            
            # Send via SMTP
            with smtplib.SMTP(self.smtp_config['host'], self.smtp_config['port']) as server:
                server.starttls()  # Enable TLS
                server.login(self.smtp_config['username'], self.smtp_config['password'])
                server.send_message(msg)
            
            logger.info(f"✅ Email sent via SMTP to {to_email}")
            return True
            
        except Exception as e:
            logger.error(f"❌ SMTP error: {e}")
            return False

    async def _send_email_ses(self, to_email: str, subject: str, html_body: str, text_body: str) -> bool:
        """Send email via SES SDK"""
        try:
            response = self.ses_client.send_email(
                Source=self.from_email,
                Destination={'ToAddresses': [to_email]},
                Message={
                    'Subject': {'Data': subject, 'Charset': 'UTF-8'},
                    'Body': {
                        'Html': {'Data': html_body, 'Charset': 'UTF-8'},
                        'Text': {'Data': text_body, 'Charset': 'UTF-8'}
                    }
                }
            )
            logger.info(f"✅ Email sent via SES: {response['MessageId']}")
            return True

        except ClientError as e:
            logger.error(f"❌ SES error: {e.response['Error']['Message']}")
            return False
        except Exception as e:
            logger.error(f"❌ Email sending error: {e}")
            return False

    def _get_email_header(self, title: str) -> str:
        """Get email header HTML"""
        return f"""
        <!DOCTYPE html>
        <html>
        <head>
            <meta charset="UTF-8">
            <meta name="viewport" content="width=device-width, initial-scale=1.0">
            <title>{title}</title>
            <style>
                body {{ font-family: 'Segoe UI', Tahoma, Geneva, Verdana, sans-serif; line-height: 1.6; color: #333; margin: 0; padding: 0; }}
                .container {{ max-width: 600px; margin: 0 auto; background-color: #ffffff; }}
                .header {{ background: linear-gradient(135deg, #667eea 0%, #764ba2 100%); color: white; padding: 30px; text-align: center; }}
                .header h1 {{ margin: 0; font-size: 28px; font-weight: 300; }}
                .content {{ padding: 40px 30px; }}
                .footer {{ background-color: #f8f9fa; padding: 20px; text-align: center; color: #666; font-size: 14px; }}
                .button {{ display: inline-block; background: linear-gradient(135deg, #667eea 0%, #764ba2 100%); color: white; padding: 12px 30px; text-decoration: none; border-radius: 25px; margin: 20px 0; }}
                .highlight {{ background-color: #f8f9fa; padding: 20px; border-left: 4px solid #667eea; margin: 20px 0; }}
                .meeting-details {{ background-color: #e8f4fd; padding: 20px; border-radius: 8px; margin: 20px 0; }}
                .key-points {{ background-color: #f0f8ff; padding: 15px; border-radius: 5px; margin: 15px 0; }}
                .emoji {{ font-size: 20px; }}
            </style>
        </head>
        <body>
            <div class="container">
        """

    def _get_email_footer(self) -> str:
        """Get email footer HTML"""
        return f"""
            </div>
        </body>
        </html>
        """

    def _get_interested_email_html(self, client_name: str, call_summary: Dict[str, Any]) -> str:
        """Get HTML for interested customer email"""
        key_points = self._format_key_points_html(call_summary.get('key_points', []))
        
        return f"""
        {self._get_email_header("Thank you for your interest!")}
        <div class="header">
            <h1>🎉 Thank you for your interest!</h1>
        </div>
        <div class="content">
            <h2>Dear {client_name},</h2>
            
            <p>We're thrilled that you're interested in our services! Your recent conversation with our AI assistant has shown great potential for collaboration.</p>
            
            <div class="highlight">
                <h3>📋 Key Points from Our Conversation:</h3>
                {key_points}
            </div>
            
            <h3>🚀 What Happens Next:</h3>
            <ul>
                <li><strong>24-48 hours:</strong> Our team will review your requirements and prepare a customized proposal</li>
                <li><strong>Calendar Invite:</strong> You'll receive available time slots for a detailed discovery call</li>
                <li><strong>Personalized Solution:</strong> We'll create a tailored approach based on your specific needs</li>
            </ul>
            
            <p>We're committed to providing you with the best possible service and look forward to working together!</p>
            
            <p style="text-align: center;">
                <a href="mailto:contact@altruisadvisor.com" class="button">📧 Contact Us</a>
            </p>
        </div>
        {self._get_email_footer()}
        """

    def _get_not_interested_email_html(self, client_name: str, call_summary: Dict[str, Any]) -> str:
        """Get HTML for not interested customer email"""
        return f"""
        {self._get_email_header("Thank you for your time")}
        <div class="header">
            <h1>🙏 Thank you for your time</h1>
        </div>
        <div class="content">
            <h2>Dear {client_name},</h2>
            
            <p>Thank you for taking the time to speak with us today. We truly appreciate your consideration of our services.</p>
            
            <p>We understand that our services may not be the right fit for you at this time, and we respect your decision completely.</p>
            
            <div class="highlight">
                <p><strong>💡 Remember:</strong> If your circumstances change in the future, we'd be happy to hear from you. Our team is always here to help when you're ready.</p>
            </div>
            
            <p>We've noted your preferences and will ensure that we respect your decision going forward.</p>
            
            <p>Wishing you all the best in your endeavors!</p>
        </div>
        {self._get_email_footer()}
        """

    def _get_follow_up_email_html(self, client_name: str, call_summary: Dict[str, Any]) -> str:
        """Get HTML for follow-up email"""
        key_points = self._format_key_points_html(call_summary.get('key_points', []))
        concerns = self._format_concerns_html(call_summary.get('customer_concerns', []))
        
        return f"""
        {self._get_email_header("Follow-up on our conversation")}
        <div class="header">
            <h1>📞 Follow-up on our conversation</h1>
        </div>
        <div class="content">
            <h2>Dear {client_name},</h2>
            
            <p>Thank you for our recent conversation. We wanted to follow up on the points we discussed and ensure we addressed all your questions.</p>
            
            <div class="key-points">
                <h3>💬 Key Discussion Points:</h3>
                {key_points}
            </div>
            
            <div class="highlight">
                <h3>🤔 Customer Concerns Addressed:</h3>
                {concerns}
            </div>
            
            <p>We're here to help address any additional questions you may have. Please feel free to reach out if you'd like to discuss anything further.</p>
            
            <p style="text-align: center;">
                <a href="mailto:contact@altruisadvisor.com" class="button">📧 Get in Touch</a>
            </p>
        </div>
        {self._get_email_footer()}
        """

    def _get_meeting_scheduled_email_html(self, client_name: str, call_summary: Dict[str, Any]) -> str:
        """Get HTML for meeting scheduled email"""
        meeting_time = call_summary.get('meeting_time', 'TBD')
        agent_name = call_summary.get('agent_name', 'Our Team')
        
        return f"""
        {self._get_email_header("Meeting Confirmation")}
        <div class="header">
            <h1>📅 Meeting Confirmation</h1>
        </div>
        <div class="content">
            <h2>Dear {client_name},</h2>
            
            <p>Your discovery call has been scheduled successfully! We're excited to meet with you.</p>
            
            <div class="meeting-details">
                <h3>📋 Meeting Details:</h3>
                <ul>
                    <li><strong>Date & Time:</strong> {meeting_time}</li>
                    <li><strong>Duration:</strong> 30 minutes</li>
                    <li><strong>Format:</strong> Video call (link will be sent separately)</li>
                    <li><strong>Agent:</strong> {agent_name}</li>
                </ul>
            </div>
            
            <h3>🎯 What to expect:</h3>
            <ul>
                <li>Detailed discussion of your needs and requirements</li>
                <li>Custom solution recommendations</li>
                <li>Q&A session</li>
                <li>Next steps planning</li>
            </ul>
            
            <div class="highlight">
                <p><strong>💡 Need to reschedule?</strong> Please let us know at least 24 hours in advance, and we'll be happy to accommodate you.</p>
            </div>
            
            <p>We look forward to our conversation!</p>
        </div>
        {self._get_email_footer()}
        """

    def _get_agent_assignment_email_html(self, agent_name: str, client_info: Dict[str, Any], call_summary: Dict[str, Any]) -> str:
        """Get HTML for agent assignment email"""
        client_name = client_info.get('client_name', 'Unknown Client')
        key_points = self._format_key_points_html(call_summary.get('key_points', []))
        concerns = self._format_concerns_html(call_summary.get('customer_concerns', []))
        actions = self._format_actions_html(call_summary.get('recommended_actions', []))
        
        return f"""
        {self._get_email_header("New Client Assignment")}
        <div class="header">
            <h1>👨‍💼 New Client Assignment</h1>
        </div>
        <div class="content">
            <h2>Dear {agent_name},</h2>
            
            <p>You have been assigned a new client based on their recent conversation with our AI system.</p>
            
            <div class="meeting-details">
                <h3>👤 Client Information:</h3>
                <ul>
                    <li><strong>Name:</strong> {client_name}</li>
                    <li><strong>Phone:</strong> {client_info.get('phone', 'N/A')}</li>
                    <li><strong>Email:</strong> {client_info.get('email', 'N/A')}</li>
                </ul>
            </div>
            
            <div class="key-points">
                <h3>📋 Call Summary:</h3>
                <ul>
                    <li><strong>Outcome:</strong> {call_summary.get('outcome', 'N/A')}</li>
                    <li><strong>Sentiment:</strong> {call_summary.get('sentiment', 'N/A')}</li>
                </ul>
            </div>
            
            <div class="highlight">
                <h3>💬 Key Discussion Points:</h3>
                {key_points}
            </div>
            
            <div class="key-points">
                <h3>🤔 Customer Concerns:</h3>
                {concerns}
            </div>
            
            <div class="highlight">
                <h3>✅ Recommended Actions:</h3>
                {actions}
            </div>
            
            <p>Please review the client's information and prepare for the follow-up call.</p>
        </div>
        {self._get_email_footer()}
        """

    def _get_meeting_confirmation_email_html(self, client_name: str, agent_name: str, meeting_details: Dict[str, Any]) -> str:
        """Get HTML for meeting confirmation email"""
        meeting_time = meeting_details.get('meeting_time', 'TBD')
        calendar_link = meeting_details.get('calendar_link', 'Will be sent separately')
        
        return f"""
        {self._get_email_header("Meeting Confirmation")}
        <div class="header">
            <h1>📅 Meeting Confirmation</h1>
        </div>
        <div class="content">
            <h2>Dear {client_name},</h2>
            
            <p>Your discovery call has been confirmed!</p>
            
            <div class="meeting-details">
                <h3>📋 Meeting Details:</h3>
                <ul>
                    <li><strong>Date & Time:</strong> {meeting_time}</li>
                    <li><strong>Duration:</strong> 30 minutes</li>
                    <li><strong>Agent:</strong> {agent_name}</li>
                    <li><strong>Format:</strong> Video call</li>
                </ul>
            </div>
            
            <div class="highlight">
                <p><strong>📅 Calendar Link:</strong> {calendar_link}</p>
            </div>
            
            <h3>🎯 What to expect:</h3>
            <ul>
                <li>Detailed discussion of your needs and requirements</li>
                <li>Custom solution recommendations</li>
                <li>Q&A session</li>
                <li>Next steps planning</li>
            </ul>
            
            <p>Please let us know if you need to reschedule or have any questions.</p>
            
            <p>Best regards,<br>{agent_name}<br>The Altruis Team</p>
        </div>
        {self._get_email_footer()}
        """

    # Text versions for email clients that don't support HTML
    def _get_interested_email_text(self, client_name: str, call_summary: Dict[str, Any]) -> str:
        """Get text version for interested customer email"""
        key_points = self._format_key_points_text(call_summary.get('key_points', []))
        return f"""
Dear {client_name},

Thank you for your interest in our services! We're excited that you're interested in working with us.

Based on our conversation, here are the key points we discussed:
{key_points}

What happens next:
- Our team will review your requirements within 24-48 hours
- You'll receive calendar invites for available time slots
- We'll create a personalized solution based on your needs

If you have any immediate questions, please don't hesitate to reach out.

Best regards,
The Altruis Team
        """.strip()

    def _get_not_interested_email_text(self, client_name: str, call_summary: Dict[str, Any]) -> str:
        """Get text version for not interested customer email"""
        return f"""
Dear {client_name},

Thank you for taking the time to speak with us today. We appreciate your consideration.

We understand that our services may not be the right fit for you at this time. If your circumstances change in the future, we'd be happy to hear from you.

We've noted your preferences and will respect your decision.

Best regards,
The Altruis Team
        """.strip()

    def _get_follow_up_email_text(self, client_name: str, call_summary: Dict[str, Any]) -> str:
        """Get text version for follow-up email"""
        key_points = self._format_key_points_text(call_summary.get('key_points', []))
        concerns = self._format_concerns_text(call_summary.get('customer_concerns', []))
        return f"""
Dear {client_name},

Thank you for our recent conversation. We wanted to follow up on the points we discussed.

Key Discussion Points:
{key_points}

Customer Concerns Addressed:
{concerns}

We're here to help address any questions you may have. Please feel free to reach out if you'd like to discuss further.

Best regards,
The Altruis Team
        """.strip()

    def _get_meeting_scheduled_email_text(self, client_name: str, call_summary: Dict[str, Any]) -> str:
        """Get text version for meeting scheduled email"""
        meeting_time = call_summary.get('meeting_time', 'TBD')
        return f"""
Dear {client_name},

Your discovery call has been scheduled successfully!

Meeting Details:
- Date: {meeting_time}
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

    def _get_agent_assignment_email_text(self, agent_name: str, client_info: Dict[str, Any], call_summary: Dict[str, Any]) -> str:
        """Get text version for agent assignment email"""
        client_name = client_info.get('client_name', 'Unknown Client')
        key_points = self._format_key_points_text(call_summary.get('key_points', []))
        concerns = self._format_concerns_text(call_summary.get('customer_concerns', []))
        actions = self._format_actions_text(call_summary.get('recommended_actions', []))
        return f"""
Dear {agent_name},

You have been assigned a new client based on their recent conversation with our AI system.

Client Information:
- Name: {client_name}
- Phone: {client_info.get('phone', 'N/A')}
- Email: {client_info.get('email', 'N/A')}

Call Summary:
- Outcome: {call_summary.get('outcome', 'N/A')}
- Sentiment: {call_summary.get('sentiment', 'N/A')}

Key Points: {key_points}

Customer Concerns: {concerns}

Recommended Actions: {actions}

Please review the client's information and prepare for the follow-up call.

Best regards,
The Altruis Team
        """.strip()

    def _get_meeting_confirmation_email_text(self, client_name: str, agent_name: str, meeting_details: Dict[str, Any]) -> str:
        """Get text version for meeting confirmation email"""
        meeting_time = meeting_details.get('meeting_time', 'TBD')
        calendar_link = meeting_details.get('calendar_link', 'Will be sent separately')
        return f"""
Dear {client_name},

Your discovery call has been confirmed!

Meeting Details:
- Date: {meeting_time}
- Duration: 30 minutes
- Agent: {agent_name}
- Format: Video call

Calendar Link: {calendar_link}

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

    # Helper methods for formatting
    def _format_key_points_html(self, points: List[str]) -> str:
        """Format key points for HTML email"""
        if not points:
            return "<p>No specific points discussed</p>"
        return "".join([f"<li>{point}</li>" for point in points[:5]])

    def _format_concerns_html(self, concerns: List[str]) -> str:
        """Format customer concerns for HTML email"""
        if not concerns:
            return "<p>No specific concerns raised</p>"
        return "".join([f"<li>{concern}</li>" for concern in concerns[:3]])

    def _format_actions_html(self, actions: List[str]) -> str:
        """Format recommended actions for HTML email"""
        if not actions:
            return "<p>No specific actions recommended</p>"
        return "".join([f"<li>{action}</li>" for action in actions[:3]])

    def _format_key_points_text(self, points: List[str]) -> str:
        """Format key points for text email"""
        if not points:
            return "- No specific points discussed"
        return "\n".join([f"- {point}" for point in points[:5]])

    def _format_concerns_text(self, concerns: List[str]) -> str:
        """Format customer concerns for text email"""
        if not concerns:
            return "- No specific concerns raised"
        return "\n".join([f"- {concern}" for concern in concerns[:3]])

    def _format_actions_text(self, actions: List[str]) -> str:
        """Format recommended actions for text email"""
        if not actions:
            return "- No specific actions recommended"
        return "\n".join([f"- {action}" for action in actions[:3]])

    def get_stats(self) -> Dict[str, Any]:
        """Get email service statistics"""
        return {
            "emails_sent": self.emails_sent,
            "emails_failed": self.emails_failed,
            "success_rate": self.emails_sent / (self.emails_sent + self.emails_failed) * 100 if (self.emails_sent + self.emails_failed) > 0 else 0,
            "configured": self.is_configured()
        }