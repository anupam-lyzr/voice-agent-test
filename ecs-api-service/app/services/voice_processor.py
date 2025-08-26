"""
Enhanced Voice Processor Service - Production Ready
Handles all customer responses including clarifying questions and interruptions
"""

import asyncio
import httpx
import logging
import time
from typing import Dict, Any, Optional, List
from datetime import datetime

from shared.config.settings import settings
from shared.models.call_session import CallSession, ConversationStage
from shared.utils.redis_client import redis_client

logger = logging.getLogger(__name__)

class VoiceProcessor:
    """Enhanced service for processing customer speech and generating responses"""
    
    def __init__(self):
        self.httpx_client = httpx.AsyncClient(timeout=30.0)
        self._configured = False
        
        # Enhanced response patterns for all scenarios with comprehensive variations
        self.response_patterns = {
            "yes_responses": ["yes", "yeah", "yep", "sure", "absolutely", "definitely", "of course", "okay", "ok", "sounds good", "that's fine", "it will", "i would", "i am", "i'm interested", "interested", "sounds like a good idea", "that sounds good", "i think so", "probably", "likely", "i guess", "i suppose"],
            "no_responses": ["no", "nope", "not really", "not interested", "no thanks", "don't think so", "i'm not", "not at this time", "not right now", "i don't think so", "probably not", "i doubt it", "i'm not sure", "i don't know", "maybe later", "not today", "i'm busy", "i don't have time", "i'm not looking", "i'm not in the market"],
            "maybe_responses": ["maybe", "not sure", "i don't know", "let me think", "perhaps", "i might", "i could", "possibly", "i'll consider it", "let me think about it", "i need to think", "i'm not certain", "i'm undecided", "i'm on the fence", "i'm not sure yet"],
            "dnc_requests": ["remove", "do not call", "don't call", "take me off", "unsubscribe", "stop calling", "remove me", "delete me", "i don't want calls", "no more calls", "stop the calls", "don't contact me", "remove from list", "take off list", "don't want to be called", "no calls please", "stop contacting me"],
            
            # COMPREHENSIVE: Clarifying question patterns with all variations
            "identity_questions": [
                # Direct identity questions
                "who is this", "where are you calling from", "what company", "who are you",
                "where are you from", "what's your name", "who am i speaking with",
                "what organization", "what business", "what was your name again",
                "where are you calling from again", "who is calling", "who is this calling",
                "what company is this", "what business is this", "what organization is this",
                "who are you calling for", "who do you represent", "what do you represent",
                "who are you with", "what are you calling about", "why are you calling",
                "what's this about", "what's the purpose", "what's this call about",
                "what is this about", "what is this call about", "what is this for",
                "who is this message from", "who sent you", "who told you to call",
                "how did you get my number", "where did you get my number",
                "who gave you my number", "how do you know me", "why do you have my number",
                "what's your name again", "i didn't catch your name", "what was that name",
                "who did you say you were", "what did you say your name was",
                "i didn't hear your name", "can you repeat your name", "what's your company",
                "what company are you with", "what business are you with",
                "what organization are you with", "who do you work for",
                "what do you do", "what's your job", "what's your role",
                "are you a salesperson", "are you selling something", "is this a sales call",
                "are you trying to sell me something", "what are you selling",
                "is this a marketing call", "is this a promotional call",
                "are you a telemarketer", "is this a telemarketing call"
            ],
            "ai_questions": [
                # AI/Robot detection questions with all variations
                "are you a robot", "are you ai", "are you artificial", "are you real",
                "is this automated", "are you human", "is this a recording", "are you an ai agent",
                "are you artificial intelligence", "are you a computer", "are you automated",
                "is this a computer", "is this a machine", "are you a machine",
                "are you a bot", "are you a chatbot", "is this a bot",
                "are you automated", "is this automated", "are you a program",
                "is this a program", "are you software", "is this software",
                "are you a virtual assistant", "are you a digital assistant",
                "are you an automated system", "is this an automated system",
                "are you a voice assistant", "are you siri", "are you alexa",
                "are you google", "are you cortana", "are you a virtual agent",
                "is this a virtual agent", "are you a digital agent",
                "are you an electronic agent", "are you a synthetic voice",
                "is this a synthetic voice", "are you a computer voice",
                "is this a computer voice", "are you a digital voice",
                "is this a digital voice", "are you a virtual voice",
                "is this a virtual voice", "are you a machine voice",
                "is this a machine voice", "are you a robotic voice",
                "is this a robotic voice", "are you a computer program",
                "is this a computer program", "are you an algorithm",
                "is this an algorithm", "are you a script", "is this a script",
                "are you a recording", "is this a recording", "are you a message",
                "is this a message", "are you a pre-recorded message",
                "is this a pre-recorded message", "are you a voice message",
                "is this a voice message", "are you a phone tree",
                "is this a phone tree", "are you an ivr", "is this an ivr",
                "are you an interactive voice response", "is this an interactive voice response",
                "are you a call center", "is this a call center", "are you a customer service",
                "is this customer service", "are you a support line",
                "is this a support line", "are you a helpline", "is this a helpline",
                "are you a hotline", "is this a hotline", "are you a service",
                "is this a service", "are you a system", "is this a system",
                "are you a platform", "is this a platform", "are you an application",
                "is this an application", "are you an app", "is this an app",
                "are you a tool", "is this a tool", "are you a device",
                "is this a device", "are you a machine", "is this a machine",
                "are you a computer", "is this a computer", "are you a server",
                "is this a server", "are you a network", "is this a network",
                "are you a database", "is this a database", "are you a system",
                "is this a system", "are you a program", "is this a program",
                "are you a script", "is this a script", "are you a bot",
                "is this a bot", "are you a chatbot", "is this a chatbot",
                "are you a virtual assistant", "is this a virtual assistant",
                "are you a digital assistant", "is this a digital assistant",
                "are you an ai assistant", "is this an ai assistant",
                "are you an artificial intelligence", "is this artificial intelligence",
                "are you a machine learning", "is this machine learning",
                "are you a neural network", "is this a neural network",
                "are you a deep learning", "is this deep learning",
                "are you a natural language processing", "is this natural language processing",
                "are you an nlp", "is this an nlp", "are you a language model",
                "is this a language model", "are you a transformer", "is this a transformer",
                "are you a gpt", "is this a gpt", "are you a large language model",
                "is this a large language model", "are you an llm", "is this an llm",
                "are you a generative ai", "is this generative ai",
                "are you a conversational ai", "is this conversational ai",
                "are you a dialogue system", "is this a dialogue system",
                "are you a speech recognition", "is this speech recognition",
                "are you a voice recognition", "is this voice recognition",
                "are you a text to speech", "is this text to speech",
                "are you a speech to text", "is this speech to text",
                "are you a voice synthesis", "is this voice synthesis",
                "are you a voice generation", "is this voice generation",
                "are you a voice cloning", "is this voice cloning",
                "are you a voice replication", "is this voice replication",
                "are you a voice simulation", "is this voice simulation",
                "are you a voice emulation", "is this voice emulation",
                "are you a voice mimicry", "is this voice mimicry",
                "are you a voice imitation", "is this voice imitation",
                "are you a voice reproduction", "is this voice reproduction",
                "are you a voice copy", "is this a voice copy",
                "are you a voice duplicate", "is this a voice duplicate",
                "are you a voice replica", "is this a voice replica",
                "are you a voice facsimile", "is this a voice facsimile",
                "are you a voice reproduction", "is this voice reproduction",
                "are you a voice simulation", "is this voice simulation",
                "are you a voice emulation", "is this voice emulation",
                "are you a voice mimicry", "is this voice mimicry",
                "are you a voice imitation", "is this voice imitation",
                "are you a voice copy", "is this a voice copy",
                "are you a voice duplicate", "is this a voice duplicate",
                "are you a voice replica", "is this a voice replica",
                "are you a voice facsimile", "is this a voice facsimile"
            ],
            "memory_questions": [
                # Memory/recall questions with all variations
                "don't remember", "don't recall", "never heard of you", "never worked with",
                "don't know you", "who did i work with", "i don't remember working with you",
                "don't remember working with you", "never worked with you", "don't know you",
                "i don't remember", "i don't recall", "i don't know you",
                "i've never heard of you", "i've never worked with you",
                "i don't know who you are", "i don't recognize you",
                "i don't recognize your company", "i don't recognize your business",
                "i don't recognize your organization", "i don't remember your company",
                "i don't remember your business", "i don't remember your organization",
                "i don't recall your company", "i don't recall your business",
                "i don't recall your organization", "i don't know your company",
                "i don't know your business", "i don't know your organization",
                "i've never heard of your company", "i've never heard of your business",
                "i've never heard of your organization", "i don't remember working with you",
                "i don't recall working with you", "i don't know who i worked with",
                "i don't remember who i worked with", "i don't recall who i worked with",
                "i don't know who helped me", "i don't remember who helped me",
                "i don't recall who helped me", "i don't know who assisted me",
                "i don't remember who assisted me", "i don't recall who assisted me",
                "i don't know who my agent was", "i don't remember who my agent was",
                "i don't recall who my agent was", "i don't know who my representative was",
                "i don't remember who my representative was", "i don't recall who my representative was",
                "i don't know who my advisor was", "i don't remember who my advisor was",
                "i don't recall who my advisor was", "i don't know who my consultant was",
                "i don't remember who my consultant was", "i don't recall who my consultant was",
                "i don't know who my broker was", "i don't remember who my broker was",
                "i don't recall who my broker was", "i don't know who my agent is",
                "i don't remember who my agent is", "i don't recall who my agent is",
                "i don't know who my representative is", "i don't remember who my representative is",
                "i don't recall who my representative is", "i don't know who my advisor is",
                "i don't remember who my advisor is", "i don't recall who my advisor is",
                "i don't know who my consultant is", "i don't remember who my consultant is",
                "i don't recall who my consultant is", "i don't know who my broker is",
                "i don't remember who my broker is", "i don't recall who my broker is",
                "i don't know who helped me before", "i don't remember who helped me before",
                "i don't recall who helped me before", "i don't know who assisted me before",
                "i don't remember who assisted me before", "i don't recall who assisted me before",
                "i don't know who my previous agent was", "i don't remember who my previous agent was",
                "i don't recall who my previous agent was", "i don't know who my last agent was",
                "i don't remember who my last agent was", "i don't recall who my last agent was",
                "i don't know who i spoke with before", "i don't remember who i spoke with before",
                "i don't recall who i spoke with before", "i don't know who i talked to before",
                "i don't remember who i talked to before", "i don't recall who i talked to before",
                "i don't know who i worked with before", "i don't remember who i worked with before",
                "i don't recall who i worked with before", "i don't know who i dealt with before",
                "i don't remember who i dealt with before", "i don't recall who i dealt with before",
                "i don't know who i had before", "i don't remember who i had before",
                "i don't recall who i had before", "i don't know who was helping me",
                "i don't remember who was helping me", "i don't recall who was helping me",
                "i don't know who was assisting me", "i don't remember who was assisting me",
                "i don't recall who was assisting me", "i don't know who was my agent",
                "i don't remember who was my agent", "i don't recall who was my agent",
                "i don't know who was my representative", "i don't remember who was my representative",
                "i don't recall who was my representative", "i don't know who was my advisor",
                "i don't remember who was my advisor", "i don't recall who was my advisor",
                "i don't know who was my consultant", "i don't remember who was my consultant",
                "i don't recall who was my consultant", "i don't know who was my broker",
                "i don't remember who was my broker", "i don't recall who was my broker",
                "i don't know who was helping me before", "i don't remember who was helping me before",
                "i don't recall who was helping me before", "i don't know who was assisting me before",
                "i don't remember who was assisting me before", "i don't recall who was assisting me before",
                "i don't know who was my previous agent", "i don't remember who was my previous agent",
                "i don't recall who was my previous agent", "i don't know who was my last agent",
                "i don't remember who was my last agent", "i don't recall who was my last agent",
                "i don't know who was my agent before", "i don't remember who was my agent before",
                "i don't recall who was my agent before", "i don't know who was my representative before",
                "i don't remember who was my representative before", "i don't recall who was my representative before",
                "i don't know who was my advisor before", "i don't remember who was my advisor before",
                "i don't recall who was my advisor before", "i don't know who was my consultant before",
                "i don't remember who was my consultant before", "i don't recall who was my consultant before",
                "i don't know who was my broker before", "i don't remember who was my broker before",
                "i don't recall who was my broker before", "i don't know who was helping me last time",
                "i don't remember who was helping me last time", "i don't recall who was helping me last time",
                "i don't know who was assisting me last time", "i don't remember who was assisting me last time",
                "i don't recall who was assisting me last time", "i don't know who was my agent last time",
                "i don't remember who was my agent last time", "i don't recall who was my agent last time",
                "i don't know who was my representative last time", "i don't remember who was my representative last time",
                "i don't recall who was my representative last time", "i don't know who was my advisor last time",
                "i don't remember who was my advisor last time", "i don't recall who was my advisor last time",
                "i don't know who was my consultant last time", "i don't remember who was my consultant last time",
                "i don't recall who was my consultant last time", "i don't know who was my broker last time",
                "i don't remember who was my broker last time", "i don't recall who was my broker last time"
            ],
            "repeat_requests": [
                # Repeat/rephrase requests with all variations
                "can you repeat", "say that again", "didn't catch that", "what did you say",
                "could you repeat", "pardon", "excuse me", "come again", "i didn't hear that",
                "i didn't catch that", "i didn't get that", "i didn't understand that",
                "i didn't hear you", "i didn't catch you", "i didn't get you",
                "i didn't understand you", "i didn't hear what you said",
                "i didn't catch what you said", "i didn't get what you said",
                "i didn't understand what you said", "i didn't hear your name",
                "i didn't catch your name", "i didn't get your name",
                "i didn't understand your name", "i didn't hear your company",
                "i didn't catch your company", "i didn't get your company",
                "i didn't understand your company", "i didn't hear your business",
                "i didn't catch your business", "i didn't get your business",
                "i didn't understand your business", "i didn't hear your organization",
                "i didn't catch your organization", "i didn't get your organization",
                "i didn't understand your organization", "i didn't hear where you're from",
                "i didn't catch where you're from", "i didn't get where you're from",
                "i didn't understand where you're from", "i didn't hear who you are",
                "i didn't catch who you are", "i didn't get who you are",
                "i didn't understand who you are", "i didn't hear what you said",
                "i didn't catch what you said", "i didn't get what you said",
                "i didn't understand what you said", "i didn't hear the name",
                "i didn't catch the name", "i didn't get the name",
                "i didn't understand the name", "i didn't hear the company",
                "i didn't catch the company", "i didn't get the company",
                "i didn't understand the company", "i didn't hear the business",
                "i didn't catch the business", "i didn't get the business",
                "i didn't understand the business", "i didn't hear the organization",
                "i didn't catch the organization", "i didn't get the organization",
                "i didn't understand the organization", "i didn't hear where you're calling from",
                "i didn't catch where you're calling from", "i didn't get where you're calling from",
                "i didn't understand where you're calling from", "i didn't hear who you're calling for",
                "i didn't catch who you're calling for", "i didn't get who you're calling for",
                "i didn't understand who you're calling for", "i didn't hear what this is about",
                "i didn't catch what this is about", "i didn't get what this is about",
                "i didn't understand what this is about", "i didn't hear the purpose",
                "i didn't catch the purpose", "i didn't get the purpose",
                "i didn't understand the purpose", "i didn't hear the reason",
                "i didn't catch the reason", "i didn't get the reason",
                "i didn't understand the reason", "i didn't hear the call",
                "i didn't catch the call", "i didn't get the call",
                "i didn't understand the call", "i didn't hear the message",
                "i didn't catch the message", "i didn't get the message",
                "i didn't understand the message", "i didn't hear the information",
                "i didn't catch the information", "i didn't get the information",
                "i didn't understand the information", "i didn't hear the details",
                "i didn't catch the details", "i didn't get the details",
                "i didn't understand the details", "i didn't hear the explanation",
                "i didn't catch the explanation", "i didn't get the explanation",
                "i didn't understand the explanation", "i didn't hear the context",
                "i didn't catch the context", "i didn't get the context",
                "i didn't understand the context", "i didn't hear the background",
                "i didn't catch the background", "i didn't get the background",
                "i didn't understand the background", "i didn't hear the story",
                "i didn't catch the story", "i didn't get the story",
                "i didn't understand the story", "i didn't hear the situation",
                "i didn't catch the situation", "i didn't get the situation",
                "i didn't understand the situation", "i didn't hear the circumstances",
                "i didn't catch the circumstances", "i didn't get the circumstances",
                "i didn't understand the circumstances", "i didn't hear the reason for the call",
                "i didn't catch the reason for the call", "i didn't get the reason for the call",
                "i didn't understand the reason for the call", "i didn't hear why you're calling",
                "i didn't catch why you're calling", "i didn't get why you're calling",
                "i didn't understand why you're calling", "i didn't hear what you want",
                "i didn't catch what you want", "i didn't get what you want",
                "i didn't understand what you want", "i didn't hear what you need",
                "i didn't catch what you need", "i didn't get what you need",
                "i didn't understand what you need", "i didn't hear what you're offering",
                "i didn't catch what you're offering", "i didn't get what you're offering",
                "i didn't understand what you're offering", "i didn't hear what you're selling",
                "i didn't catch what you're selling", "i didn't get what you're selling",
                "i didn't understand what you're selling", "i didn't hear what you're promoting",
                "i didn't catch what you're promoting", "i didn't get what you're promoting",
                "i didn't understand what you're promoting", "i didn't hear what you're advertising",
                "i didn't catch what you're advertising", "i didn't get what you're advertising",
                "i didn't understand what you're advertising", "i didn't hear what you're marketing",
                "i didn't catch what you're marketing", "i didn't get what you're marketing",
                "i didn't understand what you're marketing", "i didn't hear what you're providing",
                "i didn't catch what you're providing", "i didn't get what you're providing",
                "i didn't understand what you're providing", "i didn't hear what you're giving",
                "i didn't catch what you're giving", "i didn't get what you're giving",
                "i didn't understand what you're giving", "i didn't hear what you're offering",
                "i didn't catch what you're offering", "i didn't get what you're offering",
                "i didn't understand what you're offering", "i didn't hear what you're providing",
                "i didn't catch what you're providing", "i didn't get what you're providing",
                "i didn't understand what you're providing", "i didn't hear what you're giving",
                "i didn't catch what you're giving", "i didn't get what you're giving",
                "i didn't understand what you're giving", "i didn't hear what you're offering",
                "i didn't catch what you're offering", "i didn't get what you're offering",
                "i didn't understand what you're offering", "i didn't hear what you're providing",
                "i didn't catch what you're providing", "i didn't get what you're providing",
                "i didn't understand what you're providing", "i didn't hear what you're giving",
                "i didn't catch what you're giving", "i didn't get what you're giving",
                "i didn't understand what you're giving"
            ],
            
            # Interruption patterns
            "interruption_commands": [
                "wait", "stop", "hold on", "pause", "hang on", "just a minute", "one second",
                "hold up", "slow down", "not so fast", "wait a minute", "wait a second",
                "hold on a second", "hang on a minute", "just wait", "stop talking",
                "be quiet", "shut up", "quiet", "silence", "enough", "that's enough"
            ],
            
            # Voicemail detection patterns
            "voicemail_patterns": [
                "you've reached", "leave a message", "voicemail", "after the tone",
                "record your message", "leave your message", "at the sound of the tone",
                "beep", "message box", "voice mailbox", "answering machine",
                "call back", "call me back", "return my call", "get back to me",
                "i'll call you back", "i'll get back to you", "i'll return your call"
            ],
            
            # Busy/call back patterns
            "busy_patterns": [
                "i'm busy", "call me back", "call back later", "i'm in a meeting",
                "i'm driving", "i'm at work", "i'm in the middle of something",
                "i can't talk right now", "not a good time", "bad timing",
                "i'm occupied", "i'm tied up", "i'm unavailable", "i'm unavailable right now"
            ]
        }
        
        # Enhanced delay filling responses for LYZR processing
        self.delay_fillers = [
            "That's a great question, let me make sure I give you the most accurate information.",
            "I want to provide you with the best answer possible, please give me just a moment.",
            "Let me check on that for you to ensure I'm giving you the correct details.",
            "That's an excellent point, let me get you the most up-to-date information.",
            "I appreciate you asking that, let me pull up the specifics for you.",
            "That's a very good question, let me look into that for you right away.",
            "I want to make sure I give you the right information, just a moment please.",
            "Let me verify that information for you to ensure accuracy.",
            "That's an important question, let me get the most current details for you.",
            "I want to provide you with the most helpful answer, please give me a moment.",
            "Let me check our records to give you the most accurate response.",
            "That's a thoughtful question, let me gather the right information for you.",
            "I want to make sure I have the latest information for you, just a moment.",
            "Let me look that up for you to ensure I give you the correct answer.",
            "That's a great point, let me get you the most up-to-date details."
        ]
        
        # Silence detection responses (matching user requirements)
        self.silence_responses = {
            "first": "I'm sorry, I didn't hear anything. Did you say something?",
            "second": "I'm sorry, I didn't hear anything. Did you say something?",
            "final": "You can call us back at 8-3-3, 2-2-7, 8-5-0-0. Have a great day."
        }
        
        self._configure()
    
    def _configure(self):
        """Configure the voice processor"""
        try:
            self._configured = True
            logger.info("✅ Enhanced Voice Processor configured successfully")
        except Exception as e:
            logger.error(f"❌ Voice Processor configuration error: {e}")
            self._configured = False
    
    def is_configured(self) -> bool:
        """Check if voice processor is configured"""
        return self._configured
    
    async def process_customer_input(
        self, 
        customer_input: str, 
        session: CallSession, 
        confidence: float = 0.8,
        is_interruption: bool = False
    ) -> Dict[str, Any]:
        """
        Enhanced processing with clarifying questions and interruption handling
        """
        start_time = time.time()
        
        # Handle interruptions
        if is_interruption:
            return await self._handle_interruption(customer_input, session, start_time)
        
        # Sanitize input
        customer_input = customer_input.lower().strip().replace(".", "").replace(",", "")
        
        logger.info(
            f"🗣️ Processing input: '{customer_input}' for session {session.session_id} "
            f"in stage: {session.conversation_stage.value if hasattr(session.conversation_stage, 'value') else session.conversation_stage}"
        )
        
        try:
            # PRIORITY 1: Check for clarifying questions FIRST (before state machine)
            clarifying_response = await self._check_clarifying_questions(customer_input, session, start_time)
            if clarifying_response:
                return clarifying_response
            
            # PRIORITY 2: State machine logic for conversation flow
            if session.conversation_stage == ConversationStage.GREETING:
                if self._is_interested(customer_input):
                    return await self._handle_initial_interest(session, start_time)
                elif self._is_not_interested(customer_input):
                    return await self._handle_initial_disinterest(session, start_time)
                elif self._is_dnc_request(customer_input):
                    return await self._handle_dnc_request(session, start_time)
                elif self._is_maybe(customer_input):
                    return await self._handle_maybe_response(session, start_time)
                else:
                    # Check if this is an unrecognized question that should go to Lyzr
                    if self._is_question(customer_input):
                        return await self._handle_unknown_question(customer_input, session, start_time)
                    else:
                        return await self._handle_unclear_response(session, start_time, "greeting")
            
            elif session.conversation_stage == ConversationStage.SCHEDULING:
                if self._is_interested(customer_input):
                    return await self._handle_scheduling_confirmation(session, start_time)
                elif self._is_not_interested(customer_input):
                    return await self._handle_scheduling_rejection(session, start_time)
                elif self._is_dnc_request(customer_input):
                    return await self._handle_dnc_request(session, start_time)
                else:
                    # Check if this is an unrecognized question that should go to Lyzr
                    if self._is_question(customer_input):
                        return await self._handle_unknown_question(customer_input, session, start_time)
                    else:
                        return await self._handle_unclear_response(session, start_time, "scheduling")
            
            elif session.conversation_stage == ConversationStage.DNC_CHECK:
                if self._is_interested(customer_input):
                    return await self._handle_keep_communications(session, start_time)
                elif self._is_not_interested(customer_input) or self._is_dnc_request(customer_input):
                    return await self._handle_dnc_confirmation(session, start_time)
                else:
                    # Check if this is an unrecognized question that should go to Lyzr
                    if self._is_question(customer_input):
                        return await self._handle_unknown_question(customer_input, session, start_time)
                    else:
                        return await self._handle_unclear_response(session, start_time, "dnc_check")
            
            # If we're in GOODBYE or any unexpected stage, end the call
            else:
                logger.info(f"✅ In final stage: {session.conversation_stage.value if hasattr(session.conversation_stage, 'value') else session.conversation_stage}")
                return await self._create_response(
                    response_text="Thank you for your time today. Have a wonderful day!",
                    response_category="goodbye",
                    conversation_stage=ConversationStage.GOODBYE,
                    end_conversation=True,
                    outcome="completed",
                    start_time=start_time,
                    detected_intent="completed",
                    session=session
                )
                
        except Exception as e:
            logger.error(f"❌ Voice processing error: {e}")
            return await self._create_response(
                response_text="I apologize, I'm having some technical difficulties. Thank you for your patience.",
                response_category="error",
                conversation_stage=ConversationStage.GOODBYE,
                end_conversation=True,
                outcome="error",
                start_time=start_time,
                detected_intent="error",
                session=session
            )
    
    async def _check_clarifying_questions(
        self, 
        customer_input: str, 
        session: CallSession, 
        start_time: float
    ) -> Optional[Dict[str, Any]]:
        """Check for and handle clarifying questions"""
        
        # Identity questions: "Who is this?", "Where are you calling from?", "What is this about?"
        if any(phrase in customer_input for phrase in self.response_patterns["identity_questions"]):
            return await self._handle_identity_question(customer_input, session, start_time)
        
        # AI questions: "Are you an AI?"
        if any(phrase in customer_input for phrase in self.response_patterns["ai_questions"]):
            return await self._handle_ai_question(customer_input, session, start_time)
        
        # Memory questions: "I don't remember working with you"
        if any(phrase in customer_input for phrase in self.response_patterns["memory_questions"]):
            return await self._handle_memory_question(customer_input, session, start_time)
        
        # Repeat requests: "Can you say that again?"
        if any(phrase in customer_input for phrase in self.response_patterns["repeat_requests"]):
            return await self._handle_repeat_request(customer_input, session, start_time)
        
        # Interruption commands: "Wait", "Stop"
        if any(phrase in customer_input for phrase in self.response_patterns["interruption_commands"]):
            return await self._handle_interruption_command(customer_input, session, start_time)
        
        # Busy/call back requests: "I'm busy, call me back" (PRIORITY: Check before voicemail)
        if any(phrase in customer_input for phrase in self.response_patterns["busy_patterns"]):
            return await self._handle_busy_call_back(customer_input, session, start_time)
        
        # Voicemail detection: "You've reached..." (Check after busy patterns)
        if any(phrase in customer_input for phrase in self.response_patterns["voicemail_patterns"]):
            return await self._handle_voicemail_detection(customer_input, session, start_time)
        
        return None
    
    async def _handle_identity_question(self, customer_input: str, session: CallSession, start_time: float) -> Dict[str, Any]:
        """Handle 'Who is this?' or 'Where are you calling from?' questions"""
        
        client_name = session.client_data.get("first_name", "")
        
        return await self._create_response(
            response_text=(
                f"Hi {client_name}, this is Alex from Altruis Advisor Group. "
                f"We're a health insurance brokerage that's helped you in the past. "
                f"I'm calling to see if we can assist you during this year's Open Enrollment. "
                f"Would you be interested in reviewing your options?"
            ),
            response_category="identity_clarification",
            conversation_stage=session.conversation_stage,  # Stay in same stage
            end_conversation=False,
            outcome="identity_clarified",
            start_time=start_time,
            detected_intent="identity_question",
            session=session
        )
    
    async def _handle_ai_question(self, customer_input: str, session: CallSession, start_time: float) -> Dict[str, Any]:
        """Handle 'Are you an AI?' questions"""
        
        return await self._create_response(
            response_text=(
                "I'm Alex, a representative from Altruis Advisor Group. "
                "I'm calling because we've helped you with health insurance before, "
                "and I wanted to see if we could assist you this year. "
                "Would you be interested in exploring your options?"
            ),
            response_category="ai_clarification",
            conversation_stage=session.conversation_stage,  # Stay in same stage
            end_conversation=False,
            outcome="ai_question_handled",
            start_time=start_time,
            detected_intent="ai_question",
            session=session
        )
    
    async def _handle_memory_question(self, customer_input: str, session: CallSession, start_time: float) -> Dict[str, Any]:
        """Handle 'I don't remember working with you' questions"""
        
        agent_name = session.client_data.get("last_agent", "our team")
        # Use specific agent name if available, otherwise use "our team"
        if agent_name and agent_name != "our team":
            agent_reference = f"{agent_name} here at Altruis"
        else:
            agent_reference = "one of our agents here at Altruis"
        
        return await self._create_response(
            response_text=(
                f"No worries at all! You previously worked with {agent_reference} "
                f"for your health insurance needs. We're a brokerage that helps people find "
                f"the best coverage options. Since it's Open Enrollment season, I wanted to "
                f"reach out to see if you'd like assistance this year. Are you interested?"
            ),
            response_category="memory_clarification",
            conversation_stage=session.conversation_stage,  # Stay in same stage
            end_conversation=False,
            outcome="memory_clarified",
            start_time=start_time,
            detected_intent="memory_question",
            session=session
        )
    
    async def _handle_repeat_request(self, customer_input: str, session: CallSession, start_time: float) -> Dict[str, Any]:
        """Handle 'Can you repeat that?' requests"""
        
        client_name = session.client_data.get("first_name", "")
        
        return await self._create_response(
            response_text=(
                f"Of course! I'm Alex from Altruis Advisor Group. We've helped you "
                f"with health insurance before, and I'm calling to see if we can "
                f"assist you during Open Enrollment this year. Are you interested "
                f"in reviewing your options?"
            ),
            response_category="repeat_response",
            conversation_stage=session.conversation_stage,  # Stay in same stage
            end_conversation=False,
            outcome="repeated_message",
            start_time=start_time,
            detected_intent="repeat_request",
            session=session
        )
    
    async def _handle_interruption_command(self, customer_input: str, session: CallSession, start_time: float) -> Dict[str, Any]:
        """Handle interruption commands like 'Wait', 'Stop'"""
        
        logger.info(f"🛑 Customer interruption command: '{customer_input}'")
        
        return await self._create_response(
            response_text="Of course, I'm here to help. What would you like to know?",
            response_category="interruption_acknowledgment",
            conversation_stage=session.conversation_stage,
            end_conversation=False,
            outcome="interruption_acknowledged",
            start_time=start_time,
            detected_intent="interruption_command",
            session=session
        )
    
    async def _handle_voicemail_detection(self, customer_input: str, session: CallSession, start_time: float) -> Dict[str, Any]:
        """Handle voicemail detection"""
        
        logger.info(f"📞 Voicemail detected: '{customer_input}'")
        
        # Check if client has Medicare tag
        client_tags = session.client_data.get("tags", "")
        if "Non-Medicare" in client_tags:
            response_text = (
                "Hi, this is Alex from Altruis Advisor Group. I'm calling about your health insurance coverage. "
                "Please call us back at 833-227-8500 when you're available. Thank you!"
            )
            response_category = "non_medicare_voicemail"
        elif "Medicare" in client_tags:
            response_text = (
                "Hi, this is Alex from Altruis Advisor Group. I'm calling about your Medicare coverage. "
                "Please call us back at 833-227-8500 when you're available. Thank you!"
            )
            response_category = "medicare_voicemail"
        else:
            response_text = (
                "Hi, this is Alex from Altruis Advisor Group. I'm calling about your health insurance coverage. "
                "Please call us back at 833-227-8500 when you're available. Thank you!"
            )
            response_category = "voicemail"
        
        return await self._create_response(
            response_text=response_text,
            response_category=response_category,
            conversation_stage=ConversationStage.VOICEMAIL,
            end_conversation=True,
            outcome="voicemail",
            start_time=start_time,
            detected_intent="voicemail",
            session=session
        )
    
    async def _handle_busy_call_back(self, customer_input: str, session: CallSession, start_time: float) -> Dict[str, Any]:
        """Handle busy/call back requests"""
        
        logger.info(f"📞 Busy/call back request: '{customer_input}'")
        
        return await self._create_response(
            response_text=(
                "No problem at all! I'll call you back at a better time. "
                "Have a great day!"
            ),
            response_category="busy_call_back",
            conversation_stage=ConversationStage.CLOSING,
            end_conversation=True,
            outcome="busy_call_back",
            start_time=start_time,
            detected_intent="busy_call_back",
            session=session
        )
    
    async def _handle_unknown_question(self, customer_input: str, session: CallSession, start_time: float) -> Dict[str, Any]:
        """Handle unrecognized questions by routing to Lyzr agent"""
        
        logger.info(f"🤖 Routing unknown question to Lyzr: '{customer_input}'")
        
        # Use Lyzr agent for intelligent response
        return await self.process_with_lyzr_delay_filler(
            customer_input=customer_input,
            session=session
        )
    
    async def _handle_interruption(
        self, 
        customer_input: str, 
        session: CallSession, 
        start_time: float
    ) -> Dict[str, Any]:
        """Handle customer interruptions while agent is speaking"""
        
        logger.info(f"🛑 Customer interrupted: '{customer_input}'")
        
        # Quick responses for common interruptions
        if any(word in customer_input.lower() for word in ["yes", "yeah", "okay", "sure"]):
            return await self._create_response(
                response_text="Great! Let me continue with the details.",
                response_category="interruption_acknowledgment",
                conversation_stage=session.conversation_stage,
                end_conversation=False,
                outcome="interruption_positive",
                start_time=start_time,
                detected_intent="positive_interruption",
                session=session
            )
        
        elif any(word in customer_input.lower() for word in ["no", "stop", "wait"]):
            return await self._create_response(
                response_text="I understand. What would you like to know?",
                response_category="interruption_acknowledgment",
                conversation_stage=session.conversation_stage,
                end_conversation=False,
                outcome="interruption_negative",
                start_time=start_time,
                detected_intent="negative_interruption",
                session=session
            )
        
        else:
            return await self._create_response(
                response_text="Yes? How can I help you?",
                response_category="interruption_acknowledgment",
                conversation_stage=session.conversation_stage,
                end_conversation=False,
                outcome="interruption_unclear",
                start_time=start_time,
                detected_intent="unclear_interruption",
                session=session
            )
    
    async def process_with_lyzr_delay_filler(
        self, 
        customer_input: str, 
        session: CallSession
    ) -> Dict[str, Any]:
        """Process complex questions with LYZR while providing delay filler"""
        
        start_time = time.time()
        
        # Get a delay filler response
        import random
        filler_text = random.choice(self.delay_fillers)
        
        # Start LYZR processing in background
        lyzr_task = asyncio.create_task(self._process_with_lyzr_agent(customer_input, session))
        
        # Store the task in session for later retrieval
        session.lyzr_pending_task = lyzr_task
        
        # Return immediate filler response
        response = await self._create_response(
            response_text=filler_text,
            response_category="lyzr_delay_filler",
            conversation_stage=session.conversation_stage,
            end_conversation=False,
            outcome="processing_complex_question",
            start_time=start_time,
            detected_intent="complex_question",
            session=session
        )
        
        # Clear the task from response to avoid database serialization issues
        if "lyzr_task" in response:
            del response["lyzr_task"]
        
        return response
    
    async def _process_with_lyzr_agent(self, customer_input: str, session: CallSession) -> Dict[str, Any]:
        """Process complex questions with LYZR agent"""
        
        try:
            from services.lyzr_client import lyzr_client
            
            if not lyzr_client.is_configured():
                return {"success": False, "error": "LYZR not configured"}
            
            # Get LYZR response with timing
            start_time = time.time()
            lyzr_result = await lyzr_client.get_agent_response(
                session_id=session.lyzr_session_id,
                customer_message=customer_input,
                context={
                    "conversation_stage": session.conversation_stage.value if hasattr(session.conversation_stage, 'value') else session.conversation_stage,
                    "client_name": session.client_data.get("first_name", ""),
                    "is_first_interaction": len(session.conversation_turns) == 0,
                    "call_duration_seconds": int((time.time() - session.started_at.timestamp())),
                    "previous_response": session.conversation_turns[-1].agent_response if session.conversation_turns else "",
                    "agent_name": session.client_data.get("last_agent", "our team"),
                    "client_phone": session.phone_number
                }
            )
            lyzr_response_time = time.time() - start_time
            
            if lyzr_result["success"]:
                # Add conversation continuity - after LYZR response, return to main flow
                lyzr_response = lyzr_result["response"]
                
                # Check if LYZR response is good quality (not too short, not error-like)
                if len(lyzr_response.strip()) < 20 or "error" in lyzr_response.lower() or "sorry" in lyzr_response.lower():
                    # Use fallback if LYZR response is poor
                    fallback_response = (
                        "I'd be happy to have one of our specialists call you back with detailed information. "
                        "But first, let me ask - are you interested in reviewing your health insurance options this year?"
                    )
                    return {
                        "success": True,
                        "response_text": fallback_response,
                        "lyzr_used": False,
                        "fallback_used": True,
                        "lyzr_response_time": lyzr_response_time,
                        "return_to_main_flow": True
                    }
                else:
                    # Good LYZR response - add conversation continuity
                    continuity_text = (
                        "Now, getting back to why I called - are you interested in reviewing your health insurance options "
                        "for this year's open enrollment? A simple yes or no would be great."
                    )
                
                return {
                    "success": True,
                    "response_text": f"{lyzr_response} {continuity_text}",
                    "lyzr_used": True,
                    "lyzr_response_time": lyzr_response_time,
                    "return_to_main_flow": True,
                    "session_ended": lyzr_result.get("session_ended", False)
                }
            else:
                # LYZR failed, use fallback with conversation continuity
                fallback_response = (
                    "I'd be happy to have one of our specialists call you back with detailed information. "
                    "But first, let me ask - are you interested in reviewing your health insurance options this year?"
                )
                return {
                    "success": True,
                    "response_text": fallback_response,
                    "lyzr_used": False,
                    "fallback_used": True,
                    "lyzr_response_time": lyzr_response_time,
                    "return_to_main_flow": True
                }
                
        except Exception as e:
            logger.error(f"❌ LYZR processing error: {e}")
            fallback_response = (
                "Let me have a specialist call you back with that information. "
                "But first, let me ask - are you interested in reviewing your health insurance options this year?"
            )
            return {
                "success": True,
                "response_text": fallback_response,
                "lyzr_used": False,
                "fallback_used": True,
                "return_to_main_flow": True
            }
    
    async def check_lyzr_response_ready(self, session: CallSession) -> Optional[Dict[str, Any]]:
        """Check if LYZR response is ready and return it if available"""
        
        if hasattr(session, 'lyzr_pending_task') and session.lyzr_pending_task:
            try:
                # Check if task is done without waiting
                if session.lyzr_pending_task.done():
                    result = session.lyzr_pending_task.result()
                    session.lyzr_pending_task = None  # Clear the task
                    logger.info(f"🤖 LYZR response ready: {result.get('response_text', 'No response text')[:50]}...")
                    return result
                else:
                    logger.debug("🤖 LYZR task still running...")
                    return None  # Task still running
            except Exception as e:
                logger.error(f"❌ Error checking LYZR task: {e}")
                session.lyzr_pending_task = None  # Clear the task
                return None
        
        return None
    
    async def process_customer_input_with_lyzr_check(
        self, 
        customer_input: str, 
        session: CallSession, 
        confidence: float = 0.8,
        is_interruption: bool = False
    ) -> Dict[str, Any]:
        """
        Process customer input with LYZR response checking
        """
        # First check if there's a pending LYZR response
        lyzr_response = await self.check_lyzr_response_ready(session)
        if lyzr_response:
            logger.info("🤖 Returning LYZR response to customer")
            return lyzr_response
        
        # If no LYZR response pending, process normally
        return await self.process_customer_input(customer_input, session, confidence, is_interruption)
    
    # --- Helper methods for checking input patterns ---
    
    def _is_interested(self, text: str) -> bool:
        """Check if input indicates interest"""
        # Check for explicit no/not interested first to avoid conflicts
        if any(phrase in text for phrase in ["not interested", "no thanks", "don't think so", "not at this time"]):
            return False
        
        # Check for uncertain/acknowledgment responses that should NOT be considered interest
        uncertain_responses = ["thanks", "thank you", "i'm not sure", "not sure", "maybe", "i don't know", "i don't understand", "let me think", "let me think about it"]
        if any(word in text for word in uncertain_responses):
            return False
        
        # Single word "okay" or "ok" should be treated as acknowledgment, not strong interest
        if text.strip().lower() in ["okay", "ok"]:
            return False
            
        # Only consider strong affirmative responses as interest
        strong_interest_words = ["yes", "yeah", "yep", "sure", "absolutely", "definitely", "of course", "sounds good", "that's fine", "it will", "i would", "i am", "i'm interested", "interested", "sounds like a good idea", "that sounds good", "i think so", "probably", "likely"]
        return any(word in text for word in strong_interest_words)
    
    def _is_not_interested(self, text: str) -> bool:
        """Check if input indicates no interest"""
        # Don't classify uncertain responses as "not interested" - they should go to clarification
        uncertain_phrases = ["i'm not sure", "not sure", "maybe", "i don't know", "let me think"]
        if any(phrase in text for phrase in uncertain_phrases):
            return False
            
        return any(word in text for word in self.response_patterns["no_responses"])
    
    def _is_maybe(self, text: str) -> bool:
        """Check if input is uncertain"""
        return any(word in text for word in self.response_patterns["maybe_responses"])
    
    def _is_dnc_request(self, text: str) -> bool:
        """Check if input is a DNC request"""
        return any(phrase in text for phrase in self.response_patterns["dnc_requests"])
    
    def _is_question(self, text: str) -> bool:
        """Check if input is a question (not already handled by static responses)"""
        # Skip very short unclear responses that should go to clarification
        if text.strip() in ["what", "huh", "what?", "huh?"]:
            return False
            
        # Question indicators
        question_words = ["what", "when", "where", "who", "why", "how", "which", "whose", "whom"]
        question_indicators = ["?", "can you", "could you", "would you", "will you", "do you", "does", "is", "are", "was", "were"]
        
        # Check if text contains question words or indicators
        has_question_word = any(word in text for word in question_words)
        has_question_indicator = any(indicator in text for indicator in question_indicators)
        
        return has_question_word or has_question_indicator
    
    # --- State transition handlers (same as before) ---
    
    async def _handle_initial_interest(self, session: CallSession, start_time: float) -> Dict[str, Any]:
        """Handle when user expresses initial interest - First 'Yes'"""
        logger.info("✅ Customer interested in service - Moving to SCHEDULING stage")
        
        agent_name = session.client_data.get("last_agent", "our team")
        # Use "them" for better flow if agent name is available, otherwise use "our team"
        if agent_name and agent_name != "our team":
            agent_reference = f"{agent_name} was the last agent you worked with here at Altruis"
        else:
            agent_reference = "one of our agents was the last agent you worked with here at Altruis"
        
        session.conversation_stage = ConversationStage.SCHEDULING
        
        return await self._create_response(
            response_text=(
                f"Great, looks like {agent_reference} – "
                f"would you like to schedule a quick 15-minute discovery call with them to get reacquainted? "
                f"A simple 'Yes' or 'No' will do!"
            ),
            response_category="agent_introduction",
            conversation_stage=ConversationStage.SCHEDULING,
            end_conversation=False,
            outcome="interested",
            start_time=start_time,
            detected_intent="interested",
            session=session
        )
    
    async def _handle_initial_disinterest(self, session: CallSession, start_time: float) -> Dict[str, Any]:
        """Handle when user is not interested - First 'No'"""
        logger.info("❌ Customer not interested - Moving to DNC_CHECK stage")
        
        session.conversation_stage = ConversationStage.DNC_CHECK
        
        return await self._create_response(
            response_text=(
                "No problem at all! Would you like to continue receiving occasional "
                "health insurance updates from our team? We promise to keep them "
                "informative and not overwhelming. A simple yes or no will do!"
            ),
            response_category="not_interested",
            conversation_stage=ConversationStage.DNC_CHECK,
            end_conversation=False,
            outcome="not_interested",
            start_time=start_time,
            detected_intent="not_interested",
            session=session
        )
    
    async def _handle_scheduling_confirmation(self, session: CallSession, start_time: float) -> Dict[str, Any]:
        """Handle when user confirms they want to schedule - Second 'Yes'"""
        logger.info("✅ Customer confirmed scheduling - Ending call with success")
        
        agent_name = session.client_data.get("last_agent", "our team")
        # Use specific agent name if available, otherwise use "our team"
        if agent_name and agent_name != "our team":
            agent_reference = f"{agent_name}'s"
        else:
            agent_reference = "our team's"
        
        session.conversation_stage = ConversationStage.GOODBYE
        
        return await self._create_response(
            response_text=(
                f"Perfect! You'll receive an email with {agent_reference} available time slots. "
                f"Simply click on the time that works best for you. "
                f"Thank you so much for your time today, and have a wonderful day!"
            ),
            response_category="schedule_confirmation",
            conversation_stage=ConversationStage.GOODBYE,
            end_conversation=True,
            outcome="send_email_invite",
            start_time=start_time,
            detected_intent="send_email_invite",
            session=session
        )
    
    async def _handle_scheduling_rejection(self, session: CallSession, start_time: float) -> Dict[str, Any]:
        """Handle when user declines scheduling - Second 'No'"""
        logger.info("❌ Customer declined scheduling - Ending call")
        
        agent_name = session.client_data.get("last_agent", "our team")
        # Use specific agent name if available, otherwise use "our team"
        if agent_name and agent_name != "our team":
            agent_reference = agent_name
        else:
            agent_reference = "one of our agents"
        
        session.conversation_stage = ConversationStage.GOODBYE
        
        return await self._create_response(
            response_text=(
                f"No problem, {agent_reference} will reach out to you and the two of you can work "
                f"together to determine the best next steps. We look forward to servicing you, "
                f"have a wonderful day!"
            ),
            response_category="no_schedule_followup",
            conversation_stage=ConversationStage.GOODBYE,
            end_conversation=True,
            outcome="interested_no_schedule",  # Fixed: Changed from "interested_no_schedule" to ensure correct email mapping
            start_time=start_time,
            detected_intent="interested_no_schedule",
            session=session
        )
    
    async def _handle_dnc_request(self, session: CallSession, start_time: float) -> Dict[str, Any]:
        """Handle do-not-call request"""
        logger.info("🚫 Customer requested DNC - Ending call")
        
        session.conversation_stage = ConversationStage.GOODBYE
        
        return await self._create_response(
            response_text=(
                "I completely understand. I'll make sure you're removed from all future calls "
                "right away. You'll receive a confirmation email shortly. Our contact information "
                "will be in that email if you ever change your mind - remember, our service is "
                "always free. Have a wonderful day!"
            ),
            response_category="dnc_confirmation",
            conversation_stage=ConversationStage.GOODBYE,
            end_conversation=True,
            outcome="dnc_requested",
            start_time=start_time,
            detected_intent="dnc_requested",
            session=session
        )
    
    async def _handle_dnc_confirmation(self, session: CallSession, start_time: float) -> Dict[str, Any]:
        """Handle when user confirms DNC - Second 'No' to communications"""
        logger.info("🚫 Customer confirmed DNC - Ending call")
        
        session.conversation_stage = ConversationStage.GOODBYE
        
        return await self._create_response(
            response_text=(
                "Understood, we will make sure you are removed from all future communications "
                "and send you a confirmation email once that is done. Our contact details will "
                "be in that email as well, so if you do change your mind in the future please "
                "feel free to reach out – we are always here to help and our service is always "
                "free of charge. Have a wonderful day!"
            ),
            response_category="dnc_confirmation",
            conversation_stage=ConversationStage.GOODBYE,
            end_conversation=True,
            outcome="dnc_requested",
            start_time=start_time,
            detected_intent="dnc_requested",
            session=session
        )
    
    async def _handle_keep_communications(self, session: CallSession, start_time: float) -> Dict[str, Any]:
        """Handle when user wants to keep receiving communications - Second 'Yes'"""
        logger.info("✅ Customer wants to keep communications - Ending call")
        
        session.conversation_stage = ConversationStage.GOODBYE
        
        return await self._create_response(
            response_text=(
                "Great, we're happy to keep you informed throughout the year regarding the "
                "ever-changing world of health insurance. If you'd like to connect with one "
                "of our insurance experts in the future please feel free to reach out – "
                "we are always here to help and our service is always free of charge. "
                "Have a wonderful day!"
            ),
            response_category="keep_communications",
            conversation_stage=ConversationStage.GOODBYE,
            end_conversation=True,
            outcome="keep_communications",  # Fixed: Changed from "not_interested" to "keep_communications"
            start_time=start_time,
            detected_intent="keep_communications",
            session=session
        )
    
    async def _handle_maybe_response(self, session: CallSession, start_time: float) -> Dict[str, Any]:
        """Handle uncertain responses"""
        logger.info("🤔 Customer uncertain - Asking for clarification")
        
        return await self._create_response(
            response_text=(
                "I understand you might need some time to think about it. "
                "Let me ask you this - are you currently happy with your health insurance, "
                "or would you be open to learning about potentially better options? "
                "There's no obligation, and our consultation is completely free. "
                "What do you think?"
            ),
            response_category="clarification",
            conversation_stage=session.conversation_stage,
            end_conversation=False,
            outcome="clarification_needed",
            start_time=start_time,
            detected_intent="maybe",
            session=session
        )
    
    async def _handle_unclear_response(self, session: CallSession, start_time: float, context: str) -> Dict[str, Any]:
        """Handle unclear responses based on context"""
        logger.info(f"❓ Unclear response in {context} - Asking for clarification")
        
        if context == "greeting":
            text = (
                "I apologize, I didn't quite catch that. "
                "Would you be interested in reviewing your health insurance options "
                "for this year's open enrollment? A simple yes or no would be great."
            )
        elif context == "scheduling":
            agent_name = session.client_data.get("last_agent", "your agent")
            text = (
                f"Let me clarify - would you like us to send you an email with "
                f"{agent_name}'s available times for a brief consultation? "
                f"Just say yes if you'd like that, or no if you're not interested."
            )
        elif context == "dnc_check":
            text = (
                "I want to make sure I understand correctly. "
                "Would you like to continue receiving health insurance updates from us? "
                "Please say yes or no."
            )
        else:
            text = (
                "I apologize, I didn't understand that. "
                "Could you please repeat your response?"
            )
        
        return await self._create_response(
            response_text=text,
            response_category="clarification",
            conversation_stage=session.conversation_stage,
            end_conversation=False,
            outcome="clarification_needed",
            start_time=start_time,
            detected_intent="unclear",
            session=session
        )
    
    async def _handle_silence_detection(self, session: CallSession, silence_count: int, start_time: float) -> Dict[str, Any]:
        """Handle silence detection with progressive responses"""
        
        if silence_count == 1:
            response_text = self.silence_responses["first"]
            end_conversation = False
            outcome = "silence_first"
        elif silence_count == 2:
            response_text = self.silence_responses["second"]
            end_conversation = False
            outcome = "silence_second"
        else:
            response_text = self.silence_responses["final"]
            end_conversation = True
            outcome = "silence_final"
        
        return await self._create_response(
            response_text=response_text,
            response_category="silence_detection",
            conversation_stage=session.conversation_stage,
            end_conversation=end_conversation,
            outcome=outcome,
            start_time=start_time,
            detected_intent="silence",
            session=session
        )
    
    async def _create_response(
        self,
        response_text: str,
        response_category: str,
        conversation_stage: ConversationStage,
        end_conversation: bool,
        outcome: str,
        start_time: float,
        detected_intent: str = None,
        lyzr_task: Optional[asyncio.Task] = None,
        session: Optional[CallSession] = None
    ) -> Dict[str, Any]:
        """Create standardized response"""
        
        if hasattr(conversation_stage, 'value'):
            stage_value = conversation_stage.value if hasattr(conversation_stage, 'value') else conversation_stage
        else:
            stage_value = conversation_stage
        
        response = {
            "success": True,
            "response_text": response_text,
            "response_category": response_category,
            "conversation_stage": stage_value,
            "end_conversation": end_conversation,
            "outcome": outcome,
            "processing_time_ms": int((time.time() - start_time) * 1000),
            "detected_intent": detected_intent or outcome
        }
        
        # Don't include lyzr_task in response to avoid database serialization issues
        # The task is stored in session.lyzr_pending_task instead
        
        # Generate summary if conversation is ending
        if end_conversation and session:
            summary = await self._generate_call_summary(session, outcome, response_text)
            response["call_summary"] = summary
        
        return response
    
    async def _generate_call_summary(self, session: CallSession, outcome: str, final_response: str) -> str:
        """Generate a concise summary of the call for dashboard display"""
        
        try:
            # Try to get LYZR summary first (more sophisticated)
            lyzr_summary = await self._get_lyzr_call_summary(session, outcome, final_response)
            if lyzr_summary:
                return lyzr_summary
            
            # Fallback to rule-based summary
            return await self._generate_rule_based_summary(session, outcome, final_response)
            
        except Exception as e:
            logger.error(f"❌ Error generating call summary: {e}")
            return f"Call completed with {session.client_data.get('first_name', 'client')}. Outcome: {outcome}"
    
    async def _get_lyzr_call_summary(self, session: CallSession, outcome: str, final_response: str) -> Optional[str]:
        """Get sophisticated call summary from LYZR summary agent"""
        
        try:
            from services.lyzr_client import lyzr_client
            
            if not lyzr_client.is_configured():
                return None
            
            # Build conversation history for summary
            conversation_history = []
            for turn in session.conversation_turns:
                try:
                    # Handle potential None values and missing attributes
                    customer_speech = turn.customer_speech if turn.customer_speech else "No speech detected"
                    agent_response = turn.agent_response if turn.agent_response else "No response"
                    
                    # Get conversation stage safely
                    if hasattr(turn, 'conversation_stage') and turn.conversation_stage:
                        if hasattr(turn.conversation_stage, 'value'):
                            stage = turn.conversation_stage.value
                        else:
                            stage = str(turn.conversation_stage)
                    else:
                        stage = "unknown"
                    
                    conversation_history.append({
                        "customer": customer_speech,
                        "agent": agent_response,
                        "category": stage
                    })
                except Exception as e:
                    logger.warning(f"⚠️ Error processing conversation turn: {e}")
                    # Add a fallback entry
                    conversation_history.append({
                        "customer": "Error processing turn",
                        "agent": "Error processing turn", 
                        "category": "error"
                    })
            
            # Create summary request
            summary_request = {
                "session_id": f"{session.lyzr_session_id}_summary",
                "conversation_history": conversation_history,
                "outcome": outcome,
                "final_response": final_response,
                "context": {
                    "client_name": session.client_data.get("first_name", "Client"),
                    "agent_name": session.client_data.get("last_agent", "our team"),
                    "call_duration": int((time.time() - session.started_at.timestamp())),
                    "client_tags": session.client_data.get("tags", ""),
                    "total_turns": len(session.conversation_turns)
                }
            }
            
            # Get LYZR summary (with timeout)
            # Build conversation transcript from history
            conversation_transcript = ""
            for turn in conversation_history:
                conversation_transcript += f"Customer: {turn['customer']}\n"
                conversation_transcript += f"Agent: {turn['agent']}\n"
            
            # Ensure we have a valid conversation transcript
            if not conversation_transcript.strip():
                logger.warning("⚠️ Empty conversation transcript, using fallback summary")
                return None
            
            lyzr_result = await asyncio.wait_for(
                lyzr_client.generate_call_summary(
                    conversation_transcript=conversation_transcript,
                    client_name=session.client_data.get("first_name", "Client"),
                    call_outcome=outcome
                ),
                timeout=5.0  # 5 second timeout for summary
            )
            
            if lyzr_result and lyzr_result.get("success"):
                summary = lyzr_result.get("summary", "")
                if len(summary.strip()) > 20:  # Ensure summary is substantial
                    logger.info(f"🤖 LYZR generated summary: {summary}")
                    return summary
                else:
                    logger.warning("🤖 LYZR summary too short, using fallback")
                    return None
            else:
                logger.warning(f"🤖 LYZR summary failed: {lyzr_result.get('error', 'Unknown error')}")
                return None
            
            return None
            
        except asyncio.TimeoutError:
            logger.warning("⏰ LYZR summary generation timed out, using fallback")
            return None
        except Exception as e:
            logger.error(f"❌ LYZR summary generation error: {e}")
            return None
    
    async def _generate_rule_based_summary(self, session: CallSession, outcome: str, final_response: str) -> str:
        """Generate rule-based summary as fallback"""
        
        # Build conversation context for summary
        conversation_context = {
            "client_name": session.client_data.get("first_name", "Client"),
            "agent_name": session.client_data.get("last_agent", "our team"),
            "outcome": outcome,
            "conversation_turns": len(session.conversation_turns),
            "call_duration": int((time.time() - session.started_at.timestamp())),
            "final_response": final_response,
            "client_tags": session.client_data.get("tags", "")
        }
        
        # Create summary based on outcome
        if outcome == "send_email_invite":
            summary = f"✅ {conversation_context['client_name']} interested in scheduling. Email invite sent to {conversation_context['agent_name']}."
        elif outcome == "interested_no_schedule":
            summary = f"✅ {conversation_context['client_name']} interested but declined scheduling. {conversation_context['agent_name']} will follow up directly."
        elif outcome == "dnc_requested":
            summary = f"🚫 {conversation_context['client_name']} requested DNC. Removed from future calls and confirmation email sent."
        elif outcome == "keep_communications":
            summary = f"✅ {conversation_context['client_name']} not interested but wants to stay informed. Will receive occasional updates."
        elif outcome == "voicemail":
            if "Medicare" in conversation_context['client_tags']:
                summary = f"📞 Left Medicare-specific voicemail for {conversation_context['client_name']}. Call back number provided."
            elif "Non-Medicare" in conversation_context['client_tags']:
                summary = f"📞 Left Non-Medicare voicemail for {conversation_context['client_name']}. Call back number provided."
            else:
                summary = f"📞 Left voicemail for {conversation_context['client_name']}. Call back number provided."
        elif outcome == "busy_call_back":
            summary = f"📞 {conversation_context['client_name']} was busy. Will call back at better time."
        elif outcome == "no_answer":
            summary = f"📞 No answer from {conversation_context['client_name']}. Call ended after multiple attempts."
        elif outcome == "error":
            summary = f"❌ Technical error during call with {conversation_context['client_name']}. Call ended prematurely."
        else:
            summary = f"📞 Call with {conversation_context['client_name']} completed. Outcome: {outcome}"
        
        # Add call duration if available
        if conversation_context['call_duration'] > 0:
            summary += f" Duration: {conversation_context['call_duration']}s"
        
        logger.info(f"📝 Generated rule-based summary: {summary}")
        return summary
    
    async def close(self):
        """Close HTTP client"""
        await self.httpx_client.aclose()

# Global instance
voice_processor = VoiceProcessor()