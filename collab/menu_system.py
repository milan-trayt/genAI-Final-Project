#!/usr/bin/env python3
"""
LangChain-powered interactive menu system with agent-based navigation.
"""

import asyncio
import logging
import sys
from typing import Dict, Any, List, Optional, Callable
from datetime import datetime
from enum import Enum

from langchain.agents import Tool, AgentExecutor, create_react_agent
from langchain.agents.agent_types import AgentType
from langchain.tools.base import BaseTool
from langchain.schema import AgentAction, AgentFinish
from langchain.prompts import PromptTemplate
from langchain.callbacks.base import BaseCallbackHandler
from langchain.schema.output_parser import BaseOutputParser
from langchain_openai import ChatOpenAI
from pydantic import BaseModel, Field

from config import get_config
from session_manager import SessionManager, get_session_manager
from query_processor import QueryProcessor, get_query_processor
from rag_chain import RAGChain, get_rag_chain
from cache_manager import CacheManager, get_cache_manager

logger = logging.getLogger(__name__)


class MenuState(Enum):
    """Menu state enumeration."""
    MAIN_MENU = "main_menu"
    ONE_TIME_QUERY = "one_time_query"
    CONVERSATIONAL_MODE = "conversational_mode"
    SESSION_MANAGEMENT = "session_management"
    SETTINGS = "settings"
    EXIT = "exit"


class MenuAction(BaseModel):
    """Menu action model."""
    action: str = Field(description="The action to perform")
    parameters: Dict[str, Any] = Field(default_factory=dict, description="Action parameters")


class MenuOutputParser(BaseOutputParser):
    """Output parser for menu actions."""
    
    def parse(self, text: str) -> MenuAction:
        """Parse menu action from text."""
        text = text.strip()
        
        # Simple parsing for menu actions
        if "one_time_query" in text.lower():
            return MenuAction(action="one_time_query")
        elif "conversational" in text.lower() or "context" in text.lower():
            return MenuAction(action="conversational_mode")
        elif "session" in text.lower():
            return MenuAction(action="session_management")
        elif "settings" in text.lower() or "config" in text.lower():
            return MenuAction(action="settings")
        elif "exit" in text.lower() or "quit" in text.lower():
            return MenuAction(action="exit")
        else:
            return MenuAction(action="main_menu")
    
    @property
    def _type(self) -> str:
        return "menu_action"


class MenuCallbackHandler(BaseCallbackHandler):
    """Callback handler for menu system events."""
    
    def __init__(self, menu_system: 'MenuSystem'):
        self.menu_system = menu_system
    
    def on_agent_action(self, action: AgentAction, **kwargs) -> None:
        """Called when agent takes an action."""
        logger.debug(f"Agent action: {action.tool} with input: {action.tool_input}")
    
    def on_agent_finish(self, finish: AgentFinish, **kwargs) -> None:
        """Called when agent finishes."""
        logger.debug(f"Agent finished with output: {finish.return_values}")
    
    def on_tool_start(self, serialized: Dict[str, Any], input_str: str, **kwargs) -> None:
        """Called when tool starts."""
        tool_name = serialized.get("name", "Unknown")
        logger.debug(f"Tool {tool_name} started with input: {input_str}")
    
    def on_tool_end(self, output: str, **kwargs) -> None:
        """Called when tool ends."""
        logger.debug(f"Tool completed with output: {output[:100]}...")


class OneTimeQueryTool(BaseTool):
    """Tool for one-time queries."""
    
    name: str = "one_time_query"
    description: str = "Process a single query without conversation history"
    
    def __init__(self, rag_chain: RAGChain):
        super().__init__()
        object.__setattr__(self, 'rag_chain', rag_chain)
    
    def _run(self, query: str) -> str:
        """Run one-time query."""
        try:
            # Use asyncio to run the async method
            loop = asyncio.get_event_loop()
            if loop.is_running():
                # If we're already in an async context, create a task
                task = asyncio.create_task(self.rag_chain.query_oneshot(query))
                # For now, return a placeholder - this would need proper async handling
                return "Query submitted for processing..."
            else:
                result = asyncio.run(self.rag_chain.query_oneshot(query))
                return result.response
        except Exception as e:
            logger.error(f"One-time query failed: {e}")
            return f"Error processing query: {str(e)}"
    
    async def _arun(self, query: str) -> str:
        """Async version of run."""
        try:
            result = await self.rag_chain.query_oneshot(query)
            return result.response
        except Exception as e:
            logger.error(f"One-time query failed: {e}")
            return f"Error processing query: {str(e)}"


