#!/usr/bin/env python3
"""
Interactive Frontend for RAG Document Ingestion
Streamlit-based web interface for document processing
"""

import streamlit as st
import os
import tempfile
from pathlib import Path
from typing import List, Dict, Any
import pandas as pd

# Import the existing ingestion logic
from interactive_ingestion import InteractiveRAGIngestion
from models import (
    create_pdf_source, create_web_source, create_github_source, 
    create_confluence_source, create_github_codebase_source, create_csv_source
)
from websocket_server import get_websocket_server

# Ensure WebSocket server starts when module loads
get_websocket_server()

class IngestionFrontend:
    def __init__(self):
        self.ingestion = None
        self.initialize_session_state()
    
    def initialize_session_state(self):
        """Initialize Streamlit session state"""
        if 'sources' not in st.session_state:
            st.session_state.sources = []
        if 'ingestion_initialized' not in st.session_state:
            st.session_state.ingestion_initialized = False
        if 'processing_status' not in st.session_state:
            st.session_state.processing_status = None
        if 'is_processing' not in st.session_state:
            st.session_state.is_processing = False
        if 'current_step' not in st.session_state:
            st.session_state.current_step = None
        if 'processing_details' not in st.session_state:
            st.session_state.processing_details = []
    
    def initialize_ingestion(self):
        """Initialize the RAG ingestion pipeline"""
        if not st.session_state.ingestion_initialized:
            with st.spinner("Initializing RAG pipeline..."):
                try:
                    # Start WebSocket server
                    get_websocket_server()
                    self.ingestion = InteractiveRAGIngestion()
                    st.session_state.ingestion_initialized = True
                    st.success("✅ RAG pipeline initialized successfully!")
                except Exception as e:
                    st.error(f"❌ Failed to initialize pipeline: {e}")
                    return False
        else:
            self.ingestion = InteractiveRAGIngestion()
        return True
    
    def render_sidebar(self):
        """Render the sidebar with source management"""
        st.sidebar.header("📚 Document Sources")
        
        if st.session_state.sources:
            st.sidebar.subheader(f"Added Sources ({len(st.session_state.sources)})")
            for i, source in enumerate(st.session_state.sources):
                with st.sidebar.expander(f"{source['type'].upper()} - {source['name'][:30]}..."):
                    st.write(f"**Type:** {source['type']}")
                    st.write(f"**Path:** {source['path']}")
                    if st.button(f"Remove", key=f"remove_{i}", disabled=st.session_state.is_processing):
                        st.session_state.sources.pop(i)
                        st.rerun()
        else:
            st.sidebar.info("No sources added yet")
        
        # Clear all sources
        if st.session_state.sources and st.sidebar.button("🗑️ Clear All Sources", disabled=st.session_state.is_processing):
            st.session_state.sources = []
            st.rerun()
    
    def add_web_sources(self):
        """Add web document sources"""
        st.subheader("🌐 Web Documents")
        
        # Text area for multiple URLs
        urls_text = st.text_area(
            "Enter URLs (one per line):",
            height=150,
            placeholder="https://docs.aws.amazon.com/vpc/latest/userguide/\nhttps://docs.aws.amazon.com/ec2/latest/userguide/",
            disabled=st.session_state.is_processing
        )
        
        doc_type = st.text_input("Document type:", value="web_documentation", disabled=st.session_state.is_processing)
        
        if st.button("Add Web Sources", disabled=st.session_state.is_processing):
            if urls_text.strip():
                urls = [url.strip() for url in urls_text.strip().split('\n') if url.strip()]
                valid_urls = [url for url in urls if url.startswith(('http://', 'https://'))]
                
                added_count = 0
                for url in valid_urls:
                    # Create individual source for each URL
                    source = {
                        'type': 'web',
                        'name': f"Web: {url.split('/')[-1] or url.split('//')[-1]}",
                        'path': url,
                        'doc_type': doc_type,
                        'source_obj': create_web_source(url, doc_type)
                    }
                    st.session_state.sources.append(source)
                    added_count += 1
                
                if added_count > 0:
                    st.success(f"✅ Added {added_count} web sources")
                if len(valid_urls) != len(urls):
                    st.warning(f"⚠️ Skipped {len(urls) - len(valid_urls)} invalid URLs")
                st.rerun()
            else:
                st.error("Please enter at least one URL")
    
    def add_github_sources(self):
        """Add GitHub repository sources"""
        st.subheader("🐙 GitHub Repositories")
        
        tab1, tab2 = st.tabs(["Issues/PRs", "Codebase"])
        
        with tab1:
            st.write("**GitHub Issues and Pull Requests**")
            repos_text = st.text_area(
                "Enter repositories (one per line, format: owner/repo):",
                height=100,
                placeholder="aws/aws-cli\nterraform-providers/terraform-provider-aws",
                disabled=st.session_state.is_processing
            )
            
            col1, col2 = st.columns(2)
            with col1:
                include_prs = st.checkbox("Include Pull Requests", value=True, disabled=st.session_state.is_processing)
            with col2:
                include_issues = st.checkbox("Include Issues", value=True, disabled=st.session_state.is_processing)
            
            access_token = st.text_input("GitHub Access Token (optional):", type="password", disabled=st.session_state.is_processing)
            
            if st.button("Add GitHub Issues/PRs", disabled=st.session_state.is_processing):
                if repos_text.strip():
                    repos = [repo.strip() for repo in repos_text.strip().split('\n') if repo.strip()]
                    valid_repos = [repo for repo in repos if '/' in repo and len(repo.split('/')) == 2]
                    
                    added_count = 0
                    for repo in valid_repos:
                        # Create individual source for each repository
                        source = {
                            'type': 'github',
                            'name': f"GitHub Issues: {repo}",
                            'path': repo,
                            'doc_type': 'github_issues',
                            'source_obj': create_github_source(repo, access_token or None, include_prs, include_issues)
                        }
                        st.session_state.sources.append(source)
                        added_count += 1
                    
                    if added_count > 0:
                        st.success(f"✅ Added {added_count} GitHub repositories")
                    if len(valid_repos) != len(repos):
                        st.warning(f"⚠️ Skipped {len(repos) - len(valid_repos)} invalid repository formats")
                    st.rerun()
                else:
                    st.error("Please enter at least one repository")
        
        with tab2:
            st.write("**GitHub Codebase Files**")
            codebase_repos = st.text_area(
                "Enter repositories (one per line, format: owner/repo):",
                height=100,
                placeholder="aws/aws-cli\nterraform-providers/terraform-provider-aws",
                key="codebase_repos",
                disabled=st.session_state.is_processing
            )
            
            col1, col2 = st.columns(2)
            with col1:
                custom_extensions = st.text_input(
                    "File extensions (comma-separated):",
                    placeholder=".py,.js,.ts,.md,.yml",
                    disabled=st.session_state.is_processing
                )
            with col2:
                max_size_mb = st.number_input("Max file size (MB):", min_value=0.1, max_value=10.0, value=1.0, disabled=st.session_state.is_processing)
            
            codebase_token = st.text_input("GitHub Access Token (optional):", type="password", key="codebase_token", disabled=st.session_state.is_processing)
            
            if st.button("Add GitHub Codebase", disabled=st.session_state.is_processing):
                if codebase_repos.strip():
                    repos = [repo.strip() for repo in codebase_repos.strip().split('\n') if repo.strip()]
                    valid_repos = [repo for repo in repos if '/' in repo and len(repo.split('/')) == 2]
                    
                    file_extensions = None
                    if custom_extensions.strip():
                        file_extensions = [ext.strip() for ext in custom_extensions.split(',')]
                    else:
                        file_extensions = []  # Empty list means all files
                    
                    max_file_size = int(max_size_mb * 1024 * 1024)
                    
                    added_count = 0
                    for repo in valid_repos:
                        # Create individual source for each repository
                        source = {
                            'type': 'github_codebase',
                            'name': f"GitHub Code: {repo}",
                            'path': repo,
                            'doc_type': 'github_codebase',
                            'source_obj': create_github_codebase_source(
                                repo, codebase_token or None, file_extensions, max_file_size
                            )
                        }
                        st.session_state.sources.append(source)
                        added_count += 1
                    
                    if added_count > 0:
                        st.success(f"✅ Added {added_count} GitHub codebases")
                    if len(valid_repos) != len(repos):
                        st.warning(f"⚠️ Skipped {len(repos) - len(valid_repos)} invalid repository formats")
                    st.rerun()
                else:
                    st.error("Please enter at least one repository")
    
    def add_file_uploads(self):
        """Add file upload sources"""
        st.subheader("📁 File Uploads")
        
        tab1, tab2 = st.tabs(["PDF Files", "CSV Files"])
        
        with tab1:
            st.write("**PDF Files**")
            
            pdf_upload_method = st.radio(
                "Choose upload method:",
                ["Upload File (< 200MB)", "File Path (Large Files)"],
                disabled=st.session_state.is_processing,
                key="pdf_method"
            )
            
            pdf_doc_type = st.text_input("PDF document type:", value="pdf_document", disabled=st.session_state.is_processing)
            
            if pdf_upload_method == "Upload File (< 200MB)":
                pdf_files = st.file_uploader(
                    "Choose PDF files:",
                    type=['pdf'],
                    accept_multiple_files=True,
                    disabled=st.session_state.is_processing,
                    key="pdf_uploader",
                    help="Drag and drop works, or click Browse files"
                )
                
                if pdf_files and st.button("Add PDF Files", disabled=st.session_state.is_processing):
                    for pdf_file in pdf_files:
                        with tempfile.NamedTemporaryFile(delete=False, suffix='.pdf') as tmp_file:
                            tmp_file.write(pdf_file.read())
                            tmp_path = tmp_file.name
                        
                        source = {
                            'type': 'pdf',
                            'name': pdf_file.name,
                            'path': tmp_path,
                            'doc_type': pdf_doc_type,
                            'source_obj': create_pdf_source(tmp_path, pdf_doc_type)
                        }
                        st.session_state.sources.append(source)
                    
                    st.success(f"✅ Added {len(pdf_files)} PDF files")
                    st.rerun()
            
            else:  # File Path method
                st.info("💡 For large files, copy your PDF to the container's data directory first")
                pdf_path = st.text_input(
                    "Enter PDF file path (e.g., /workspace/data/large_file.pdf):",
                    disabled=st.session_state.is_processing
                )
                
                if pdf_path and st.button("Add PDF from Path", disabled=st.session_state.is_processing):
                    if Path(pdf_path).exists():
                        source = {
                            'type': 'pdf',
                            'name': Path(pdf_path).name,
                            'path': pdf_path,
                            'doc_type': pdf_doc_type,
                            'source_obj': create_pdf_source(pdf_path, pdf_doc_type)
                        }
                        st.session_state.sources.append(source)
                        st.success(f"✅ Added PDF file: {Path(pdf_path).name}")
                        st.rerun()
                    else:
                        st.error(f"❌ File not found: {pdf_path}")
        
        with tab2:
            st.write("**CSV Files**")
            
            upload_method = st.radio(
                "Choose upload method:",
                ["Upload File (< 200MB)", "File Path (Large Files)"],
                disabled=st.session_state.is_processing
            )
            
            csv_doc_type = st.text_input("CSV document type:", value="csv_document", disabled=st.session_state.is_processing)
            
            if upload_method == "Upload File (< 200MB)":
                csv_files = st.file_uploader(
                    "Choose CSV files:",
                    type=['csv'],
                    accept_multiple_files=True,
                    disabled=st.session_state.is_processing,
                    key="csv_uploader",
                    help="Drag and drop works, or click Browse files"
                )
                
                if csv_files and st.button("Add CSV Files", disabled=st.session_state.is_processing):
                    for csv_file in csv_files:
                        with tempfile.NamedTemporaryFile(delete=False, suffix='.csv') as tmp_file:
                            tmp_file.write(csv_file.read())
                            tmp_path = tmp_file.name
                        
                        source = {
                            'type': 'csv',
                            'name': csv_file.name,
                            'path': tmp_path,
                            'doc_type': csv_doc_type,
                            'source_obj': create_csv_source(tmp_path, csv_doc_type)
                        }
                        st.session_state.sources.append(source)
                    
                    st.success(f"✅ Added {len(csv_files)} CSV files")
                    st.rerun()
            
            else:  # File Path method
                st.info("💡 For large files, copy your CSV to the container's data directory first")
                csv_path = st.text_input(
                    "Enter CSV file path (e.g., /workspace/data/large_file.csv):",
                    disabled=st.session_state.is_processing
                )
                
                if csv_path and st.button("Add CSV from Path", disabled=st.session_state.is_processing):
                    if Path(csv_path).exists():
                        source = {
                            'type': 'csv',
                            'name': Path(csv_path).name,
                            'path': csv_path,
                            'doc_type': csv_doc_type,
                            'source_obj': create_csv_source(csv_path, csv_doc_type)
                        }
                        st.session_state.sources.append(source)
                        st.success(f"✅ Added CSV file: {Path(csv_path).name}")
                        st.rerun()
                    else:
                        st.error(f"❌ File not found: {csv_path}")
    
    def add_confluence_source(self):
        """Add Confluence sources"""
        st.subheader("📋 Confluence")
        
        confluence_url = st.text_input("Confluence URL:", disabled=st.session_state.is_processing)
        
        col1, col2 = st.columns(2)
        with col1:
            username = st.text_input("Username:", disabled=st.session_state.is_processing)
        with col2:
            api_key = st.text_input("API Key:", type="password", disabled=st.session_state.is_processing)
        
        col3, col4 = st.columns(2)
        with col3:
            page_ids = st.text_input("Page IDs (comma-separated, optional):", disabled=st.session_state.is_processing)
        with col4:
            space_key = st.text_input("Space Key (optional):", disabled=st.session_state.is_processing)
        
        if st.button("Add Confluence Source", disabled=st.session_state.is_processing):
            if confluence_url and username and api_key:
                page_ids_list = [pid.strip() for pid in page_ids.split(',') if pid.strip()] if page_ids else None
                
                source = {
                    'type': 'confluence',
                    'name': confluence_url.split('/')[-1] or 'Confluence',
                    'path': confluence_url,
                    'doc_type': 'confluence',
                    'source_obj': create_confluence_source(
                        confluence_url, username, api_key, page_ids_list, space_key or None
                    )
                }
                st.session_state.sources.append(source)
                st.success("✅ Added Confluence source")
                st.rerun()
            else:
                st.error("Please fill in URL, username, and API key")
    
    def process_documents(self):
        """Process all added documents with WebSocket updates"""
        st.subheader("🔄 Process Documents")
        
        if not st.session_state.sources:
            st.warning("No sources added. Please add some documents first.")
            return
        
        st.write(f"**Ready to process {len(st.session_state.sources)} sources:**")
        for source in st.session_state.sources:
            st.write(f"- {source['type'].upper()}: {source['name']}")
        
        # WebSocket connection info
        st.info("🔌 Real-time updates via Socket.IO on http://localhost:8503")
        
        # WebSocket client HTML/JS
        websocket_html = """
        <div id="websocket-status" style="padding: 10px; margin: 10px 0; border-radius: 5px; background: #f0f0f0;">
            <strong>WebSocket Status:</strong> <span id="ws-status">Connecting...</span>
        </div>
        <div id="processing-updates" style="height: 300px; overflow-y: auto; border: 1px solid #ddd; padding: 10px; background: #f9f9f9; font-family: monospace; font-size: 12px;">
            <div>Waiting for processing updates...</div>
        </div>
        
        <script src="https://cdn.socket.io/4.7.0/socket.io.min.js"></script>
        <script>
        const socket = io('http://localhost:8503');
        const statusEl = document.getElementById('ws-status');
        const updatesEl = document.getElementById('processing-updates');
        
        socket.on('connect', function() {
            statusEl.textContent = 'Connected';
            statusEl.style.color = 'green';
        });
        
        socket.on('disconnect', function() {
            statusEl.textContent = 'Disconnected';
            statusEl.style.color = 'red';
        });
        
        socket.on('connect_error', function() {
            statusEl.textContent = 'Error';
            statusEl.style.color = 'red';
        });
        
        socket.on('processing_update', function(data) {
            const timestamp = new Date().toLocaleTimeString();
            const updateDiv = document.createElement('div');
            updateDiv.style.marginBottom = '5px';
            
            let icon = '📝';
            if (data.type === 'log') icon = '📄';
            else if (data.type === 'progress') icon = '🔄';
            else if (data.type === 'complete') icon = '✅';
            else if (data.type === 'error') icon = '❌';
            
            updateDiv.innerHTML = `<span style="color: #666;">[${timestamp}]</span> ${icon} ${data.message}`;
            updatesEl.appendChild(updateDiv);
            updatesEl.scrollTop = updatesEl.scrollHeight;
        });
        </script>
        """
        
        st.components.v1.html(websocket_html, height=400)
        
        if st.button("🚀 Start Processing", type="primary"):
            if not self.initialize_ingestion():
                return
            
            # Add sources to ingestion pipeline
            self.ingestion.document_sources = [source['source_obj'] for source in st.session_state.sources]
            
            # Simple progress indicators
            progress_bar = st.progress(0)
            status_text = st.empty()
            
            try:
                status_text.text("🔧 Initializing pipeline...")
                progress_bar.progress(10)
                
                # Start processing (WebSocket will handle real-time updates)
                self.ingestion.process_documents()
                
                progress_bar.progress(100)
                status_text.text("🎉 Processing completed!")
                
                # Display final stats
                if hasattr(self.ingestion, 'processing_stats'):
                    stats = self.ingestion.processing_stats
                    col1, col2, col3 = st.columns(3)
                    with col1:
                        st.metric("Documents Loaded", stats.documents_loaded)
                    with col2:
                        st.metric("Chunks Created", stats.chunks_created)
                    with col3:
                        st.metric("Embeddings Created", stats.embeddings_created)
                
                st.success("✅ All documents processed successfully!")
                
                # Option to clear sources
                if st.button("🗑️ Clear Processed Sources"):
                    st.session_state.sources = []
                    st.rerun()
                
            except Exception as e:
                st.error(f"❌ Processing failed: {str(e)}")
                progress_bar.progress(0)
                status_text.text("Processing failed!")
    

    
    def render_main_interface(self):
        """Render the main interface"""
        st.title("🤖 RAG Document Ingestion")
        st.markdown("Upload and process documents for your AI assistant")
        
        # Initialize ingestion pipeline
        if not st.session_state.ingestion_initialized:
            if st.button("🔧 Initialize Pipeline", disabled=st.session_state.is_processing):
                self.initialize_ingestion()
        
        if st.session_state.ingestion_initialized:
            # Main tabs
            tab1, tab2, tab3, tab4, tab5 = st.tabs([
                "🌐 Web", "🐙 GitHub", "📁 Files", "📋 Confluence", "🔄 Process"
            ])
            
            with tab1:
                self.add_web_sources()
            
            with tab2:
                self.add_github_sources()
            
            with tab3:
                self.add_file_uploads()
            
            with tab4:
                self.add_confluence_source()
            
            with tab5:
                self.process_documents()
    
    def run(self):
        """Run the Streamlit app"""
        st.set_page_config(
            page_title="RAG Document Ingestion",
            page_icon="🤖",
            layout="wide"
        )
        
        self.render_sidebar()
        self.render_main_interface()

def main():
    app = IngestionFrontend()
    app.run()

if __name__ == "__main__":
    main()