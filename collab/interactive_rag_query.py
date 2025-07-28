#!/usr/bin/env python3
"""
Main InteractiveRAGQuery application with comprehensive LangChain integration.
"""

import asyncio
import logging
import signal
import sys
from typing import Optional, Dict, Any
from datetime import datetime

from langchain.callbacks.manager import CallbackManager
from langchain.callbacks.base import BaseCallbackHandler

from config import get_config
from database_manager import DatabaseManager, get_database_manager, close_database_manager
from redis_manager import RedisManager, get_redis_manager, close_redis_manager
from session_manager import SessionManager, get_session_manager, close_session_manager
from query_processor import QueryProcessor, get_query_processor, close_query_processor
from rag_chain import RAGChain, get_rag_chain, close_rag_chain
from cache_manager import CacheManager, get_cache_manager, close_cache_manager
from menu_system import MenuSystem, get_menu_system, close_menu_system
from error_handler import ErrorHandler, get_error_handler, ErrorSeverity, create_error_context

logger = logging.getLogger(__name__)


class ApplicationCallbackHandler(BaseCallbackHandler):
    """Main application callback handler for monitoring and logging."""
    
    def __init__(self, app: 'InteractiveRAGQuery'):
        self.app = app
        self.operation_count = 0
        self.start_time = datetime.now()
    
    def on_llm_start(self, serialized: Dict[str, Any], prompts: list, **kwargs) -> None:
        """Called when LLM starts."""
        self.operation_count += 1
        logger.debug(f"LLM operation #{self.operation_count} started")
    
    def on_chain_start(self, serialized: Dict[str, Any], inputs: Dict[str, Any], **kwargs) -> None:
        """Called when chain starts."""
        self.operation_count += 1
        logger.debug(f"Chain operation #{self.operation_count} started")
    
    def on_tool_start(self, serialized: Dict[str, Any], input_str: str, **kwargs) -> None:
        """Called when tool starts."""
        self.operation_count += 1
        logger.debug(f"Tool operation #{self.operation_count} started")
    
    def get_stats(self) -> Dict[str, Any]:
        """Get application statistics."""
        uptime = (datetime.now() - self.start_time).total_seconds()
        return {
            'total_operations': self.operation_count,
            'uptime_seconds': uptime,
            'start_time': self.start_time.isoformat(),
            'operations_per_minute': (self.operation_count / uptime) * 60 if uptime > 0 else 0
        }


