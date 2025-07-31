#!/usr/bin/env python3
"""
Session management system with comprehensive LangChain memory integration.
"""

import asyncio
import logging
import uuid
from datetime import datetime
from typing import List, Optional, Dict, Any, Union

from langchain.schema import BaseMessage, HumanMessage, AIMessage
from langchain.memory import ConversationBufferMemory, ConversationSummaryMemory
from langchain_core.chat_history import BaseChatMessageHistory
from langchain.llms.base import BaseLLM
from langchain.callbacks.base import BaseCallbackHandler

from database_manager import DatabaseManager, PostgreSQLChatMessageHistory, get_database_manager
from redis_manager import RedisManager, RedisChatMessageHistory, get_redis_manager
from config import get_config

logger = logging.getLogger(__name__)


class HybridChatMessageHistory(BaseChatMessageHistory):
    """Hybrid chat message history using both Redis cache and PostgreSQL persistence."""
    
    def __init__(self, session_id: str, db_manager: DatabaseManager, redis_manager: RedisManager):
        self.session_id = session_id
        self.db_manager = db_manager
        self.redis_manager = redis_manager
        self.redis_history = redis_manager.get_chat_message_history(session_id)
        self.db_history = db_manager.get_chat_message_history(session_id)
        self._messages: List[BaseMessage] = []
        self._loaded = False
    
    @property
    def messages(self) -> List[BaseMessage]:
        """Get messages, loading from cache/database if needed."""
        if not self._loaded:
            # Run the async loading synchronously
            loop = asyncio.get_event_loop()
            if loop.is_running():
                # If we're in an async context, we need to handle this differently
                # For now, return current messages and trigger background loading
                asyncio.create_task(self._load_messages())
                return self._messages
            else:
                loop.run_until_complete(self._load_messages())
        return self._messages
    
    async def _load_messages(self):
        """Load messages from Redis cache first, then database if needed."""
        try:
            # Try Redis first for speed
            try:
                redis_messages = await self.redis_manager.get_session_messages(self.session_id)
                if redis_messages and isinstance(redis_messages, list):
                    self._messages = redis_messages
                    logger.debug(f"Loaded {len(redis_messages)} messages from Redis cache for session {self.session_id}")
                    self._loaded = True
                    return
            except Exception as redis_error:
                logger.warning(f"Redis message loading failed for session {self.session_id}: {redis_error}")
            
            # Fallback to database
            try:
                db_messages = await self.db_manager.load_session_messages(self.session_id)
                if isinstance(db_messages, list):
                    self._messages = db_messages
                    
                    # Cache in Redis for future access
                    if db_messages:
                        try:
                            await self.redis_manager.save_session_messages(self.session_id, db_messages)
                        except Exception as cache_error:
                            logger.warning(f"Failed to cache messages in Redis: {cache_error}")
                        
                        logger.debug(f"Loaded {len(db_messages)} messages from database for session {self.session_id}")
                else:
                    logger.warning(f"Invalid message format from database for session {self.session_id}")
                    self._messages = []
            except Exception as db_error:
                logger.error(f"Database message loading failed for session {self.session_id}: {db_error}")
                self._messages = []
            
            self._loaded = True
        except Exception as e:
            logger.error(f"Failed to load messages for session {self.session_id}: {e}")
            self._messages = []
            self._loaded = True
    
    def add_message(self, message: BaseMessage) -> None:
        """Add a message to the history."""
        self._messages.append(message)
        
        # Save to both Redis and database asynchronously
        asyncio.create_task(self._save_message(message))
    
    async def _save_message(self, message: BaseMessage):
        """Save message to both Redis and database."""
        try:
            # Save to database for persistence
            await self.db_manager.save_message_to_session(self.session_id, message)
            
            # Update Redis cache
            await self.redis_manager.save_session_messages(self.session_id, self._messages)
            
            logger.debug(f"Saved message to both database and Redis for session {self.session_id}")
        except Exception as e:
            logger.error(f"Failed to save message for session {self.session_id}: {e}")
    
    def clear(self) -> None:
        """Clear all messages."""
        self._messages.clear()
        asyncio.create_task(self._clear_all())
    
    async def _clear_all(self):
        """Clear messages from both Redis and database."""
        try:
            await self.db_manager.clear_session_messages(self.session_id)
            await self.redis_manager.clear_session_messages(self.session_id)
            logger.debug(f"Cleared all messages for session {self.session_id}")
        except Exception as e:
            logger.error(f"Failed to clear messages for session {self.session_id}: {e}")


