#!/usr/bin/env python3
"""
Interactive RAG Document Ingestion Pipeline
Clean implementation based on complete_working_rag.py
"""

import os
import httpx
import openai
import uuid
import requests
import time
from pathlib import Path
from typing import List, Dict, Any, Optional
from datetime import datetime

# Local imports
from models import (
    DocumentSource, ProcessingStats, IngestionConfig,
    AWS_DOCUMENTATION_SOURCES, TERRAFORM_DOCUMENTATION_SOURCES,
    create_pdf_source, create_web_source, create_github_source, create_confluence_source,
    create_github_codebase_source, create_csv_source
)
from config import get_config
from websocket_server import send_processing_update

class WorkingOpenAIEmbeddings:
    """Custom OpenAI embeddings wrapper that bypasses LangChain's client issues"""
    
    def __init__(self, model: str = "text-embedding-ada-002"):
        self.model = model
        config = get_config()
        
        # Create explicit httpx client to avoid proxies issue
        http_client = httpx.Client()
        
        # Create OpenAI client with explicit http_client
        self.client = openai.OpenAI(
            api_key=config.openai.api_key,
            http_client=http_client
        )
    
    def embed_query(self, text: str) -> List[float]:
        """Embed a single query text"""
        response = self.client.embeddings.create(
            model=self.model,
            input=text
        )
        return response.data[0].embedding
    
    def embed_documents(self, texts: List[str]) -> List[List[float]]:
        """Embed multiple documents"""
        embeddings = []
        for text in texts:
            embedding = self.embed_query(text)
            embeddings.append(embedding)
        return embeddings

class WorkingOpenAIChat:
    """Custom OpenAI chat wrapper that bypasses LangChain's client issues"""
    
    def __init__(self, model: str = "gpt-4.1-nano", temperature: float = 0):
        self.model = model
        self.temperature = temperature
        config = get_config()
        
        # Create explicit httpx client to avoid proxies issue
        http_client = httpx.Client()
        
        # Create OpenAI client with explicit http_client
        self.client = openai.OpenAI(
            api_key=config.openai.api_key,
            http_client=http_client
        )
    
    def invoke(self, prompt: str) -> str:
        """Generate response for a prompt"""
        response = self.client.chat.completions.create(
            model=self.model,
            messages=[{"role": "user", "content": prompt}],
            temperature=self.temperature
        )
        return response.choices[0].message.content

