#!/usr/bin/env python3
"""
Simple API server for collab container to handle ingestion requests
"""

from flask import Flask, request, jsonify
from flask_cors import CORS
from flask_socketio import SocketIO, emit, join_room
import json
import subprocess
import sys
import os
import threading
import time
import logging
from websocket_server import initialize_websocket_server, get_websocket_server

# Setup logging
logging.basicConfig(level=logging.WARNING)
logger = logging.getLogger(__name__)

app = Flask(__name__)
CORS(app, origins="*", methods=['GET', 'POST', 'OPTIONS'], allow_headers=['Content-Type', 'Authorization'])
socketio = SocketIO(
    app, 
    cors_allowed_origins="*", 
    ping_timeout=120, 
    ping_interval=30, 
    logger=True, 
    engineio_logger=True,
    # Enable full WebSocket support with upgrades
    allow_upgrades=True,  # Enable transport upgrades
    transports=['polling', 'websocket'],  # Allow both transports
    async_mode='threading'  # Use threading mode for better compatibility
)

# Initialize websocket server
ws_server = initialize_websocket_server(socketio)

@app.route('/api/process', methods=['POST', 'OPTIONS'])
def process_documents():
    if request.method == 'OPTIONS':
        response = jsonify({})
        response.headers.add('Access-Control-Allow-Origin', '*')
        response.headers.add('Access-Control-Allow-Headers', 'Content-Type')
        response.headers.add('Access-Control-Allow-Methods', 'POST, OPTIONS')
        return response
    
    try:
        data = request.get_json()
        input_data = data.get('input', '{}')
        session_id = data.get('session_id', 'default')
        
        # Check if session is already processing
        if hasattr(app, 'active_sessions') and session_id in app.active_sessions:
            return jsonify({
                "status": "error",
                "message": "Session already processing"
            }), 400
        
        # Mark session as active
        if not hasattr(app, 'active_sessions'):
            app.active_sessions = set()
        if not hasattr(app, 'active_threads'):
            app.active_threads = {}
        app.active_sessions.add(session_id)
        
        def run_processing():
            with app.app_context():
                # Set stop flag for this session
                if not hasattr(app, 'stop_flags'):
                    app.stop_flags = {}
                app.stop_flags[session_id] = False
                
                # Register session with websocket server
                ws_server.register_session(session_id)
                
                try:
                    parsed_input = json.loads(input_data)
                    sources = parsed_input.get('sources', [])
                    ws_server.emit_log(session_id, f'Starting processing of {len(sources)} sources...')
                    ws_server.emit_log(session_id, f'Processing configuration: chunk_size=1000, chunk_overlap=200')
                    
                    # Process each source
                    for i, source in enumerate(sources):
                        # Check if processing should stop
                        if app.stop_flags.get(session_id, False):
                            ws_server.emit_log(session_id, 'Processing stopped by user', 'info')
                            ws_server.emit_completion(session_id, False, 'Processing stopped by user')
                            return
                        
                        source_name = source.get("name", "unknown")
                        source_type = source.get('type', 'unknown')
                        ws_server.emit_log(session_id, f'[{i+1}/{len(sources)}] Processing {source_type.upper()}: {source_name}')
                        ws_server.emit_progress(session_id, i + 1, len(sources), source_name)
                        
                        # Call the original processing endpoint
                        input_data_single = json.dumps({
                            'sources': [source],
                            'config': {'chunk_size': 1000, 'chunk_overlap': 200}
                        })
                        
                        # Create a temporary ingestion instance and process the source
                        from interactive_ingestion import InteractiveRAGIngestion
                        from models import create_web_source, create_github_codebase_source, create_pdf_source, create_csv_source
                        
                        temp_ingestion = InteractiveRAGIngestion()
                        
                        # Track ingestion instance for stopping
                        if not hasattr(app, 'active_ingestion_instances'):
                            app.active_ingestion_instances = {}
                        app.active_ingestion_instances[session_id] = temp_ingestion
                        
                        # Convert source dict to proper source object
                        source_type = source.get('type', 'unknown')
                        custom_metadata = source.get('customMetadata', {})
                        
                        if source_type == 'web':
                            source_obj = create_web_source(source['path'], source.get('docType', 'web_documentation'))
                        elif source_type == 'github':
                            source_obj = create_github_codebase_source(
                                source['path'], 
                                source.get('token'), 
                                source.get('extensions', []), 
                                1024*1024  # 1MB default
                            )
                            # Add token to metadata for loader access
                            source_obj.metadata['access_token'] = source.get('token')
                        elif source_type == 'pdf':
                            source_obj = create_pdf_source(source['path'], source.get('docType', 'pdf_document'))
                        elif source_type == 'csv':
                            source_obj = create_csv_source(source['path'], source.get('docType', 'csv_document'))
                        else:
                            ws_server.emit_log(session_id, f'Unknown source type: {source_type}', 'error')
                            continue
                        
                        # Add custom metadata to source
                        if custom_metadata:
                            source_obj.metadata.update(custom_metadata)
                            
                        temp_ingestion.document_sources = [source_obj]
                        
                        ws_server.emit_log(session_id, f'Loading documents from {source_type}...')
                        try:
                            # Add timing
                            import time
                            start_time = time.time()
                            temp_ingestion.process_documents(session_id)
                            end_time = time.time()
                            processing_time = end_time - start_time
                            ws_server.emit_log(session_id, f'[{i+1}/{len(sources)}] Completed {source_name} in {processing_time:.2f}s')
                        except Exception as source_error:
                            error_msg = str(source_error)
                            ws_server.emit_log(session_id, f'[{i+1}/{len(sources)}] Failed {source_name}: {error_msg}', 'error')
                    
                    # Emit completion with stats
                    total_time = time.time() - ws_server.active_sessions[session_id]['start_time'].timestamp()
                    ws_server.emit_log(session_id, f'Processing completed successfully!')
                    ws_server.emit_log(session_id, f'Summary: {len(sources)} sources processed in {total_time:.2f}s')
                    ws_server.emit_log(session_id, f'💾 Documents have been indexed and are ready for querying')
                    
                    stats = {
                        'total_sources': len(sources),
                        'processing_time': total_time
                    }
                    ws_server.emit_completion(session_id, True, 'All sources processed successfully!', stats)
                    
                except Exception as e:
                    ws_server.emit_completion(session_id, False, f'Processing failed: {str(e)}')
                    
                finally:
                    # Clean up session data
                    if hasattr(app, 'active_sessions') and session_id in app.active_sessions:
                        app.active_sessions.remove(session_id)
                    if hasattr(app, 'stop_flags') and session_id in app.stop_flags:
                        del app.stop_flags[session_id]
                    if hasattr(app, 'active_threads') and session_id in app.active_threads:
                        del app.active_threads[session_id]
                    if hasattr(app, 'active_ingestion_instances') and session_id in app.active_ingestion_instances:
                        del app.active_ingestion_instances[session_id]
                    
                    # Unregister session from websocket server
                    ws_server.unregister_session(session_id)
        
        try:
            thread = threading.Thread(target=run_processing)
            thread.daemon = True
            app.active_threads[session_id] = thread
            thread.start()
        except Exception as e:
            return jsonify({"status": "error", "message": f"Failed to start processing: {str(e)}"}), 500
        
        return jsonify({
            "status": "started",
            "message": "Processing started, connect to WebSocket for real-time updates",
            "session_id": session_id
        })
        

    except Exception as e:
        return jsonify({
            "status": "error", 
            "message": str(e)
        }), 500

