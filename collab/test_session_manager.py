#!/usr/bin/env python3
"""
Unit tests for SessionManager using LangChain memory testing utilities.
"""

import asyncio
import pytest
import uuid
from unittest.mock import AsyncMock, MagicMock, patch
from datetime import datetime

from langchain.schema import HumanMessage, AIMessage
from langchain.memory import ConversationBufferMemory

from session_manager import SessionManager, HybridChatMessageHistory
from database_manager import DatabaseManager
from redis_manager import RedisManager


class TestSessionManager:
    """Test cases for SessionManager."""
    
    @pytest.fixture
    async def mock_db_manager(self):
        """Mock database manager."""
        db_manager = AsyncMock(spec=DatabaseManager)
        db_manager.create_session.return_value = "test_session_123"
        db_manager.load_session_messages.return_value = []
        db_manager.save_message_to_session.return_value = None
        db_manager.clear_session_messages.return_value = None
        db_manager.list_sessions.return_value = [
            {
                'session_id': 'test_session_123',
                'tab_id': 'test_tab',
                'tab_name': 'Test Session',
                'created_at': datetime.now(),
                'updated_at': datetime.now(),
                'message_count': 0
            }
        ]
        return db_manager
    
    @pytest.fixture
    async def mock_redis_manager(self):
        """Mock Redis manager."""
        redis_manager = AsyncMock(spec=RedisManager)
        redis_manager.get_session_messages.return_value = None
        redis_manager.save_session_messages.return_value = True
        redis_manager.clear_session_messages.return_value = True
        return redis_manager
    
    @pytest.fixture
    async def session_manager(self, mock_db_manager, mock_redis_manager):
        """Create SessionManager with mocked dependencies."""
        manager = SessionManager(mock_db_manager, mock_redis_manager)
        await manager.initialize()
        return manager
    
    @pytest.mark.asyncio
    async def test_create_session(self, session_manager, mock_db_manager):
        """Test session creation."""
        session_id = await session_manager.create_session("test_tab", "Test Session")
        
        assert session_id == "test_session_123"
        mock_db_manager.create_session.assert_called_once_with("test_tab", "Test Session")
        assert session_id in session_manager._memories
        assert session_id in session_manager._histories
    
    @pytest.mark.asyncio
    async def test_load_session(self, session_manager, mock_db_manager):
        """Test session loading."""
        success = await session_manager.load_session("test_session_123")
        
        assert success is True
        assert session_manager.current_session_id == "test_session_123"
        assert "test_session_123" in session_manager._memories
        assert "test_session_123" in session_manager._histories
    
    @pytest.mark.asyncio
    async def test_add_user_message(self, session_manager):
        """Test adding user message."""
        session_id = await session_manager.create_session("test_tab", "Test Session")
        await session_manager.add_user_message("Hello, world!", session_id)
        
        memory = session_manager.get_memory(session_id)
        assert memory is not None
        
        # Check that message was added to memory
        messages = memory.chat_memory.messages
        assert len(messages) >= 1
        assert isinstance(messages[-1], HumanMessage)
        assert messages[-1].content == "Hello, world!"
    
    @pytest.mark.asyncio
    async def test_add_ai_message(self, session_manager):
        """Test adding AI message."""
        session_id = await session_manager.create_session("test_tab", "Test Session")
        await session_manager.add_ai_message("Hello! How can I help you?", session_id)
        
        memory = session_manager.get_memory(session_id)
        assert memory is not None
        
        # Check that message was added to memory
        messages = memory.chat_memory.messages
        assert len(messages) >= 1
        assert isinstance(messages[-1], AIMessage)
        assert messages[-1].content == "Hello! How can I help you?"
    
    @pytest.mark.asyncio
    async def test_get_conversation_context(self, session_manager):
        """Test getting conversation context."""
        session_id = await session_manager.create_session("test_tab", "Test Session")
        
        # Add some messages
        await session_manager.add_user_message("What is Python?", session_id)
        await session_manager.add_ai_message("Python is a programming language.", session_id)
        
        context = await session_manager.get_conversation_context(session_id)
        
        assert "Human: What is Python?" in context
        assert "Assistant: Python is a programming language." in context
    
    @pytest.mark.asyncio
    async def test_delete_session(self, session_manager, mock_db_manager, mock_redis_manager):
        """Test session deletion."""
        session_id = await session_manager.create_session("test_tab", "Test Session")
        
        mock_db_manager.delete_session.return_value = True
        success = await session_manager.delete_session(session_id)
        
        assert success is True
        mock_db_manager.delete_session.assert_called_once_with(session_id)
        mock_redis_manager.clear_session_messages.assert_called_once_with(session_id)
        assert session_id not in session_manager._memories
        assert session_id not in session_manager._histories
    
    @pytest.mark.asyncio
    async def test_get_session_stats(self, session_manager, mock_db_manager):
        """Test getting session statistics."""
        session_id = await session_manager.create_session("test_tab", "Test Session")
        
        stats = await session_manager.get_session_stats(session_id)
        
        assert stats['session_id'] == session_id
        assert stats['tab_id'] == 'test_tab'
        assert stats['tab_name'] == 'Test Session'
        assert 'message_count' in stats
        assert 'memory_type' in stats


