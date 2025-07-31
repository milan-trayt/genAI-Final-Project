#!/usr/bin/env python3
"""
Redis client wrapper for caching operations with LangChain integration.
"""

import asyncio
import json
import logging
import hashlib
from datetime import datetime, timedelta
from typing import Optional, Dict, Any, List
from contextlib import asynccontextmanager

import redis.asyncio as redis
from redis.asyncio import Redis
from langchain.schema import BaseMessage, HumanMessage, AIMessage
from langchain_core.chat_history import BaseChatMessageHistory
from langchain_core.caches import BaseCache

from config import get_config

logger = logging.getLogger(__name__)


class RedisChatMessageHistory(BaseChatMessageHistory):
    """LangChain-compatible Redis chat message history."""
    
    def __init__(self, session_id: str, redis_manager: 'RedisManager', ttl: int = 3600):
        self.session_id = session_id
        self.redis_manager = redis_manager
        self.ttl = ttl
        self._messages: List[BaseMessage] = []
        self._loaded = False
    
    @property
    def messages(self) -> List[BaseMessage]:
        """Get messages, loading from Redis if needed."""
        if not self._loaded:
            asyncio.create_task(self._load_messages())
        return self._messages
    
    async def _load_messages(self):
        """Load messages from Redis."""
        try:
            messages = await self.redis_manager.get_session_messages(self.session_id)
            self._messages = messages or []
            self._loaded = True
        except Exception as e:
            logger.error(f"Failed to load messages from Redis for session {self.session_id}: {e}")
            self._messages = []
            self._loaded = True
    
    def add_message(self, message: BaseMessage) -> None:
        """Add a message to the history."""
        self._messages.append(message)
        # Save to Redis asynchronously
        asyncio.create_task(self._save_messages())
    
    async def _save_messages(self):
        """Save messages to Redis."""
        try:
            await self.redis_manager.save_session_messages(self.session_id, self._messages, self.ttl)
        except Exception as e:
            logger.error(f"Failed to save messages to Redis for session {self.session_id}: {e}")
    
    def clear(self) -> None:
        """Clear all messages."""
        self._messages.clear()
        asyncio.create_task(self.redis_manager.clear_session_messages(self.session_id))


class LangChainRedisCache(BaseCache):
    """LangChain-compatible Redis cache implementation."""
    
    def __init__(self, redis_manager: 'RedisManager', ttl: int = 3600):
        self.redis_manager = redis_manager
        self.ttl = ttl
    
    def lookup(self, prompt: str, llm_string: str) -> Optional[List[str]]:
        """Look up cached response."""
        try:
            # Create async task to get cached response
            loop = asyncio.get_event_loop()
            if loop.is_running():
                # If we're in an async context, we can't use asyncio.run
                task = asyncio.create_task(self._async_lookup(prompt, llm_string))
                return None  # Return None for now, will be handled by async version
            else:
                return asyncio.run(self._async_lookup(prompt, llm_string))
        except Exception as e:
            logger.warning(f"Cache lookup failed: {e}")
            return None
    
    async def _async_lookup(self, prompt: str, llm_string: str) -> Optional[List[str]]:
        """Async version of lookup."""
        cache_key = self._generate_cache_key(prompt, llm_string)
        cached_response = await self.redis_manager.get_cached_response(cache_key)
        return [cached_response] if cached_response else None
    
    def update(self, prompt: str, llm_string: str, return_val: List[str]) -> None:
        """Update cache with new response."""
        try:
            cache_key = self._generate_cache_key(prompt, llm_string)
            response = return_val[0] if return_val else ""
            asyncio.create_task(self.redis_manager.cache_response(cache_key, response, self.ttl))
        except Exception as e:
            logger.warning(f"Cache update failed: {e}")
    
    def _generate_cache_key(self, prompt: str, llm_string: str) -> str:
        """Generate cache key from prompt and LLM string."""
        key_data = f"{prompt}:{llm_string}"
        return hashlib.md5(key_data.encode()).hexdigest()


