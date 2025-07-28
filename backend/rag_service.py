"""
RAG Service - Core service class that orchestrates all RAG components.
"""

import asyncio
import logging
from typing import Optional, Dict, Any, List
from datetime import datetime

from config import get_config
from database_manager import DatabaseManager, get_database_manager
from redis_manager import RedisManager, get_redis_manager
from session_manager import SessionManager, get_session_manager
from query_processor import QueryProcessor, get_query_processor
from rag_chain import RAGChain, get_rag_chain
from cache_manager import CacheManager, get_cache_manager
from error_handler import ErrorHandler, get_error_handler

logger = logging.getLogger(__name__)


class RAGService:
    """Core RAG service that orchestrates all components."""
    
    def __init__(self):
        self.config = get_config()
        self.error_handler = get_error_handler()
        
        # Component instances
        self.database_manager: Optional[DatabaseManager] = None
        self.redis_manager: Optional[RedisManager] = None
        self.session_manager: Optional[SessionManager] = None
        self.query_processor: Optional[QueryProcessor] = None
        self.rag_chain: Optional[RAGChain] = None
        self.cache_manager: Optional[CacheManager] = None
        
        self._initialized = False
    
    async def initialize(self) -> bool:
        """Initialize all RAG components."""
        if self._initialized:
            return True
        
        try:
            logger.info("🚀 Initializing RAG Service...")
            
            # Initialize infrastructure components
            self.database_manager = await get_database_manager()
            self.redis_manager = await get_redis_manager()
            self.cache_manager = await get_cache_manager()
            
            # Initialize core RAG components
            self.query_processor = await get_query_processor()
            self.session_manager = await get_session_manager()
            self.rag_chain = await get_rag_chain(
                self.query_processor,
                self.session_manager,
                self.cache_manager
            )
            
            self._initialized = True
            logger.info("✅ RAG Service initialized successfully")
            return True
            
        except Exception as e:
            logger.error(f"Failed to initialize RAG service: {e}")
            return False
    
    async def process_one_time_query(self, query: str, top_k: int = 5) -> Dict[str, Any]:
        """Process a one-time query without conversation history."""
        if not self._initialized:
            await self.initialize()
        
        try:
            result = await self.rag_chain.query_oneshot(query, top_k)
            
            return {
                "response": result.response,
                "processing_time": result.processing_time,
                "cached": result.cached,
                "timestamp": datetime.utcnow()
            }
            
        except Exception as e:
            logger.error(f"One-time query failed: {e}")
            return {
                "response": f"I apologize, but I encountered an error processing your query: {str(e)}",
                "processing_time": 0.0,
                "cached": False,
                "timestamp": datetime.utcnow()
            }
    
    async def process_conversational_query(self, query: str, session_id: str, top_k: int = 5) -> Dict[str, Any]:
        """Process a conversational query with session context."""
        if not self._initialized:
            await self.initialize()
        
        try:
            result = await self.rag_chain.query_conversational(query, session_id, top_k)
            
            return {
                "response": result.response,
                "processing_time": result.processing_time,
                "cached": result.cached,
                "timestamp": datetime.utcnow()
            }
            
        except Exception as e:
            logger.error(f"Conversational query failed: {e}")
            return {
                "response": f"I apologize, but I encountered an error processing your query: {str(e)}",
                "processing_time": 0.0,
                "cached": False,
                "timestamp": datetime.utcnow()
            }
    
    async def generate_topic_from_query(self, query: str) -> str:
        """Generate a short topic description from the first query."""
        if not self._initialized:
            await self.initialize()
        
        try:
            # Use OpenAI to generate a concise topic
            from langchain.prompts import PromptTemplate
            
            topic_prompt = PromptTemplate(
                template="Generate a short, descriptive topic title (max 4-5 words) for this question: {query}\n\nTopic:",
                input_variables=["query"]
            )
            
            prompt_text = topic_prompt.format(query=query)
            topic = await self.rag_chain.llm.apredict(prompt_text)
            
            # Clean up the response
            topic = topic.strip().replace('"', '').replace("'", "")
            
            # Fallback if generation fails or is too long
            if len(topic) > 50 or not topic:
                words = query.split()[:4]
                topic = " ".join(words) + ("..." if len(query.split()) > 4 else "")
            
            return topic
            
        except Exception as e:
            logger.error(f"Topic generation failed: {e}")
            # Fallback to first few words of query
            words = query.split()[:4]
            return " ".join(words) + ("..." if len(query.split()) > 4 else "")
    
    async def create_session(self, session_name: Optional[str] = None) -> Dict[str, Any]:
        """Create a new conversation session."""
        if not self._initialized:
            await self.initialize()
        
        try:
            session_name = session_name or f"API Session {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}"
            session_id = await self.session_manager.create_session("api", session_name)
            
            return {
                "session_id": session_id,
                "session_name": session_name,
                "created_at": datetime.utcnow()
            }
            
        except Exception as e:
            logger.error(f"Session creation failed: {e}")
            raise
    
    async def list_sessions(self) -> Dict[str, Any]:
        """List all available sessions."""
        if not self._initialized:
            await self.initialize()
        
        try:
            sessions = await self.session_manager.list_sessions()
            
            session_info = []
            for session in sessions:
                session_info.append({
                    "session_id": session["session_id"],
                    "session_name": session.get("tab_name", "Unnamed Session"),
                    "created_at": session["created_at"],
                    "updated_at": session["updated_at"],
                    "message_count": session.get("message_count", 0)
                })
            
            return {
                "sessions": session_info,
                "total_count": len(session_info)
            }
            
        except Exception as e:
            logger.error(f"Session listing failed: {e}")
            return {
                "sessions": [],
                "total_count": 0
            }
    
    async def delete_session(self, session_id: str) -> bool:
        """Delete a session."""
        if not self._initialized:
            await self.initialize()
        
        try:
            return await self.session_manager.delete_session(session_id)
        except Exception as e:
            logger.error(f"Session deletion failed: {e}")
            return False
    
    async def get_session_history(self, session_id: str) -> List[Dict[str, Any]]:
        """Get conversation history for a session."""
        if not self._initialized:
            await self.initialize()
        
        try:
            # Load the session first
            await self.session_manager.load_session(session_id)
            
            # Get message history
            history = self.session_manager.get_message_history(session_id)
            if not history:
                return []
            
            # Ensure messages are loaded
            await self.session_manager.ensure_messages_loaded(session_id)
            
            # Convert messages to API format
            messages = []
            for message in history.messages:
                role = "user" if message.__class__.__name__ == "HumanMessage" else "assistant"
                messages.append({
                    "role": role,
                    "content": message.content,
                    "timestamp": datetime.utcnow().isoformat()
                })
            
            return messages
            
        except Exception as e:
            logger.error(f"Getting session history failed: {e}")
            return []
    
    async def update_session_name(self, session_id: str, session_name: str) -> bool:
        """Update session name in database."""
        if not self._initialized:
            await self.initialize()
        
        try:
            return await self.database_manager.update_session_name(session_id, session_name)
        except Exception as e:
            logger.error(f"Session name update failed: {e}")
            return False
    
    async def get_health_status(self) -> Dict[str, Any]:
        """Get health status of all components."""
        if not self._initialized:
            return {
                "status": "unhealthy",
                "components": {"service": {"status": "not_initialized"}},
                "timestamp": datetime.utcnow(),
                "version": "1.0.0"
            }
        
        try:
            components = {}
            
            # Check database
            if self.database_manager:
                db_healthy = await self.database_manager.health_check()
                components["database"] = {"status": "healthy" if db_healthy else "unhealthy"}
            
            # Check Redis
            if self.redis_manager:
                redis_healthy = await self.redis_manager.health_check()
                components["redis"] = {"status": "healthy" if redis_healthy else "unhealthy"}
            
            # Check query processor
            if self.query_processor:
                qp_healthy = await self.query_processor.health_check()
                components["query_processor"] = {"status": "healthy" if qp_healthy else "unhealthy"}
            
            # Overall status
            all_healthy = all(comp.get("status") == "healthy" for comp in components.values())
            overall_status = "healthy" if all_healthy else "unhealthy"
            
            return {
                "status": overall_status,
                "components": components,
                "timestamp": datetime.utcnow(),
                "version": "1.0.0"
            }
            
        except Exception as e:
            logger.error(f"Health check failed: {e}")
            return {
                "status": "unhealthy",
                "components": {"error": str(e)},
                "timestamp": datetime.utcnow(),
                "version": "1.0.0"
            }
    
    async def get_index_stats(self) -> Dict[str, Any]:
        """Get vector index statistics."""
        if not self._initialized:
            await self.initialize()
        
        try:
            stats = await self.query_processor.get_index_stats()
            return {
                "total_vectors": stats.get("total_vectors", 0),
                "dimension": stats.get("dimension", 1536),
                "index_fullness": stats.get("index_fullness", 0.0),
                "timestamp": datetime.utcnow()
            }
        except Exception as e:
            logger.error(f"Index stats failed: {e}")
            return {
                "total_vectors": 0,
                "dimension": 1536,
                "index_fullness": 0.0,
                "timestamp": datetime.utcnow()
            }
    
    async def close(self):
        """Clean up service resources."""
        if not self._initialized:
            return
        
        try:
            # Close components in reverse order
            if self.rag_chain:
                await self.rag_chain.close()
            
            if self.session_manager:
                await self.session_manager.close()
            
            if self.query_processor:
                await self.query_processor.close()
            
            if self.cache_manager:
                await self.cache_manager.close()
            
            if self.redis_manager:
                await self.redis_manager.close()
            
            if self.database_manager:
                await self.database_manager.close()
            
            self._initialized = False
            logger.info("✅ RAG Service closed successfully")
            
        except Exception as e:
            logger.error(f"Error during service shutdown: {e}")


# Global service instance
_rag_service = None


async def get_rag_service() -> RAGService:
    """Get or create RAG service instance."""
    global _rag_service
    
    if _rag_service is None:
        _rag_service = RAGService()
        await _rag_service.initialize()
    
    return _rag_service


async def close_rag_service():
    """Close RAG service."""
    global _rag_service
    
    if _rag_service:
        await _rag_service.close()
        _rag_service = None