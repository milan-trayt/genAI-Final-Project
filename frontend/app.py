#!/usr/bin/env python3
"""
Streamlit frontend for GenAI DevOps Assistant.
"""

import streamlit as st
import time
import threading
from typing import Dict, Any, Optional
import uuid

from config import config
from api_client import api_client
from session_manager import get_session_manager

# Page configuration
st.set_page_config(
    page_title=config.app_title,
    page_icon=config.page_icon,
    layout=config.layout,
    initial_sidebar_state=config.initial_sidebar_state
)

def check_backend_health():
    """Check if backend is healthy and show status."""
    if not api_client.check_health():
        st.error("❌ Backend is not available. Please ensure the backend service is running.")
        st.stop()
    else:
        st.success("✅ Backend is healthy")

def render_sidebar():
    """Render the sidebar with session management."""
    with st.sidebar:
        st.title("💬 Sessions")
        
        # Create new session button
        if st.button("➕ New Session", use_container_width=True):
            session_id = get_session_manager().create_new_session()
            if session_id:
                st.success(f"Created new session!")
                st.rerun()
        
        st.divider()
        
        # List existing sessions
        sessions = get_session_manager().get_all_sessions()
        
        if not sessions:
            st.info("No sessions yet. Create your first session!")
        else:
            st.subheader("Active Sessions")
            
            for session_id, session_info in sessions.items():
                col1, col2 = st.columns([4, 1])
                
                with col1:
                    # Session button
                    is_active = session_id == st.session_state.active_session_id
                    button_label = f"{'🟢' if is_active else '⚪'} {session_info['name']}"
                    
                    if st.button(button_label, key=f"session_{session_id}", use_container_width=True):
                        get_session_manager().set_active_session(session_id)
                        st.rerun()
                
                with col2:
                    # Delete button
                    if st.button("🗑️", key=f"delete_{session_id}", help="Delete session"):
                        if get_session_manager().delete_session(session_id):
                            st.success("Session deleted!")
                            st.rerun()
        
        st.divider()
        
        # One-shot query button
        if st.button("⚡ One-Shot Query", use_container_width=True, help="Ask a question without context"):
            st.session_state.show_oneshot_modal = True
            st.rerun()

def render_oneshot_modal():
    """Render the one-shot query modal."""
    if st.session_state.get("show_oneshot_modal", False):
        with st.container():
            st.subheader("⚡ One-Shot Query")
            st.info("Ask a question without conversation context. This won't be saved to any session.")
            
            # Initialize oneshot query in session state if not exists
            if "oneshot_query_text" not in st.session_state:
                st.session_state.oneshot_query_text = ""
            
            # Query input
            oneshot_query = st.text_area(
                "Your question:",
                value=st.session_state.oneshot_query_text,
                placeholder="What is Docker?",
                key="oneshot_input",
                height=100
            )
            
            # Update session state with current input
            st.session_state.oneshot_query_text = oneshot_query
            
            col1, col2, col3 = st.columns([1, 1, 1])
            
            with col1:
                if st.button("Send Query", disabled=not oneshot_query.strip()):
                    if oneshot_query.strip():
                        with st.spinner("Processing your query..."):
                            result = api_client.query_oneshot(oneshot_query.strip(), config.default_top_k)
                        
                        if result:
                            st.success("✅ Query completed!")
                            st.markdown("**Response:**")
                            st.markdown(result["response"])
                            
                            if result.get("processing_time"):
                                st.caption(f"⏱️ Processing time: {result['processing_time']:.2f}s")
            
            with col2:
                if st.button("Clear"):
                    st.session_state.oneshot_query_text = ""
                    st.rerun()
            
            with col3:
                if st.button("Close"):
                    st.session_state.show_oneshot_modal = False
                    st.session_state.oneshot_query_text = ""
                    st.rerun()
            
            st.divider()

