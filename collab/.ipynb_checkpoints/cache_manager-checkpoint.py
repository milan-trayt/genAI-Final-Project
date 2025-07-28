#!/usr/bin/env python3
"""
LangChain-integrated caching layer for performance optimization.
"""

import asyncio
import json
import logging
import hashlib
from datetime import datetime, timedelta
from typing import Optional, Dict, Any, List, Union

from langchain.cache import BaseCache
from langchain.schema import BaseMessage, HumanMessage, AIMessage, Generation, LLMResult
from langchain.callbacks.base import BaseCallbackHandler
from langchain.memory.chat_message_histories import BaseChatMessageHistory

from redis_manager import RedisManager, get_redis_manager
from config import get_config

logger = logging.getLogger(__name__)


class CacheCallbackHandler(BaseCallbackHandler):
    """Callback handler for cache-related events and metrics."""
    
    def __init__(self, cache_manager: 'CacheManager'):
        self.cache_manager = cache_manager
        self.cache_hits = 0
        self.cache_misses = 0
        self.start_time = None
    
    def on_llm_start(self, serialized: Dict[str, Any], prompts: List[str], **kwargs) -> None:
        """Called when LLM starts running."""
        self.start_time = datetime.now()
        logger.debug(f"LLM started with {len(prompts)} prompts")
    
    def on_llm_end(self, response: LLMResult, **kwargs) -> None:
        """Called when LLM ends running."""
        if self.start_time:
            duration = (datetime.now() - self.start_time).total_seconds()
            logger.debug(f"LLM completed in {duration:.2f}s")
            
            # Cache the response
            for generation in response.generations:
                for gen in generation:
                    asyncio.create_task(self._cache_generation(gen))
    
    async def _cache_generation(self, generation: Generation):
        """Cache a generation result."""
        try:
            # This would be called by the LLM cache implementation
            pass
        except Exception as e:
            logger.warning(f"Failed to cache generation: {e}")
    
    def on_llm_error(self, error: Union[Exception, KeyboardInterrupt], **kwargs) -> None:
        """Called when LLM errors."""
        logger.error(f"LLM error: {error}")
    
    def increment_cache_hit(self):
        """Increment cache hit counter."""
        self.cache_hits += 1
        logger.debug(f"Cache hit! Total hits: {self.cache_hits}")
    
    def increment_cache_miss(self):
        """Increment cache miss counter."""
        self.cache_misses += 1
        logger.debug(f"Cache miss! Total misses: {self.cache_misses}")
    
    def get_cache_stats(self) -> Dict[str, Any]:
        """Get cache statistics."""
        total_requests = self.cache_hits + self.cache_misses
        hit_rate = (self.cache_hits / total_requests) if total_requests > 0 else 0
        
        return {
            'cache_hits': self.cache_hits,
            'cache_misses': self.cache_misses,
            'total_requests': total_requests,
            'hit_rate': hit_rate,
            'timestamp': datetime.now().isoformat()
        }


