#!/usr/bin/env python3
"""
Test AWS SES Configuration
Run this script to test your AWS SES setup
"""

import os
import boto3
from botocore.exceptions import ClientError, NoCredentialsError

def test_ses_configuration():
    """Test AWS SES configuration"""
    
    # Get environment variables
    aws_region = os.getenv('AWS_REGION', 'us-east-1')
    aws_access_key = os.getenv('AWS_ACCESS_KEY_ID')
    aws_secret_key = os.getenv('AWS_SECRET_ACCESS_KEY')
    from_email = os.getenv('FROM_EMAIL')
    to_email = os.getenv('TEST_EMAIL', 'your-test-email@gmail.com')
    
    print("🔧 Testing AWS SES Configuration...")
    print(f"Region: {aws_region}")
    print(f"From Email: {from_email}")
    print(f"To Email: {to_email}")
    
    if not all([aws_access_key, aws_secret_key, from_email]):
        print("❌ Missing required environment variables!")
        print("Please set AWS_ACCESS_KEY_ID, AWS_SECRET_ACCESS_KEY, and FROM_EMAIL")
        return False
    
    try:
        # Create SES client
        ses_client = boto3.client(
            'ses',
            region_name=aws_region,
            aws_access_key_id=aws_access_key,
            aws_secret_access_key=aws_secret_key
        )
        
        print("✅ SES client created successfully")
        
        # Test sending email
        subject = "Test Email from Voice Agent System"
        body = """
        Hello!
        
        This is a test email from your Voice Agent system.
        
        If you receive this email, your AWS SES configuration is working correctly!
        
        Best regards,
        Voice Agent System
        """
        
        response = ses_client.send_email(
            Source=from_email,
            Destination={'ToAddresses': [to_email]},
            Message={
                'Subject': {'Data': subject, 'Charset': 'UTF-8'},
                'Body': {'Text': {'Data': body, 'Charset': 'UTF-8'}}
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
            print("This usually means the email addresses are not verified in SES")
        elif error_code == 'AccessDenied':
            print(f"❌ Access denied: {error_message}")
            print("Check your IAM permissions for SES")
        else:
            print(f"❌ SES error: {error_code} - {error_message}")
        
        return False
        
    except Exception as e:
        print(f"❌ Unexpected error: {e}")
        return False

if __name__ == "__main__":
    # Load environment variables from .env file
    try:
        from dotenv import load_dotenv
        load_dotenv()
        print("✅ Loaded environment variables from .env file")
    except ImportError:
        print("⚠️ python-dotenv not installed, using system environment variables")
    
    success = test_ses_configuration()
    
    if success:
        print("\n🎉 SES configuration is working correctly!")
        print("You can now use the Voice Agent system with real email sending.")
    else:
        print("\n❌ SES configuration failed!")
        print("Please check your AWS credentials and SES setup.")
