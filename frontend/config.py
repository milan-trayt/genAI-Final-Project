#!/usr/bin/env python3
"""
Configuration for Streamlit frontend.
"""

import os
from typing import Dict, Any

class Config:
    """Configuration class for frontend."""
    
    def __init__(self):
        self.backend_url = os.getenv("BACKEND_URL", "http://localhost:8000")
        self.app_title = "DevOps Assistant"
        self.page_icon = ""
        self.layout = "wide"
        self.initial_sidebar_state = "expanded"
        
        # API endpoints
        self.endpoints = {
            "health": f"{self.backend_url}/health",
            "sessions": f"{self.backend_url}/sessions",
            "query_conversational": f"{self.backend_url}/query/conversational",
            "query_oneshot": f"{self.backend_url}/query/one-time",
            "generate_topic": f"{self.backend_url}/generate-topic"
        }
        
        # UI settings
        self.max_message_length = 4000
        self.default_top_k = 5
        self.typing_delay = 0.01
        
    def get_endpoint(self, name: str) -> str:
        """Get API endpoint URL."""
        return self.endpoints.get(name, "")

# Global config instance
config = Config()