class ConversationalQueryTool(BaseTool):
    """Tool for conversational queries."""
    
    name: str = "conversational_query"
    description: str = "Process a query with conversation history in a specific session"
    
    def __init__(self, rag_chain: RAGChain, session_manager: SessionManager):
        super().__init__()
        object.__setattr__(self, 'rag_chain', rag_chain)
        object.__setattr__(self, 'session_manager', session_manager)
    
    def _run(self, query: str, session_id: str = None) -> str:
        """Run conversational query."""
        try:
            if not session_id:
                session_id = self.session_manager.current_session_id
            
            if not session_id:
                return "No active session. Please create or select a session first."
            
            # Use asyncio to run the async method
            loop = asyncio.get_event_loop()
            if loop.is_running():
                task = asyncio.create_task(self.rag_chain.query_conversational(query, session_id))
                return "Query submitted for processing..."
            else:
                result = asyncio.run(self.rag_chain.query_conversational(query, session_id))
                return result.response
        except Exception as e:
            logger.error(f"Conversational query failed: {e}")
            return f"Error processing query: {str(e)}"
    
    async def _arun(self, query: str, session_id: str = None) -> str:
        """Async version of run."""
        try:
            if not session_id:
                session_id = self.session_manager.current_session_id
            
            if not session_id:
                return "No active session. Please create or select a session first."
            
            result = await self.rag_chain.query_conversational(query, session_id)
            return result.response
        except Exception as e:
            logger.error(f"Conversational query failed: {e}")
            return f"Error processing query: {str(e)}"


class SessionManagementTool(BaseTool):
    """Tool for session management operations."""
    
    name: str = "session_management"
    description: str = "Manage chat sessions - create, list, delete, or switch sessions"
    
    def __init__(self, session_manager: SessionManager):
        super().__init__()
        object.__setattr__(self, 'session_manager', session_manager)
    
    def _run(self, action: str, **kwargs) -> str:
        """Run session management action."""
        try:
            loop = asyncio.get_event_loop()
            if loop.is_running():
                task = asyncio.create_task(self._async_run(action, **kwargs))
                return "Session management operation submitted..."
            else:
                return asyncio.run(self._async_run(action, **kwargs))
        except Exception as e:
            logger.error(f"Session management failed: {e}")
            return f"Error: {str(e)}"
    
    async def _arun(self, action: str, **kwargs) -> str:
        """Async version of run."""
        return await self._async_run(action, **kwargs)
    
    async def _async_run(self, action: str, **kwargs) -> str:
        """Async implementation of session management."""
        try:
            if action == "list":
                sessions = await self.session_manager.list_sessions()
                if not sessions:
                    return "No sessions found."
                
                result = "Available sessions:\n"
                for i, session in enumerate(sessions, 1):
                    result += f"{i}. {session['session_id']} - {session.get('tab_name', 'Unnamed')} "
                    result += f"({session.get('message_count', 0)} messages)\n"
                return result
            
            elif action == "create":
                session_name = kwargs.get('name', f"Session {datetime.now().strftime('%H:%M:%S')}")
                session_id = await self.session_manager.create_session("interactive", session_name)
                self.session_manager.set_current_session(session_id)
                return f"Created and switched to session: {session_id}"
            
            elif action == "switch":
                session_id = kwargs.get('session_id')
                if not session_id:
                    return "Session ID required for switching"
                
                success = await self.session_manager.load_session(session_id)
                if success:
                    return f"Switched to session: {session_id}"
                else:
                    return f"Failed to switch to session: {session_id}"
            
            elif action == "delete":
                session_id = kwargs.get('session_id')
                if not session_id:
                    return "Session ID required for deletion"
                
                success = await self.session_manager.delete_session(session_id)
                if success:
                    return f"Deleted session: {session_id}"
                else:
                    return f"Failed to delete session: {session_id}"
            
            elif action == "stats":
                session_id = kwargs.get('session_id') or self.session_manager.current_session_id
                if not session_id:
                    return "No active session"
                
                stats = await self.session_manager.get_session_stats(session_id)
                if stats:
                    return f"Session Stats:\n" + "\n".join([f"{k}: {v}" for k, v in stats.items()])
                else:
                    return "No stats available"
            
            else:
                return f"Unknown session action: {action}"
                
        except Exception as e:
            logger.error(f"Session management action failed: {e}")
            return f"Error: {str(e)}"