class LangChainRedisCache(BaseCache):
    """Enhanced LangChain-compatible Redis cache with metrics and callbacks."""
    
    def __init__(self, redis_manager: RedisManager, ttl: int = 3600, callback_handler: CacheCallbackHandler = None):
        self.redis_manager = redis_manager
        self.ttl = ttl
        self.callback_handler = callback_handler
    
    def lookup(self, prompt: str, llm_string: str) -> Optional[List[Generation]]:
        """Look up cached response."""
        try:
            # For synchronous interface, we need to handle async operations carefully
            loop = asyncio.get_event_loop()
            if loop.is_running():
                # Create a task but don't wait for it in sync context
                task = asyncio.create_task(self._async_lookup(prompt, llm_string))
                # Return None for now - async version will handle caching
                return None
            else:
                return asyncio.run(self._async_lookup(prompt, llm_string))
        except Exception as e:
            logger.warning(f"Cache lookup failed: {e}")
            if self.callback_handler:
                self.callback_handler.increment_cache_miss()
            return None
    
    async def _async_lookup(self, prompt: str, llm_string: str) -> Optional[List[Generation]]:
        """Async version of lookup."""
        try:
            cache_key = self._generate_cache_key(prompt, llm_string)
            cached_response = await self.redis_manager.get_cached_response(cache_key)
            
            if cached_response:
                if self.callback_handler:
                    self.callback_handler.increment_cache_hit()
                
                # Parse cached response back to Generation objects
                try:
                    cached_data = json.loads(cached_response)
                    generations = [Generation(text=cached_data['text'])]
                    return generations
                except (json.JSONDecodeError, KeyError):
                    # If parsing fails, treat as cache miss
                    if self.callback_handler:
                        self.callback_handler.increment_cache_miss()
                    return None
            else:
                if self.callback_handler:
                    self.callback_handler.increment_cache_miss()
                return None
                
        except Exception as e:
            logger.warning(f"Async cache lookup failed: {e}")
            if self.callback_handler:
                self.callback_handler.increment_cache_miss()
            return None
    
    def update(self, prompt: str, llm_string: str, return_val: List[Generation]) -> None:
        """Update cache with new response."""
        try:
            cache_key = self._generate_cache_key(prompt, llm_string)
            
            if return_val and len(return_val) > 0:
                # Serialize the first generation
                generation_data = {
                    'text': return_val[0].text,
                    'generation_info': getattr(return_val[0], 'generation_info', None)
                }
                
                asyncio.create_task(
                    self.redis_manager.cache_response(
                        cache_key, 
                        json.dumps(generation_data), 
                        self.ttl
                    )
                )
                
        except Exception as e:
            logger.warning(f"Cache update failed: {e}")
    
    def _generate_cache_key(self, prompt: str, llm_string: str) -> str:
        """Generate cache key from prompt and LLM string."""
        key_data = f"llm_cache:{prompt}:{llm_string}"
        return hashlib.md5(key_data.encode()).hexdigest()


class SemanticCache:
    """Semantic cache for embeddings and similar queries."""
    
    def __init__(self, redis_manager: RedisManager, similarity_threshold: float = 0.95):
        self.redis_manager = redis_manager
        self.similarity_threshold = similarity_threshold
    
    async def get_similar_response(self, query_embedding: List[float], query_text: str) -> Optional[str]:
        """Get cached response for semantically similar query."""
        try:
            # For now, use exact text matching - could be enhanced with vector similarity
            cache_key = self._generate_semantic_key(query_text)
            return await self.redis_manager.get_cached_response(cache_key)
        except Exception as e:
            logger.warning(f"Semantic cache lookup failed: {e}")
            return None
    
    async def cache_semantic_response(self, query_embedding: List[float], query_text: str, response: str, ttl: int = 3600):
        """Cache response with semantic key."""
        try:
            cache_key = self._generate_semantic_key(query_text)
            await self.redis_manager.cache_response(cache_key, response, ttl)
            
            # Also cache the embedding for future similarity comparisons
            embedding_key = f"embedding:{cache_key}"
            await self.redis_manager.cache_embeddings(query_text, query_embedding, ttl)
            
        except Exception as e:
            logger.warning(f"Semantic cache storage failed: {e}")
    
    def _generate_semantic_key(self, query_text: str) -> str:
        """Generate semantic cache key."""
        # Normalize query text for better matching
        normalized_query = query_text.lower().strip()
        return hashlib.md5(f"semantic:{normalized_query}".encode()).hexdigest()


class MemoryCache:
    """Cache for LangChain memory objects and conversation state."""
    
    def __init__(self, redis_manager: RedisManager):
        self.redis_manager = redis_manager
    
    async def cache_memory_state(self, session_id: str, memory_data: Dict[str, Any], ttl: int = 3600):
        """Cache memory state for quick restoration."""
        try:
            cache_key = f"memory_state:{session_id}"
            await self.redis_manager.cache_session_state(session_id, memory_data, ttl)
            logger.debug(f"Cached memory state for session {session_id}")
        except Exception as e:
            logger.warning(f"Memory state caching failed for {session_id}: {e}")
    
    async def get_memory_state(self, session_id: str) -> Optional[Dict[str, Any]]:
        """Get cached memory state."""
        try:
            return await self.redis_manager.get_session_state(session_id)
        except Exception as e:
            logger.warning(f"Memory state retrieval failed for {session_id}: {e}")
            return None
    
    async def invalidate_memory_cache(self, session_id: str):
        """Invalidate cached memory state."""
        try:
            await self.redis_manager.clear_session_messages(session_id)
            logger.debug(f"Invalidated memory cache for session {session_id}")
        except Exception as e:
            logger.warning(f"Memory cache invalidation failed for {session_id}: {e}")