@app.route('/api/stop', methods=['POST', 'OPTIONS'])
def stop_processing():
    if request.method == 'OPTIONS':
        response = jsonify({})
        response.headers.add('Access-Control-Allow-Origin', '*')
        response.headers.add('Access-Control-Allow-Headers', 'Content-Type')
        response.headers.add('Access-Control-Allow-Methods', 'POST, OPTIONS')
        return response
    
    try:
        data = request.get_json()
        session_id = data.get('session_id')
        
        if not session_id:
            return jsonify({"status": "error", "message": "Session ID required"}), 400
        
        # Set stop flag
        if hasattr(app, 'stop_flags'):
            app.stop_flags[session_id] = True
        
        # Also set stop flag on ingestion instance if it exists
        if hasattr(app, 'active_ingestion_instances') and session_id in app.active_ingestion_instances:
            app.active_ingestion_instances[session_id].should_stop = True
        
        return jsonify({
            "status": "success",
            "message": "Stop signal sent"
        })
        
    except Exception as e:
        return jsonify({
            "status": "error",
            "message": str(e)
        }), 500

@app.route('/api/ingest', methods=['POST', 'OPTIONS'])
def ingest_documents():
    """Legacy endpoint for backward compatibility"""
    return process_documents()

@app.route('/api/upload', methods=['POST', 'OPTIONS'])
def upload_file():
    if request.method == 'OPTIONS':
        response = jsonify({})
        response.headers.add('Access-Control-Allow-Origin', '*')
        response.headers.add('Access-Control-Allow-Headers', 'Content-Type')
        response.headers.add('Access-Control-Allow-Methods', 'POST, OPTIONS')
        return response
    
    print(f"📤 Upload request received")
    print(f"Request files: {list(request.files.keys())}")
    print(f"Request form: {dict(request.form)}")
    
    try:
        if 'file' not in request.files:
            print("No file in request")
            return jsonify({"status": "error", "message": "No file provided"}), 400
        
        file = request.files['file']
        print(f"File received: {file.filename}, Content-Type: {file.content_type}")
        
        if file.filename == '':
            print("Empty filename")
            return jsonify({"status": "error", "message": "No file selected"}), 400
        
        # Create uploads directory in current working directory
        uploads_dir = os.path.join(os.getcwd(), 'uploads')
        print(f"Creating uploads directory: {uploads_dir}")
        os.makedirs(uploads_dir, exist_ok=True)
        
        # Save file with safe filename
        filename = file.filename
        filepath = os.path.join(uploads_dir, filename)
        print(f"💾 Saving file to: {filepath}")
        
        try:
            file.save(filepath)
            file_size = os.path.getsize(filepath)
            print(f"File saved successfully: {filename} ({file_size} bytes)")
        except Exception as save_error:
            print(f"Failed to save file: {str(save_error)}")
            return jsonify({
                "status": "error",
                "message": f"Failed to save file: {str(save_error)}"
            }), 500
        
        print(f"Upload completed successfully: {filename}")
        return jsonify({
            "status": "success",
            "message": "File uploaded successfully",
            "filepath": filepath,
            "filename": filename
        })
        
    except Exception as e:
        return jsonify({
            "status": "error",
            "message": str(e)
        }), 500

