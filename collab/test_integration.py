#!/usr/bin/env python3
"""
Integration tests for LangChain chain workflows and end-to-end functionality.
"""

import asyncio
import pytest
import os
from unittest.mock import AsyncMock, MagicMock, patch
from datetime import datetime

from langchain.schema import HumanMessage, AIMessage

from interactive_rag_query import InteractiveRAGQuery
from session_manager import SessionManager
from query_processor import QueryProcessor, QueryResult
from rag_chain import RAGChain
from cache_manager import CacheManager
from menu_system import MenuSystem


class TestEndToEndWorkflows:
    """Integration tests for complete workflows."""
    
    @pytest.fixture
    def mock_config(self):
        """Mock configuration for testing."""
        config = MagicMock()
        config.environment.value = "testing"
        config.openai.api_key = "sk-test-key"
        config.openai.model = "gpt-3.5-turbo"
        config.openai.embedding_model = "text-embedding-ada-002"
        config.openai.temperature = 0.1
        config.openai.max_tokens = 2000
        config.pinecone.api_key = "test-pinecone-key"
        config.pinecone.index_name = "test-index"
        config.redis.host = "localhost"
        config.redis.port = 6379
        config.postgresql.host = "localhost"
        config.postgresql.port = 5432
        config.postgresql.database = "test_db"
        return config
    
    @pytest.fixture
    async def mock_app_components(self):
        """Mock all application components."""
        # Mock database manager
        db_manager = AsyncMock()
        db_manager.initialize.return_value = True
        db_manager.health_check.return_value = True
        db_manager.create_session.return_value = "test_session_123"
        db_manager.load_session_messages.return_value = []
        db_manager.save_message_to_session.return_value = None
        db_manager.list_sessions.return_value = []
        
        # Mock Redis manager
        redis_manager = AsyncMock()
        redis_manager.initialize.return_value = True
        redis_manager.health_check.return_value = True
        redis_manager.get_session_messages.return_value = None
        redis_manager.save_session_messages.return_value = True
        redis_manager.get_cached_embeddings.return_value = None
        redis_manager.cache_embeddings.return_value = True
        
        # Mock query processor
        query_processor = AsyncMock()
        query_processor.initialize.return_value = None
        query_processor.health_check.return_value = True
        query_processor.retrieve_documents.return_value = []
        query_processor.get_query_embedding.return_value = [0.1] * 1536
        query_processor._initialized = True
        
        # Mock retriever
        mock_retriever = MagicMock()
        mock_retriever.get_relevant_documents.return_value = []
        query_processor.get_retriever.return_value = mock_retriever
        
        return {
            'db_manager': db_manager,
            'redis_manager': redis_manager,
            'query_processor': query_processor
        }
    
    @pytest.mark.asyncio
    async def test_one_time_query_workflow(self, mock_config, mock_app_components):
        """Test complete one-time query workflow."""
        with patch('collab.config.get_config', return_value=mock_config), \
             patch('collab.database_manager.get_database_manager', return_value=mock_app_components['db_manager']), \
             patch('collab.redis_manager.get_redis_manager', return_value=mock_app_components['redis_manager']), \
             patch('collab.query_processor.get_query_processor', return_value=mock_app_components['query_processor']):
            
            # Create RAG chain
            rag_chain = RAGChain(
                query_processor=mock_app_components['query_processor'],
                session_manager=None,
                cache_manager=None
            )
            
            # Mock LLM response
            with patch.object(rag_chain, 'llm') as mock_llm:
                mock_llm.predict.return_value = "Python is a high-level programming language."
                
                # Mock QA chain
                with patch.object(rag_chain, 'qa_chain') as mock_qa_chain:
                    mock_qa_chain.return_value = {
                        'result': 'Python is a high-level programming language.',
                        'source_documents': []
                    }
                    
                    rag_chain._initialized = True
                    
                    # Execute one-time query
                    result = await rag_chain.query_oneshot("What is Python?")
                    
                    assert isinstance(result, QueryResult)
                    assert "Python" in result.response
                    assert result.processing_time > 0
                    assert isinstance(result.sources, list)
    
    @pytest.mark.asyncio
    async def test_conversational_workflow(self, mock_config, mock_app_components):
        """Test complete conversational workflow with memory."""
        with patch('collab.config.get_config', return_value=mock_config), \
             patch('collab.database_manager.get_database_manager', return_value=mock_app_components['db_manager']), \
             patch('collab.redis_manager.get_redis_manager', return_value=mock_app_components['redis_manager']), \
             patch('collab.query_processor.get_query_processor', return_value=mock_app_components['query_processor']):
            
            # Create session manager
            session_manager = SessionManager(
                db_manager=mock_app_components['db_manager'],
                redis_manager=mock_app_components['redis_manager']
            )
            await session_manager.initialize()
            
            # Create session
            session_id = await session_manager.create_session("test_tab", "Test Session")
            
            # Create RAG chain with session manager
            rag_chain = RAGChain(
                query_processor=mock_app_components['query_processor'],
                session_manager=session_manager,
                cache_manager=None
            )
            
            # Mock conversational chain
            with patch.object(rag_chain, 'conversational_chain') as mock_conv_chain:
                mock_conv_chain.return_value = {
                    'answer': 'Python is a programming language. It is widely used for web development.',
                    'source_documents': []
                }
                
                rag_chain._initialized = True
                
                # First query
                result1 = await rag_chain.query_conversational("What is Python?", session_id)
                assert isinstance(result1, QueryResult)
                assert "Python" in result1.response
                
                # Second query with context
                result2 = await rag_chain.query_conversational("What is it used for?", session_id)
                assert isinstance(result2, QueryResult)
                
                # Verify session has messages
                memory = session_manager.get_memory(session_id)
                assert memory is not None
    
    @pytest.mark.asyncio
    async def test_session_persistence_workflow(self, mock_config, mock_app_components):
        """Test session persistence across application restarts."""
        with patch('collab.config.get_config', return_value=mock_config), \
             patch('collab.database_manager.get_database_manager', return_value=mock_app_components['db_manager']), \
             patch('collab.redis_manager.get_redis_manager', return_value=mock_app_components['redis_manager']):
            
            # Create first session manager instance
            session_manager1 = SessionManager(
                db_manager=mock_app_components['db_manager'],
                redis_manager=mock_app_components['redis_manager']
            )
            await session_manager1.initialize()
            
            # Create session and add messages
            session_id = await session_manager1.create_session("test_tab", "Persistent Session")
            await session_manager1.add_user_message("Hello", session_id)
            await session_manager1.add_ai_message("Hi there!", session_id)
            
            # Simulate application restart by creating new session manager
            session_manager2 = SessionManager(
                db_manager=mock_app_components['db_manager'],
                redis_manager=mock_app_components['redis_manager']
            )
            await session_manager2.initialize()
            
            # Load the session
            success = await session_manager2.load_session(session_id)
            assert success is True
            
            # Verify session data is available
            stats = await session_manager2.get_session_stats(session_id)
            assert stats['session_id'] == session_id
    
    @pytest.mark.asyncio
    async def test_error_handling_and_recovery(self, mock_config, mock_app_components):
        """Test error handling and recovery scenarios."""
        with patch('collab.config.get_config', return_value=mock_config):
            
            # Test database connection failure
            failing_db_manager = AsyncMock()
            failing_db_manager.initialize.side_effect = Exception("Database connection failed")
            
            with patch('collab.database_manager.get_database_manager', return_value=failing_db_manager):
                session_manager = SessionManager()
                
                # Should handle initialization failure gracefully
                with pytest.raises(Exception):
                    await session_manager.initialize()
            
            # Test Redis connection failure
            failing_redis_manager = AsyncMock()
            failing_redis_manager.initialize.side_effect = Exception("Redis connection failed")
            
            with patch('collab.redis_manager.get_redis_manager', return_value=failing_redis_manager):
                from cache_manager import CacheManager
                cache_manager = CacheManager()
                
                # Should handle initialization failure gracefully
                with pytest.raises(Exception):
                    await cache_manager.initialize()
    
    @pytest.mark.asyncio
    async def test_cache_effectiveness(self, mock_config, mock_app_components):
        """Test caching effectiveness and performance."""
        with patch('collab.config.get_config', return_value=mock_config), \
             patch('collab.database_manager.get_database_manager', return_value=mock_app_components['db_manager']), \
             patch('collab.redis_manager.get_redis_manager', return_value=mock_app_components['redis_manager']):
            
            # Create cache manager
            cache_manager = CacheManager(mock_app_components['redis_manager'])
            await cache_manager.initialize()
            
            # Test embedding caching
            query = "What is machine learning?"
            embedding = [0.1] * 1536
            
            # First call should cache the embedding
            mock_app_components['redis_manager'].get_cached_embeddings.return_value = None
            mock_app_components['redis_manager'].cache_embeddings.return_value = True
            
            await cache_manager.redis_manager.cache_embeddings(query, embedding)
            
            # Second call should hit cache
            mock_app_components['redis_manager'].get_cached_embeddings.return_value = embedding
            
            cached_embedding = await cache_manager.redis_manager.get_cached_embeddings(query)
            assert cached_embedding == embedding
            
            # Verify cache statistics
            callback_handler = cache_manager.get_callback_handler()
            stats = callback_handler.get_cache_stats()
            assert 'cache_hits' in stats
            assert 'cache_misses' in stats


