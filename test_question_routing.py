#!/usr/bin/env python3
"""
Test script to verify question routing logic
"""

import asyncio
import sys
import os

# Add the app directory to the path
sys.path.append(os.path.join(os.path.dirname(__file__), 'ecs-api-service', 'app'))

from services.voice_processor import voice_processor
from shared.models.call_session import CallSession, ConversationStage, CallStatusEnum
from datetime import datetime
import uuid

async def test_question_routing():
    """Test the question routing logic"""
    print("🧪 Testing question routing logic...")
    
    # Create a test session
    session = CallSession(
        session_id=str(uuid.uuid4()),
        twilio_call_sid="test_call",
        client_id="test_client",
        phone_number="+1234567890",
        call_status=CallStatusEnum.IN_PROGRESS,
        conversation_stage=ConversationStage.GREETING,
        conversation_turns=[],
        client_data={
            "first_name": "John",
            "last_name": "Doe",
            "phone": "+1234567890",
            "email": "john@example.com",
            "last_agent": "Alex"
        },
        started_at=datetime.utcnow(),
        no_speech_count=0,
        lyzr_agent_id="test_agent",
        lyzr_session_id=f"test_session_{uuid.uuid4().hex[:8]}"
    )
    
    # Test cases
    test_cases = [
        # Static response questions (should use static responses)
        {
            "question": "Are you an AI agent?",
            "expected_category": "ai_clarification",
            "expected_intent": "ai_question",
            "description": "AI question - should use static response"
        },
        {
            "question": "What was your name again?",
            "expected_category": "identity_clarification", 
            "expected_intent": "identity_question",
            "description": "Identity question - should use static response"
        },
        {
            "question": "I don't remember working with you, where are you calling from again?",
            "expected_category": "memory_clarification",
            "expected_intent": "memory_question", 
            "description": "Memory question - should use static response"
        },
        {
            "question": "I'm sorry, where are you from?",
            "expected_category": "identity_clarification",
            "expected_intent": "identity_question",
            "description": "Identity question - should use static response"
        },
        
        # Unknown questions (should go to Lyzr)
        {
            "question": "What are your business hours?",
            "expected_category": "lyzr_delay_filler",
            "expected_intent": "complex_question",
            "description": "Unknown question - should go to Lyzr"
        },
        {
            "question": "How much does your service cost?",
            "expected_category": "lyzr_delay_filler", 
            "expected_intent": "complex_question",
            "description": "Unknown question - should go to Lyzr"
        },
        {
            "question": "Can you explain the difference between HMO and PPO?",
            "expected_category": "lyzr_delay_filler",
            "expected_intent": "complex_question", 
            "description": "Unknown question - should go to Lyzr"
        },
        {
            "question": "What happens if I miss open enrollment?",
            "expected_category": "lyzr_delay_filler",
            "expected_intent": "complex_question",
            "description": "Unknown question - should go to Lyzr"
        },
        
        # Non-question responses (should use unclear response)
        {
            "question": "I'm busy right now",
            "expected_category": "clarification",
            "expected_intent": "unclear",
            "description": "Non-question - should use unclear response"
        },
        {
            "question": "Let me think about it",
            "expected_category": "clarification", 
            "expected_intent": "unclear",
            "description": "Non-question - should use unclear response"
        }
    ]
    
    for i, test_case in enumerate(test_cases, 1):
        print(f"\n📝 Test {i}: {test_case['description']}")
        print(f"   Question: '{test_case['question']}'")
        
        try:
            result = await voice_processor.process_customer_input(
                customer_input=test_case['question'],
                session=session,
                confidence=0.9
            )
            
            actual_category = result.get('response_category', 'unknown')
            actual_intent = result.get('detected_intent', 'unknown')
            has_lyzr_task = result.get('lyzr_task') is not None
            
            print(f"   Expected category: {test_case['expected_category']}")
            print(f"   Actual category: {actual_category}")
            print(f"   Expected intent: {test_case['expected_intent']}")
            print(f"   Actual intent: {actual_intent}")
            print(f"   Lyzr task created: {has_lyzr_task}")
            
            # Check if results match expectations
            category_match = actual_category == test_case['expected_category']
            intent_match = actual_intent == test_case['expected_intent']
            
            if category_match and intent_match:
                print("   ✅ PASS")
            else:
                print("   ❌ FAIL")
                print(f"   Expected: {test_case['expected_category']}/{test_case['expected_intent']}")
                print(f"   Actual: {actual_category}/{actual_intent}")
                
        except Exception as e:
            print(f"   ❌ Error: {e}")

async def test_question_detection():
    """Test the question detection logic"""
    print("\n🔍 Testing question detection logic...")
    
    test_questions = [
        # Should be detected as questions
        ("What are your business hours?", True),
        ("How much does it cost?", True),
        ("Can you help me?", True),
        ("Is this covered?", True),
        ("When does enrollment end?", True),
        ("Where is your office?", True),
        ("Why should I choose you?", True),
        ("Which plan is best?", True),
        
        # Should NOT be detected as questions
        ("I'm interested", False),
        ("No thanks", False),
        ("Maybe later", False),
        ("I'm busy", False),
        ("Let me think", False),
        ("Call me back", False),
        ("Remove me from your list", False),
        ("Yes, I'd like that", False)
    ]
    
    for question, expected in test_questions:
        actual = voice_processor._is_question(question.lower())
        status = "✅" if actual == expected else "❌"
        print(f"{status} '{question}' -> {actual} (expected: {expected})")

async def main():
    """Main test function"""
    print("🚀 Starting question routing test...")
    
    # Test question detection
    await test_question_detection()
    
    # Test question routing
    await test_question_routing()
    
    print("\n✅ Test completed!")

if __name__ == "__main__":
    asyncio.run(main())
