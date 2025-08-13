"""
Redis Cache Utilities
High-performance caching for session data and temporary storage
"""

import json
import logging
from typing import Any, Dict, List, Optional, Union
from datetime import datetime, timedelta
import redis.asyncio as redis
from redis.exceptions import ConnectionError, RedisError

from shared.config.settings import settings
from shared.models.call_session import CallSession, SessionCache

logger = logging.getLogger(__name__)

class RedisClient:
    """Async Redis client wrapper for caching"""
    
    def __init__(self):
        self.client: Optional[redis.Redis] = None
        self._connected = False
        self.connection_pool = None
    
    async def connect(self):
        """Connect to Redis"""
        try:
            logger.info(f"Connecting to Redis: {settings.redis_url}")
            
            # Create connection pool
            self.connection_pool = redis.ConnectionPool.from_url(
                settings.redis_url,
                max_connections=20,
                socket_timeout=5,
                socket_connect_timeout=5,
                health_check_interval=30
            )
            
            self.client = redis.Redis(connection_pool=self.connection_pool)
            
            # Test connection
            await self.client.ping()
            
            self._connected = True
            logger.info("✅ Redis connected successfully")
            
        except Exception as e:
            logger.error(f"❌ Redis connection failed: {e}")
            # Don't raise exception - allow system to work without cache
            self._connected = False
    
    async def disconnect(self):
        """Disconnect from Redis"""
        if self.client:
            await self.client.close()
            self._connected = False
            logger.info("Redis disconnected")
    
    def is_connected(self) -> bool:
        """Check if Redis is connected"""
        return self._connected
    
    async def set(self, key: str, value: Any, ttl: Optional[int] = None) -> bool:
        """Set a value in Redis with optional TTL"""
        if not self._connected:
            return False
        
        try:
            # Serialize value
            if isinstance(value, (dict, list)):
                value = json.dumps(value, default=str)
            elif not isinstance(value, (str, bytes, int, float)):
                value = str(value)
            
            if ttl:
                await self.client.setex(key, ttl, value)
            else:
                await self.client.set(key, value)
            
            return True
        except Exception as e:
            logger.error(f"Redis SET error: {e}")
            return False
    
    async def get(self, key: str, default: Any = None) -> Any:
        """Get a value from Redis"""
        if not self._connected:
            return default
        
        try:
            value = await self.client.get(key)
            if value is None:
                return default
            
            # Try to deserialize JSON
            try:
                return json.loads(value)
            except (json.JSONDecodeError, TypeError):
                return value.decode('utf-8') if isinstance(value, bytes) else value
        except Exception as e:
            logger.error(f"Redis GET error: {e}")
            return default
    
    async def delete(self, key: str) -> bool:
        """Delete a key from Redis"""
        if not self._connected:
            return False
        
        try:
            result = await self.client.delete(key)
            return result > 0
        except Exception as e:
            logger.error(f"Redis DELETE error: {e}")
            return False
    
    async def exists(self, key: str) -> bool:
        """Check if key exists in Redis"""
        if not self._connected:
            return False
        
        try:
            result = await self.client.exists(key)
            return result > 0
        except Exception as e:
            logger.error(f"Redis EXISTS error: {e}")
            return False
    
    async def increment(self, key: str, amount: int = 1) -> Optional[int]:
        """Increment a numeric value"""
        if not self._connected:
            return None
        
        try:
            return await self.client.incrby(key, amount)
        except Exception as e:
            logger.error(f"Redis INCR error: {e}")
            return None
    
    async def expire(self, key: str, ttl: int) -> bool:
        """Set TTL for existing key"""
        if not self._connected:
            return False
        
        try:
            return await self.client.expire(key, ttl)
        except Exception as e:
            logger.error(f"Redis EXPIRE error: {e}")
            return False
    
    async def keys(self, pattern: str) -> List[str]:
        """Get keys matching pattern"""
        if not self._connected:
            return []
        
        try:
            keys = await self.client.keys(pattern)
            return [key.decode('utf-8') if isinstance(key, bytes) else key for key in keys]
        except Exception as e:
            logger.error(f"Redis KEYS error: {e}")
            return []
    
    async def hset(self, key: str, field: str, value: Any) -> bool:
        """Set field in hash"""
        if not self._connected:
            return False
        
        try:
            if isinstance(value, (dict, list)):
                value = json.dumps(value, default=str)
            elif not isinstance(value, (str, bytes, int, float)):
                value = str(value)
            
            await self.client.hset(key, field, value)
            return True
        except Exception as e:
            logger.error(f"Redis HSET error: {e}")
            return False
    
    async def hget(self, key: str, field: str, default: Any = None) -> Any:
        """Get field from hash"""
        if not self._connected:
            return default
        
        try:
            value = await self.client.hget(key, field)
            if value is None:
                return default
            
            # Try to deserialize JSON
            try:
                return json.loads(value)
            except (json.JSONDecodeError, TypeError):
                return value.decode('utf-8') if isinstance(value, bytes) else value
        except Exception as e:
            logger.error(f"Redis HGET error: {e}")
            return default
    
    async def hgetall(self, key: str) -> Dict[str, Any]:
        """Get all fields from hash"""
        if not self._connected:
            return {}
        
        try:
            result = await self.client.hgetall(key)
            decoded_result = {}
            
            for field, value in result.items():
                field_str = field.decode('utf-8') if isinstance(field, bytes) else field
                
                # Try to deserialize JSON
                try:
                    decoded_result[field_str] = json.loads(value)
                except (json.JSONDecodeError, TypeError):
                    decoded_result[field_str] = value.decode('utf-8') if isinstance(value, bytes) else value
            
            return decoded_result
        except Exception as e:
            logger.error(f"Redis HGETALL error: {e}")
            return {}