class InteractiveRAGIngestion:
    """Interactive RAG document ingestion system."""
    
    def __init__(self):
        self.config = get_config()
        self.document_sources: List[DocumentSource] = []
        self.processing_stats = ProcessingStats()
        self.ingestion_config = IngestionConfig()
        
        # Working components
        self.embeddings = None
        self.llm = None
        self.index = None
        
        print("\n" + "=" * 60)
        print("🤖 GenAI DevOps Assistant - RAG Ingestion Pipeline")
        print("📚 Working OpenAI + Pinecone Document Processing")
        print("=" * 60)
        print(f"Environment: {self.config.environment.value}")
        print(f"OpenAI Model: {self.config.openai.embedding_model}")
        print(f"Pinecone Index: {self.config.pinecone.index_name}")
        print("=" * 60)
        
        # Initialize RAG pipeline
        self.initialize_pipeline()
    
    def initialize_pipeline(self):
        """Initialize the RAG pipeline."""
        try:
            print("\n🔧 Initializing RAG pipeline...")
            
            # Initialize working OpenAI components
            self.embeddings = WorkingOpenAIEmbeddings()
            self.llm = WorkingOpenAIChat()
            
            # Test embeddings
            test_embedding = self.embeddings.embed_query("test")
            print(f"✅ OpenAI embeddings working (dimension: {len(test_embedding)})")
            
            # Test LLM
            test_response = self.llm.invoke("Say 'Hello'")
            print(f"✅ OpenAI chat working (response: {test_response})")
            
            # Initialize Pinecone
            from pinecone import Pinecone, ServerlessSpec
            pc = Pinecone(api_key=self.config.pinecone.api_key)
            
            # Get or create index
            index_name = self.config.pinecone.index_name
            existing_indexes = [index.name for index in pc.list_indexes()]
            
            if index_name not in existing_indexes:
                print(f"Creating Pinecone index: {index_name}")
                pc.create_index(
                    name=index_name,
                    dimension=1536,
                    metric='cosine',
                    spec=ServerlessSpec(cloud='aws', region='us-east-1')
                )
                import time
                time.sleep(10)
            
            self.index = pc.Index(index_name)
            print("✅ Pinecone index ready")
            
            print("✅ Pipeline initialized successfully!")
            self.display_index_stats()
                
        except Exception as e:
            print(f"❌ Error initializing pipeline: {e}")
            import traceback
            traceback.print_exc()
            print("❌ Failed to initialize. Please check your configuration.")
            exit(1)
    
    def process_documents(self, session_id: str = "default"):
        """Process all added document sources."""
        if not self.document_sources:
            msg = "No document sources added. Please add sources first."
            print(f"\n❌ {msg}")
            send_processing_update(session_id, "error", msg)
            return
        
        start_time = time.time()  # Track processing start time
        msg = f"Processing {len(self.document_sources)} document sources..."
        print(f"\n🔄 {msg}")
        send_processing_update(session_id, "start", msg, {"total_sources": len(self.document_sources)})
        
        try:
            from langchain.text_splitter import RecursiveCharacterTextSplitter
            from langchain.schema import Document
            
            # Optimize chunk size based on source type
            if any(s.source_type == 'csv' for s in self.document_sources):
                chunk_size = 1500
                chunk_overlap = 50
            elif any(s.source_type == 'github_codebase' for s in self.document_sources):
                chunk_size = 800
                chunk_overlap = 100
            else:
                chunk_size = self.ingestion_config.chunk_size
                chunk_overlap = self.ingestion_config.chunk_overlap
            
            text_splitter = RecursiveCharacterTextSplitter(
                chunk_size=chunk_size,
                chunk_overlap=chunk_overlap
            )
            
            all_documents = []
            sources_to_remove = []
            
            # Load documents from all sources
            for i, source in enumerate(self.document_sources):
                try:
                    msg = f"Processing: {source.source_type} - {source.source_path}"
                    print(f"\n📄 {msg}")
                    send_processing_update(session_id, "source_processing", msg, {
                        "source_index": i + 1,
                        "total_sources": len(self.document_sources),
                        "source_type": source.source_type,
                        "source_path": source.source_path
                    })
                    
                    docs = self._load_documents_from_source(source)
                    if docs:
                        all_documents.extend(docs)
                        sources_to_remove.append(source)
                        msg = f"Loaded {len(docs)} documents"
                        print(f"✅ {msg}")
                        send_processing_update(session_id, "source_complete", msg, {"documents_loaded": len(docs)})
                    else:
                        msg = "No documents loaded from this source"
                        print(f"⚠️ {msg}")
                        send_processing_update(session_id, "warning", msg)
                except Exception as e:
                    msg = f"Error loading from {source.source_path}: {e}"
                    print(f"❌ {msg}")
                    send_processing_update(session_id, "error", msg)
                    continue
            
            if not all_documents:
                msg = "No documents loaded from any source"
                print(f"\n❌ {msg}")
                send_processing_update(session_id, "error", msg)
                return
            
            msg = f"Splitting {len(all_documents)} documents into chunks..."
            print(f"\n📝 {msg}")
            send_processing_update(session_id, "chunking", msg, {"total_documents": len(all_documents)})
            
            texts = text_splitter.split_documents(all_documents)
            msg = f"Created {len(texts)} text chunks"
            print(f"✅ {msg}")
            send_processing_update(session_id, "chunking_complete", msg, {"total_chunks": len(texts)})
            
            msg = "Creating embeddings and storing in Pinecone..."
            print(f"\n🔗 {msg}")
            send_processing_update(session_id, "embedding_start", msg)
            
            text_contents = [doc.page_content for doc in texts]
            
            msg = f"Creating embeddings for {len(text_contents)} chunks..."
            print(f"  {msg}")
            send_processing_update(session_id, "embedding_progress", msg, {"total_chunks": len(text_contents)})
            
            embeddings = self.embeddings.embed_documents(text_contents)
            
            vectors_to_upsert = []
            for i, (doc, embedding) in enumerate(zip(texts, embeddings)):
                try:
                    filtered_metadata = self._filter_metadata(doc.metadata)
                    filtered_metadata['text'] = doc.page_content
                    
                    vectors_to_upsert.append({
                        'id': f'doc_{i}_{uuid.uuid4().hex[:8]}',
                        'values': embedding,
                        'metadata': filtered_metadata
                    })
                    
                    if (i + 1) % 100 == 0:
                        msg = f"Processed {i + 1}/{len(texts)} chunks"
                        print(f"  {msg}")
                        send_processing_update(session_id, "embedding_progress", msg, {
                            "processed": i + 1,
                            "total": len(texts)
                        })
                        
                except Exception as e:
                    print(f"❌ Error processing chunk {i}: {e}")
                    continue
            
            if vectors_to_upsert:
                batch_size = self.ingestion_config.batch_size
                total_batches = (len(vectors_to_upsert) + batch_size - 1) // batch_size
                
                for i in range(0, len(vectors_to_upsert), batch_size):
                    batch = vectors_to_upsert[i:i + batch_size]
                    self.index.upsert(vectors=batch)
                    batch_num = i // batch_size + 1
                    msg = f"Uploaded batch {batch_num}/{total_batches}"
                    print(f"  {msg}")
                    send_processing_update(session_id, "upload_progress", msg, {
                        "batch": batch_num,
                        "total_batches": total_batches
                    })
                
                msg = f"Successfully processed and stored {len(vectors_to_upsert)} document chunks!"
                print(f"\n✅ {msg}")
                
                self.processing_stats.documents_loaded = len(all_documents)
                self.processing_stats.chunks_created = len(texts)
                self.processing_stats.embeddings_created = len(vectors_to_upsert)
                
                send_processing_update(session_id, "complete", msg, {
                    "status": "success",
                    "stats": {
                        "total_sources": len(sources_to_remove),
                        "documents_loaded": self.processing_stats.documents_loaded,
                        "chunks_created": self.processing_stats.chunks_created,
                        "embeddings_created": self.processing_stats.embeddings_created,
                        "processing_time": time.time() - start_time if 'start_time' in locals() else 0
                    }
                })
                
                # Remove successfully processed sources
                for source in sources_to_remove:
                    if source in self.document_sources:
                        self.document_sources.remove(source)
                if sources_to_remove:
                    print(f"✅ Removed {len(sources_to_remove)} successfully processed sources")
                
                self.display_processing_stats()
                self.display_index_stats()
            else:
                msg = "No valid chunks created for storage"
                print(f"\n❌ {msg}")
                send_processing_update(session_id, "error", msg)
                
        except Exception as e:
            msg = f"Error during processing: {e}"
            print(f"\n❌ {msg}")
            send_processing_update(session_id, "error", msg)
            import traceback
            traceback.print_exc()
    
    def _filter_metadata(self, metadata: Dict[str, Any]) -> Dict[str, Any]:
        """Filter metadata to keep only serializable values"""
        filtered = {}
        for key, value in metadata.items():
            if isinstance(value, (str, int, float, bool, type(None))):
                filtered[key] = value
            elif isinstance(value, (list, dict)):
                try:
                    import json
                    json.dumps(value)
                    filtered[key] = value
                except (TypeError, ValueError):
                    continue
            else:
                filtered[key] = str(value)
        return filtered
    
    def _load_documents_from_source(self, source: DocumentSource) -> List:
        """Load documents from a source"""
        try:
            if source.source_type == 'pdf':
                return self._load_pdf_documents(source)
            elif source.source_type == 'web':
                return self._load_web_documents(source)
            elif source.source_type == 'github':
                return self._load_github_documents(source)
            elif source.source_type == 'github_codebase':
                return self._load_github_codebase_documents(source)
            elif source.source_type == 'confluence':
                return self._load_confluence_documents(source)
            elif source.source_type == 'csv':
                return self._load_csv_documents(source)
            else:
                print(f"❌ Unsupported source type: {source.source_type}")
                return []
        except Exception as e:
            print(f"❌ Error loading from {source.source_type}: {e}")
            return []
    
    def _load_pdf_documents(self, source: DocumentSource) -> List:
        """Load PDF documents"""
        from langchain_community.document_loaders import PyPDFLoader
        loader = PyPDFLoader(source.source_path)
        return loader.load()
    
    def _load_web_documents(self, source: DocumentSource) -> List:
        """Load web documents with JavaScript support"""
        try:
            # Try enhanced Selenium loader first for JavaScript-heavy sites
            from selenium_web_loader import EnhancedSeleniumWebLoader, CompatibleSeleniumLoader
            
            metadata = source.metadata or {}
            use_selenium = metadata.get('use_selenium', True)
            wait_for_element = metadata.get('wait_for_element')
            wait_for_text = metadata.get('wait_for_text')
            additional_wait = metadata.get('additional_wait', 3)
            browser = metadata.get('browser', 'chrome')
            
            if use_selenium:
                print(f"  Using Selenium loader for JavaScript-heavy content...")
                
                # Use the compatible wrapper for single URLs
                if isinstance(source.source_path, str):
                    urls = [source.source_path]
                else:
                    urls = source.source_path
                
                # Try enhanced loader first
                try:
                    loader = EnhancedSeleniumWebLoader(
                        browser=browser,
                        headless=True,
                        wait_time=15
                    )
                    
                    if len(urls) == 1:
                        doc = loader.load_url_with_js_wait(
                            url=urls[0],
                            wait_for_element=wait_for_element,
                            wait_for_text=wait_for_text,
                            additional_wait=additional_wait
                        )
                        return [doc] if doc.page_content else []
                    else:
                        return loader.load_urls(urls)
                        
                except Exception as selenium_error:
                    print(f"  Enhanced Selenium loader failed: {selenium_error}")
                    print(f"  Trying compatible Selenium loader...")
                    
                    # Fallback to compatible loader
                    try:
                        compatible_loader = CompatibleSeleniumLoader(
                            urls=urls,
                            browser=browser,
                            headless=True,
                            wait_time=15
                        )
                        return compatible_loader.load()
                    except Exception as compatible_error:
                        print(f"  Compatible Selenium loader failed: {compatible_error}")
                        print(f"  Falling back to basic WebBaseLoader...")
            
            # Fallback to basic web loader
            from langchain_community.document_loaders import WebBaseLoader
            print(f"  Using basic WebBaseLoader...")
            loader = WebBaseLoader(source.source_path)
            return loader.load()
            
        except Exception as e:
            print(f"  Error in web document loading: {e}")
            # Final fallback
            try:
                from langchain_community.document_loaders import WebBaseLoader
                loader = WebBaseLoader(source.source_path)
                return loader.load()
            except Exception as final_error:
                print(f"  Final fallback failed: {final_error}")
                return []
    
    def _load_github_documents(self, source: DocumentSource) -> List:
        """Load GitHub issues and PRs"""
        from langchain_community.document_loaders import GitHubIssuesLoader
        metadata = source.metadata or {}
        loader = GitHubIssuesLoader(
            repo=source.source_path,
            access_token=metadata.get('access_token'),
            include_prs=metadata.get('include_prs', True)
        )
        return loader.load()
    
    def _load_github_codebase_documents(self, source: DocumentSource) -> List:
        """Load GitHub codebase files using GithubFileLoader"""
        from langchain_community.document_loaders import GithubFileLoader
        
        metadata = source.metadata or {}
        access_token = metadata.get('access_token')
        file_extensions = metadata.get('file_extensions', ['.py', '.js', '.ts', '.md', '.tf', '.yml', '.yaml'])
        
        # Try main branch first
        try:
            loader = GithubFileLoader(
                repo=source.source_path,
                branch="main",
                access_token=access_token,
                github_api_url="https://api.github.com",
                file_filter=lambda file_path: any(file_path.endswith(ext) for ext in file_extensions)
            )
            documents = loader.load()
            print(f"✅ Loaded {len(documents)} files from GitHub repository (main branch)")
            return documents
        except Exception:
            # Try master branch if main fails
            try:
                loader = GithubFileLoader(
                    repo=source.source_path,
                    branch="master",
                    access_token=access_token,
                    github_api_url="https://api.github.com",
                    file_filter=lambda file_path: any(file_path.endswith(ext) for ext in file_extensions)
                )
                documents = loader.load()
                print(f"✅ Loaded {len(documents)} files from GitHub repository (master branch)")
                return documents
            except Exception as e:
                print(f"❌ Error loading GitHub repository: {e}")
                raise e
    

    
    def _load_confluence_documents(self, source: DocumentSource) -> List:
        """Load Confluence documents"""
        from langchain_community.document_loaders import ConfluenceLoader
        metadata = source.metadata or {}
        
        loader = ConfluenceLoader(
            url=source.source_path,
            username=metadata.get('username'),
            api_key=metadata.get('api_key'),
            page_ids=metadata.get('page_ids'),
            space_key=metadata.get('space_key')
        )
        return loader.load()
    
    def _load_csv_documents(self, source: DocumentSource) -> List:
        """Load large CSV documents in chunks"""
        import pandas as pd
        from langchain.schema import Document
        
        documents = []
        chunk_size = 1000  # Process 1000 rows at a time
        
        try:
            # Read CSV in chunks to handle large files
            for chunk_num, chunk_df in enumerate(pd.read_csv(source.source_path, chunksize=chunk_size)):
                # Convert chunk to string representation
                chunk_content = chunk_df.to_string(index=False)
                
                doc = Document(
                    page_content=chunk_content,
                    metadata={
                        'source_type': 'csv',
                        'source_path': source.source_path,
                        'chunk_number': chunk_num,
                        'rows_count': len(chunk_df),
                        'columns': list(chunk_df.columns)
                    }
                )
                documents.append(doc)
                
                # Progress feedback
                if (chunk_num + 1) % 10 == 0:
                    print(f"  Processed {(chunk_num + 1) * chunk_size} rows...")
                    
        except Exception as e:
            print(f"Error processing CSV: {e}")
            # Fallback to original loader for smaller files
            from langchain_community.document_loaders import CSVLoader
            loader = CSVLoader(file_path=source.source_path)
            return loader.load()
        
        print(f"✅ Processed {len(documents)} chunks from CSV file")
        return documents
    
    def test_search(self):
        """Test search functionality."""
        query = input("\nEnter search query: ").strip()
        if not query:
            print("❌ No query provided")
            return
        
        try:
            print(f"\n🔍 Searching for: '{query}'")
            
            # Get query embedding
            query_embedding = self.embeddings.embed_query(query)
            
            # Search in Pinecone
            search_results = self.index.query(
                vector=query_embedding,
                top_k=5,
                include_metadata=True
            )
            
            if search_results.matches:
                print(f"\n📋 Found {len(search_results.matches)} results:")
                for i, match in enumerate(search_results.matches, 1):
                    print(f"\n{i}. Score: {match.score:.4f}")
                    print(f"   Source: {match.metadata.get('source_path', 'Unknown')}")
                    print(f"   Content: {match.metadata.get('text', '')[:200]}...")
                
                # Test RAG response
                print(f"\n🤖 Generating RAG response...")
                context = "\n\n".join([match.metadata.get('text', '') for match in search_results.matches[:3]])
                
                prompt = f"""Use the following context to answer the question. If you don't know the answer based on the context, say you don't know.

Context:
{context}

Question: {query}
Answer:"""
                
                response = self.llm.invoke(prompt)
                print(f"\n💬 RAG Response: {response}")
            else:
                print("\n❌ No results found")
                
        except Exception as e:
            print(f"\n❌ Search error: {e}")
            import traceback
            traceback.print_exc()
    
    def display_index_stats(self):
        """Display current index statistics."""
        try:
            if self.index:
                stats = self.index.describe_index_stats()
                print(f"\n📊 Current index stats:")
                print(f"   Total vectors: {stats.get('total_vector_count', 0)}")
                print(f"   Dimension: {stats.get('dimension', 1536)}")
                print(f"   Index fullness: {stats.get('index_fullness', 0):.2%}")
                if stats.get('namespaces'):
                    print(f"   Namespaces: {list(stats['namespaces'].keys())}")
            else:
                print("\n❌ Index not initialized")
        except Exception as e:
            print(f"\n❌ Error getting index stats: {e}")
    
    def display_processing_stats(self):
        """Display processing statistics."""
        print(f"\n📊 Processing Statistics:")
        print(f"   Documents loaded: {self.processing_stats.documents_loaded}")
        print(f"   Chunks created: {self.processing_stats.chunks_created}")
        print(f"   Embeddings created: {self.processing_stats.embeddings_created}")
        print(f"   Processing time: {self.processing_stats.processing_time:.2f} seconds")
        print(f"   Errors: {len(self.processing_stats.errors)}")
    
    # Menu methods
    def add_pdf_source(self):
        """Add PDF document source."""
        print("\n📄 Adding PDF Document")
        pdf_path = input("Enter PDF file path: ").strip()
        if not pdf_path or not Path(pdf_path).exists():
            print("❌ Invalid file path")
            return
        
        doc_type = input("Document type (default: pdf_document): ").strip() or "pdf_document"
        source = create_pdf_source(pdf_path, doc_type)
        self.document_sources.append(source)
        print(f"✅ Added PDF source: {pdf_path}")
    
    def add_web_sources(self):
        """Add web document sources."""
        print("\n🌐 Adding Web Documents")
        print("Enter URLs (one per line, empty line to finish):")
        urls = []
        
        while True:
            url = input("> ").strip()
            if not url:
                break
            if url.startswith('http'):
                urls.append(url)
                print(f"  ✅ Added: {url}")
            else:
                print(f"  ❌ Invalid URL: {url}")
        
        if not urls:
            print("❌ No valid URLs provided")
            return
        
        for url in urls:
            source = create_web_source(url, 'web_documentation')
            self.document_sources.append(source)
        
        print(f"✅ Added {len(urls)} web sources")
    
    def add_confluence_source(self):
        """Add Confluence document source."""
        print("\n📋 Adding Confluence Source")
        confluence_url = input("Confluence URL: ").strip()
        username = input("Username: ").strip()
        api_key = input("API Key: ").strip()
        
        if not all([confluence_url, username, api_key]):
            print("❌ Missing required credentials")
            return
        
        page_ids_input = input("Page IDs (comma-separated, optional): ").strip()
        space_key = input("Space key (optional): ").strip()
        
        page_ids = [pid.strip() for pid in page_ids_input.split(',') if pid.strip()] if page_ids_input else None
        
        source = create_confluence_source(
            confluence_url, username, api_key, page_ids, space_key if space_key else None
        )
        
        self.document_sources.append(source)
        print(f"✅ Added Confluence source: {confluence_url}")
    
    def add_github_source(self):
        """Add GitHub repository source for issues/PRs."""
        print("\n🐙 Adding GitHub Repository (Issues/PRs)")
        repo = input("Repository (e.g., 'owner/repo'): ").strip()
        access_token = input("GitHub access token (optional): ").strip()
        
        if not repo:
            print("❌ Repository name is required")
            return
        
        include_prs = input("Include Pull Requests? (y/n): ").strip().lower() == 'y'
        include_issues = input("Include Issues? (y/n): ").strip().lower() == 'y'
        
        source = create_github_source(
            repo, access_token if access_token else None, include_prs, include_issues
        )
        
        self.document_sources.append(source)
        print(f"✅ Added GitHub source: {repo}")
    
    def add_github_codebase_source(self):
        """Add GitHub codebase source."""
        print("\n💻 Adding GitHub Codebase")
        repo = input("Repository (e.g., 'owner/repo'): ").strip()
        access_token = input("GitHub access token (optional): ").strip()
        
        if not repo:
            print("❌ Repository name is required")
            return
        
        print("\nFile extension filtering:")
        print("Default: .py, .js, .ts, .java, .cpp, .c, .h, .hpp, .go, .rs, .php, .rb, .swift, .kt, .scala, .md, .rst, .txt, .yml, .yaml, .json, .xml")
        custom_extensions = input("Custom extensions (comma-separated, or press Enter for default): ").strip()
        
        file_extensions = None
        if custom_extensions:
            file_extensions = [ext.strip() for ext in custom_extensions.split(',')]
        
        try:
            max_size_mb = float(input("Max file size in MB (default 1): ") or "1")
            max_file_size = int(max_size_mb * 1024 * 1024)
        except ValueError:
            max_file_size = 1024 * 1024
        
        source = create_github_codebase_source(
            repo=repo,
            access_token=access_token if access_token else None,
            file_extensions=file_extensions,
            max_file_size=max_file_size
        )
        
        self.document_sources.append(source)
        print(f"✅ Added GitHub codebase source: {repo}")
    
    def add_predefined_aws_sources(self):
        """Add predefined AWS documentation sources."""
        print("\n🌐 Adding AWS Documentation Sources")
        self.document_sources.extend(AWS_DOCUMENTATION_SOURCES)
        print(f"✅ Added {len(AWS_DOCUMENTATION_SOURCES)} AWS documentation sources")
    
    def add_terraform_sources(self):
        """Add Terraform documentation sources."""
        print("\n🏗️ Adding Terraform Documentation Sources")
        self.document_sources.extend(TERRAFORM_DOCUMENTATION_SOURCES)
        print(f"✅ Added {len(TERRAFORM_DOCUMENTATION_SOURCES)} Terraform documentation sources")
    
    def add_csv_source(self):
        """Add CSV document source."""
        print("\n📊 Adding CSV Document")
        csv_path = input("Enter CSV file path: ").strip()
        if not csv_path or not Path(csv_path).exists():
            print("❌ Invalid file path")
            return
        
        doc_type = input("Document type (default: csv_document): ").strip() or "csv_document"
        source = create_csv_source(csv_path, doc_type)
        self.document_sources.append(source)
        print(f"✅ Added CSV source: {csv_path}")
    
    def display_sources(self):
        """Display current document sources."""
        if not self.document_sources:
            print("\n📝 No document sources added yet")
            return
        
        print(f"\n📝 Current Document Sources ({len(self.document_sources)}):")
        for i, source in enumerate(self.document_sources, 1):
            doc_type = source.metadata.get('doc_type', 'unknown')
            print(f"{i:2d}. [{source.source_type.upper()}] {source.source_path}")
            print(f"     Type: {doc_type}")
    
    def remove_source(self):
        """Remove a document source."""
        if not self.document_sources:
            print("\n❌ No sources to remove")
            return
        
        self.display_sources()
        
        try:
            index = int(input("Enter source number to remove: ")) - 1
            if 0 <= index < len(self.document_sources):
                removed = self.document_sources.pop(index)
                print(f"✅ Removed: {removed.source_path}")
            else:
                print("❌ Invalid source number")
        except ValueError:
            print("❌ Invalid input")
    
    def display_menu(self):
        """Display main menu."""
        print("\n📋 RAG Ingestion Menu")
        print("=" * 25)
        print("1. Add PDF document")
        print("2. Add web documents")
        print("3. Add Confluence source")
        print("4. Add GitHub repository (issues/PRs)")
        print("5. Add GitHub codebase")
        print("6. Add CSV document")
        print("7. Add AWS documentation (predefined)")
        print("8. Add Terraform documentation")
        print("9. Display current sources")
        print("10. Remove source")
        print("11. Process all documents")
        print("12. Test search")
        print("13. View index statistics")
        print("0. Exit")
        print("=" * 25)
    
    def run(self):
        """Run the interactive ingestion interface."""
        while True:
            self.display_menu()
            
            try:
                choice = input("\nSelect option: ").strip()
                
                if choice == '0':
                    print("\n👋 Goodbye!")
                    break
                elif choice == '1':
                    self.add_pdf_source()
                elif choice == '2':
                    self.add_web_sources()
                elif choice == '3':
                    self.add_confluence_source()
                elif choice == '4':
                    self.add_github_source()
                elif choice == '5':
                    self.add_github_codebase_source()
                elif choice == '6':
                    self.add_csv_source()
                elif choice == '7':
                    self.add_predefined_aws_sources()
                elif choice == '8':
                    self.add_terraform_sources()
                elif choice == '9':
                    self.display_sources()
                elif choice == '10':
                    self.remove_source()
                elif choice == '11':
                    self.process_documents()
                elif choice == '12':
                    self.test_search()
                elif choice == '13':
                    self.display_index_stats()
                else:
                    print("\n❌ Invalid option")
                    
            except KeyboardInterrupt:
                print("\n\n👋 Interrupted by user. Goodbye!")
                break
            except Exception as e:
                print(f"\n❌ Unexpected error: {e}")

