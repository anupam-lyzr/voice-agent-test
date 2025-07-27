import json
import boto3
import os
from datetime import datetime
import pytz

def lambda_handler(event, context):
    """
    Process campaign queue with business hours validation
    """
    
    # CRITICAL: Check business hours first
    if not is_business_hours():
        return {
            'statusCode': 200,
            'body': json.dumps({
                'message': 'Outside business hours - queue processing paused',
                'timestamp': datetime.utcnow().isoformat()
            })
        }
    
    # Initialize AWS clients
    sqs = boto3.client('sqs')
    ecs = boto3.client('ecs')
    
    queue_url = os.environ['QUEUE_URL']
    cluster_name = os.environ['ECS_CLUSTER']
    task_definition = os.environ['WORKER_TASK_DEFINITION']
    subnet_id = os.environ['SUBNET_ID']
    
    try:
        # Get messages from queue
        response = sqs.receive_message(
            QueueUrl=queue_url,
            MaxNumberOfMessages=10,
            WaitTimeSeconds=5,
            VisibilityTimeoutSeconds=300
        )
        
        messages = response.get('Messages', [])
        processed_count = 0
        
        for message in messages:
            try:
                # Parse message body
                message_body = json.loads(message['Body'])
                
                # Start ECS worker task for this client
                task_response = ecs.run_task(
                    cluster=cluster_name,
                    taskDefinition=task_definition,
                    launchType='FARGATE',
                    networkConfiguration={
                        'awsvpcConfiguration': {
                            'subnets': [subnet_id],
                            'assignPublicIp': 'ENABLED',
                            'securityGroups': [os.environ['SECURITY_GROUP_ID']]
                        }
                    },
                    overrides={
                        'containerOverrides': [{
                            'name': 'worker-service',
                            'environment': [
                                {
                                    'name': 'CLIENT_DATA',
                                    'value': json.dumps(message_body)
                                },
                                {
                                    'name': 'MESSAGE_RECEIPT_HANDLE',
                                    'value': message['ReceiptHandle']
                                }
                            ]
                        }]
                    }
                )
                
                # Delete processed message from queue
                sqs.delete_message(
                    QueueUrl=queue_url,
                    ReceiptHandle=message['ReceiptHandle']
                )
                
                processed_count += 1
                
            except Exception as e:
                print(f"Error processing message: {str(e)}")
                continue
        
        return {
            'statusCode': 200,
            'body': json.dumps({
                'processed_messages': processed_count,
                'timestamp': datetime.utcnow().isoformat()
            })
        }
        
    except Exception as e:
        print(f"Lambda execution error: {str(e)}")
        return {
            'statusCode': 500,
            'body': json.dumps({
                'error': str(e),
                'timestamp': datetime.utcnow().isoformat()
            })
        }

def is_business_hours():
    """
    Check if current time is within business hours (9 AM-5 PM ET, Mon-Fri)
    """
    et_tz = pytz.timezone('America/New_York')
    now_et = datetime.now(et_tz)
    
    # Check weekday (0=Monday, 6=Sunday)
    if now_et.weekday() >= 5:  # Saturday or Sunday
        return False
    
    # Check time (9 AM to 5 PM)
    if now_et.hour < 9 or now_et.hour >= 17:
        return False
    
    return True