class SessionCache:
    """Cache manager for call sessions"""
    
    def __init__(self, redis_client: RedisClient):
        self.redis = redis_client
        self.session_prefix = "session:"
        self.active_calls_key = "active_calls"
        self.metrics_prefix = "metrics:"
    
    async def save_session(self, session: CallSession) -> bool:
        """Save session to cache"""
        # Store by twilio_call_sid for easier retrieval
        if not session.twilio_call_sid:
            logger.warning(f"⚠️ Cannot cache session {session.session_id}: twilio_call_sid is None")
            return False
            
        key = f"{self.session_prefix}{session.twilio_call_sid}"
        session_data = session.model_dump(mode='json')
        
        success = await self.redis.set(key, session_data, ttl=settings.session_cache_ttl)
        
        if success:
            # Add to active calls set
            await self.redis.hset(
                self.active_calls_key,
                session.twilio_call_sid,
                {
                    "phone_number": session.phone_number,
                    "status": session.call_status.value,
                    "started_at": session.started_at.isoformat(),
                    "twilio_call_sid": session.twilio_call_sid
                }
            )
        
        return success
    
    async def get_session(self, twilio_call_sid: str) -> Optional[CallSession]:
        """Get session from cache by twilio_call_sid"""
        key = f"{self.session_prefix}{twilio_call_sid}"
        session_data = await self.redis.get(key)
        
        if session_data:
            try:
                return CallSession(**session_data)
            except Exception as e:
                logger.error(f"Failed to deserialize session for call_sid {twilio_call_sid}: {e}")
                return None
        
        return None
    
    async def delete_session(self, twilio_call_sid: str) -> bool:
        """Delete session from cache by twilio_call_sid"""
        key = f"{self.session_prefix}{twilio_call_sid}"
        
        # Remove from both session cache and active calls
        deleted = await self.redis.delete(key)
        await self.redis.client.hdel(self.active_calls_key, twilio_call_sid)
        
        return deleted
    
    async def get_active_sessions(self) -> List[Dict[str, Any]]:
        """Get all active call sessions"""
        active_calls = await self.redis.hgetall(self.active_calls_key)
        return list(active_calls.values())
    
    async def cleanup_expired_sessions(self) -> int:
        """Clean up expired sessions"""
        if not self.redis.is_connected():
            return 0
        
        try:
            # Get all session keys
            session_keys = await self.redis.keys(f"{self.session_prefix}*")
            cleaned_count = 0
            
            for key in session_keys:
                exists = await self.redis.exists(key)
                if not exists:
                    # Session expired, remove from active calls
                    twilio_call_sid = key.replace(self.session_prefix, "")
                    await self.redis.client.hdel(self.active_calls_key, twilio_call_sid)
                    cleaned_count += 1
            
            logger.info(f"Cleaned up {cleaned_count} expired sessions")
            return cleaned_count
        except Exception as e:
            logger.error(f"Session cleanup error: {e}")
            return 0

