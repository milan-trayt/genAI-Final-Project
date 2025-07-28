#!/usr/bin/env python3
"""
API client for backend communication.
"""

import requests
import streamlit as st
from typing import Dict, Any, List, Optional
import json
import time

from config import config

class APIClient:
    """Client for communicating with the backend API."""
    
    def __init__(self):
        self.session = requests.Session()
        self.session.headers.update({
            "Content-Type": "application/json"
        })
    
    def check_health(self) -> bool:
        """Check if backend is healthy."""
        try:
            response = self.session.get(config.get_endpoint("health"), timeout=5)
            return response.status_code == 200
        except Exception as e:
            st.error(f"Backend health check failed: {e}")
            return False
    
    def create_session(self, session_name: str) -> Optional[Dict[str, Any]]:
        """Create a new session."""
        try:
            payload = {"session_name": session_name}
            response = self.session.post(
                config.get_endpoint("sessions"),
                json=payload,
                timeout=10
            )
            
            if response.status_code == 200:
                return response.json()
            else:
                st.error(f"Failed to create session: {response.text}")
                return None
                
        except Exception as e:
            st.error(f"Error creating session: {e}")
            return None
    
    def list_sessions(self) -> List[Dict[str, Any]]:
        """List all sessions."""
        try:
            response = self.session.get(config.get_endpoint("sessions"), timeout=10)
            
            if response.status_code == 200:
                return response.json()
            else:
                st.error(f"Failed to list sessions: {response.text}")
                return []
                
        except Exception as e:
            st.error(f"Error listing sessions: {e}")
            return []
    
    def delete_session(self, session_id: str) -> bool:
        """Delete a session."""
        try:
            response = self.session.delete(
                f"{config.get_endpoint('sessions')}/{session_id}",
                timeout=10
            )
            return response.status_code == 200
            
        except Exception as e:
            st.error(f"Error deleting session: {e}")
            return False
    
    def query_conversational(self, query: str, session_id: str, top_k: int = 5) -> Optional[Dict[str, Any]]:
        """Send a conversational query."""
        try:
            payload = {
                "query": query,
                "session_id": session_id,
                "top_k": top_k
            }
            
            response = self.session.post(
                config.get_endpoint("query_conversational"),
                json=payload,
                timeout=60
            )
            
            if response.status_code == 200:
                return response.json()
            else:
                st.error(f"Query failed: {response.text}")
                return None
                
        except Exception as e:
            st.error(f"Error sending query: {e}")
            return None
    
    def query_oneshot(self, query: str, top_k: int = 5) -> Optional[Dict[str, Any]]:
        """Send a one-shot query without context."""
        try:
            payload = {
                "query": query,
                "top_k": top_k
            }
            
            response = self.session.post(
                config.get_endpoint("query_oneshot"),
                json=payload,
                timeout=60
            )
            
            if response.status_code == 200:
                return response.json()
            else:
                st.error(f"One-shot query failed: {response.text}")
                return None
                
        except Exception as e:
            st.error(f"Error sending one-shot query: {e}")
            return None
    
    def generate_topic(self, query: str) -> Optional[str]:
        """Generate a topic from a query."""
        try:
            payload = {"query": query}
            
            response = self.session.post(
                config.get_endpoint("generate_topic"),
                json=payload,
                timeout=30
            )
            
            if response.status_code == 200:
                return response.json().get("topic")
            else:
                return None
                
        except Exception:
            return None
    
    def get_session_history(self, session_id: str) -> List[Dict[str, Any]]:
        """Get conversation history for a session."""
        try:
            response = self.session.get(
                f"{config.get_endpoint('sessions')}/{session_id}/history",
                timeout=30
            )
            
            if response.status_code == 200:
                return response.json().get("messages", [])
            else:
                return []
                
        except Exception:
            return []
    
    def update_session_name(self, session_id: str, session_name: str) -> bool:
        """Update session name."""
        try:
            payload = {"session_name": session_name}
            
            response = self.session.put(
                f"{config.get_endpoint('sessions')}/{session_id}",
                json=payload,
                timeout=10
            )
            
            return response.status_code == 200
                
        except Exception:
            return False

# Global API client instance
api_client = APIClient()