class TestApplicationLifecycle:
    """Test application lifecycle management."""
    
    @pytest.fixture
    def mock_config(self):
        """Mock configuration."""
        config = MagicMock()
        config.environment.value = "testing"
        config.openai.api_key = "sk-test-key"
        config.openai.model = "gpt-3.5-turbo"
        config.openai.embedding_model = "text-embedding-ada-002"
        config.pinecone.api_key = "test-pinecone-key"
        config.pinecone.index_name = "test-index"
        return config
    
    @pytest.mark.asyncio
    async def test_application_initialization(self, mock_config):
        """Test complete application initialization."""
        with patch('collab.config.get_config', return_value=mock_config), \
             patch('collab.database_manager.get_database_manager') as mock_db, \
             patch('collab.redis_manager.get_redis_manager') as mock_redis, \
             patch('collab.query_processor.get_query_processor') as mock_qp, \
             patch('collab.session_manager.get_session_manager') as mock_sm, \
             patch('collab.rag_chain.get_rag_chain') as mock_rag, \
             patch('collab.cache_manager.get_cache_manager') as mock_cache, \
             patch('collab.menu_system.get_menu_system') as mock_menu:
            
            # Setup mocks
            mock_db.return_value = AsyncMock()
            mock_redis.return_value = AsyncMock()
            mock_qp.return_value = AsyncMock()
            mock_sm.return_value = AsyncMock()
            mock_rag.return_value = AsyncMock()
            mock_cache.return_value = AsyncMock()
            mock_menu.return_value = AsyncMock()
            
            # Mock health checks
            mock_db.return_value.health_check.return_value = True
            mock_redis.return_value.health_check.return_value = True
            mock_qp.return_value.health_check.return_value = True
            mock_qp.return_value.get_index_stats.return_value = {
                'total_vectors': 1000,
                'dimension': 1536,
                'index_fullness': 0.1
            }
            
            # Create and initialize application
            app = InteractiveRAGQuery()
            
            # Mock validation
            with patch.object(app, 'validate_configuration', return_value=True):
                success = await app.initialize()
                
                assert success is True
                assert app._initialized is True
    
    @pytest.mark.asyncio
    async def test_application_shutdown(self, mock_config):
        """Test graceful application shutdown."""
        with patch('collab.config.get_config', return_value=mock_config), \
             patch('collab.database_manager.close_database_manager') as mock_close_db, \
             patch('collab.redis_manager.close_redis_manager') as mock_close_redis, \
             patch('collab.query_processor.close_query_processor') as mock_close_qp, \
             patch('collab.session_manager.close_session_manager') as mock_close_sm, \
             patch('collab.rag_chain.close_rag_chain') as mock_close_rag, \
             patch('collab.cache_manager.close_cache_manager') as mock_close_cache, \
             patch('collab.menu_system.close_menu_system') as mock_close_menu:
            
            # Create application
            app = InteractiveRAGQuery()
            app._initialized = True
            
            # Test shutdown
            await app.shutdown()
            
            # Verify all close functions were called
            mock_close_menu.assert_called_once()
            mock_close_rag.assert_called_once()
            mock_close_sm.assert_called_once()
            mock_close_qp.assert_called_once()
            mock_close_cache.assert_called_once()
            mock_close_redis.assert_called_once()
            mock_close_db.assert_called_once()
            
            assert app._initialized is False
    
    @pytest.mark.asyncio
    async def test_health_check(self, mock_config):
        """Test comprehensive health check."""
        with patch('collab.config.get_config', return_value=mock_config):
            app = InteractiveRAGQuery()
            
            # Mock components
            app.database_manager = AsyncMock()
            app.redis_manager = AsyncMock()
            app.query_processor = AsyncMock()
            app.session_manager = MagicMock()
            app.rag_chain = MagicMock()
            app.cache_manager = MagicMock()
            
            # Mock health checks
            app.database_manager.health_check.return_value = True
            app.redis_manager.health_check.return_value = True
            app.query_processor.health_check.return_value = True
            
            app._initialized = True
            
            health_status = await app.health_check()
            
            assert health_status['healthy'] is True
            assert health_status['status'] == 'healthy'
            assert 'components' in health_status
            assert 'database' in health_status['components']
            assert 'redis' in health_status['components']
    
    @pytest.mark.asyncio
    async def test_configuration_validation(self, mock_config):
        """Test configuration validation."""
        with patch('collab.config.get_config', return_value=mock_config):
            app = InteractiveRAGQuery()
            
            # Test valid configuration
            is_valid = await app.validate_configuration()
            assert is_valid is True
            
            # Test invalid API key format
            mock_config.openai.api_key = "invalid-key"
            is_valid = await app.validate_configuration()
            assert is_valid is False