class TestHybridChatMessageHistory:
    """Test cases for HybridChatMessageHistory."""
    
    @pytest.fixture
    async def mock_db_manager(self):
        """Mock database manager."""
        db_manager = AsyncMock(spec=DatabaseManager)
        db_manager.load_session_messages.return_value = [
            HumanMessage(content="Test message 1"),
            AIMessage(content="Test response 1")
        ]
        db_manager.save_message_to_session.return_value = None
        db_manager.clear_session_messages.return_value = None
        return db_manager
    
    @pytest.fixture
    async def mock_redis_manager(self):
        """Mock Redis manager."""
        redis_manager = AsyncMock(spec=RedisManager)
        redis_manager.get_session_messages.return_value = None
        redis_manager.save_session_messages.return_value = True
        redis_manager.clear_session_messages.return_value = True
        return redis_manager
    
    @pytest.fixture
    def hybrid_history(self, mock_db_manager, mock_redis_manager):
        """Create HybridChatMessageHistory with mocked dependencies."""
        return HybridChatMessageHistory("test_session", mock_db_manager, mock_redis_manager)
    
    @pytest.mark.asyncio
    async def test_load_from_database_when_redis_empty(self, hybrid_history, mock_db_manager, mock_redis_manager):
        """Test loading from database when Redis cache is empty."""
        # Simulate Redis returning None (cache miss)
        mock_redis_manager.get_session_messages.return_value = None
        
        # Access messages property to trigger loading
        await hybrid_history._load_messages()
        
        # Should have loaded from database
        mock_db_manager.load_session_messages.assert_called_once_with("test_session")
        # Should have cached in Redis
        mock_redis_manager.save_session_messages.assert_called_once()
    
    @pytest.mark.asyncio
    async def test_load_from_redis_cache(self, hybrid_history, mock_db_manager, mock_redis_manager):
        """Test loading from Redis cache when available."""
        # Simulate Redis returning cached messages
        cached_messages = [
            HumanMessage(content="Cached message"),
            AIMessage(content="Cached response")
        ]
        mock_redis_manager.get_session_messages.return_value = cached_messages
        
        # Access messages property to trigger loading
        await hybrid_history._load_messages()
        
        # Should have loaded from Redis, not database
        mock_redis_manager.get_session_messages.assert_called_once_with("test_session")
        mock_db_manager.load_session_messages.assert_not_called()
    
    def test_add_message(self, hybrid_history):
        """Test adding message to history."""
        message = HumanMessage(content="Test message")
        hybrid_history.add_message(message)
        
        # Message should be added to internal list
        assert len(hybrid_history._messages) == 1
        assert hybrid_history._messages[0] == message
    
    @pytest.mark.asyncio
    async def test_clear_messages(self, hybrid_history, mock_db_manager, mock_redis_manager):
        """Test clearing all messages."""
        # Add a message first
        hybrid_history.add_message(HumanMessage(content="Test"))
        assert len(hybrid_history._messages) == 1
        
        # Clear messages
        hybrid_history.clear()
        
        # Should clear internal messages
        assert len(hybrid_history._messages) == 0


if __name__ == "__main__":
    # Run tests
    pytest.main([__file__, "-v"])