def main():
    """Main execution function."""
    import sys
    import argparse
    
    parser = argparse.ArgumentParser(description='Process documents for RAG ingestion')
    parser.add_argument('--input', type=str, help='JSON input with sources and config')
    args = parser.parse_args()
    
    if args.input:
        import json
        try:
            input_data = json.loads(args.input)
            ingestion = InteractiveRAGIngestion()
            
            # Process each source
            for source in input_data.get('sources', []):
                source_type = source.get('type')
                
                if source_type == 'web':
                    web_source = create_web_source(source.get('path'), source.get('docType', 'web_document'))
                    ingestion.document_sources.append(web_source)
                elif source_type == 'github':
                    github_source = create_github_codebase_source(
                        source.get('path'), 
                        source.get('token'), 
                        source.get('extensions', []),
                        source.get('maxSize', 1024*1024)
                    )
                    ingestion.document_sources.append(github_source)
                elif source_type == 'pdf':
                    pdf_source = create_pdf_source(source.get('path'), source.get('docType', 'pdf_document'))
                    ingestion.document_sources.append(pdf_source)
                elif source_type == 'csv':
                    csv_source = create_csv_source(source.get('path'), source.get('docType', 'csv_document'))
                    ingestion.document_sources.append(csv_source)

            
            # Process documents
            ingestion.process_documents()
            print("SUCCESS: Documents processed successfully")
            
        except Exception as e:
            print(f"ERROR: {str(e)}")
            sys.exit(1)
    else:
        # Interactive mode
        try:
            ingestion = InteractiveRAGIngestion()
            ingestion.run()
        except Exception as e:
            print(f"\n❌ Fatal error: {e}")
            exit(1)

if __name__ == "__main__":
    main()