class SessionCallbackHandler(BaseCallbackHandler):
    """Callback handler for session-related events."""
    
    def __init__(self, session_manager: 'SessionManager'):
        self.session_manager = session_manager
    
    def on_llm_start(self, serialized: Dict[str, Any], prompts: List[str], **kwargs) -> None:
        """Called when LLM starts running."""
        logger.debug(f"LLM started for session {self.session_manager.current_session_id}")
    
    def on_llm_end(self, response, **kwargs) -> None:
        """Called when LLM ends running."""
        logger.debug(f"LLM completed for session {self.session_manager.current_session_id}")
    
    def on_llm_error(self, error: Union[Exception, KeyboardInterrupt], **kwargs) -> None:
        """Called when LLM errors."""
        logger.error(f"LLM error in session {self.session_manager.current_session_id}: {error}")


class SessionManager:
    """Comprehensive session management with LangChain memory integration."""
    
    def __init__(self, db_manager: DatabaseManager = None, redis_manager: RedisManager = None, llm: BaseLLM = None):
        self.config = get_config()
        self.db_manager = db_manager
        self.redis_manager = redis_manager
        self.llm = llm
        self.current_session_id: Optional[str] = None
        self.current_tab_id: Optional[str] = None
        self.callback_handler = SessionCallbackHandler(self)
        self._memories: Dict[str, Union[ConversationBufferMemory, ConversationSummaryMemory]] = {}
        self._histories: Dict[str, HybridChatMessageHistory] = {}
    
    async def initialize(self):
        """Initialize session manager with database and Redis connections."""
        if not self.db_manager:
            self.db_manager = await get_database_manager()
        
        if not self.redis_manager:
            self.redis_manager = await get_redis_manager()
        
        logger.info("Session manager initialized successfully")
    
    async def create_session(self, tab_id: str, session_name: str = None, use_summary_memory: bool = False) -> str:
        """Create a new session with LangChain memory."""
        session_id = await self.db_manager.create_session(tab_id, session_name)
        
        # Create hybrid message history
        history = HybridChatMessageHistory(session_id, self.db_manager, self.redis_manager)
        self._histories[session_id] = history
        
        # Create appropriate memory type
        if use_summary_memory and self.llm:
            memory = ConversationSummaryMemory(
                llm=self.llm,
                chat_memory=history,
                return_messages=True,
                max_token_limit=2000
            )
        else:
            memory = ConversationBufferMemory(
                chat_memory=history,
                return_messages=True,
                max_token_limit=4000
            )
        
        self._memories[session_id] = memory
        
        logger.info(f"Created new session {session_id} with {'summary' if use_summary_memory else 'buffer'} memory")
        return session_id
    
    async def load_session(self, session_id: str) -> bool:
        """Load an existing session."""
        try:
            # Check if session exists in database
            sessions = await self.db_manager.list_sessions()
            session_exists = any(s['session_id'] == session_id for s in sessions)
            
            if not session_exists:
                logger.warning(f"Session {session_id} not found")
                return False
            
            # Create hybrid message history if not already loaded
            if session_id not in self._histories:
                history = HybridChatMessageHistory(session_id, self.db_manager, self.redis_manager)
                self._histories[session_id] = history
                
                # Create buffer memory for existing session
                memory = ConversationBufferMemory(
                    chat_memory=history,
                    return_messages=True,
                    max_token_limit=4000
                )
                self._memories[session_id] = memory
            
            self.current_session_id = session_id
            logger.info(f"Loaded session {session_id}")
            return True
            
        except Exception as e:
            logger.error(f"Failed to load session {session_id}: {e}")
            return False
    
    def get_memory(self, session_id: str = None) -> Optional[Union[ConversationBufferMemory, ConversationSummaryMemory]]:
        """Get LangChain memory for a session."""
        session_id = session_id or self.current_session_id
        if not session_id:
            return None
        
        return self._memories.get(session_id)
    
    def get_message_history(self, session_id: str = None) -> Optional[HybridChatMessageHistory]:
        """Get message history for a session."""
        session_id = session_id or self.current_session_id
        if not session_id:
            return None
        
        return self._histories.get(session_id)
    
    async def ensure_messages_loaded(self, session_id: str = None):
        """Ensure messages are loaded for a session."""
        session_id = session_id or self.current_session_id
        if not session_id:
            return
        
        history = self.get_message_history(session_id)
        if history and not history._loaded:
            await history._load_messages()
    
    async def add_message(self, message: BaseMessage, session_id: str = None):
        """Add a message to the current session."""
        session_id = session_id or self.current_session_id
        if not session_id:
            raise ValueError("No active session")
        
        history = self.get_message_history(session_id)
        if history:
            history.add_message(message)
            logger.debug(f"Added message to session {session_id}")
        else:
            logger.error(f"No history found for session {session_id}")
    
    async def add_user_message(self, content: str, session_id: str = None, query_type: str = "general"):
        """Add a user message to the session."""
        message = HumanMessage(content=content)
        # Store query_type in message metadata
        message.additional_kwargs = {'query_type': query_type}
        await self.add_message(message, session_id)
    
    async def add_ai_message(self, content: str, session_id: str = None, query_type: str = "general"):
        """Add an AI message to the session."""
        message = AIMessage(content=content)
        # Store query_type in message metadata
        message.additional_kwargs = {'query_type': query_type}
        await self.add_message(message, session_id)
    
    async def get_conversation_context(self, session_id: str = None, max_messages: int = 10) -> str:
        """Get conversation context as formatted string."""
        session_id = session_id or self.current_session_id
        if not session_id:
            return ""
        
        history = self.get_message_history(session_id)
        if not history:
            return ""
        
        messages = history.messages[-max_messages:] if max_messages else history.messages
        
        context_parts = []
        for message in messages:
            role = "Human" if isinstance(message, HumanMessage) else "Assistant"
            context_parts.append(f"{role}: {message.content}")
        
        return "\n".join(context_parts)
    
    async def list_sessions(self, tab_id: str = None) -> List[Dict[str, Any]]:
        """List available sessions."""
        return await self.db_manager.list_sessions(tab_id)
    
    async def delete_session(self, session_id: str) -> bool:
        """Delete a session and clean up memory."""
        try:
            # Remove from memory caches
            self._memories.pop(session_id, None)
            self._histories.pop(session_id, None)
            
            # Delete from database
            success = await self.db_manager.delete_session(session_id)
            
            # Clear Redis cache
            await self.redis_manager.clear_session_messages(session_id)
            
            if session_id == self.current_session_id:
                self.current_session_id = None
                self.current_tab_id = None
            
            logger.info(f"Deleted session {session_id}")
            return success
            
        except Exception as e:
            logger.error(f"Failed to delete session {session_id}: {e}")
            return False
    
    async def clear_session_history(self, session_id: str = None):
        """Clear history for a session without deleting the session."""
        session_id = session_id or self.current_session_id
        if not session_id:
            return
        
        history = self.get_message_history(session_id)
        if history:
            history.clear()
            logger.info(f"Cleared history for session {session_id}")
    
    async def get_session_stats(self, session_id: str = None) -> Dict[str, Any]:
        """Get statistics for a session."""
        session_id = session_id or self.current_session_id
        if not session_id:
            return {}
        
        try:
            sessions = await self.db_manager.list_sessions()
            session_info = next((s for s in sessions if s['session_id'] == session_id), None)
            
            if not session_info:
                return {}
            
            history = self.get_message_history(session_id)
            message_count = len(history.messages) if history else 0
            
            return {
                'session_id': session_id,
                'tab_id': session_info.get('tab_id'),
                'tab_name': session_info.get('tab_name'),
                'created_at': session_info.get('created_at'),
                'updated_at': session_info.get('updated_at'),
                'message_count': message_count,
                'memory_type': type(self._memories.get(session_id, None)).__name__ if session_id in self._memories else None
            }
            
        except Exception as e:
            logger.error(f"Failed to get session stats for {session_id}: {e}")
            return {}
    
    def set_current_session(self, session_id: str, tab_id: str = None):
        """Set the current active session."""
        self.current_session_id = session_id
        self.current_tab_id = tab_id
        logger.debug(f"Set current session to {session_id}")
    
    async def switch_memory_type(self, session_id: str, use_summary_memory: bool):
        """Switch memory type for a session."""
        if not self.llm and use_summary_memory:
            logger.warning("Cannot switch to summary memory without LLM")
            return False
        
        history = self.get_message_history(session_id)
        if not history:
            logger.error(f"No history found for session {session_id}")
            return False
        
        try:
            if use_summary_memory:
                memory = ConversationSummaryMemory(
                    llm=self.llm,
                    chat_memory=history,
                    return_messages=True,
                    max_token_limit=2000
                )
            else:
                memory = ConversationBufferMemory(
                    chat_memory=history,
                    return_messages=True,
                    max_token_limit=4000
                )
            
            self._memories[session_id] = memory
            logger.info(f"Switched session {session_id} to {'summary' if use_summary_memory else 'buffer'} memory")
            return True
            
        except Exception as e:
            logger.error(f"Failed to switch memory type for session {session_id}: {e}")
            return False
    
    async def close(self):
        """Clean up session manager resources."""
        self._memories.clear()
        self._histories.clear()
        self.current_session_id = None
        self.current_tab_id = None
        logger.info("Session manager closed")


# Global session manager instance
_session_manager = None


async def get_session_manager(llm: BaseLLM = None) -> SessionManager:
    """Get or create session manager instance."""
    global _session_manager
    
    if _session_manager is None:
        _session_manager = SessionManager(llm=llm)
        await _session_manager.initialize()
    
    return _session_manager


async def close_session_manager():
    """Close session manager."""
    global _session_manager
    
    if _session_manager:
        await _session_manager.close()
        _session_manager = None