class MetricsCache:
    """Cache manager for performance metrics"""
    
    def __init__(self, redis_client: RedisClient):
        self.redis = redis_client
        self.metrics_prefix = "metrics:"
        self.daily_stats_key = "daily_stats"
    
    async def record_call_metric(self, metric_type: str, value: float, timestamp: Optional[datetime] = None):
        """Record a call performance metric"""
        if timestamp is None:
            timestamp = datetime.utcnow()
        
        # Store in time-series format
        date_key = timestamp.strftime("%Y-%m-%d")
        hour_key = timestamp.strftime("%H")
        
        metric_key = f"{self.metrics_prefix}{metric_type}:{date_key}:{hour_key}"
        
        # Add to sorted set with timestamp as score
        await self.redis.client.zadd(metric_key, {str(value): timestamp.timestamp()})
        
        # Set expiry for 7 days
        await self.redis.expire(metric_key, 7 * 24 * 3600)
    
    async def get_hourly_metrics(self, metric_type: str, date: datetime) -> List[Dict[str, Any]]:
        """Get hourly metrics for a specific date"""
        metrics = []
        date_str = date.strftime("%Y-%m-%d")
        
        for hour in range(24):
            hour_str = f"{hour:02d}"
            metric_key = f"{self.metrics_prefix}{metric_type}:{date_str}:{hour_str}"
            
            # Get all values for this hour
            values = await self.redis.client.zrange(metric_key, 0, -1, withscores=True)
            
            if values:
                metric_values = [float(val[0]) for val in values]
                metrics.append({
                    "hour": hour,
                    "count": len(metric_values),
                    "average": sum(metric_values) / len(metric_values),
                    "min": min(metric_values),
                    "max": max(metric_values)
                })
            else:
                metrics.append({
                    "hour": hour,
                    "count": 0,
                    "average": 0,
                    "min": 0,
                    "max": 0
                })
        
        return metrics
    
    async def record_daily_stat(self, stat_name: str, value: Union[int, float]):
        """Record daily campaign statistics"""
        today = datetime.utcnow().strftime("%Y-%m-%d")
        stat_key = f"{self.daily_stats_key}:{today}"
        
        await self.redis.hset(stat_key, stat_name, value)
        await self.redis.expire(stat_key, 30 * 24 * 3600)  # Keep for 30 days
    
    async def get_daily_stats(self, date: Optional[datetime] = None) -> Dict[str, Any]:
        """Get daily statistics"""
        if date is None:
            date = datetime.utcnow()
        
        date_str = date.strftime("%Y-%m-%d")
        stat_key = f"{self.daily_stats_key}:{date_str}"
        
        return await self.redis.hgetall(stat_key)

class ResponseCache:
    """Cache for LYZR agent responses to avoid duplicate API calls"""
    
    def __init__(self, redis_client: RedisClient):
        self.redis = redis_client
        self.response_prefix = "response:"
        self.static_audio_prefix = "static_audio:"
    
    async def get_cached_response(self, input_hash: str) -> Optional[str]:
        """Get cached agent response"""
        key = f"{self.response_prefix}{input_hash}"
        return await self.redis.get(key)
    
    async def cache_response(self, input_hash: str, response: str, ttl: int = None) -> bool:
        """Cache agent response"""
        if ttl is None:
            ttl = settings.cache_ttl_seconds
        
        key = f"{self.response_prefix}{input_hash}"
        return await self.redis.set(key, response, ttl=ttl)
    
    async def get_static_audio_url(self, audio_key: str) -> Optional[str]:
        """Get static audio URL from cache"""
        key = f"{self.static_audio_prefix}{audio_key}"
        return await self.redis.get(key)
    
    async def cache_static_audio_url(self, audio_key: str, audio_url: str) -> bool:
        """Cache static audio URL"""
        key = f"{self.static_audio_prefix}{audio_key}"
        # Static audio URLs don't expire
        return await self.redis.set(key, audio_url)
    
    async def clear_response_cache(self) -> int:
        """Clear all cached responses"""
        keys = await self.redis.keys(f"{self.response_prefix}*")
        if keys:
            await self.redis.client.delete(*keys)
            return len(keys)
        return 0

# Global Redis client instance
redis_client = RedisClient()

# Cache manager instances
session_cache: Optional[SessionCache] = None
metrics_cache: Optional[MetricsCache] = None
response_cache: Optional[ResponseCache] = None

async def init_redis():
    """Initialize Redis connection and cache managers"""
    global session_cache, metrics_cache, response_cache
    
    await redis_client.connect()
    
    if redis_client.is_connected():
        session_cache = SessionCache(redis_client)
        metrics_cache = MetricsCache(redis_client)
        response_cache = ResponseCache(redis_client)
        logger.info("✅ Redis cache managers initialized")
    else:
        logger.warning("⚠️ Redis not available - running without cache")

async def close_redis():
    """Close Redis connection"""
    await redis_client.disconnect()
    logger.info("Redis connection closed")

# Utility functions for easy access
async def cache_session(session: CallSession) -> bool:
    """Cache a call session"""
    if session_cache:
        return await session_cache.save_session(session)
    return False

async def get_cached_session(session_id: str) -> Optional[CallSession]:
    """Get cached call session"""
    if session_cache:
        return await session_cache.get_session(session_id)
    return None

async def record_performance_metric(metric_type: str, value: float):
    """Record a performance metric"""
    if metrics_cache:
        await metrics_cache.record_call_metric(metric_type, value)