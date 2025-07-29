#!/usr/bin/env python3
"""
WebSocket Server Module for Real-time Processing Updates
Provides centralized websocket server management for document ingestion
"""

import logging
import time
from datetime import datetime
from typing import Dict, Any, Optional, Set
from flask_socketio import SocketIO, emit, join_room, leave_room
import threading

logger = logging.getLogger(__name__)

class WebSocketServer:
    """Centralized websocket server management"""
    
    def __init__(self, socketio: SocketIO):
        self.socketio = socketio
        self.active_sessions: Dict[str, Dict[str, Any]] = {}
        self.connected_clients: Set[str] = set()
        self._lock = threading.Lock()
        
    def initialize(self):
        """Initialize websocket server with event handlers"""
        logger.info("🔌 Initializing WebSocket server...")
        
        @self.socketio.on('connect')
        def handle_connect():
            from flask import request
            client_id = request.sid
            logger.info(f'Client connected: {client_id}')
            with self._lock:
                self.connected_clients.add(client_id)
            
        @self.socketio.on('disconnect')
        def handle_disconnect():
            from flask import request
            client_id = request.sid
            logger.info(f'Client disconnected: {client_id}')
            with self._lock:
                self.connected_clients.discard(client_id)
                
        @self.socketio.on('join_session')
        def handle_join_session(data):
            from flask import request
            session_id = data.get('session_id', 'default')
            client_id = request.sid
            
            logger.info(f'Client {client_id} joining session: {session_id}')
            join_room(session_id)
            
            # Register session
            self.register_session(session_id, client_id)
            
            # Confirm join
            emit('joined', {
                'session_id': session_id,
                'timestamp': datetime.now().isoformat()
            })
            
            # Send a test processing update immediately after joining to test the connection
            logger.info(f"Sending test processing update to session {session_id}")
            self.socketio.emit('processing_update', {
                'type': 'log',
                'message': '🧪 Test: WebSocket connection verified after joining',
                'level': 'info',
                'timestamp': datetime.now().isoformat(),
                'session_id': session_id
            }, room=session_id)
            

            
        logger.info("✅ WebSocket server initialized")
    
    def register_session(self, session_id: str, client_id: str = None):
        """Register a new processing session"""
        with self._lock:
            if session_id not in self.active_sessions:
                self.active_sessions[session_id] = {
                    'session_id': session_id,
                    'client_id': client_id,
                    'status': 'active',
                    'start_time': datetime.now(),
                    'last_update': datetime.now(),
                    'message_count': 0
                }
                logger.info(f"📝 Registered session: {session_id}")
    
    def unregister_session(self, session_id: str):
        """Unregister a completed processing session"""
        with self._lock:
            if session_id in self.active_sessions:
                del self.active_sessions[session_id]
                logger.info(f"🗑️ Unregistered session: {session_id}")
    
    def emit_log(self, session_id: str, message: str, log_level: str = 'info'):
        """Emit a log message to a specific session"""
        self._emit_update(session_id, {
            'type': 'log',
            'message': message,
            'level': log_level,
            'timestamp': datetime.now().isoformat()
        })
    
    def emit_progress(self, session_id: str, current: int, total: int, current_item: str = None):
        """Emit progress update to a specific session"""
        progress_data = {
            'type': 'progress',
            'current': current,
            'total': total,
            'percentage': round((current / total) * 100, 1) if total > 0 else 0,
            'timestamp': datetime.now().isoformat()
        }
        
        if current_item:
            progress_data['current_item'] = current_item
            progress_data['message'] = f'Processing {current}/{total}: {current_item}'
        else:
            progress_data['message'] = f'Progress: {current}/{total} ({progress_data["percentage"]}%)'
            
        self._emit_update(session_id, progress_data)
    
    def emit_completion(self, session_id: str, success: bool, message: str, stats: Dict = None):
        """Emit completion status to a specific session"""
        completion_data = {
            'type': 'complete',
            'status': 'success' if success else 'error',
            'message': message,
            'timestamp': datetime.now().isoformat()
        }
        
        if stats:
            completion_data['data'] = {'stats': stats}
            
        self._emit_update(session_id, completion_data)
        
        # Update session status
        with self._lock:
            if session_id in self.active_sessions:
                self.active_sessions[session_id]['status'] = 'completed' if success else 'failed'
    
    def emit_error(self, session_id: str, error_message: str, error_details: str = None):
        """Emit error message to a specific session"""
        error_data = {
            'type': 'error',
            'message': error_message,
            'timestamp': datetime.now().isoformat()
        }
        
        if error_details:
            error_data['details'] = error_details
            
        self._emit_update(session_id, error_data)
    
    def _emit_update(self, session_id: str, data: Dict[str, Any]):
        """Internal method to emit updates to a session room"""
        try:
            # Add session_id to data
            data['session_id'] = session_id
            
            # Emit to session room only (clients join the room, so they'll receive it)
            self.socketio.emit('processing_update', data, room=session_id)
            
            # Update session stats
            with self._lock:
                if session_id in self.active_sessions:
                    self.active_sessions[session_id]['last_update'] = datetime.now()
                    self.active_sessions[session_id]['message_count'] += 1
            
            logger.info(f"📡 Emitted {data['type']} to session {session_id}: {data.get('message', '')[:100]}")
            
        except Exception as e:
            logger.error(f"❌ Failed to emit update to session {session_id}: {e}")
    
    def get_session_info(self, session_id: str) -> Optional[Dict[str, Any]]:
        """Get information about a specific session"""
        with self._lock:
            return self.active_sessions.get(session_id)
    
    def get_active_sessions(self) -> Dict[str, Dict[str, Any]]:
        """Get all active sessions"""
        with self._lock:
            return self.active_sessions.copy()
    
    def cleanup_stale_sessions(self, max_age_minutes: int = 30):
        """Clean up sessions that haven't been updated recently"""
        cutoff_time = datetime.now().timestamp() - (max_age_minutes * 60)
        
        with self._lock:
            stale_sessions = [
                session_id for session_id, session_info in self.active_sessions.items()
                if session_info['last_update'].timestamp() < cutoff_time
            ]
            
            for session_id in stale_sessions:
                logger.info(f"🧹 Cleaning up stale session: {session_id}")
                del self.active_sessions[session_id]
    
    def get_connection_count(self) -> int:
        """Get number of connected clients"""
        with self._lock:
            return len(self.connected_clients)