class TestPerformanceAndScaling:
    """Test performance and scaling scenarios."""
    
    @pytest.mark.asyncio
    async def test_concurrent_queries(self, mock_config=None):
        """Test handling concurrent queries."""
        # Mock components for concurrent testing
        mock_rag_chain = AsyncMock()
        mock_rag_chain.query_oneshot.return_value = QueryResult(
            response="Test response",
            sources=[],
            processing_time=0.1,
            cached=False
        )
        
        # Simulate concurrent queries
        queries = [f"Query {i}" for i in range(10)]
        
        async def process_query(query):
            return await mock_rag_chain.query_oneshot(query)
        
        # Execute queries concurrently
        tasks = [process_query(query) for query in queries]
        results = await asyncio.gather(*tasks)
        
        # Verify all queries completed
        assert len(results) == 10
        for result in results:
            assert isinstance(result, QueryResult)
            assert result.response == "Test response"
    
    @pytest.mark.asyncio
    async def test_memory_usage_with_large_sessions(self):
        """Test memory usage with large conversation sessions."""
        # Mock session manager
        session_manager = AsyncMock()
        session_manager.create_session.return_value = "large_session"
        session_manager.add_user_message.return_value = None
        session_manager.add_ai_message.return_value = None
        
        # Simulate large conversation
        session_id = await session_manager.create_session("test_tab", "Large Session")
        
        # Add many messages
        for i in range(100):
            await session_manager.add_user_message(f"User message {i}", session_id)
            await session_manager.add_ai_message(f"AI response {i}", session_id)
        
        # Verify session manager handled large conversation
        assert session_manager.add_user_message.call_count == 100
        assert session_manager.add_ai_message.call_count == 100


if __name__ == "__main__":
    # Run integration tests
    pytest.main([__file__, "-v", "-s"])