#!/usr/bin/env python3
"""
Session management for Streamlit frontend.
"""

import streamlit as st
from typing import Dict, Any, List, Optional
import uuid
from datetime import datetime

from api_client import api_client

# Initialize session state at module level
def _ensure_session_state():
    """Ensure session state is initialized."""
    if "sessions" not in st.session_state:
        st.session_state.sessions = {}
    if "active_session_id" not in st.session_state:
        st.session_state.active_session_id = None
    if "session_counter" not in st.session_state:
        st.session_state.session_counter = 1
    if "messages" not in st.session_state:
        st.session_state.messages = {}
    if "sessions_loaded" not in st.session_state:
        st.session_state.sessions_loaded = False

class SessionManager:
    """Manages sessions and conversation state in Streamlit."""
    
    def __init__(self):
        self._initialized = False
    
    def create_new_session(self, session_name: str = None) -> Optional[str]:
        """Create a new session."""
        _ensure_session_state()
        
        if not session_name:
            session_name = f"New Session"
        
        # Create session via API
        session_data = api_client.create_session(session_name)
        
        if session_data:
            session_id = session_data["session_id"]
            
            # Store session info locally
            st.session_state.sessions[session_id] = {
                "id": session_id,
                "name": session_name,
                "created_at": session_data.get("created_at", datetime.now().isoformat()),
                "message_count": 0,
                "needs_rename": True  # Flag to rename after first message
            }
            
            # Initialize messages for this session
            st.session_state.messages[session_id] = []
            
            # Set as active session
            st.session_state.active_session_id = session_id
            
            # Mark sessions as loaded since we just created one
            st.session_state.sessions_loaded = True
            
            return session_id
        
        return None
    
    def update_session_name_from_query(self, session_id: str, query: str):
        """Update session name based on first query."""
        _ensure_session_state()
        
        if session_id in st.session_state.sessions and st.session_state.sessions[session_id].get("needs_rename", False):
            # Generate topic from query
            topic = api_client.generate_topic(query)
            
            if topic:
                # Update in backend/database
                if api_client.update_session_name(session_id, topic):
                    # Update local state only if backend update succeeded
                    st.session_state.sessions[session_id]["name"] = topic
                    st.session_state.sessions[session_id]["needs_rename"] = False
    
    def delete_session(self, session_id: str) -> bool:
        """Delete a session."""
        _ensure_session_state()
        
        if api_client.delete_session(session_id):
            # Remove from local state
            if session_id in st.session_state.sessions:
                del st.session_state.sessions[session_id]
            
            if session_id in st.session_state.messages:
                del st.session_state.messages[session_id]
            
            # If this was the active session, clear it
            if st.session_state.active_session_id == session_id:
                st.session_state.active_session_id = None
            
            return True
        
        return False
    
    def get_active_session(self) -> Optional[Dict[str, Any]]:
        """Get the currently active session."""
        _ensure_session_state()
        
        if st.session_state.active_session_id:
            return st.session_state.sessions.get(st.session_state.active_session_id)
        return None
    
    def set_active_session(self, session_id: str):
        """Set the active session."""
        _ensure_session_state()
        
        if session_id in st.session_state.sessions:
            st.session_state.active_session_id = session_id
            
            # Load messages from backend if not already loaded
            if session_id not in st.session_state.messages or not st.session_state.messages[session_id]:
                try:
                    messages = api_client.get_session_history(session_id)
                    st.session_state.messages[session_id] = messages
                except Exception as e:
                    st.error(f"Failed to load session history: {e}")
                    st.session_state.messages[session_id] = []
    
    def get_session_messages(self, session_id: str) -> List[Dict[str, Any]]:
        """Get messages for a session."""
        _ensure_session_state()
        return st.session_state.messages.get(session_id, [])
    
    def add_message(self, session_id: str, role: str, content: str, processing_time: float = None):
        """Add a message to a session."""
        _ensure_session_state()
        
        if session_id not in st.session_state.messages:
            st.session_state.messages[session_id] = []
        
        message = {
            "role": role,
            "content": content,
            "timestamp": datetime.now().isoformat()
        }
        
        if processing_time:
            message["processing_time"] = processing_time
        
        st.session_state.messages[session_id].append(message)
        
        # Update message count
        if session_id in st.session_state.sessions:
            st.session_state.sessions[session_id]["message_count"] = len(st.session_state.messages[session_id])
    
    def clear_session_messages(self, session_id: str):
        """Clear all messages from a session."""
        _ensure_session_state()
        
        if session_id in st.session_state.messages:
            st.session_state.messages[session_id] = []
        
        if session_id in st.session_state.sessions:
            st.session_state.sessions[session_id]["message_count"] = 0
    
    def load_sessions_from_backend(self):
        """Load sessions from backend API."""
        _ensure_session_state()
        
        if st.session_state.sessions_loaded:
            return
        
        try:
            # Get sessions from backend
            backend_sessions = api_client.list_sessions()
            
            if backend_sessions and "sessions" in backend_sessions:
                # Convert backend format to frontend format
                for session in backend_sessions["sessions"]:
                    session_id = session["session_id"]
                    st.session_state.sessions[session_id] = {
                        "id": session_id,
                        "name": session.get("session_name", "Unnamed Session"),
                        "created_at": session.get("created_at", datetime.now().isoformat()),
                        "message_count": session.get("message_count", 0),
                        "needs_rename": False
                    }
                    
                    # Initialize empty messages for each session
                    if session_id not in st.session_state.messages:
                        st.session_state.messages[session_id] = []
                
                st.session_state.sessions_loaded = True
                
        except Exception as e:
            st.error(f"Failed to load sessions: {e}")
    
    def get_all_sessions(self) -> Dict[str, Dict[str, Any]]:
        """Get all sessions, loading from backend if needed."""
        _ensure_session_state()
        
        # Load from backend if not already loaded
        if not st.session_state.sessions_loaded:
            self.load_sessions_from_backend()
        
        return st.session_state.sessions
    
    def rename_session(self, session_id: str, new_name: str):
        """Rename a session."""
        _ensure_session_state()
        
        if session_id in st.session_state.sessions:
            st.session_state.sessions[session_id]["name"] = new_name

# Global session manager instance - initialized lazily
_session_manager = None

def get_session_manager() -> SessionManager:
    """Get or create session manager instance."""
    global _session_manager
    if _session_manager is None:
        _session_manager = SessionManager()
        _ensure_session_state()  # Initialize immediately
    return _session_manager