class InteractiveRAGQuery:
    """Main application class with comprehensive LangChain integration."""
    
    def __init__(self):
        self.config = get_config()
        self.error_handler = get_error_handler()
        self.app_callback_handler = ApplicationCallbackHandler(self)
        
        # Create callback manager with all handlers
        self.callback_manager = CallbackManager([
            self.error_handler.get_callback_handler(),
            self.app_callback_handler
        ])
        
        # Component instances
        self.database_manager: Optional[DatabaseManager] = None
        self.redis_manager: Optional[RedisManager] = None
        self.session_manager: Optional[SessionManager] = None
        self.query_processor: Optional[QueryProcessor] = None
        self.rag_chain: Optional[RAGChain] = None
        self.cache_manager: Optional[CacheManager] = None
        self.menu_system: Optional[MenuSystem] = None
        
        # Application state
        self._initialized = False
        self._running = False
        self._shutdown_requested = False
        
        # Setup signal handlers
        self._setup_signal_handlers()
    
    def _setup_signal_handlers(self):
        """Setup signal handlers for graceful shutdown."""
        def signal_handler(signum, frame):
            logger.info(f"Received signal {signum}, initiating graceful shutdown...")
            self._shutdown_requested = True
            if self._running:
                asyncio.create_task(self.shutdown())
        
        signal.signal(signal.SIGINT, signal_handler)
        signal.signal(signal.SIGTERM, signal_handler)
    
    async def initialize(self) -> bool:
        """Initialize all application components."""
        if self._initialized:
            return True
        
        try:
            logger.info("🚀 Initializing Interactive RAG Query System...")
            
            # Initialize components in dependency order
            await self._initialize_infrastructure()
            await self._initialize_core_components()
            await self._initialize_application_layer()
            
            self._initialized = True
            logger.info("✅ Interactive RAG Query System initialized successfully!")
            
            # Display system status
            await self._display_system_status()
            
            return True
            
        except Exception as e:
            error_context = create_error_context(
                e, "application", "initialization", ErrorSeverity.CRITICAL
            )
            user_message = self.error_handler.handle_error(error_context)
            logger.critical(f"Failed to initialize application: {user_message}")
            return False
    
    async def _initialize_infrastructure(self):
        """Initialize infrastructure components (database, cache)."""
        logger.info("🔧 Initializing infrastructure components...")
        
        # Initialize database manager
        self.database_manager = await self.error_handler.retry_with_backoff(
            get_database_manager,
            "database_initialization"
        )
        
        # Initialize Redis manager
        self.redis_manager = await self.error_handler.retry_with_backoff(
            get_redis_manager,
            "redis_initialization"
        )
        
        # Initialize cache manager
        self.cache_manager = await get_cache_manager()
        
        logger.info("✅ Infrastructure components initialized")
    
    async def _initialize_core_components(self):
        """Initialize core RAG components."""
        logger.info("🧠 Initializing core RAG components...")
        
        # Initialize query processor
        self.query_processor = await get_query_processor()
        
        # Initialize session manager
        self.session_manager = await get_session_manager()
        
        # Initialize RAG chain
        self.rag_chain = await get_rag_chain(
            self.query_processor,
            self.session_manager,
            self.cache_manager
        )
        
        logger.info("✅ Core RAG components initialized")
    
    async def _initialize_application_layer(self):
        """Initialize application layer components."""
        logger.info("🎯 Initializing application layer...")
        
        # Initialize menu system
        self.menu_system = await get_menu_system()
        
        logger.info("✅ Application layer initialized")
    
    async def _display_system_status(self):
        """Display system status after initialization."""
        print("\n" + "=" * 70)
        print("🤖 Interactive RAG Query System - Status Report")
        print("=" * 70)
        
        # Component status
        components = [
            ("Database Manager", self.database_manager, self.database_manager.health_check() if self.database_manager else False),
            ("Redis Manager", self.redis_manager, self.redis_manager.health_check() if self.redis_manager else False),
            ("Query Processor", self.query_processor, self.query_processor.health_check() if self.query_processor else False),
            ("Session Manager", self.session_manager, True if self.session_manager else False),
            ("RAG Chain", self.rag_chain, True if self.rag_chain else False),
            ("Cache Manager", self.cache_manager, True if self.cache_manager else False),
            ("Menu System", self.menu_system, True if self.menu_system else False)
        ]
        
        for name, component, health_check in components:
            if asyncio.iscoroutine(health_check):
                is_healthy = await health_check
            else:
                is_healthy = health_check
            
            status = "✅ Ready" if component and is_healthy else "❌ Not Ready"
            print(f"{name:20} : {status}")
        
        # System configuration
        print(f"\nConfiguration:")
        print(f"Environment        : {self.config.environment.value}")
        print(f"OpenAI Model       : {self.config.openai.model}")
        print(f"Embedding Model    : {self.config.openai.embedding_model}")
        print(f"Pinecone Index     : {self.config.pinecone.index_name}")
        
        # Index statistics
        if self.query_processor:
            try:
                stats = await self.query_processor.get_index_stats()
                print(f"\nVector Index Stats:")
                print(f"Total Vectors      : {stats.get('total_vectors', 0):,}")
                print(f"Dimension          : {stats.get('dimension', 1536)}")
                print(f"Index Fullness     : {stats.get('index_fullness', 0):.2%}")
            except Exception as e:
                print(f"Vector Index Stats : Error retrieving stats ({e})")
        
        print("=" * 70)
    
    async def run(self):
        """Run the interactive application."""
        if not self._initialized:
            success = await self.initialize()
            if not success:
                logger.error("Failed to initialize application")
                return False
        
        try:
            self._running = True
            logger.info("🎯 Starting interactive menu system...")
            
            # Run the menu system
            await self.menu_system.run()
            
            return True
            
        except KeyboardInterrupt:
            logger.info("Application interrupted by user")
            return True
        except Exception as e:
            error_context = create_error_context(
                e, "application", "run", ErrorSeverity.HIGH
            )
            user_message = self.error_handler.handle_error(error_context)
            logger.error(f"Application runtime error: {user_message}")
            return False
        finally:
            self._running = False
            await self.shutdown()
    
    async def shutdown(self):
        """Gracefully shutdown the application."""
        if not self._initialized:
            return
        
        logger.info("🛑 Shutting down Interactive RAG Query System...")
        
        try:
            # Close components in reverse order
            if self.menu_system:
                await close_menu_system()
            
            if self.rag_chain:
                await close_rag_chain()
            
            if self.session_manager:
                await close_session_manager()
            
            if self.query_processor:
                await close_query_processor()
            
            if self.cache_manager:
                await close_cache_manager()
            
            if self.redis_manager:
                await close_redis_manager()
            
            if self.database_manager:
                await close_database_manager()
            
            self._initialized = False
            logger.info("✅ Shutdown completed successfully")
            
        except Exception as e:
            logger.error(f"Error during shutdown: {e}")
    
    async def health_check(self) -> Dict[str, Any]:
        """Perform comprehensive health check."""
        if not self._initialized:
            return {"status": "not_initialized", "healthy": False}
        
        health_status = {
            "status": "healthy",
            "healthy": True,
            "timestamp": datetime.now().isoformat(),
            "components": {}
        }
        
        # Check each component
        components = [
            ("database", self.database_manager.health_check() if self.database_manager else False),
            ("redis", self.redis_manager.health_check() if self.redis_manager else False),
            ("query_processor", self.query_processor.health_check() if self.query_processor else False),
            ("session_manager", True if self.session_manager else False),
            ("rag_chain", True if self.rag_chain else False),
            ("cache_manager", True if self.cache_manager else False)
        ]
        
        for name, health_check in components:
            try:
                if asyncio.iscoroutine(health_check):
                    is_healthy = await health_check
                else:
                    is_healthy = health_check
                
                health_status["components"][name] = {
                    "healthy": is_healthy,
                    "status": "ok" if is_healthy else "error"
                }
                
                if not is_healthy:
                    health_status["healthy"] = False
                    health_status["status"] = "degraded"
                    
            except Exception as e:
                health_status["components"][name] = {
                    "healthy": False,
                    "status": "error",
                    "error": str(e)
                }
                health_status["healthy"] = False
                health_status["status"] = "degraded"
        
        return health_status
    
    def get_application_stats(self) -> Dict[str, Any]:
        """Get comprehensive application statistics."""
        stats = {
            "application": self.app_callback_handler.get_stats(),
            "initialized": self._initialized,
            "running": self._running,
            "config": {
                "environment": self.config.environment.value,
                "openai_model": self.config.openai.model,
                "embedding_model": self.config.openai.embedding_model,
                "pinecone_index": self.config.pinecone.index_name
            }
        }
        
        # Add error statistics
        if self.error_handler:
            stats["errors"] = self.error_handler.get_error_statistics()
        
        # Add component-specific stats
        if self.rag_chain:
            stats["rag_chain"] = self.rag_chain.get_chain_stats()
        
        return stats
    
    async def validate_configuration(self) -> bool:
        """Validate system configuration."""
        try:
            logger.info("🔍 Validating system configuration...")
            
            # Check required environment variables
            required_vars = [
                "OPENAI_API_KEY",
                "PINECONE_API_KEY",
                "PINECONE_ENVIRONMENT",
                "PINECONE_INDEX_NAME"
            ]
            
            missing_vars = []
            for var in required_vars:
                if not getattr(self.config.openai, var.lower().replace('openai_', ''), None) and \
                   not getattr(self.config.pinecone, var.lower().replace('pinecone_', ''), None):
                    missing_vars.append(var)
            
            if missing_vars:
                logger.error(f"Missing required environment variables: {missing_vars}")
                return False
            
            # Validate API keys format
            if not self.config.openai.api_key.startswith('sk-'):
                logger.error("Invalid OpenAI API key format")
                return False
            
            logger.info("✅ Configuration validation passed")
            return True
            
        except Exception as e:
            logger.error(f"Configuration validation failed: {e}")
            return False


async def main():
    """Main entry point."""
    # Setup logging
    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
        handlers=[
            logging.StreamHandler(sys.stdout),
            logging.FileHandler('interactive_rag_query.log')
        ]
    )
    
    # Create and run application
    app = InteractiveRAGQuery()
    
    try:
        # Validate configuration first
        if not await app.validate_configuration():
            print("❌ Configuration validation failed. Please check your environment variables.")
            return 1
        
        # Run the application
        success = await app.run()
        return 0 if success else 1
        
    except Exception as e:
        logger.critical(f"Fatal application error: {e}")
        return 1
    finally:
        await app.shutdown()


if __name__ == "__main__":
    try:
        exit_code = asyncio.run(main())
        sys.exit(exit_code)
    except KeyboardInterrupt:
        print("\n👋 Application interrupted by user. Goodbye!")
        sys.exit(0)
    except Exception as e:
        print(f"❌ Fatal error: {e}")
        sys.exit(1)