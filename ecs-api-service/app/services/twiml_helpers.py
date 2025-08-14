"""
TwiML Helper Functions - COMPLETELY FIXED with Male Voice Consistency
Creates Twilio XML responses for voice calls with proper male voice fallbacks
"""

import logging
from typing import Optional, Dict, Any

logger = logging.getLogger(__name__)

# FIXED: Use consistent male voice for all fallbacks to match Alex
MALE_VOICE = "Polly.Matthew"  # Professional male voice consistent with Alex

def create_simple_twiml(message: str) -> str:
    """Create simple TwiML response with Say verb"""
    
    # Clean message for TTS
    clean_message = _clean_text_for_twiml(message)
    
    return f"""<?xml version="1.0" encoding="UTF-8"?>
<Response>
    <Say voice="{MALE_VOICE}">{clean_message}</Say>
</Response>"""

def create_voice_twiml(
    audio_url: str,
    gather_action: str,
    session_id: Optional[str] = None,
    timeout: int = 5,
    speech_timeout: str = "auto"
) -> str:
    """Create TwiML response with audio playback and speech gathering"""
    
    return f"""<?xml version="1.0" encoding="UTF-8"?>
<Response>
    <Play>{audio_url}</Play>
    <Gather action="{gather_action}" method="POST" input="speech" timeout="{timeout}" speechTimeout="{speech_timeout}">
        <Say voice="{MALE_VOICE}">Please respond.</Say>
    </Gather>
    <Say voice="{MALE_VOICE}">I didn't hear you. Thank you for calling. Goodbye.</Say>
</Response>"""

def create_fallback_twiml(text: str, gather_action: str) -> str:
    """Create fallback TwiML when audio generation fails"""
    
    clean_text = _clean_text_for_twiml(text)
    
    return f"""<?xml version="1.0" encoding="UTF-8"?>
<Response>
    <Say voice="{MALE_VOICE}">{clean_text}</Say>
    <Gather action="{gather_action}" method="POST" input="speech" timeout="5" speechTimeout="auto">
        <Say voice="{MALE_VOICE}">Please respond.</Say>
    </Gather>
    <Say voice="{MALE_VOICE}">Thank you for your time. Goodbye.</Say>
</Response>"""

def create_media_stream_twiml(websocket_url: str) -> str:
    """Create TwiML response for media streaming"""
    
    return f"""<?xml version="1.0" encoding="UTF-8"?>
<Response>
    <Say voice="{MALE_VOICE}">Connecting you now.</Say>
    <Connect>
        <Stream url="{websocket_url}" />
    </Connect>
</Response>"""

def create_conference_twiml(
    conference_name: str,
    wait_url: Optional[str] = None,
    muted: bool = False
) -> str:
    """Create TwiML response for conference calls"""
    
    muted_attr = 'muted="true"' if muted else ''
    wait_url_attr = f'waitUrl="{wait_url}"' if wait_url else ''
    
    return f"""<?xml version="1.0" encoding="UTF-8"?>
<Response>
    <Say voice="{MALE_VOICE}">Joining conference.</Say>
    <Dial>
        <Conference {muted_attr} {wait_url_attr}>{conference_name}</Conference>
    </Dial>
</Response>"""

def create_transfer_twiml(phone_number: str, caller_id: Optional[str] = None) -> str:
    """Create TwiML response for call transfer"""
    
    caller_id_attr = f'callerId="{caller_id}"' if caller_id else ''
    
    return f"""<?xml version="1.0" encoding="UTF-8"?>
<Response>
    <Say voice="{MALE_VOICE}">Transferring your call.</Say>
    <Dial {caller_id_attr}>{phone_number}</Dial>
</Response>"""

def create_voicemail_twiml(
    recording_action: str,
    max_length: int = 120,
    beep_message: str = "Please leave a message after the beep."
) -> str:
    """Create TwiML response for voicemail (note: not used for our voicemail detection)"""
    
    clean_message = _clean_text_for_twiml(beep_message)
    
    return f"""<?xml version="1.0" encoding="UTF-8"?>
<Response>
    <Say voice="{MALE_VOICE}">{clean_message}</Say>
    <Record 
        action="{recording_action}" 
        method="POST" 
        maxLength="{max_length}"
        playBeep="true"
        finishOnKey="#"
    />
    <Say voice="{MALE_VOICE}">Thank you for your message. Goodbye.</Say>
</Response>"""

def create_gather_digits_twiml(
    action: str,
    num_digits: int = 1,
    timeout: int = 5,
    prompt: str = "Press a number."
) -> str:
    """Create TwiML response for collecting digits"""
    
    clean_prompt = _clean_text_for_twiml(prompt)
    
    return f"""<?xml version="1.0" encoding="UTF-8"?>
<Response>
    <Gather action="{action}" method="POST" numDigits="{num_digits}" timeout="{timeout}">
        <Say voice="{MALE_VOICE}">{clean_prompt}</Say>
    </Gather>
    <Say voice="{MALE_VOICE}">I didn't receive input. Goodbye.</Say>
</Response>"""

def create_redirect_twiml(url: str) -> str:
    """Create TwiML response to redirect call flow"""
    
    return f"""<?xml version="1.0" encoding="UTF-8"?>
<Response>
    <Redirect>{url}</Redirect>
</Response>"""

def create_hangup_twiml(goodbye_message: str = "Thank you for calling. Goodbye.") -> str:
    """Create TwiML response to end call gracefully"""
    
    clean_message = _clean_text_for_twiml(goodbye_message)
    
    return f"""<?xml version="1.0" encoding="UTF-8"?>
<Response>
    <Say voice="{MALE_VOICE}">{clean_message}</Say>
    <Hangup/>
</Response>"""