def render_chat_interface():
    """Render the main chat interface."""
    active_session = get_session_manager().get_active_session()
    
    if not active_session:
        st.info("👈 Select a session from the sidebar or create a new one to start chatting!")
        return
    
    # Handle force refresh to show completed messages
    if st.session_state.get("force_refresh", False):
        st.session_state.force_refresh = False
        st.rerun()
    
    # Process queued message if any
    if st.session_state.get("queued_prompt") and not st.session_state.get("generating", False):
        prompt = st.session_state.queued_prompt
        del st.session_state.queued_prompt
        
        # Set generating status
        st.session_state.generating = True
        
        # Add user message
        get_session_manager().add_message(active_session["id"], "user", prompt)
        
        # Display user message
        with st.chat_message("user"):
            st.markdown(prompt)
        
        # Generate response
        with st.chat_message("assistant"):
            with st.spinner("Thinking..."):
                result = api_client.query_conversational(
                    prompt, 
                    active_session["id"], 
                    config.default_top_k
                )
            
            if result:
                response_text = result["response"]
                
                # Save the response immediately
                get_session_manager().add_message(
                    active_session["id"], 
                    "assistant", 
                    response_text,
                    result.get("processing_time")
                )
                
                # Display response immediately (no typing effect for queued messages)
                st.markdown(response_text)
                
                # Add processing time
                if result.get("processing_time"):
                    st.caption(f"⏱️ {result['processing_time']:.2f}s")
            else:
                st.error("Failed to get response. Please try again.")
        
        # Clear generating status
        st.session_state.generating = False
        return  # Exit early after processing queued message
    
    # Process pending prompt after session name update rerun
    if st.session_state.get("pending_prompt") and st.session_state.get("pending_session_id") == active_session["id"]:
        prompt = st.session_state.pending_prompt
        message_id = st.session_state.get("pending_message_id", "pending")
        del st.session_state.pending_prompt
        del st.session_state.pending_session_id
        if "pending_message_id" in st.session_state:
            del st.session_state.pending_message_id
        
        # Process the pending prompt
        get_session_manager().add_message(active_session["id"], "user", prompt)
        
        # Display user message
        with st.chat_message("user"):
            st.markdown(prompt)
        
        # Generate response
        with st.chat_message("assistant"):
            with st.spinner("Thinking..."):
                result = api_client.query_conversational(
                    prompt, 
                    active_session["id"], 
                    config.default_top_k
                )
            
            if result:
                response_text = result["response"]
                
                # Save the response immediately
                get_session_manager().add_message(
                    active_session["id"], 
                    "assistant", 
                    response_text,
                    result.get("processing_time")
                )
                
                # Display response with typing effect
                response_placeholder = st.empty()
                
                # Set generating to True during typing
                st.session_state.generating = True
                
                # Typing effect with interruption check
                displayed_text = ""
                for char in response_text:
                    # Check if typing should be skipped
                    if st.session_state.get("skip_typing", False):
                        response_placeholder.markdown(response_text)
                        st.session_state.skip_typing = False
                        break
                    
                    displayed_text += char
                    response_placeholder.markdown(displayed_text + "▌")
                    time.sleep(config.typing_delay)
                else:
                    response_placeholder.markdown(response_text)
                
                # Add processing time
                if result.get("processing_time"):
                    st.caption(f"⏱️ {result['processing_time']:.2f}s")
                
                # Clear generating status after typing completes
                st.session_state.generating = False
            else:
                st.session_state.generating = False
                st.error("Failed to get response. Please try again.")
        
        return  # Exit early after processing pending prompt
    
    # Session header
    st.header(f"💬 {active_session['name']}")
    
    # Chat messages container
    messages_container = st.container()
    
    with messages_container:
        messages = get_session_manager().get_session_messages(active_session["id"])
        
        if not messages:
            st.info("Start a conversation by typing a message below!")
        else:
            for message in messages:
                with st.chat_message(message["role"]):
                    st.markdown(message["content"])
                    
                    if message.get("processing_time"):
                        st.caption(f"⏱️ {message['processing_time']:.2f}s")
    
    # Process queued message first
    if st.session_state.get("queued_prompt") and not st.session_state.get("generating", False):
        prompt = st.session_state.queued_prompt
        del st.session_state.queued_prompt
        
        # Add and display queued user message
        get_session_manager().add_message(active_session["id"], "user", prompt)
        with st.chat_message("user"):
            st.markdown(prompt)
        
        # Generate response for queued message
        with st.chat_message("assistant"):
            with st.spinner("Thinking..."):
                result = api_client.query_conversational(
                    prompt, 
                    active_session["id"], 
                    config.default_top_k
                )
            
            if result:
                response_text = result["response"]
                get_session_manager().add_message(
                    active_session["id"], 
                    "assistant", 
                    response_text,
                    result.get("processing_time")
                )
                st.markdown(response_text)  # No typing for queued messages
                if result.get("processing_time"):
                    st.caption(f"⏱️ {result['processing_time']:.2f}s")
        return
    
    # Chat input
    if prompt := st.chat_input("Ask me anything about DevOps, cloud infrastructure, or software development..."):
        # If currently generating, queue the message and make current typing instant
        if st.session_state.get("generating", False):
            st.session_state.skip_typing = True
            st.session_state.queued_prompt = prompt
            return  # Don't process new message yet
        
        # Update session name if this is the first message (without blocking)
        if active_session.get("needs_rename", False):
            get_session_manager().update_session_name_from_query(active_session["id"], prompt)
            st.session_state.pending_prompt = prompt
            st.session_state.pending_session_id = active_session["id"]
            st.rerun()
        
        # Add user message
        get_session_manager().add_message(active_session["id"], "user", prompt)
        
        # Display user message
        with st.chat_message("user"):
            st.markdown(prompt)
        
        # Generate response
        with st.chat_message("assistant"):
            with st.spinner("Thinking..."):
                result = api_client.query_conversational(
                    prompt, 
                    active_session["id"], 
                    config.default_top_k
                )
            
            if result:
                # Display response with typing effect
                response_placeholder = st.empty()
                response_text = result["response"]
                
                # Simulate typing effect
                displayed_text = ""
                for char in response_text:
                    displayed_text += char
                    response_placeholder.markdown(displayed_text + "▌")
                    time.sleep(config.typing_delay)
                
                response_placeholder.markdown(response_text)
                
                # Add processing time
                if result.get("processing_time"):
                    st.caption(f"⏱️ {result['processing_time']:.2f}s")
                
                # Add assistant message to session
                get_session_manager().add_message(
                    active_session["id"], 
                    "assistant", 
                    response_text,
                    result.get("processing_time")
                )
                

            else:
                st.error("Failed to get response. Please try again.")

def main():
    """Main application function."""
    # Initialize session manager and session state first
    get_session_manager()
    
    # Initialize other session state
    if "show_oneshot_modal" not in st.session_state:
        st.session_state.show_oneshot_modal = False
    if "generating" not in st.session_state:
        st.session_state.generating = False
    
    # App header
    st.title(f"{config.page_icon} {config.app_title}")
    
    # Check backend health
    with st.expander("🔧 System Status", expanded=False):
        check_backend_health()
    
    # Render sidebar
    render_sidebar()
    
    # Render one-shot modal if active
    if st.session_state.get("show_oneshot_modal", False):
        render_oneshot_modal()
    else:
        # Render main chat interface
        render_chat_interface()
    
    # Footer
    st.divider()
    st.caption("💡 Use the sidebar to manage sessions or click 'One-Shot Query' for context-free questions.")

if __name__ == "__main__":
    main()