#!/usr/bin/env python3
"""
Database connection utilities for PostgreSQL integration with LangChain.
"""

import asyncio
import logging
import json
import uuid
from datetime import datetime
from typing import List, Optional, Dict, Any
from contextlib import asynccontextmanager

import asyncpg
from asyncpg import Pool, Connection
from langchain.schema import BaseMessage, HumanMessage, AIMessage
from langchain_core.chat_history import BaseChatMessageHistory

from config import get_config

logger = logging.getLogger(__name__)


class PostgreSQLChatMessageHistory(BaseChatMessageHistory):
    """LangChain-compatible PostgreSQL chat message history."""
    
    def __init__(self, session_id: str, db_manager: 'DatabaseManager'):
        self.session_id = session_id
        self.db_manager = db_manager
        self._messages: List[BaseMessage] = []
        self._loaded = False
    
    @property
    def messages(self) -> List[BaseMessage]:
        """Get messages, loading from database if needed."""
        if not self._loaded:
            asyncio.create_task(self._load_messages())
        return self._messages
    
    async def _load_messages(self):
        """Load messages from database."""
        try:
            messages = await self.db_manager.load_session_messages(self.session_id)
            self._messages = messages
            self._loaded = True
        except Exception as e:
            logger.error(f"Failed to load messages for session {self.session_id}: {e}")
            self._messages = []
            self._loaded = True
    
    def add_message(self, message: BaseMessage) -> None:
        """Add a message to the history."""
        self._messages.append(message)
        # Save to database asynchronously
        asyncio.create_task(self._save_message(message))
    
    async def _save_message(self, message: BaseMessage):
        """Save message to database."""
        try:
            await self.db_manager.save_message_to_session(self.session_id, message)
        except Exception as e:
            logger.error(f"Failed to save message to session {self.session_id}: {e}")
    
    def clear(self) -> None:
        """Clear all messages."""
        self._messages.clear()
        asyncio.create_task(self.db_manager.clear_session_messages(self.session_id))


