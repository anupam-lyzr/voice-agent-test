"""
Shared Configuration Settings - Fixed with proper defaults
"""

from pydantic_settings import BaseSettings
from pydantic import Field, validator
from typing import Optional, List
import os

class Settings(BaseSettings):
    """Global application settings with proper defaults"""
    
    # Application Settings
    app_name: str = "Voice Agent Production"
    debug: bool = Field(default=False)
    environment: str = Field(default="development")
    host: str = Field(default="0.0.0.0")
    port: int = Field(default=8000)

    # AWS Configuration
    aws_region: Optional[str] = Field(default=None)
    aws_account_id: Optional[str] = Field(default=None)
    aws_session_token: Optional[str] = Field(default=None)
    
    # Database Configuration with defaults
    documentdb_host: str = Field(default="localhost")
    documentdb_port: int = Field(default=27017)
    documentdb_database: str = Field(default="voice_agent")
    documentdb_username: str = Field(default="admin")
    documentdb_password: str = Field(default="password123")
    documentdb_ssl: bool = Field(default=False)
    
    # Redis Configuration with defaults
    redis_url: str = Field(default="redis://localhost:6379")
    # redis_password: Optional[str] = Field(default=None)
    redis_db: int = Field(default=0)
    
    # Twilio Configuration
    twilio_account_sid: str = Field(default="")
    twilio_auth_token: str = Field(default="")
    twilio_phone_number: str = Field(default="")
    
    # AI Service API Keys
    deepgram_api_key: str = Field(default="", env="DEEPGRAM_API_KEY")
    elevenlabs_api_key: str = Field(default="")
    
    # LYZR Configuration
    lyzr_api_base_url: str = Field(default="https://agent-prod.studio.lyzr.ai")
    lyzr_conversation_agent_id: str = Field(default="")
    lyzr_summary_agent_id: str = Field(default="")
    lyzr_user_api_key: str = Field(default="")
    lyzr_api_key: Optional[str] = Field(default=None)
    
    # Voice Settings with defaults
    default_voice_id: str = Field(default="xtENCNNHEgtE8xBjLMt0")
    voice_stability: float = Field(default=0.55)
    voice_similarity_boost: float = Field(default=0.70)
    voice_style: float = Field(default=0.2)
    voice_speed: float = Field(default=0.87)
    use_speaker_boost: bool = Field(default=True)
    elevenlabs_voice_id: Optional[str] = Field(default=None)
    elevenlabs_voice_speed: Optional[float] = Field(default=None)
    elevenlabs_voice_settings: Optional[str] = Field(default=None)

    # CRM Configuration
    capsule_api_token: Optional[str] = Field(default=None)
    capsule_api_url: Optional[str] = Field(default=None)

    # Google Calendar Integration
    google_calendar_client_id: Optional[str] = Field(default=None)
    google_calendar_client_secret: Optional[str] = Field(default=None)

    # Email Configuration
    ses_region: Optional[str] = Field(default=None)
    from_email: Optional[str] = Field(default=None)

    # S3 Configuration
    s3_bucket_audio: Optional[str] = Field(default=None)
    s3_bucket_recordings: Optional[str] = Field(default=None)

    # Performance Settings with defaults
    max_concurrent_calls: int = Field(default=30)
    call_timeout_seconds: int = Field(default=300)
    max_call_attempts: int = Field(default=6)
    cache_ttl_seconds: int = Field(default=300)
    session_cache_ttl: int = Field(default=1800)
    webhook_timeout: int = Field(default=10)
    
    # Business Hours with defaults
    business_start_hour: int = Field(default=9)
    business_end_hour: int = Field(default=17)
    business_days: str = Field(default="1,2,3,4,5")
    business_timezone: str = Field(default="America/New_York")
    
    # Queue Settings with defaults (for worker)
    sqs_queue_url: str = Field(default="")
    sqs_visibility_timeout: int = Field(default=300)
    sqs_wait_time: int = Field(default=20)
    
    # Other settings
    base_url: str = Field(default="http://localhost:8000")
    tts_model: str = Field(default="eleven_turbo_v2_5")
    tts_output_format: str = Field(default="mp3_22050_32")
    stt_model: str = Field(default="nova", env="STT_MODEL")
    stt_language: str = Field(default="en-US", env="STT_LANGUAGE")
    
    class Config:
        env_file = ".env"
        case_sensitive = False

    def is_production(self) -> bool:
        """Check if running in production environment"""
        return self.environment.lower() == "production"

    @property
    def mongodb_uri(self) -> str:
        """Get MongoDB connection URI based on the environment."""
        if self.documentdb_username and self.documentdb_password:
            auth = f"{self.documentdb_username}:{self.documentdb_password}@"
        else:
            auth = ""

        if self.is_production():
            # Use AWS DocumentDB style URI
            # NOTE: Do NOT include `authSource=admin` for AWS DocumentDB unless required (not needed here)
            ssl_params = "?ssl=true&retryWrites=false&tlsAllowInvalidCertificates=true"
            return f"mongodb://{auth}{self.documentdb_host}:{self.documentdb_port}/{ssl_params}"
        else:
            # Local dev needs authSource=admin because the root user is created in the admin DB
            return f"mongodb://{auth}{self.documentdb_host}:{self.documentdb_port}/{self.documentdb_database}?authSource=admin"

        
    @property
    def elevenlabs_voice_settings(self) -> dict:
        """Get ElevenLabs voice settings"""
        return {
            "stability": self.voice_stability,
            "similarity_boost": self.voice_similarity_boost,
            "style": self.voice_style,
            "use_speaker_boost": self.use_speaker_boost,
            "speed": self.voice_speed
        }


    @property
    def business_days_list(self) -> List[int]:
        """Get business days as list of integers"""
        return [int(day.strip()) for day in self.business_days.split(",")]
    
    def get_webhook_url(self, endpoint: str) -> str:
        """Get full webhook URL for Twilio"""
        return f"{self.base_url.rstrip('/')}/twilio/{endpoint}"
    
    def is_production(self) -> bool:
        """Check if running in production environment"""
        return self.environment.lower() == "production"
    
    # def is_business_hours(self) -> bool:
    #     """Check if current time is within business hours"""
    #     try:
    #         tz = pytz.timezone(self.business_timezone)
    #         now = datetime.now(tz)
            
    #         # Check weekday (0=Monday, 6=Sunday)
    #         if now.weekday() not in self.business_days_list:
    #             return False
            
    #         # Check time
    #         if now.hour < self.business_start_hour or now.hour >= self.business_end_hour:
    #             return False
            
    #         return True
    #     except Exception:
    #         # If timezone fails, default to False for safety
    #         return False

    def is_business_hours(self) -> bool:
        """Check if current time is within business hours"""
        # For development/testing, always return True
        if self.environment.lower() == "development":
            return True
            
        try:
            tz = pytz.timezone(self.business_timezone)
            now = datetime.now(tz)
            
            # Check weekday (0=Monday, 6=Sunday)
            if now.weekday() not in self.business_days_list:
                return False
            
            # Check time
            if now.hour < self.business_start_hour or now.hour >= self.business_end_hour:
                return False
            
            return True
        except Exception:
            return False
    
    def validate_required_settings(self) -> dict:
        """Validate that required settings are configured"""
        validation_results = {}
        
        required_for_production = {
            "twilio_account_sid": self.twilio_account_sid,
            "twilio_auth_token": self.twilio_auth_token,
            "twilio_phone_number": self.twilio_phone_number,
            "deepgram_api_key": self.deepgram_api_key,
            "elevenlabs_api_key": self.elevenlabs_api_key,
            "lyzr_conversation_agent_id": self.lyzr_conversation_agent_id,
            "lyzr_summary_agent_id": self.lyzr_summary_agent_id,
            "lyzr_user_api_key": self.lyzr_user_api_key,
        }
        
        for key, value in required_for_production.items():
            is_valid = value and value.strip() != "" and not value.startswith("your_")
            validation_results[key] = {
                "valid": is_valid,
                "configured": bool(value and value.strip()),
                "message": "✅ Configured" if is_valid else "❌ Not configured or using placeholder"
            }
        
        return validation_results

# Global settings instance
settings = Settings()