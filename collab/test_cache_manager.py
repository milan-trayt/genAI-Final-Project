#!/usr/bin/env python3
"""
Unit tests for CacheManager using LangChain cache testing tools.
"""

import asyncio
import pytest
import json
from unittest.mock import AsyncMock, MagicMock, patch
from datetime import datetime

from langchain.schema import Generation, LLMResult
from langchain.schema import HumanMessage, AIMessage

from cache_manager import CacheManager, LangChainRedisCache, SemanticCache, MemoryCache, CacheCallbackHandler
from redis_manager import RedisManager


class TestCacheManager:
    """Test cases for CacheManager."""
    
    @pytest.fixture
    def mock_redis_manager(self):
        """Mock Redis manager."""
        redis_manager = AsyncMock(spec=RedisManager)
        redis_manager.get_cached_response.return_value = None
        redis_manager.cache_response.return_value = True
        redis_manager.get_cached_embeddings.return_value = None
        redis_manager.cache_embeddings.return_value = True
        redis_manager.get_session_state.return_value = None
        redis_manager.cache_session_state.return_value = True
        return redis_manager
    
    @pytest.fixture
    async def cache_manager(self, mock_redis_manager):
        """Create CacheManager with mocked dependencies."""
        manager = CacheManager(mock_redis_manager)
        await manager.initialize()
        return manager
    
    @pytest.mark.asyncio
    async def test_initialization(self, cache_manager):
        """Test cache manager initialization."""
        assert cache_manager._initialized is True
        assert cache_manager.llm_cache is not None
        assert cache_manager.semantic_cache is not None
        assert cache_manager.memory_cache is not None
    
    def test_get_langchain_cache(self, cache_manager):
        """Test getting LangChain cache instance."""
        cache = cache_manager.get_langchain_cache()
        
        assert isinstance(cache, LangChainRedisCache)
        assert cache.redis_manager == cache_manager.redis_manager
    
    def test_get_semantic_cache(self, cache_manager):
        """Test getting semantic cache instance."""
        cache = cache_manager.get_semantic_cache()
        
        assert isinstance(cache, SemanticCache)
        assert cache.redis_manager == cache_manager.redis_manager
    
    def test_get_memory_cache(self, cache_manager):
        """Test getting memory cache instance."""
        cache = cache_manager.get_memory_cache()
        
        assert isinstance(cache, MemoryCache)
        assert cache.redis_manager == cache_manager.redis_manager
    
    def test_get_callback_handler(self, cache_manager):
        """Test getting callback handler."""
        handler = cache_manager.get_callback_handler()
        
        assert isinstance(handler, CacheCallbackHandler)
        assert handler.cache_manager == cache_manager
    
    @pytest.mark.asyncio
    async def test_warm_cache(self, cache_manager):
        """Test cache warming."""
        common_queries = ["What is Python?", "How to use Docker?", "AWS best practices"]
        
        # This should not raise an exception
        await cache_manager.warm_cache(common_queries)
    
    @pytest.mark.asyncio
    async def test_get_cache_statistics(self, cache_manager, mock_redis_manager):
        """Test getting cache statistics."""
        # Mock redis stats
        mock_redis_manager.get_cache_stats = AsyncMock(return_value={
            'connected_clients': 1,
            'used_memory': '1MB',
            'keyspace_hits': 100,
            'keyspace_misses': 20
        })
        
        stats = await cache_manager.get_cache_statistics()
        
        assert 'callback_stats' in stats
        assert 'timestamp' in stats
    
    @pytest.mark.asyncio
    async def test_flush_all_caches(self, cache_manager, mock_redis_manager):
        """Test flushing all caches."""
        mock_redis_manager.flush_cache.return_value = True
        
        await cache_manager.flush_all_caches()
        
        mock_redis_manager.flush_cache.assert_called_once()


class TestLangChainRedisCache:
    """Test cases for LangChainRedisCache."""
    
    @pytest.fixture
    def mock_redis_manager(self):
        """Mock Redis manager."""
        redis_manager = AsyncMock(spec=RedisManager)
        return redis_manager
    
    @pytest.fixture
    def mock_callback_handler(self):
        """Mock callback handler."""
        handler = MagicMock(spec=CacheCallbackHandler)
        return handler
    
    @pytest.fixture
    def redis_cache(self, mock_redis_manager, mock_callback_handler):
        """Create LangChainRedisCache."""
        return LangChainRedisCache(
            redis_manager=mock_redis_manager,
            ttl=3600,
            callback_handler=mock_callback_handler
        )
    
    def test_lookup_cache_miss(self, redis_cache, mock_redis_manager, mock_callback_handler):
        """Test cache lookup with cache miss."""
        mock_redis_manager.get_cached_response.return_value = None
        
        result = redis_cache.lookup("test prompt", "test llm")
        
        # Should return None for cache miss in sync context
        assert result is None
        mock_callback_handler.increment_cache_miss.assert_called_once()
    
    def test_update_cache(self, redis_cache, mock_redis_manager):
        """Test cache update."""
        generations = [Generation(text="Test response")]
        
        redis_cache.update("test prompt", "test llm", generations)
        
        # Should create async task to cache response
        # We can't easily test the async task creation in sync test
        assert True  # Test passes if no exception is raised
    
    def test_generate_cache_key(self, redis_cache):
        """Test cache key generation."""
        key = redis_cache._generate_cache_key("test prompt", "test llm")
        
        assert isinstance(key, str)
        assert len(key) == 32  # MD5 hash length


