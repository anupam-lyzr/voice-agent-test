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
from .email_signature import email_signature

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

    async def send_slot_selection_email(self, client_email: str, client_name: str, agent_name: str, available_slots: List[Dict[str, Any]]) -> Dict[str, Any]:
        """Send slot selection email with available time slots"""
        try:
            if not self.is_configured():
                logger.warning("⚠️ Email service not configured, logging slot selection email")
                logger.info(f"📧 Slot selection email would be sent to {client_email}")
                logger.info(f"📅 Available slots: {len(available_slots)}")
                return {"success": True, "method": "logged"}
            
            # Get email templates
            html_content = self._get_slot_selection_email_html(client_name, available_slots)
            text_content = self._get_slot_selection_email_text(client_name, available_slots)
            
            # Send email
            subject = f"Choose Your Preferred Time Slot - {agent_name}"
            
            result = await self._send_email(
                to_email=client_email,
                subject=subject,
                html_content=html_content,
                text_content=text_content
            )
            
            if result.get("success"):
                logger.info(f"✅ Slot selection email sent to {client_email}")
                return {"success": True, "email_id": result.get("message_id")}
            else:
                logger.error(f"❌ Failed to send slot selection email: {result.get('error')}")
                return {"success": False, "error": result.get("error")}
                
        except Exception as e:
            logger.error(f"❌ Error sending slot selection email: {e}")
            return {"success": False, "error": str(e)}

    async def send_meeting_confirmation_email(self, client_email: str, client_name: str, agent_name: str, meeting_details: Dict[str, Any]) -> Dict[str, Any]:
        """Send meeting confirmation email"""
        try:
            if not self.is_configured():
                logger.warning("⚠️ Email service not configured, logging meeting confirmation")
                logger.info(f"📧 Meeting confirmation would be sent to {client_email}")
                return {"success": True, "method": "logged"}
            
            # Get email templates
            html_content = self._get_slot_confirmation_email_html(client_name, meeting_details)
            text_content = self._get_slot_confirmation_email_text(client_name, meeting_details)
            
            # Send email
            meeting_time = meeting_details.get('meeting_time', 'TBD')
            subject = f"Meeting Confirmed - {meeting_time}"
            
            result = await self._send_email(
                to_email=client_email,
                subject=subject,
                html_content=html_content,
                text_content=text_content
            )
            
            if result.get("success"):
                logger.info(f"✅ Meeting confirmation email sent to {client_email}")
                return {"success": True, "email_id": result.get("message_id")}
            else:
                logger.error(f"❌ Failed to send meeting confirmation: {result.get('error')}")
                return {"success": False, "error": result.get("error")}
                
        except Exception as e:
            logger.error(f"❌ Error sending meeting confirmation: {e}")
            return {"success": False, "error": str(e)}

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
                    "html": self._get_agent_assignment_email_html("Agent", {"client_name": client_name}, call_summary),
                    "text": self._get_agent_assignment_email_text("Agent", {"client_name": client_name}, call_summary)
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
        """Get email footer HTML with configurable signature"""
        signature_html = email_signature.get_html_signature()
        
        return f"""
            </div>
            {signature_html}
            <div class="footer" style="margin-top: 20px; padding-top: 20px; border-top: 1px solid #e0e0e0; text-align: center; color: #666; font-size: 12px;">
                <p>© 2024 Altruis Advisor Group. All rights reserved.</p>
                <p>This email was sent from an automated system. Please do not reply directly to this email.</p>
            </div>
        </body>
        </html>
        """

    def _get_interested_email_html(self, client_name: str, call_summary: Dict[str, Any]) -> str:
        """Get HTML for interested customer email - matches document format"""
        return f"""
        {self._get_email_header("Thank you for your time!")}
        <div class="header">
            <h1>Thank you for your time!</h1>
        </div>
        <div class="content">
            <h2>Hello {client_name},</h2>
            
            <p>Thank you for your time today! As requested, we will continue to keep you up to date with the latest and greatest health insurance information. If you'd like to connect with one of our insurance experts at any time, please feel free to reach out. We are always here to help and our services are always free of charge.</p>
        </div>
        {self._get_email_footer()}
        """

    def _get_not_interested_email_html(self, client_name: str, call_summary: Dict[str, Any]) -> str:
        """Get HTML for not interested customer email - matches document format"""
        return f"""
        {self._get_email_header("Your request has been processed")}
        <div class="header">
            <h1>Your request has been processed</h1>
        </div>
        <div class="content">
            <h2>Hello {client_name},</h2>
            
            <p>We removed your email address from our correspondence platform so you should not receive any additional communications from our team. If your situation changes and you'd like to connect with one of our insurance experts in the future, please feel free to reach out. We are always here to help and our services are always free of charge.</p>
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
        logger.info(f"🔍 DEBUG: _get_agent_assignment_email_html called with agent_name={agent_name}, client_info={client_info}, call_summary={call_summary}")
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

    # NEW: Missing Email Templates for Complete Scheduling System
    
    def _get_no_answer_email_html(self, client_name: str, call_summary: Dict[str, Any]) -> str:
        """Get HTML for no answer email"""
        return f"""
        {self._get_email_header("We tried to reach you")}
        <div class="header">
            <h1>📞 We tried to reach you</h1>
        </div>
        <div class="content">
            <h2>Dear {client_name},</h2>
            
            <p>We recently tried to reach you regarding your health insurance needs, but we weren't able to connect.</p>
            
            <p>We wanted to let you know that we're here to help with:</p>
            <ul>
                <li>Policy reviews and updates</li>
                <li>Open enrollment guidance</li>
                <li>Cost-saving opportunities</li>
                <li>Coverage optimization</li>
            </ul>
            
            <div class="highlight">
                <p><strong>💡 No pressure:</strong> If you're interested in learning more, we'd be happy to schedule a convenient time to discuss your options.</p>
            </div>
            
            <p style="text-align: center;">
                <a href="mailto:contact@altruisadvisor.com" class="button">📧 Schedule a Call</a>
            </p>
            
            <p>If you prefer not to receive these communications, please let us know.</p>
        </div>
        {self._get_email_footer()}
        """

    def _get_voicemail_email_html(self, client_name: str, call_summary: Dict[str, Any]) -> str:
        """Get HTML for voicemail email"""
        return f"""
        {self._get_email_header("We left you a message")}
        <div class="header">
            <h1>📱 We left you a message</h1>
        </div>
        <div class="content">
            <h2>Dear {client_name},</h2>
            
            <p>We called you earlier and left a voicemail about your health insurance needs.</p>
            
            <p>In case you missed it, we're reaching out to help with:</p>
            <ul>
                <li>Reviewing your current coverage</li>
                <li>Exploring cost-saving options</li>
                <li>Open enrollment planning</li>
                <li>Policy updates and changes</li>
            </ul>
            
            <div class="highlight">
                <p><strong>🎯 Our services are completely free</strong> and there's no obligation to make any changes.</p>
            </div>
            
            <p style="text-align: center;">
                <a href="mailto:contact@altruisadvisor.com" class="button">📧 Get in Touch</a>
            </p>
            
            <p>We look forward to hearing from you!</p>
        </div>
        {self._get_email_footer()}
        """

    def _get_interested_no_schedule_email_html(self, client_name: str, call_summary: Dict[str, Any]) -> str:
        """Get HTML for interested but no schedule email"""
        key_points = self._format_key_points_html(call_summary.get('key_points', []))
        
        return f"""
        {self._get_email_header("Thank you for your interest!")}
        <div class="header">
            <h1>🎉 Thank you for your interest!</h1>
        </div>
        <div class="content">
            <h2>Dear {client_name},</h2>
            
            <p>We're thrilled that you're interested in our services! Your recent conversation with Alex has shown great potential for collaboration.</p>
            
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

    def _get_interested_and_scheduled_email_html(self, client_name: str, call_summary: Dict[str, Any]) -> str:
        """Get HTML for interested and scheduled email"""
        meeting_time = call_summary.get('meeting_time', 'TBD')
        agent_name = call_summary.get('agent_name', 'Our Team')
        
        return f"""
        {self._get_email_header("Meeting Scheduled - Discovery Call")}
        <div class="header">
            <h1>📅 Meeting Scheduled - Discovery Call</h1>
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

    def _get_not_interested_no_dnc_email_html(self, client_name: str, call_summary: Dict[str, Any]) -> str:
        """Get HTML for not interested but no DNC email"""
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

    def _get_not_interested_with_dnc_email_html(self, client_name: str, call_summary: Dict[str, Any]) -> str:
        """Get HTML for not interested with DNC email"""
        return f"""
        {self._get_email_header("Your request has been processed")}
        <div class="header">
            <h1>✅ Your request has been processed</h1>
        </div>
        <div class="content">
            <h2>Dear {client_name},</h2>
            
            <p>Thank you for your time today. We have processed your request to be removed from our calling list.</p>
            
            <div class="highlight">
                <p><strong>✅ Confirmation:</strong> You have been successfully added to our Do Not Call list. We will no longer contact you via phone.</p>
            </div>
            
            <p>We respect your decision and appreciate you letting us know your preference.</p>
            
            <p>If you change your mind in the future and would like to hear from us again, you can always reach out to us directly.</p>
            
            <p>Thank you for your understanding.</p>
        </div>
        {self._get_email_footer()}
        """

    def _get_interested_but_dnc_email_html(self, client_name: str, call_summary: Dict[str, Any]) -> str:
        """Get HTML for interested but DNC email (conflicting scenario)"""
        return f"""
        {self._get_email_header("Thank you for your interest!")}
        <div class="header">
            <h1>🎉 Thank you for your interest!</h1>
        </div>
        <div class="content">
            <h2>Dear {client_name},</h2>
            
            <p>We're thrilled that you're interested in our services! However, we also noted that you requested to be removed from our calling list.</p>
            
            <div class="highlight">
                <p><strong>📧 Email Communication:</strong> Since you expressed interest, we'll send you important updates via email only. You won't receive any phone calls from us.</p>
            </div>
            
            <p>If you'd like to proceed with our services, please contact us via email and we'll be happy to help!</p>
            
            <p style="text-align: center;">
                <a href="mailto:contact@altruisadvisor.com" class="button">📧 Contact Us</a>
            </p>
            
            <p>Thank you for your interest!</p>
        </div>
        {self._get_email_footer()}
        """

    def _get_unclear_response_email_html(self, client_name: str, call_summary: Dict[str, Any]) -> str:
        """Get HTML for unclear response email"""
        key_points = self._format_key_points_html(call_summary.get('key_points', []))
        
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
            
            <p>We're here to help address any additional questions you may have. Please feel free to reach out if you'd like to discuss anything further.</p>
            
            <p style="text-align: center;">
                <a href="mailto:contact@altruisadvisor.com" class="button">📧 Get in Touch</a>
            </p>
        </div>
        {self._get_email_footer()}
        """

    def _get_busy_call_back_email_html(self, client_name: str, call_summary: Dict[str, Any]) -> str:
        """Get HTML for busy call back email"""
        return f"""
        {self._get_email_header("We'll call you back as requested")}
        <div class="header">
            <h1>📞 We'll call you back as requested</h1>
        </div>
        <div class="content">
            <h2>Dear {client_name},</h2>
            
            <p>We understand you were busy when we called. As requested, we'll try to reach you again at a more convenient time.</p>
            
            <p>In the meantime, here's what we wanted to discuss:</p>
            <ul>
                <li>Reviewing your current health insurance coverage</li>
                <li>Exploring potential cost-saving opportunities</li>
                <li>Open enrollment planning and guidance</li>
                <li>Policy updates and changes</li>
            </ul>
            
            <div class="highlight">
                <p><strong>💡 No pressure:</strong> Our services are completely free and there's no obligation to make any changes.</p>
            </div>
            
            <p>If you'd prefer to schedule a specific time that works for you, please let us know!</p>
            
            <p style="text-align: center;">
                <a href="mailto:contact@altruisadvisor.com" class="button">📧 Schedule a Call</a>
            </p>
        </div>
        {self._get_email_footer()}
        """

    def _get_slot_selection_email_html(self, client_name: str, available_slots: List[Dict[str, Any]]) -> str:
        """Get HTML for slot selection email"""
        slots_html = ""
        for i, slot in enumerate(available_slots, 1):
            slot_time = slot.get('time', 'TBD')
            slot_date = slot.get('date', 'TBD')
            slot_link = slot.get('link', '#')
            slots_html += f"""
                <div class="slot-option">
                    <h4>Option {i}: {slot_date} at {slot_time}</h4>
                    <a href="{slot_link}" class="button">📅 Select This Time</a>
                </div>
            """
        
        return f"""
        {self._get_email_header("Choose Your Preferred Time Slot")}
        <div class="header">
            <h1>📅 Choose Your Preferred Time Slot</h1>
        </div>
        <div class="content">
            <h2>Dear {client_name},</h2>
            
            <p>Great news! We have several available time slots for your discovery call. Please select the one that works best for you.</p>
            
            <div class="slot-selection">
                <h3>🕐 Available Time Slots:</h3>
                {slots_html}
            </div>
            
            <div class="highlight">
                <p><strong>💡 What to expect:</strong> Your discovery call will be 30 minutes long and will cover your specific needs and requirements.</p>
            </div>
            
            <p>If none of these times work for you, please reply to this email and we'll find a time that does!</p>
            
            <p>We look forward to meeting with you!</p>
        </div>
        {self._get_email_footer()}
        """

    def _get_slot_confirmation_email_html(self, client_name: str, meeting_details: Dict[str, Any]) -> str:
        """Get HTML for slot confirmation email"""
        meeting_time = meeting_details.get('meeting_time', 'TBD')
        agent_name = meeting_details.get('agent_name', 'Our Team')
        calendar_link = meeting_details.get('calendar_link', 'Will be sent separately')
        meet_link = meeting_details.get('meet_link', 'Will be sent separately')
        
        return f"""
        {self._get_email_header("Meeting Confirmed")}
        <div class="header">
            <h1>✅ Meeting Confirmed</h1>
        </div>
        <div class="content">
            <h2>Dear {client_name},</h2>
            
            <p>Perfect! Your discovery call has been confirmed for <strong>{meeting_time}</strong>.</p>
            
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
                <p><strong>📅 Calendar Link:</strong> <a href="{calendar_link}">Add to Calendar</a></p>
                <p><strong>🎥 Video Link:</strong> <a href="{meet_link}">Join Meeting</a></p>
            </div>
            
            <h3>🎯 What to expect:</h3>
            <ul>
                <li>Detailed discussion of your needs and requirements</li>
                <li>Custom solution recommendations</li>
                <li>Q&A session</li>
                <li>Next steps planning</li>
            </ul>
            
            <p>We look forward to our conversation!</p>
        </div>
        {self._get_email_footer()}
        """

    def _get_meeting_reminder_email_html(self, client_name: str, meeting_details: Dict[str, Any]) -> str:
        """Get HTML for meeting reminder email"""
        meeting_time = meeting_details.get('meeting_time', 'TBD')
        agent_name = meeting_details.get('agent_name', 'Our Team')
        meet_link = meeting_details.get('meet_link', 'Will be sent separately')
        
        return f"""
        {self._get_email_header("Reminder: Your Discovery Call Tomorrow")}
        <div class="header">
            <h1>📅 Reminder: Your Discovery Call Tomorrow</h1>
        </div>
        <div class="content">
            <h2>Dear {client_name},</h2>
            
            <p>This is a friendly reminder that you have a discovery call scheduled for tomorrow at <strong>{meeting_time}</strong>.</p>
            
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
                <p><strong>🎥 Video Link:</strong> <a href="{meet_link}">Join Meeting</a></p>
            </div>
            
            <p>Please make sure you have a stable internet connection and are in a quiet environment for our call.</p>
            
            <p>If you need to reschedule, please contact us as soon as possible.</p>
            
            <p>We look forward to meeting with you!</p>
        </div>
        {self._get_email_footer()}
        """

    def _get_meeting_reminder_agent_email_html(self, agent_name: str, client_info: Dict[str, Any], meeting_details: Dict[str, Any]) -> str:
        """Get HTML for meeting reminder email to agent"""
        client_name = client_info.get('client_name', 'Unknown Client')
        meeting_time = meeting_details.get('meeting_time', 'TBD')
        meet_link = meeting_details.get('meet_link', 'Will be sent separately')
        
        return f"""
        {self._get_email_header("Reminder: Discovery Call Tomorrow")}
        <div class="header">
            <h1>📅 Reminder: Discovery Call Tomorrow</h1>
        </div>
        <div class="content">
            <h2>Dear {agent_name},</h2>
            
            <p>This is a reminder that you have a discovery call scheduled for tomorrow at <strong>{meeting_time}</strong>.</p>
            
            <div class="meeting-details">
                <h3>👤 Client Information:</h3>
                <ul>
                    <li><strong>Name:</strong> {client_name}</li>
                    <li><strong>Phone:</strong> {client_info.get('phone', 'N/A')}</li>
                    <li><strong>Email:</strong> {client_info.get('email', 'N/A')}</li>
                </ul>
            </div>
            
            <div class="meeting-details">
                <h3>📋 Meeting Details:</h3>
                <ul>
                    <li><strong>Date & Time:</strong> {meeting_time}</li>
                    <li><strong>Duration:</strong> 30 minutes</li>
                    <li><strong>Format:</strong> Video call</li>
                </ul>
            </div>
            
            <div class="highlight">
                <p><strong>🎥 Video Link:</strong> <a href="{meet_link}">Join Meeting</a></p>
            </div>
            
            <p>Please review the client's information and prepare for the call.</p>
            
            <p>Good luck with the meeting!</p>
        </div>
        {self._get_email_footer()}
        """

    def _get_reschedule_info_email_html(self, client_name: str, meeting_details: Dict[str, Any]) -> str:
        """Get HTML for reschedule information email"""
        meeting_time = meeting_details.get('meeting_time', 'TBD')
        
        return f"""
        {self._get_email_header("Need to Reschedule? Here's How")}
        <div class="header">
            <h1>📞 Need to Reschedule? Here's How</h1>
        </div>
        <div class="content">
            <h2>Dear {client_name},</h2>
            
            <p>We understand that sometimes schedules change. If you need to reschedule your discovery call scheduled for <strong>{meeting_time}</strong>, here's how to do it:</p>
            
            <div class="reschedule-options">
                <h3>📧 Email Us:</h3>
                <p>Send an email to <a href="mailto:contact@altruisadvisor.com">contact@altruisadvisor.com</a> with your preferred new time.</p>
                
                <h3>📞 Call Us:</h3>
                <p>Call us at <strong>833.227.8500</strong> and we'll help you find a new time that works.</p>
                
                <h3>⏰ Response Time:</h3>
                <p>We'll respond within 24 hours to confirm your new appointment time.</p>
            </div>
            
            <div class="highlight">
                <p><strong>💡 Please note:</strong> We request at least 24 hours notice for rescheduling to help us accommodate other clients.</p>
            </div>
            
            <p>Thank you for your understanding!</p>
        </div>
        {self._get_email_footer()}
        """

    # NEW: Email templates that match the document exactly
    
    def _get_reengagement_email_html(self, client_name: str, call_summary: Dict[str, Any]) -> str:
        """Get HTML for re-engagement email - matches document format"""
        return f"""
        {self._get_email_header("Re-engagement from Altruis Advisor Group")}
        <div class="header">
            <h1>Re-engagement from Altruis Advisor Group</h1>
        </div>
        <div class="content">
            <h2>Hello {client_name},</h2>
            
            <p>Alex here from Altruis Advisor Group (on behalf of our CEO Anthony Fracchia), I just tried contacting you by phone. We've helped you with your health insurance needs in the past and I'm reaching out to see if we can be of service to you this year during Open Enrollment? As a friendly reminder, our services are provided free of charge 😊.</p>
            
            <div class="response-options">
                <p><strong>Reply "Yes"</strong> and one of our insurance experts will reach out to schedule a discovery call to get reacquainted with your specific situation.</p>
                <p><strong>Reply "No"</strong> and our team will not contact you unless you reach out in the future.</p>
                <p><strong>Reply "Remove"</strong> and we will remove you from all future correspondence</p>
            </div>
            
            <p>We look forward to hearing back from you</p>
            <p>Have a wonderful day!</p>
        </div>
        {self._get_email_footer()}
        """

    def _get_reengagement_yes_response_html(self, client_name: str, call_summary: Dict[str, Any]) -> str:
        """Get HTML for re-engagement 'Yes' response - matches document format"""
        return f"""
        {self._get_email_header("Thank you for your response!")}
        <div class="header">
            <h1>Thank you for your response!</h1>
        </div>
        <div class="content">
            <h2>{client_name},</h2>
            
            <p>Thank you for the quick response😊! One of our insurance experts will be contacting you shortly to schedule a 15 discovery call to get reacquainted with your health insurance situation and determine the next steps.</p>
            
            <p>We are looking forward to assisting you!</p>
            <p>Have a wonderful day!</p>
        </div>
        {self._get_email_footer()}
        """

    def _get_reengagement_no_response_html(self, client_name: str, call_summary: Dict[str, Any]) -> str:
        """Get HTML for re-engagement 'No' response - matches document format"""
        return f"""
        {self._get_email_header("Thank you for your response!")}
        <div class="header">
            <h1>Thank you for your response!</h1>
        </div>
        <div class="content">
            <h2>{client_name},</h2>
            
            <p>Thank you for the quick response😊! We have designated your client file as "Do Not Contact". If we can be of service to you in the future please feel free to reach out – we are always here to help and our services are always free of charge:</p>
        </div>
        {self._get_email_footer()}
        """

    def _get_reengagement_remove_response_html(self, client_name: str, call_summary: Dict[str, Any]) -> str:
        """Get HTML for re-engagement 'Remove' response - matches document format"""
        return f"""
        {self._get_email_header("Your request has been processed")}
        <div class="header">
            <h1>Your request has been processed</h1>
        </div>
        <div class="content">
            <h2>Hello {client_name},</h2>
            
            <p>We removed your email address from our correspondence platform so you should not receive any additional communications from our team. If your situation changes and you'd like to connect with one of our insurance experts in the future, please feel free to reach out. We are always here to help and our services are always free of charge.</p>
        </div>
        {self._get_email_footer()}
        """

    # Text versions for email clients that don't support HTML
    def _get_interested_email_text(self, client_name: str, call_summary: Dict[str, Any]) -> str:
        """Get text version for interested customer email - matches document format"""
        signature_text = email_signature.get_text_signature()
        return f"""
Hello {client_name},

Thank you for your time today! As requested, we will continue to keep you up to date with the latest and greatest health insurance information. If you'd like to connect with one of our insurance experts at any time, please feel free to reach out. We are always here to help and our services are always free of charge.
{signature_text}
        """.strip()

    def _get_not_interested_email_text(self, client_name: str, call_summary: Dict[str, Any]) -> str:
        """Get text version for not interested customer email - matches document format"""
        signature_text = email_signature.get_text_signature()
        return f"""
Hello {client_name},

We removed your email address from our correspondence platform so you should not receive any additional communications from our team. If your situation changes and you'd like to connect with one of our insurance experts in the future, please feel free to reach out. We are always here to help and our services are always free of charge.
{signature_text}
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
        signature_text = email_signature.get_text_signature(agent_name)
        
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
{signature_text}
        """.strip()

    # NEW: Text versions for re-engagement emails that match the document
    
    def _get_reengagement_email_text(self, client_name: str, call_summary: Dict[str, Any]) -> str:
        """Get text version for re-engagement email - matches document format"""
        signature_text = email_signature.get_text_signature()
        return f"""
Hello {client_name},

Alex here from Altruis Advisor Group (on behalf of our CEO Anthony Fracchia), I just tried contacting you by phone. We've helped you with your health insurance needs in the past and I'm reaching out to see if we can be of service to you this year during Open Enrollment? As a friendly reminder, our services are provided free of charge 😊.

Reply "Yes" and one of our insurance experts will reach out to schedule a discovery call to get reacquainted with your specific situation.
Reply "No" and our team will not contact you unless you reach out in the future.
Reply "Remove" and we will remove you from all future correspondence

We look forward to hearing back from you
Have a wonderful day!
{signature_text}
        """.strip()

    def _get_reengagement_yes_response_text(self, client_name: str, call_summary: Dict[str, Any]) -> str:
        """Get text version for re-engagement 'Yes' response - matches document format"""
        signature_text = email_signature.get_text_signature()
        return f"""
{client_name},

Thank you for the quick response😊! One of our insurance experts will be contacting you shortly to schedule a 15 discovery call to get reacquainted with your health insurance situation and determine the next steps.

We are looking forward to assisting you!
Have a wonderful day!
{signature_text}
        """.strip()

    def _get_reengagement_no_response_text(self, client_name: str, call_summary: Dict[str, Any]) -> str:
        """Get text version for re-engagement 'No' response - matches document format"""
        signature_text = email_signature.get_text_signature()
        return f"""
{client_name},

Thank you for the quick response😊! We have designated your client file as "Do Not Contact". If we can be of service to you in the future please feel free to reach out – we are always here to help and our services are always free of charge:
{signature_text}
        """.strip()

    def _get_reengagement_remove_response_text(self, client_name: str, call_summary: Dict[str, Any]) -> str:
        """Get text version for re-engagement 'Remove' response - matches document format"""
        signature_text = email_signature.get_text_signature()
        return f"""
Hello {client_name},

We removed your email address from our correspondence platform so you should not receive any additional communications from our team. If your situation changes and you'd like to connect with one of our insurance experts in the future, please feel free to reach out. We are always here to help and our services are always free of charge.
{signature_text}
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