class DatabaseManager:
    """PostgreSQL database manager with LangChain integration."""
    
    def __init__(self, config=None):
        self.config = config or get_config()
        self.pool: Optional[Pool] = None
        self._initialized = False
    
    async def initialize(self) -> bool:
        """Initialize database connection pool."""
        if self._initialized:
            return True
            
        try:
            # Build connection string
            connection_string = (
                f"postgresql://{self.config.postgresql.user}:"
                f"{self.config.postgresql.password}@"
                f"{self.config.postgresql.host}:"
                f"{self.config.postgresql.port}/"
                f"{self.config.postgresql.database}"
            )
            
            self.pool = await asyncpg.create_pool(
                connection_string,
                min_size=self.config.postgresql.min_connections,
                max_size=self.config.postgresql.max_connections,
                command_timeout=self.config.postgresql.timeout
            )
            
            # Create tables if they don't exist
            await self._create_tables()
            self._initialized = True
            logger.info("Database manager initialized successfully")
            return True
            
        except Exception as e:
            logger.error(f"Database initialization failed: {e}")
            self.pool = None
            self._initialized = False
            return False
    
    async def health_check(self) -> bool:
        """Check database health."""
        if not self.pool:
            return False
        
        try:
            async with self.pool.acquire() as conn:
                await conn.fetchval("SELECT 1")
                return True
        except Exception as e:
            logger.error(f"Database health check failed: {e}")
            return False
    
    async def close(self):
        """Close database connection pool."""
        if self.pool:
            await self.pool.close()
            self.pool = None
            self._initialized = False
    
    @asynccontextmanager
    async def get_connection(self):
        """Get database connection context manager."""
        if not self.pool:
            raise RuntimeError("Database not initialized")
        
        async with self.pool.acquire() as conn:
            yield conn
    
    async def _create_tables(self):
        """Create necessary database tables."""
        if not self.pool:
            return
        
        async with self.pool.acquire() as conn:
            # Chat sessions table
            await conn.execute("""
                CREATE TABLE IF NOT EXISTS chat_sessions (
                    session_id VARCHAR(255) PRIMARY KEY,
                    tab_id VARCHAR(255) NOT NULL,
                    tab_name VARCHAR(255),
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    metadata JSONB DEFAULT '{}'::jsonb
                )
            """)
            
            # Chat messages table
            await conn.execute("""
                CREATE TABLE IF NOT EXISTS chat_messages (
                    id SERIAL PRIMARY KEY,
                    session_id VARCHAR(255) REFERENCES chat_sessions(session_id) ON DELETE CASCADE,
                    role VARCHAR(50) NOT NULL CHECK (role IN ('user', 'assistant', 'system')),
                    content TEXT NOT NULL,
                    sources JSONB,
                    timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    metadata JSONB
                )
            """)
            
            # Create indexes
            await conn.execute("""
                CREATE INDEX IF NOT EXISTS idx_chat_messages_session_id 
                ON chat_messages(session_id)
            """)
            
            await conn.execute("""
                CREATE INDEX IF NOT EXISTS idx_chat_messages_timestamp 
                ON chat_messages(timestamp)
            """)
            
            await conn.execute("""
                CREATE INDEX IF NOT EXISTS idx_chat_sessions_tab_id 
                ON chat_sessions(tab_id)
            """)
    
    async def create_session(self, tab_id: str, tab_name: str = None) -> str:
        """Create a new chat session."""
        session_id = f"session_{uuid.uuid4().hex[:8]}"
        
        async with self.get_connection() as conn:
            await conn.execute("""
                INSERT INTO chat_sessions (session_id, tab_id, tab_name)
                VALUES ($1, $2, $3)
            """, session_id, tab_id, tab_name or "Interactive Query Session")
        
        logger.info(f"Created new session {session_id} for tab {tab_id}")
        return session_id
    
    async def load_session_messages(self, session_id: str) -> List[BaseMessage]:
        """Load messages for a session as LangChain BaseMessage objects."""
        async with self.get_connection() as conn:
            rows = await conn.fetch("""
                SELECT role, content, metadata, timestamp
                FROM chat_messages
                WHERE session_id = $1
                ORDER BY timestamp ASC
            """, session_id)
            
            messages = []
            for row in rows:
                if row['role'] == 'user':
                    message = HumanMessage(
                        content=row['content'],
                        additional_kwargs=row['metadata'] or {}
                    )
                elif row['role'] == 'assistant':
                    message = AIMessage(
                        content=row['content'],
                        additional_kwargs=row['metadata'] or {}
                    )
                else:
                    continue  # Skip system messages for now
                
                messages.append(message)
            
            return messages
    
    async def save_message_to_session(self, session_id: str, message: BaseMessage):
        """Save a message to a session."""
        role = 'user' if isinstance(message, HumanMessage) else 'assistant'
        metadata = getattr(message, 'additional_kwargs', {})
        
        async with self.get_connection() as conn:
            await conn.execute("""
                INSERT INTO chat_messages (session_id, role, content, metadata)
                VALUES ($1, $2, $3, $4)
            """, session_id, role, message.content, json.dumps(metadata))
            
            # Update session timestamp
            await conn.execute("""
                UPDATE chat_sessions 
                SET updated_at = CURRENT_TIMESTAMP 
                WHERE session_id = $1
            """, session_id)
    
    async def clear_session_messages(self, session_id: str):
        """Clear all messages from a session."""
        async with self.get_connection() as conn:
            await conn.execute("""
                DELETE FROM chat_messages WHERE session_id = $1
            """, session_id)
    
    async def list_sessions(self, tab_id: str = None) -> List[Dict[str, Any]]:
        """List available sessions."""
        async with self.get_connection() as conn:
            if tab_id:
                rows = await conn.fetch("""
                    SELECT s.session_id, s.tab_id, s.tab_name, s.created_at, s.updated_at,
                           COUNT(m.id) as message_count
                    FROM chat_sessions s
                    LEFT JOIN chat_messages m ON s.session_id = m.session_id
                    WHERE s.tab_id = $1
                    GROUP BY s.session_id, s.tab_id, s.tab_name, s.created_at, s.updated_at
                    ORDER BY s.updated_at DESC
                """, tab_id)
            else:
                rows = await conn.fetch("""
                    SELECT s.session_id, s.tab_id, s.tab_name, s.created_at, s.updated_at,
                           COUNT(m.id) as message_count
                    FROM chat_sessions s
                    LEFT JOIN chat_messages m ON s.session_id = m.session_id
                    GROUP BY s.session_id, s.tab_id, s.tab_name, s.created_at, s.updated_at
                    ORDER BY s.updated_at DESC
                """)
            
            return [dict(row) for row in rows]
    
    async def delete_session(self, session_id: str) -> bool:
        """Delete a session and all its messages."""
        async with self.get_connection() as conn:
            result = await conn.execute("""
                DELETE FROM chat_sessions WHERE session_id = $1
            """, session_id)
            
            deleted = result.split()[-1] == '1'
            if deleted:
                logger.info(f"Deleted session {session_id}")
            
            return deleted
    
    def get_chat_message_history(self, session_id: str) -> PostgreSQLChatMessageHistory:
        """Get LangChain-compatible chat message history for a session."""
        return PostgreSQLChatMessageHistory(session_id, self)


# Global database manager instance
_db_manager = None


async def get_database_manager() -> DatabaseManager:
    """Get or create database manager instance."""
    global _db_manager
    
    if _db_manager is None:
        _db_manager = DatabaseManager()
        await _db_manager.initialize()
    
    return _db_manager


async def close_database_manager():
    """Close database manager."""
    global _db_manager
    
    if _db_manager:
        await _db_manager.close()
        _db_manager = None