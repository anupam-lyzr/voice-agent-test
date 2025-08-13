#!/usr/bin/env python3
"""
Test AWS SES Configuration for ca.lyzr.app domain
Run this script to test your existing SES setup
"""

import os
import boto3
from botocore.exceptions import ClientError, NoCredentialsError

def test_ses_domain_configuration():
    """Test AWS SES configuration with existing domain"""
    
    # Get environment variables
    aws_region = os.getenv('AWS_REGION', 'us-east-1')
    aws_access_key = os.getenv('AWS_ACCESS_KEY_ID')
    aws_secret_key = os.getenv('AWS_SECRET_ACCESS_KEY')
    from_email = os.getenv('FROM_EMAIL', 'noreply@ca.lyzr.app')
    to_email = os.getenv('TEST_EMAIL', 'your-test-email@gmail.com')
    
    print("🔧 Testing AWS SES Configuration for ca.lyzr.app...")
    print(f"Region: {aws_region}")
    print(f"From Email: {from_email}")
    print(f"To Email: {to_email}")
    print(f"Account ID: 958216563951")
    
    if not all([aws_access_key, aws_secret_key]):
        print("❌ Missing required AWS credentials!")
        print("Please set AWS_ACCESS_KEY_ID and AWS_SECRET_ACCESS_KEY")
        return False
    
    try:
        # Create SES client with session token support
        ses_kwargs = {
            'service_name': 'ses',
            'region_name': aws_region,
            'aws_access_key_id': aws_access_key,
            'aws_secret_access_key': aws_secret_key
        }
        
        # Add session token if available
        aws_session_token = os.getenv('AWS_SESSION_TOKEN')
        if aws_session_token:
            ses_kwargs['aws_session_token'] = aws_session_token
            print("✅ Using AWS session token (temporary credentials)")
        
        ses_client = boto3.client(**ses_kwargs)
        
        print("✅ SES client created successfully")
        
        # Check domain verification status
        try:
            response = ses_client.get_identity_verification_attributes(
                Identities=['ca.lyzr.app']
            )
            
            domain_status = response['VerificationAttributes'].get('ca.lyzr.app', {})
            verification_status = domain_status.get('VerificationStatus', 'Unknown')
            
            print(f"✅ Domain ca.lyzr.app status: {verification_status}")
            
            if verification_status != 'Success':
                print("⚠️ Domain is not verified. Please verify ca.lyzr.app in SES console.")
                return False
                
        except Exception as e:
            print(f"⚠️ Could not check domain status: {e}")
        
        # Test sending email
        subject = "🎉 Test Email from Voice Agent System"
        html_body = """
        <!DOCTYPE html>
        <html>
        <head>
            <style>
                body { font-family: Arial, sans-serif; line-height: 1.6; color: #333; }
                .container { max-width: 600px; margin: 0 auto; padding: 20px; }
                .header { background: linear-gradient(135deg, #667eea 0%, #764ba2 100%); color: white; padding: 30px; text-align: center; border-radius: 10px; }
                .content { padding: 20px; background: #f9f9f9; border-radius: 10px; margin: 20px 0; }
                .footer { text-align: center; color: #666; font-size: 14px; }
            </style>
        </head>
        <body>
            <div class="container">
                <div class="header">
                    <h1>🎉 Voice Agent System Test</h1>
                </div>
                <div class="content">
                    <h2>Hello!</h2>
                    <p>This is a test email from your Voice Agent system using your verified domain <strong>ca.lyzr.app</strong>.</p>
                    <p>If you receive this email, your AWS SES configuration is working correctly!</p>
                    <ul>
                        <li>✅ Domain verified: ca.lyzr.app</li>
                        <li>✅ AWS SES configured</li>
                        <li>✅ Email sending working</li>
                    </ul>
                </div>
                <div class="footer">
                    <p>Best regards,<br>Voice Agent System</p>
                </div>
            </div>
        </body>
        </html>
        """
        
        text_body = """
        Hello!
        
        This is a test email from your Voice Agent system using your verified domain ca.lyzr.app.
        
        If you receive this email, your AWS SES configuration is working correctly!
        
        Best regards,
        Voice Agent System
        """
        
        response = ses_client.send_email(
            Source=from_email,
            Destination={'ToAddresses': [to_email]},
            Message={
                'Subject': {'Data': subject, 'Charset': 'UTF-8'},
                'Body': {
                    'Html': {'Data': html_body, 'Charset': 'UTF-8'},
                    'Text': {'Data': text_body, 'Charset': 'UTF-8'}
                }
            }
        )
        
        print(f"✅ Test email sent successfully!")
        print(f"Message ID: {response['MessageId']}")
        print(f"Check your email at: {to_email}")
        
        return True
        
    except NoCredentialsError:
        print("❌ AWS credentials not found!")
        print("Please check your AWS_ACCESS_KEY_ID and AWS_SECRET_ACCESS_KEY")
        return False
        
    except ClientError as e:
        error_code = e.response['Error']['Code']
        error_message = e.response['Error']['Message']
        
        if error_code == 'MessageRejected':
            print(f"❌ Email rejected: {error_message}")
            print("This usually means the recipient email is not verified in SES")
            print("Please verify your test email address in SES console")
        elif error_code == 'AccessDenied':
            print(f"❌ Access denied: {error_message}")
            print("Check your IAM permissions for SES")
        elif error_code == 'ConfigurationSetDoesNotExist':
            print(f"❌ Configuration error: {error_message}")
        else:
            print(f"❌ SES error: {error_code} - {error_message}")
        
        return False
        
    except Exception as e:
        print(f"❌ Unexpected error: {e}")
        return False

def check_ses_quota():
    """Check SES sending quota"""
    try:
        aws_region = os.getenv('AWS_REGION', 'us-east-1')
        aws_access_key = os.getenv('AWS_ACCESS_KEY_ID')
        aws_secret_key = os.getenv('AWS_SECRET_ACCESS_KEY')
        
        # Create SES client with session token support
        ses_kwargs = {
            'service_name': 'ses',
            'region_name': aws_region,
            'aws_access_key_id': aws_access_key,
            'aws_secret_access_key': aws_secret_key
        }
        
        # Add session token if available
        aws_session_token = os.getenv('AWS_SESSION_TOKEN')
        if aws_session_token:
            ses_kwargs['aws_session_token'] = aws_session_token
        
        ses_client = boto3.client(**ses_kwargs)
        
        response = ses_client.get_send_quota()
        
        print("\n📊 SES Quota Information:")
        print(f"Max 24 hour send: {response['Max24HourSend']}")
        print(f"Sent last 24 hours: {response['SentLast24Hours']}")
        print(f"Max send rate: {response['MaxSendRate']} emails/second")
        
        remaining = response['Max24HourSend'] - response['SentLast24Hours']
        print(f"Remaining today: {remaining}")
        
    except Exception as e:
        print(f"Could not check quota: {e}")

if __name__ == "__main__":
    # Load environment variables from .env file
    try:
        from dotenv import load_dotenv
        load_dotenv()
        print("✅ Loaded environment variables from .env file")
    except ImportError:
        print("⚠️ python-dotenv not installed, using system environment variables")
    
    success = test_ses_domain_configuration()
    
    if success:
        print("\n🎉 SES configuration is working correctly!")
        print("Your Voice Agent system is ready for production email sending.")
        check_ses_quota()
    else:
        print("\n❌ SES configuration failed!")
        print("Please check your AWS credentials and SES setup.")