@app.route('/health', methods=['GET'])
def health():
    return jsonify({"status": "healthy"})

@app.route('/api/status', methods=['GET'])
def status():
    """Check if ingestion system is ready"""
    try:
        # Check if required files exist
        required_files = ['interactive_ingestion.py', 'config.py', 'models.py']
        missing_files = [f for f in required_files if not os.path.exists(f)]
        
        if missing_files:
            return jsonify({
                "status": "error",
                "message": f"Missing required files: {', '.join(missing_files)}"
            }), 500
        
        return jsonify({
            "status": "ready",
            "message": "Ingestion system is ready"
        })
    except Exception as e:
        return jsonify({
            "status": "error",
            "message": str(e)
        }), 500

# WebSocket event handlers are now managed by websocket_server module

# Periodic cleanup of stale sessions
def cleanup_stale_sessions():
    """Periodically clean up stale sessions"""
    import threading
    import time
    
    def cleanup_worker():
        while True:
            try:
                time.sleep(300)  # Run every 5 minutes
                ws_server.cleanup_stale_sessions(max_age_minutes=30)
            except Exception as e:
                logger.error(f"Error during session cleanup: {e}")
    
    cleanup_thread = threading.Thread(target=cleanup_worker, daemon=True)
    cleanup_thread.start()


if __name__ == '__main__':
    cleanup_stale_sessions()
    socketio.run(app, host='0.0.0.0', port=8503, debug=True, allow_unsafe_werkzeug=True)