class RedisManager:
    """Redis cache manager with LangChain integration."""
    
    def __init__(self, config=None):
        self.config = config or get_config()
        self.redis_client: Optional[Redis] = None
        self._initialized = False
    
    async def initialize(self) -> bool:
        """Initialize Redis connection."""
        if self._initialized:
            return True
            
        try:
            self.redis_client = redis.Redis(
                host=self.config.redis.host,
                port=self.config.redis.port,
                db=self.config.redis.db,
                password=self.config.redis.password,
                ssl=self.config.redis.ssl,
                socket_timeout=self.config.redis.timeout,
                max_connections=self.config.redis.max_connections,
                retry_on_timeout=self.config.redis.retry_on_timeout,
                decode_responses=True
            )
            
            # Test connection
            await self.redis_client.ping()
            self._initialized = True
            logger.info("Redis manager initialized successfully")
            return True
            
        except Exception as e:
            logger.error(f"Redis initialization failed: {e}")
            self.redis_client = None
            self._initialized = False
            return False
    
    async def health_check(self) -> bool:
        """Check Redis health."""
        if not self.redis_client:
            return False
        
        try:
            await self.redis_client.ping()
            return True
        except Exception as e:
            logger.error(f"Redis health check failed: {e}")
            return False
    
    async def close(self):
        """Close Redis connection."""
        if self.redis_client:
            await self.redis_client.close()
            self.redis_client = None
            self._initialized = False
    
    def _generate_cache_key(self, prefix: str, *args) -> str:
        """Generate a cache key from prefix and arguments."""
        key_data = f"{prefix}:{':'.join(str(arg) for arg in args)}"
        return hashlib.md5(key_data.encode()).hexdigest()
    
    async def get_cached_response(self, cache_key: str) -> Optional[str]:
        """Get cached response from Redis."""
        if not self.redis_client:
            return None
        
        try:
            cached_data = await self.redis_client.get(f"llm_response:{cache_key}")
            return cached_data
        except Exception as e:
            logger.warning(f"Cache retrieval failed for key {cache_key}: {e}")
            return None
    
    async def cache_response(self, cache_key: str, response: str, ttl: int = 3600) -> bool:
        """Cache response in Redis."""
        if not self.redis_client:
            return False
        
        try:
            await self.redis_client.setex(
                f"llm_response:{cache_key}",
                ttl,
                response
            )
            logger.debug(f"Cached response with key {cache_key}")
            return True
        except Exception as e:
            logger.warning(f"Cache storage failed for key {cache_key}: {e}")
            return False
    
    async def get_cached_embeddings(self, query: str) -> Optional[List[float]]:
        """Get cached embeddings for a query."""
        if not self.redis_client:
            return None
        
        try:
            cache_key = self._generate_cache_key("embedding", query)
            cached_data = await self.redis_client.get(f"embedding:{cache_key}")
            
            if cached_data:
                return json.loads(cached_data)
            return None
        except Exception as e:
            logger.warning(f"Embedding cache retrieval failed: {e}")
            return None
    
    async def cache_embeddings(self, query: str, embeddings: List[float], ttl: int = 86400) -> bool:
        """Cache embeddings for a query (24 hour default TTL)."""
        if not self.redis_client:
            return False
        
        try:
            cache_key = self._generate_cache_key("embedding", query)
            
            await self.redis_client.setex(
                f"embedding:{cache_key}",
                ttl,
                json.dumps(embeddings)
            )
            logger.debug(f"Cached embeddings for query: {query[:50]}...")
            return True
        except Exception as e:
            logger.warning(f"Embedding cache storage failed: {e}")
            return False
    
    async def get_session_messages(self, session_id: str) -> Optional[List[BaseMessage]]:
        """Get cached session messages."""
        if not self.redis_client:
            return None
        
        try:
            cached_data = await self.redis_client.get(f"session_messages:{session_id}")
            if not cached_data:
                return None
            
            # Validate cached data is valid JSON
            if not isinstance(cached_data, str):
                logger.warning(f"Invalid cached data type for session {session_id}: {type(cached_data)}")
                return None
            
            messages_data = json.loads(cached_data)
            if not isinstance(messages_data, list):
                logger.warning(f"Invalid message data format for session {session_id}: expected list, got {type(messages_data)}")
                return None
            
            messages = []
            
            for msg_data in messages_data:
                if not isinstance(msg_data, dict):
                    logger.warning(f"Skipping invalid message data: {type(msg_data)}")
                    continue
                    
                if msg_data.get('type') == 'human':
                    message = HumanMessage(
                        content=msg_data.get('content', ''),
                        additional_kwargs=msg_data.get('additional_kwargs', {})
                    )
                elif msg_data.get('type') == 'ai':
                    message = AIMessage(
                        content=msg_data.get('content', ''),
                        additional_kwargs=msg_data.get('additional_kwargs', {})
                    )
                else:
                    continue
                
                messages.append(message)
            
            return messages
        except json.JSONDecodeError as e:
            logger.warning(f"JSON decode error for session {session_id}: {e}")
            return None
        except Exception as e:
            logger.warning(f"Session message retrieval failed for {session_id}: {e}")
            return None
    
    async def save_session_messages(self, session_id: str, messages: List[BaseMessage], ttl: int = 3600) -> bool:
        """Save session messages to Redis."""
        if not self.redis_client:
            return False
        
        try:
            messages_data = []
            for message in messages:
                msg_data = {
                    'type': 'human' if isinstance(message, HumanMessage) else 'ai',
                    'content': message.content,
                    'additional_kwargs': getattr(message, 'additional_kwargs', {})
                }
                messages_data.append(msg_data)
            
            await self.redis_client.setex(
                f"session_messages:{session_id}",
                ttl,
                json.dumps(messages_data)
            )
            logger.debug(f"Cached session messages for {session_id}")
            return True
        except Exception as e:
            logger.warning(f"Session message cache storage failed for {session_id}: {e}")
            return False
    
    async def clear_session_messages(self, session_id: str) -> bool:
        """Clear cached session messages."""
        if not self.redis_client:
            return False
        
        try:
            await self.redis_client.delete(f"session_messages:{session_id}")
            logger.debug(f"Cleared session cache for {session_id}")
            return True
        except Exception as e:
            logger.warning(f"Session cache clearing failed for {session_id}: {e}")
            return False
    
    async def get_session_state(self, session_id: str) -> Optional[Dict[str, Any]]:
        """Get cached session state."""
        if not self.redis_client:
            return None
        
        try:
            cached_data = await self.redis_client.get(f"session_state:{session_id}")
            if cached_data:
                return json.loads(cached_data)
            return None
        except Exception as e:
            logger.warning(f"Session state retrieval failed for {session_id}: {e}")
            return None
    
    async def cache_session_state(self, session_id: str, state: Dict[str, Any], ttl: int = 3600) -> bool:
        """Cache session state."""
        if not self.redis_client:
            return False
        
        try:
            await self.redis_client.setex(
                f"session_state:{session_id}",
                ttl,
                json.dumps(state, default=str)
            )
            logger.debug(f"Cached session state for {session_id}")
            return True
        except Exception as e:
            logger.warning(f"Session state cache storage failed for {session_id}: {e}")
            return False
    
    async def flush_cache(self, pattern: str = None) -> bool:
        """Flush cache entries matching pattern or all if no pattern."""
        if not self.redis_client:
            return False
        
        try:
            if pattern:
                keys = await self.redis_client.keys(pattern)
                if keys:
                    await self.redis_client.delete(*keys)
                    logger.info(f"Flushed {len(keys)} cache entries matching {pattern}")
            else:
                await self.redis_client.flushdb()
                logger.info("Flushed all cache entries")
            
            return True
        except Exception as e:
            logger.error(f"Cache flush failed: {e}")
            return False
    
    def get_langchain_cache(self, ttl: int = 3600) -> LangChainRedisCache:
        """Get LangChain-compatible cache instance."""
        return LangChainRedisCache(self, ttl)
    
    def get_chat_message_history(self, session_id: str, ttl: int = 3600) -> RedisChatMessageHistory:
        """Get LangChain-compatible chat message history for a session."""
        return RedisChatMessageHistory(session_id, self, ttl)


# Global Redis manager instance
_redis_manager = None


async def get_redis_manager() -> RedisManager:
    """Get or create Redis manager instance."""
    global _redis_manager
    
    if _redis_manager is None:
        _redis_manager = RedisManager()
        await _redis_manager.initialize()
    
    return _redis_manager


async def close_redis_manager():
    """Close Redis manager."""
    global _redis_manager
    
    if _redis_manager:
        await _redis_manager.close()
        _redis_manager = None