class MenuSystem:
    """LangChain-powered interactive menu system."""
    
    def __init__(self):
        self.config = get_config()
        self.current_state = MenuState.MAIN_MENU
        self.callback_handler = MenuCallbackHandler(self)
        self.output_parser = MenuOutputParser()
        
        # Components
        self.session_manager: Optional[SessionManager] = None
        self.query_processor: Optional[QueryProcessor] = None
        self.rag_chain: Optional[RAGChain] = None
        self.cache_manager: Optional[CacheManager] = None
        
        # LangChain components
        self.llm: Optional[ChatOpenAI] = None
        self.agent: Optional[AgentExecutor] = None
        self.tools: List[Tool] = []
        
        self._initialized = False
        self._running = True
    
    async def initialize(self):
        """Initialize the menu system."""
        if self._initialized:
            return
        
        try:
            logger.info("Initializing menu system...")
            
            # Initialize core components
            self.session_manager = await get_session_manager()
            self.query_processor = await get_query_processor()
            self.cache_manager = await get_cache_manager()
            self.rag_chain = await get_rag_chain(
                self.query_processor, 
                self.session_manager, 
                self.cache_manager
            )
            
            # Initialize LLM for agent
            self.llm = ChatOpenAI(
                model=self.config.openai.model,  # Use model from environment
                temperature=0.1,
                callbacks=[self.callback_handler]
            )
            
            # Create tools
            self.tools = [
                OneTimeQueryTool(self.rag_chain),
                ConversationalQueryTool(self.rag_chain, self.session_manager),
                SessionManagementTool(self.session_manager)
            ]
            
            # Create agent prompt
            agent_prompt = PromptTemplate(
                template="""You are a helpful menu navigation assistant for an interactive RAG query system.

Available tools:
{tools}

Tool descriptions:
{tool_names}

User input: {input}

Based on the user input, determine what they want to do and use the appropriate tool.

{agent_scratchpad}""",
                input_variables=["tools", "tool_names", "input", "agent_scratchpad"]
            )
            
            # Create agent (simplified version without full REACT agent)
            # For now, we'll use a simple tool-based approach
            
            self._initialized = True
            logger.info("✅ Menu system initialized successfully")
            
        except Exception as e:
            logger.error(f"Failed to initialize menu system: {e}")
            raise
    
    def display_main_menu(self):
        """Display the main menu."""
        print("\n" + "=" * 60)
        print("🤖 Interactive RAG Query System")
        print("=" * 60)
        print("1. One-time Query (no conversation history)")
        print("2. Conversational Mode (with history)")
        print("3. Session Management")
        print("4. System Settings")
        print("5. Help")
        print("0. Exit")
        print("=" * 60)
    
    def display_session_menu(self):
        """Display session management menu."""
        print("\n" + "=" * 40)
        print("📋 Session Management")
        print("=" * 40)
        print("1. List sessions")
        print("2. Create new session")
        print("3. Switch session")
        print("4. Delete session")
        print("5. Session statistics")
        print("0. Back to main menu")
        print("=" * 40)
    
    def display_help(self):
        """Display help information."""
        print("\n" + "=" * 60)
        print("❓ Help - Interactive RAG Query System")
        print("=" * 60)
        print("This system allows you to query a knowledge base using RAG (Retrieval-Augmented Generation).")
        print()
        print("🔍 One-time Query:")
        print("   - Process single queries without conversation history")
        print("   - Fast and stateless")
        print("   - Good for quick lookups")
        print()
        print("💬 Conversational Mode:")
        print("   - Maintains conversation history")
        print("   - Context-aware responses")
        print("   - Better for complex discussions")
        print()
        print("📋 Session Management:")
        print("   - Create and manage conversation sessions")
        print("   - Switch between different conversation contexts")
        print("   - View session statistics")
        print()
        print("⚙️ System Settings:")
        print("   - Configure system parameters")
        print("   - View system status")
        print("   - Cache management")
        print("=" * 60)
    
    async def handle_one_time_query(self):
        """Handle one-time query mode."""
        print("\n🔍 One-time Query Mode")
        print("Enter your query (or 'back' to return to main menu):")
        
        while True:
            try:
                query = input("\n> ").strip()
                
                if not query:
                    print("Please enter a query.")
                    continue
                
                if query.lower() in ['back', 'exit', 'quit']:
                    break
                
                print("\n🤔 Processing your query...")
                
                # Use the one-time query tool
                tool = OneTimeQueryTool(self.rag_chain)
                result = await tool._arun(query)
                
                print(f"\n💬 Response:\n{result}")
                
                # Ask if user wants to continue
                continue_query = input("\nWould you like to ask another question? (y/n): ").strip().lower()
                if continue_query not in ['y', 'yes']:
                    break
                    
            except KeyboardInterrupt:
                print("\n\nReturning to main menu...")
                break
            except Exception as e:
                print(f"\n❌ Error: {e}")
    
    async def handle_conversational_mode(self):
        """Handle conversational mode."""
        print("\n💬 Conversational Mode")
        
        # Check if there's an active session
        if not self.session_manager.current_session_id:
            print("No active session. Creating a new session...")
            session_id = await self.session_manager.create_session(
                "interactive", 
                f"Conversation {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}"
            )
            self.session_manager.set_current_session(session_id)
            print(f"Created session: {session_id}")
        
        print(f"Active session: {self.session_manager.current_session_id}")
        print("Enter your queries (or 'back' to return to main menu):")
        
        while True:
            try:
                query = input("\n> ").strip()
                
                if not query:
                    print("Please enter a query.")
                    continue
                
                if query.lower() in ['back', 'exit', 'quit']:
                    break
                
                print("\n🤔 Processing your query...")
                
                # Use the conversational query tool
                tool = ConversationalQueryTool(self.rag_chain, self.session_manager)
                result = await tool._arun(query, self.session_manager.current_session_id)
                
                print(f"\n💬 Response:\n{result}")
                
            except KeyboardInterrupt:
                print("\n\nReturning to main menu...")
                break
            except Exception as e:
                print(f"\n❌ Error: {e}")
    
    async def handle_session_management(self):
        """Handle session management."""
        while True:
            self.display_session_menu()
            
            try:
                choice = input("\nSelect option: ").strip()
                
                if choice == '0':
                    break
                elif choice == '1':
                    # List sessions
                    tool = SessionManagementTool(self.session_manager)
                    result = await tool._arun("list")
                    print(f"\n{result}")
                
                elif choice == '2':
                    # Create session
                    name = input("Enter session name (optional): ").strip()
                    tool = SessionManagementTool(self.session_manager)
                    result = await tool._arun("create", name=name if name else None)
                    print(f"\n{result}")
                
                elif choice == '3':
                    # Switch session
                    session_id = input("Enter session ID: ").strip()
                    if session_id:
                        tool = SessionManagementTool(self.session_manager)
                        result = await tool._arun("switch", session_id=session_id)
                        print(f"\n{result}")
                
                elif choice == '4':
                    # Delete session
                    session_id = input("Enter session ID to delete: ").strip()
                    if session_id:
                        confirm = input(f"Are you sure you want to delete session {session_id}? (y/n): ").strip().lower()
                        if confirm in ['y', 'yes']:
                            tool = SessionManagementTool(self.session_manager)
                            result = await tool._arun("delete", session_id=session_id)
                            print(f"\n{result}")
                
                elif choice == '5':
                    # Session statistics
                    session_id = input("Enter session ID (or press Enter for current): ").strip()
                    tool = SessionManagementTool(self.session_manager)
                    result = await tool._arun("stats", session_id=session_id if session_id else None)
                    print(f"\n{result}")
                
                else:
                    print("Invalid option. Please try again.")
                    
            except KeyboardInterrupt:
                print("\n\nReturning to main menu...")
                break
            except Exception as e:
                print(f"\n❌ Error: {e}")
    
    async def handle_settings(self):
        """Handle system settings."""
        print("\n⚙️ System Settings")
        print("1. View system status")
        print("2. Cache statistics")
        print("3. Clear cache")
        print("0. Back to main menu")
        
        choice = input("\nSelect option: ").strip()
        
        if choice == '1':
            # System status
            print("\n📊 System Status:")
            print(f"Query Processor: {'✅ Ready' if self.query_processor._initialized else '❌ Not Ready'}")
            print(f"Session Manager: {'✅ Ready' if self.session_manager._initialized else '❌ Not Ready'}")
            print(f"RAG Chain: {'✅ Ready' if self.rag_chain._initialized else '❌ Not Ready'}")
            print(f"Cache Manager: {'✅ Ready' if self.cache_manager._initialized else '❌ Not Ready'}")
            
            # Index stats
            if self.query_processor._initialized:
                stats = await self.query_processor.get_index_stats()
                print(f"\n📈 Vector Index Stats:")
                print(f"Total vectors: {stats.get('total_vectors', 0)}")
                print(f"Dimension: {stats.get('dimension', 1536)}")
                print(f"Index fullness: {stats.get('index_fullness', 0):.2%}")
        
        elif choice == '2':
            # Cache statistics
            if self.cache_manager:
                stats = await self.cache_manager.get_cache_statistics()
                print(f"\n📊 Cache Statistics:")
                print(f"Callback stats: {stats.get('callback_stats', {})}")
        
        elif choice == '3':
            # Clear cache
            confirm = input("Are you sure you want to clear all caches? (y/n): ").strip().lower()
            if confirm in ['y', 'yes']:
                if self.cache_manager:
                    await self.cache_manager.flush_all_caches()
                    print("✅ Cache cleared successfully")
    
    async def run(self):
        """Run the interactive menu system."""
        if not self._initialized:
            await self.initialize()
        
        print("\n🚀 Starting Interactive RAG Query System...")
        
        while self._running:
            try:
                self.display_main_menu()
                choice = input("\nSelect option: ").strip()
                
                if choice == '0':
                    print("\n👋 Goodbye!")
                    self._running = False
                    break
                
                elif choice == '1':
                    await self.handle_one_time_query()
                
                elif choice == '2':
                    await self.handle_conversational_mode()
                
                elif choice == '3':
                    await self.handle_session_management()
                
                elif choice == '4':
                    await self.handle_settings()
                
                elif choice == '5':
                    self.display_help()
                    input("\nPress Enter to continue...")
                
                else:
                    print("Invalid option. Please try again.")
                    
            except KeyboardInterrupt:
                print("\n\n👋 Interrupted by user. Goodbye!")
                self._running = False
                break
            except Exception as e:
                logger.error(f"Menu system error: {e}")
                print(f"\n❌ Unexpected error: {e}")
                print("Please try again or contact support.")
    
    async def close(self):
        """Clean up menu system resources."""
        self._running = False
        self._initialized = False
        logger.info("Menu system closed")


# Global menu system instance
_menu_system = None


async def get_menu_system() -> MenuSystem:
    """Get or create menu system instance."""
    global _menu_system
    
    if _menu_system is None:
        _menu_system = MenuSystem()
        await _menu_system.initialize()
    
    return _menu_system


async def close_menu_system():
    """Close menu system."""
    global _menu_system
    
    if _menu_system:
        await _menu_system.close()
        _menu_system = None