class CacheManager:
    """Comprehensive cache manager with LangChain integration."""
    
    def __init__(self, redis_manager: RedisManager = None):
        self.config = get_config()
        self.redis_manager = redis_manager
        self.callback_handler = CacheCallbackHandler(self)
        self.llm_cache: Optional[LangChainRedisCache] = None
        self.semantic_cache: Optional[SemanticCache] = None
        self.memory_cache: Optional[MemoryCache] = None
        self._initialized = False
    
    async def initialize(self):
        """Initialize cache manager."""
        if self._initialized:
            return
        
        if not self.redis_manager:
            self.redis_manager = await get_redis_manager()
        
        # Initialize cache components
        self.llm_cache = LangChainRedisCache(
            self.redis_manager, 
            ttl=3600, 
            callback_handler=self.callback_handler
        )
        
        self.semantic_cache = SemanticCache(self.redis_manager)
        self.memory_cache = MemoryCache(self.redis_manager)
        
        self._initialized = True
        logger.info("Cache manager initialized successfully")
    
    def get_langchain_cache(self) -> LangChainRedisCache:
        """Get LangChain-compatible cache instance."""
        if not self._initialized:
            raise RuntimeError("Cache manager not initialized")
        return self.llm_cache
    
    def get_semantic_cache(self) -> SemanticCache:
        """Get semantic cache instance."""
        if not self._initialized:
            raise RuntimeError("Cache manager not initialized")
        return self.semantic_cache
    
    def get_memory_cache(self) -> MemoryCache:
        """Get memory cache instance."""
        if not self._initialized:
            raise RuntimeError("Cache manager not initialized")
        return self.memory_cache
    
    def get_callback_handler(self) -> CacheCallbackHandler:
        """Get cache callback handler for metrics."""
        return self.callback_handler
    
    async def warm_cache(self, common_queries: List[str]):
        """Warm up cache with common queries."""
        logger.info(f"Warming cache with {len(common_queries)} common queries")
        
        for query in common_queries:
            try:
                # This would typically involve running the queries through the system
                # For now, we'll just log the warming process
                logger.debug(f"Warming cache for query: {query[:50]}...")
            except Exception as e:
                logger.warning(f"Cache warming failed for query: {e}")
    
    async def cleanup_expired_cache(self):
        """Clean up expired cache entries."""
        try:
            await self.redis_manager.flush_cache("*:expired:*")
            logger.info("Cleaned up expired cache entries")
        except Exception as e:
            logger.error(f"Cache cleanup failed: {e}")
    
    async def get_cache_statistics(self) -> Dict[str, Any]:
        """Get comprehensive cache statistics."""
        try:
            redis_stats = await self.redis_manager.get_cache_stats() if hasattr(self.redis_manager, 'get_cache_stats') else {}
            callback_stats = self.callback_handler.get_cache_stats()
            
            return {
                'redis_stats': redis_stats,
                'callback_stats': callback_stats,
                'timestamp': datetime.now().isoformat()
            }
        except Exception as e:
            logger.error(f"Failed to get cache statistics: {e}")
            return {'error': str(e)}
    
    async def flush_all_caches(self):
        """Flush all cache types."""
        try:
            await self.redis_manager.flush_cache()
            logger.info("Flushed all caches")
        except Exception as e:
            logger.error(f"Cache flush failed: {e}")
    
    async def close(self):
        """Close cache manager."""
        self._initialized = False
        logger.info("Cache manager closed")


# Global cache manager instance
_cache_manager = None


async def get_cache_manager() -> CacheManager:
    """Get or create cache manager instance."""
    global _cache_manager
    
    if _cache_manager is None:
        _cache_manager = CacheManager()
        await _cache_manager.initialize()
    
    return _cache_manager


async def close_cache_manager():
    """Close cache manager."""
    global _cache_manager
    
    if _cache_manager:
        await _cache_manager.close()
        _cache_manager = None