"""
Shared Configuration Settings
Environment variables and application settings for both API and Worker services
"""

from pydantic_settings import BaseSettings
from pydantic import Field
from typing import Optional, List
import os
import pytz
from datetime import datetime

class Settings(BaseSettings):
    """Global application settings"""
    
    # Application Settings
    app_name: str = "Voice Agent Production"
    debug: bool = Field(default=False, env="DEBUG")
    environment: str = Field(default="development", env="ENVIRONMENT")
    testing_mode: bool = Field(default=False, env="TESTING_MODE")
    
    # AWS Configuration
    aws_region: str = Field(default="us-east-1", env="AWS_REGION")
    aws_account_id: str = Field(default="", env="AWS_ACCOUNT_ID")
    aws_session_token: Optional[str] = Field(default=None, env="AWS_SESSION_TOKEN")
    
    # Database Configuration (DocumentDB/MongoDB)
    documentdb_host: str = Field(default="localhost", env="DOCUMENTDB_HOST")
    documentdb_port: int = Field(default=27017, env="DOCUMENTDB_PORT")
    documentdb_database: str = Field(default="voice_agent", env="DOCUMENTDB_DATABASE")
    documentdb_username: str = Field(default="admin", env="DOCUMENTDB_USERNAME")
    documentdb_password: str = Field(default="password123", env="DOCUMENTDB_PASSWORD")
    documentdb_ssl: bool = Field(default=False, env="DOCUMENTDB_SSL")
    
    # Redis Configuration
    redis_url: str = Field(default="redis://localhost:6379", env="REDIS_URL")
    # redis_password: Optional[str] = Field(default=None, env="REDIS_PASSWORD")
    redis_db: int = Field(default=0, env="REDIS_DB")
    
    # Twilio Configuration
    twilio_account_sid: str = Field(default="", env="TWILIO_ACCOUNT_SID")
    twilio_auth_token: str = Field(default="", env="TWILIO_AUTH_TOKEN")
    twilio_phone_number: str = Field(default="", env="TWILIO_PHONE_NUMBER")
    
    # AI Service API Keys
    deepgram_api_key: str = Field(default="", env="DEEPGRAM_API_KEY")
    elevenlabs_api_key: str = Field(default="", env="ELEVENLABS_API_KEY")
    
    # LYZR Configuration  
    lyzr_api_base_url: str = Field(default="https://agent-prod.studio.lyzr.ai", env="LYZR_API_BASE_URL")
    lyzr_conversation_agent_id: str = Field(default="", env="LYZR_CONVERSATION_AGENT_ID")
    lyzr_summary_agent_id: str = Field(default="", env="LYZR_SUMMARY_AGENT_ID")
    lyzr_user_api_key: str = Field(default="", env="LYZR_USER_API_KEY")
    
    # CRM Configuration
    capsule_api_token: str = Field(default="", env="CAPSULE_API_TOKEN")
    capsule_api_url: str = Field(default="https://api.capsulecrm.com", env="CAPSULE_API_URL")
    
    # Google Calendar Integration
    google_service_account_email: Optional[str] = Field(default=None, env="GOOGLE_SERVICE_ACCOUNT_EMAIL")
    google_service_account_private_key: Optional[str] = Field(default=None, env="GOOGLE_SERVICE_ACCOUNT_PRIVATE_KEY") 
    google_service_account_project_id: Optional[str] = Field(default=None, env="GOOGLE_SERVICE_ACCOUNT_PROJECT_ID")
    google_calendar_primary_id: Optional[str] = Field(default=None, env="GOOGLE_CALENDAR_PRIMARY_ID")

    
    # Email Configuration (SES/SMTP)
    ses_region: str = Field(default="us-east-1", env="SES_REGION")
    from_email: str = Field(default="aag@ca.lyzr.app", env="FROM_EMAIL")  # Updated default to match your preference
    
    # SMTP Configuration (preferred over SES SDK)
    smtp_host: Optional[str] = Field(default=None, env="SMTP_HOST")
    smtp_port: int = Field(default=587, env="SMTP_PORT")
    smtp_username: Optional[str] = Field(default=None, env="SMTP_USERNAME")
    smtp_password: Optional[str] = Field(default=None, env="SMTP_PASSWORD")
    smtp_sender_email: Optional[str] = Field(default=None, env="SMTP_SENDER_EMAIL")
    smtp_reply_to_email: Optional[str] = Field(default=None, env="SMTP_REPLY_TO_EMAIL")
    
    # S3 Configuration
    s3_bucket_audio: str = Field(default="voice-agent-audio-bucket", env="S3_BUCKET_AUDIO")
    s3_bucket_recordings: str = Field(default="voice-agent-recordings-bucket", env="S3_BUCKET_RECORDINGS")
    
    # Performance Settings
    max_concurrent_calls: int = Field(default=30, env="MAX_CONCURRENT_CALLS")
    call_timeout_seconds: int = Field(default=300, env="CALL_TIMEOUT_SECONDS")
    max_call_attempts: int = Field(default=6, env="MAX_CALL_ATTEMPTS")
    
    # Voice Processing Settings
    default_voice_id: str = Field(default="iP95p4xoKVk53GoZ742B", env="VOICE_ID")  # Adam voice
    voice_stability: float = Field(default=0.35, env="VOICE_STABILITY")
    voice_similarity_boost: float = Field(default=0.75, env="VOICE_SIMILARITY_BOOST") 
    voice_style: float = Field(default=0.45, env="VOICE_STYLE")
    use_speaker_boost: bool = Field(default=True, env="USE_SPEAKER_BOOST")
    
    # TTS Settings
    tts_model: str = Field(default="eleven_turbo_v2_5", env="TTS_MODEL")
    tts_output_format: str = Field(default="mp3_22050_32", env="TTS_OUTPUT_FORMAT")
    
    # STT Settings
    stt_model: str = Field(default="nova-2", env="STT_MODEL")
    stt_language: str = Field(default="en-US", env="STT_LANGUAGE")
    
    # Business Hours Configuration
    business_start_hour: int = Field(default=9, env="BUSINESS_START_HOUR")
    business_end_hour: int = Field(default=17, env="BUSINESS_END_HOUR") 
    business_days: str = Field(default="1,2,3,4,5", env="BUSINESS_DAYS")  # Mon-Fri
    business_timezone: str = Field(default="America/New_York", env="BUSINESS_TIMEZONE")
    
    # Cache Settings
    cache_ttl_seconds: int = Field(default=300, env="CACHE_TTL_SECONDS")  # 5 minutes
    session_cache_ttl: int = Field(default=1800, env="SESSION_CACHE_TTL")  # 30 minutes
    
    # Webhook Settings (for API service)
    base_url: str = Field(default="https://your-domain.com", env="BASE_URL")
    webhook_timeout: int = Field(default=10, env="WEBHOOK_TIMEOUT")
    
    # Queue Settings (for Worker service)
    sqs_queue_url: str = Field(default="", env="SQS_QUEUE_URL")
    sqs_visibility_timeout: int = Field(default=300, env="SQS_VISIBILITY_TIMEOUT")
    sqs_wait_time: int = Field(default=20, env="SQS_WAIT_TIME")
    
    # ECS Settings
    ecs_cluster_name: str = Field(default="voice-agent-cluster", env="ECS_CLUSTER_NAME")
    ecs_service_name: str = Field(default="voice-agent-api", env="ECS_SERVICE_NAME")

    
    class Config:
        env_file = ".env"
        case_sensitive = False
        extra = "ignore"
    
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
            "speed": self.voice_speed if hasattr(self, 'voice_speed') else 0.87  # Default speed
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
    
    def is_business_hours(self) -> bool:
        """Check if current time is within business hours"""
        # For testing mode, always return True to allow testing outside business hours
        if self.testing_mode:
            return True
            
        # For development environment, also allow testing outside business hours
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
            # If timezone fails, default to False for safety
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