def create_pause_twiml(length: int = 2) -> str:
    """Create TwiML response with pause"""
    
    return f"""<?xml version="1.0" encoding="UTF-8"?>
<Response>
    <Pause length="{length}"/>
</Response>"""

def _clean_text_for_twiml(text: str) -> str:
    """Clean text for TwiML XML compatibility"""
    
    if not text:
        return "Thank you for calling."
    
    # Replace XML-unsafe characters
    text = text.replace("&", "&amp;")
    text = text.replace("<", "&lt;")
    text = text.replace(">", "&gt;")
    text = text.replace('"', "&quot;")
    text = text.replace("'", "&apos;")
    
    # Remove line breaks and excessive whitespace
    text = text.replace("\n", " ").replace("\r", " ")
    text = " ".join(text.split())
    
    # Limit length for better voice experience
    if len(text) > 500:
        sentences = text[:500].split('.')
        if len(sentences) > 1:
            text = '.'.join(sentences[:-1]) + '.'
        else:
            text = text[:497] + "..."
    
    return text.strip()

# Advanced TwiML builders with male voice consistency
def create_dynamic_gather_twiml(
    config: Dict[str, Any],
    session_data: Optional[Dict[str, Any]] = None
) -> str:
    """Create dynamic TwiML based on configuration"""
    
    action = config.get('action', '/twilio/speech')
    input_type = config.get('input', 'speech')
    timeout = config.get('timeout', 5)
    speech_timeout = config.get('speech_timeout', 'auto')
    
    # Dynamic prompt based on session data
    if session_data and session_data.get('conversation_stage'):
        stage = session_data['conversation_stage']
        if stage == 'greeting':
            prompt = "I'm listening."
        elif stage == 'interest_check':
            prompt = "Please let me know your thoughts."
        else:
            prompt = "How can I help you?"
    else:
        prompt = config.get('prompt', 'Please respond.')
    
    clean_prompt = _clean_text_for_twiml(prompt)
    
    return f"""<?xml version="1.0" encoding="UTF-8"?>
<Response>
    <Gather action="{action}" method="POST" input="{input_type}" timeout="{timeout}" speechTimeout="{speech_timeout}">
        <Say voice="{MALE_VOICE}">{clean_prompt}</Say>
    </Gather>
    <Say voice="{MALE_VOICE}">I didn't hear you. Thank you for calling.</Say>
</Response>"""

def create_conditional_twiml(
    conditions: Dict[str, str],
    default_message: str = "Thank you for calling."
) -> str:
    """Create conditional TwiML based on runtime conditions"""
    
    # This would be expanded with actual condition checking
    # For now, return default with male voice
    return create_simple_twiml(default_message)

# Emergency fallbacks with proper male voice
def create_emergency_twiml(client_name: str = "there", should_hangup: bool = True) -> str:
    """Create emergency TwiML when all systems fail"""
    
    emergency_text = f"Hello {client_name}, this is Alex from Altruis Advisor Group. We're experiencing technical difficulties. Please call us back at 8-3-3, 2-2-7, 8-5-0-0. Thank you."
    
    if should_hangup:
        return f"""<?xml version="1.0" encoding="UTF-8"?>
<Response>
    <Say voice="{MALE_VOICE}">{emergency_text}</Say>
    <Hangup/>
</Response>"""
    else:
        return f"""<?xml version="1.0" encoding="UTF-8"?>
<Response>
    <Say voice="{MALE_VOICE}">{emergency_text}</Say>
</Response>"""

# Specialized TwiML for enhanced features
def create_no_speech_twiml(
    attempt_number: int,
    callback_number: str = "8-3-3, 2-2-7, 8-5-0-0"
) -> str:
    """Create TwiML for no-speech scenarios with callback number"""
    
    if attempt_number == 1:
        text = "I'm sorry, I can't seem to hear you clearly. If you said something, could you please speak a bit louder? I'm here to help."
    elif attempt_number == 2:
        text = "I'm still having trouble hearing you. If you're there, please try speaking directly into your phone. Can you hear me okay?"
    else:
        text = f"I apologize, but I'm having difficulty with our connection. If you'd like to speak with us, please call us back at {callback_number}. Thank you, and have a great day."
    
    clean_text = _clean_text_for_twiml(text)
    
    if attempt_number >= 3:
        return f"""<?xml version="1.0" encoding="UTF-8"?>
<Response>
    <Say voice="{MALE_VOICE}">{clean_text}</Say>
    <Hangup/>
</Response>"""
    else:
        return f"""<?xml version="1.0" encoding="UTF-8"?>
<Response>
    <Say voice="{MALE_VOICE}">{clean_text}</Say>
    <Gather action="/twilio/process-speech" method="POST" input="speech" timeout="8" speechTimeout="auto" enhanced="true">
        <Pause length="3"/>
    </Gather>
    <Say voice="{MALE_VOICE}">I still can't hear you. I'll call you back later. Goodbye.</Say>
    <Hangup/>
</Response>"""

def create_interruption_acknowledgment_twiml(acknowledgment: str = "Yes? How can I help you?") -> str:
    """Create TwiML to acknowledge customer interruptions"""
    
    clean_acknowledgment = _clean_text_for_twiml(acknowledgment)
    
    return f"""<?xml version="1.0" encoding="UTF-8"?>
<Response>
    <Say voice="{MALE_VOICE}">{clean_acknowledgment}</Say>
    <Gather action="/twilio/process-speech" method="POST" input="speech" timeout="8" speechTimeout="auto" enhanced="true">
        <Pause length="2"/>
    </Gather>
    <Say voice="{MALE_VOICE}">How can I assist you further?</Say>
</Response>"""