# Global websocket server instance
_websocket_server: Optional[WebSocketServer] = None

def initialize_websocket_server(socketio: SocketIO) -> WebSocketServer:
    """Initialize the global websocket server instance"""
    global _websocket_server
    
    if _websocket_server is None:
        _websocket_server = WebSocketServer(socketio)
        _websocket_server.initialize()
        logger.info("🚀 WebSocket server initialized globally")
    
    return _websocket_server

def get_websocket_server() -> Optional[WebSocketServer]:
    """Get the global websocket server instance"""
    return _websocket_server

def send_processing_update(session_id: str, update_type: str, message: str, data: Any = None):
    """Utility function for sending processing updates"""
    server = get_websocket_server()
    if server:
        if update_type == 'log':
            server.emit_log(session_id, message)
        elif update_type == 'progress':
            if isinstance(data, dict) and 'current' in data and 'total' in data:
                server.emit_progress(session_id, data['current'], data['total'], data.get('current_item'))
            else:
                server.emit_log(session_id, message)
        elif update_type == 'complete':
            success = data.get('status') == 'success' if data else True
            stats = data.get('stats') if data else None
            server.emit_completion(session_id, success, message, stats)
        elif update_type == 'error':
            details = data.get('details') if data else None
            server.emit_error(session_id, message, details)
        else:
            server.emit_log(session_id, message)
    else:
        # Fallback to logging if websocket server not available
        logger.info(f"[{session_id}] {update_type.upper()}: {message}")