class TestSemanticCache:
    """Test cases for SemanticCache."""
    
    @pytest.fixture
    def mock_redis_manager(self):
        """Mock Redis manager."""
        redis_manager = AsyncMock(spec=RedisManager)
        return redis_manager
    
    @pytest.fixture
    def semantic_cache(self, mock_redis_manager):
        """Create SemanticCache."""
        return SemanticCache(redis_manager=mock_redis_manager)
    
    @pytest.mark.asyncio
    async def test_get_similar_response(self, semantic_cache, mock_redis_manager):
        """Test getting similar response."""
        query_embedding = [0.1] * 1536
        query_text = "What is Python?"
        
        mock_redis_manager.get_cached_response.return_value = "Python is a programming language."
        
        response = await semantic_cache.get_similar_response(query_embedding, query_text)
        
        assert response == "Python is a programming language."
        mock_redis_manager.get_cached_response.assert_called_once()
    
    @pytest.mark.asyncio
    async def test_cache_semantic_response(self, semantic_cache, mock_redis_manager):
        """Test caching semantic response."""
        query_embedding = [0.1] * 1536
        query_text = "What is Python?"
        response = "Python is a programming language."
        
        mock_redis_manager.cache_response.return_value = True
        mock_redis_manager.cache_embeddings.return_value = True
        
        await semantic_cache.cache_semantic_response(query_embedding, query_text, response)
        
        mock_redis_manager.cache_response.assert_called_once()
        mock_redis_manager.cache_embeddings.assert_called_once()
    
    def test_generate_semantic_key(self, semantic_cache):
        """Test semantic key generation."""
        query_text = "What is Python?"
        
        key = semantic_cache._generate_semantic_key(query_text)
        
        assert isinstance(key, str)
        assert len(key) == 32  # MD5 hash length


class TestMemoryCache:
    """Test cases for MemoryCache."""
    
    @pytest.fixture
    def mock_redis_manager(self):
        """Mock Redis manager."""
        redis_manager = AsyncMock(spec=RedisManager)
        return redis_manager
    
    @pytest.fixture
    def memory_cache(self, mock_redis_manager):
        """Create MemoryCache."""
        return MemoryCache(redis_manager=mock_redis_manager)
    
    @pytest.mark.asyncio
    async def test_cache_memory_state(self, memory_cache, mock_redis_manager):
        """Test caching memory state."""
        session_id = "test_session_123"
        memory_data = {"messages": [], "summary": "Test conversation"}
        
        mock_redis_manager.cache_session_state.return_value = True
        
        await memory_cache.cache_memory_state(session_id, memory_data)
        
        mock_redis_manager.cache_session_state.assert_called_once_with(
            session_id, memory_data, 3600
        )
    
    @pytest.mark.asyncio
    async def test_get_memory_state(self, memory_cache, mock_redis_manager):
        """Test getting memory state."""
        session_id = "test_session_123"
        expected_state = {"messages": [], "summary": "Test conversation"}
        
        mock_redis_manager.get_session_state.return_value = expected_state
        
        state = await memory_cache.get_memory_state(session_id)
        
        assert state == expected_state
        mock_redis_manager.get_session_state.assert_called_once_with(session_id)
    
    @pytest.mark.asyncio
    async def test_invalidate_memory_cache(self, memory_cache, mock_redis_manager):
        """Test invalidating memory cache."""
        session_id = "test_session_123"
        
        mock_redis_manager.clear_session_messages.return_value = True
        
        await memory_cache.invalidate_memory_cache(session_id)
        
        mock_redis_manager.clear_session_messages.assert_called_once_with(session_id)


class TestCacheCallbackHandler:
    """Test cases for CacheCallbackHandler."""
    
    @pytest.fixture
    def mock_cache_manager(self):
        """Mock cache manager."""
        return MagicMock(spec=CacheManager)
    
    @pytest.fixture
    def callback_handler(self, mock_cache_manager):
        """Create CacheCallbackHandler."""
        return CacheCallbackHandler(mock_cache_manager)
    
    def test_increment_cache_hit(self, callback_handler):
        """Test incrementing cache hit counter."""
        initial_hits = callback_handler.cache_hits
        
        callback_handler.increment_cache_hit()
        
        assert callback_handler.cache_hits == initial_hits + 1
    
    def test_increment_cache_miss(self, callback_handler):
        """Test incrementing cache miss counter."""
        initial_misses = callback_handler.cache_misses
        
        callback_handler.increment_cache_miss()
        
        assert callback_handler.cache_misses == initial_misses + 1
    
    def test_get_cache_stats(self, callback_handler):
        """Test getting cache statistics."""
        # Add some hits and misses
        callback_handler.increment_cache_hit()
        callback_handler.increment_cache_hit()
        callback_handler.increment_cache_miss()
        
        stats = callback_handler.get_cache_stats()
        
        assert stats['cache_hits'] == 2
        assert stats['cache_misses'] == 1
        assert stats['total_requests'] == 3
        assert stats['hit_rate'] == 2/3
        assert 'timestamp' in stats
    
    def test_on_llm_start(self, callback_handler):
        """Test LLM start callback."""
        serialized = {"name": "test_llm"}
        prompts = ["test prompt"]
        
        # Should not raise exception
        callback_handler.on_llm_start(serialized, prompts)
    
    def test_on_llm_end(self, callback_handler):
        """Test LLM end callback."""
        response = MagicMock(spec=LLMResult)
        response.llm_output = {"token_usage": {"total_tokens": 100}}
        
        # Set start time first
        callback_handler.on_llm_start({"name": "test"}, ["prompt"])
        callback_handler.on_llm_end(response)
        
        assert callback_handler.total_tokens == 100
    
    def test_on_llm_error(self, callback_handler):
        """Test LLM error callback."""
        error = Exception("Test error")
        
        # Should not raise exception
        callback_handler.on_llm_error(error)


if __name__ == "__main__":
    # Run tests
    pytest.main([__file__, "-v"])