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
import re
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
        """Embed multiple documents in batches"""
        batch_size = 100  # OpenAI allows up to 2048 inputs per request
        all_embeddings = []
        
        for i in range(0, len(texts), batch_size):
            batch = texts[i:i + batch_size]
            try:
                response = self.client.embeddings.create(
                    model=self.model,
                    input=batch
                )
                batch_embeddings = [data.embedding for data in response.data]
                all_embeddings.extend(batch_embeddings)
            except Exception as e:
                print(f"Error processing batch {i//batch_size + 1}: {e}")
                # Fallback to individual processing for this batch
                for text in batch:
                    try:
                        embedding = self.embed_query(text)
                        all_embeddings.append(embedding)
                    except Exception as text_error:
                        print(f"Error processing individual text: {text_error}")
                        # Add zero vector as fallback
                        all_embeddings.append([0.0] * 1536)
        
        return all_embeddings

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
        

        
        # Initialize RAG pipeline
        self.initialize_pipeline()
    
    def initialize_pipeline(self):
        """Initialize the RAG pipeline."""
        try:
            self.embeddings = WorkingOpenAIEmbeddings()
            self.llm = WorkingOpenAIChat()
            test_embedding = self.embeddings.embed_query("test")
            test_response = self.llm.invoke("Say 'Hello'")
            
            # Initialize Pinecone
            from pinecone import Pinecone, ServerlessSpec
            pc = Pinecone(api_key=self.config.pinecone.api_key)
            
            # Get or create index
            index_name = self.config.pinecone.index_name
            existing_indexes = [index.name for index in pc.list_indexes()]
            
            if index_name not in existing_indexes:
                pc.create_index(
                    name=index_name,
                    dimension=1536,
                    metric='cosine',
                    spec=ServerlessSpec(cloud='aws', region='us-east-1')
                )
                import time
                time.sleep(10)
            self.index = pc.Index(index_name)
                
        except Exception as e:
            print(f"Error initializing pipeline: {e}")
            exit(1)
    
    def process_documents(self, session_id: str = "default"):
        """Process all added document sources."""
        if not self.document_sources:
            msg = "No document sources added. Please add sources first."
            send_processing_update(session_id, "error", msg)
            return
        
        start_time = time.time()
        msg = f"Processing {len(self.document_sources)} document sources..."
        send_processing_update(session_id, "start", msg, {"total_sources": len(self.document_sources)})
        
        try:
            from langchain.text_splitter import RecursiveCharacterTextSplitter
            from langchain.schema import Document
            import re
            
            all_documents = []
            sources_to_remove = []
            
            # Load documents from all sources
            for i, source in enumerate(self.document_sources):
                # Check stop flag
                if hasattr(self, 'should_stop') and self.should_stop:
                    msg = "Processing stopped by user"
                    send_processing_update(session_id, "stopped", msg)
                    return
                
                try:
                    msg = f"Processing: {source.source_type} - {source.source_path}"
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
                        send_processing_update(session_id, "source_complete", msg, {"documents_loaded": len(docs)})
                    else:
                        msg = "No documents loaded from this source"
                        send_processing_update(session_id, "warning", msg)
                except Exception as e:
                    msg = f"Error loading from {source.source_path}: {e}"
                    send_processing_update(session_id, "error", msg)
                    continue
            
            if not all_documents:
                msg = "No documents loaded from any source"
                send_processing_update(session_id, "error", msg)
                return
            
            # Check stop flag before chunking
            if hasattr(self, 'should_stop') and self.should_stop:
                msg = "Processing stopped by user"
                send_processing_update(session_id, "stopped", msg)
                return
            
            msg = f"Smart chunking {len(all_documents)} documents..."
            send_processing_update(session_id, "chunking", msg, {"total_documents": len(all_documents)})
            
            texts = self._smart_chunk_documents(all_documents)
            msg = f"Created {len(texts)} smart chunks"
            send_processing_update(session_id, "chunking_complete", msg, {"total_chunks": len(texts)})
            
            # Check stop flag before embeddings
            if hasattr(self, 'should_stop') and self.should_stop:
                msg = "Processing stopped by user"
                send_processing_update(session_id, "stopped", msg)
                return
            
            msg = "Creating embeddings and storing in Pinecone..."
            send_processing_update(session_id, "embedding_start", msg)
            
            text_contents = [doc.page_content for doc in texts]
            
            msg = f"Creating embeddings for {len(text_contents)} chunks..."
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
                        send_processing_update(session_id, "embedding_progress", msg, {
                            "processed": i + 1,
                            "total": len(texts)
                        })
                        
                except Exception as e:
                    continue
            
            if vectors_to_upsert:
                batch_size = self.ingestion_config.batch_size
                total_batches = (len(vectors_to_upsert) + batch_size - 1) // batch_size
                
                for i in range(0, len(vectors_to_upsert), batch_size):
                    batch = vectors_to_upsert[i:i + batch_size]
                    self.index.upsert(vectors=batch)
                    batch_num = i // batch_size + 1
                    msg = f"Uploaded batch {batch_num}/{total_batches}"
                    send_processing_update(session_id, "upload_progress", msg, {
                        "batch": batch_num,
                        "total_batches": total_batches
                    })
                
                msg = f"Successfully processed and stored {len(vectors_to_upsert)} document chunks!"
                
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
                
                for source in sources_to_remove:
                    if source in self.document_sources:
                        self.document_sources.remove(source)
            else:
                msg = "No valid chunks created for storage"
                send_processing_update(session_id, "error", msg)
                
        except Exception as e:
            msg = f"Error during processing: {e}"
            send_processing_update(session_id, "error", msg)
    
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
                print(f"Unsupported source type: {source.source_type}")
                return []
        except Exception as e:
            print(f"Error loading from {source.source_type}: {e}")
            return []
    
    def _load_pdf_documents(self, source: DocumentSource) -> List:
        """Load PDF documents"""
        from langchain_community.document_loaders import PyPDFLoader
        loader = PyPDFLoader(source.source_path)
        docs = loader.load()
        
        for doc in docs:
            doc.metadata.update(source.metadata)
        
        return docs
    
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
                    try:
                        compatible_loader = CompatibleSeleniumLoader(
                            urls=urls,
                            browser=browser,
                            headless=True,
                            wait_time=15
                        )
                        return compatible_loader.load()
                    except Exception as compatible_error:
                        pass
            
            # Fallback to basic web loader
            from langchain_community.document_loaders import WebBaseLoader
            loader = WebBaseLoader(source.source_path)
            docs = loader.load()
            
            # Add source metadata to each document
            for doc in docs:
                doc.metadata.update(source.metadata)
            
            return docs
            
        except Exception as e:
            try:
                from langchain_community.document_loaders import WebBaseLoader
                loader = WebBaseLoader(source.source_path)
                docs = loader.load()
                for doc in docs:
                    doc.metadata.update(source.metadata)
                return docs
            except Exception as final_error:
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
        docs = loader.load()
        
        # Add source metadata to each document
        for doc in docs:
            doc.metadata.update(source.metadata)
        
        return docs
    
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
            
            # Add source metadata to each document
            for doc in documents:
                doc.metadata.update(source.metadata)
            
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
                
                # Add source metadata to each document
                for doc in documents:
                    doc.metadata.update(source.metadata)
                
                return documents
            except Exception as e:
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
        docs = loader.load()
        
        # Add source metadata to each document
        for doc in docs:
            doc.metadata.update(source.metadata)
        
        return docs
    
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
                
                doc_metadata = {
                    'source_type': 'csv',
                    'source_path': source.source_path,
                    'chunk_number': chunk_num,
                    'rows_count': len(chunk_df),
                    'columns': list(chunk_df.columns)
                }
                doc_metadata.update(source.metadata)
                
                doc = Document(
                    page_content=chunk_content,
                    metadata=doc_metadata
                )
                documents.append(doc)
                
                if (chunk_num + 1) % 10 == 0:
                    pass
                    
        except Exception as e:
            from langchain_community.document_loaders import CSVLoader
            loader = CSVLoader(file_path=source.source_path)
            docs = loader.load()
            for doc in docs:
                doc.metadata.update(source.metadata)
            return docs
        
        return documents
    
    def test_search(self):
        """Test search functionality."""
        query = input("\nEnter search query: ").strip()
        if not query:
            print("No query provided")
            return
        
        try:
            print(f"\nSearching for: '{query}'")
            
            # Get query embedding
            query_embedding = self.embeddings.embed_query(query)
            
            # Search in Pinecone
            search_results = self.index.query(
                vector=query_embedding,
                top_k=5,
                include_metadata=True
            )
            
            if search_results.matches:
                print(f"\nFound {len(search_results.matches)} results:")
                for i, match in enumerate(search_results.matches, 1):
                    print(f"\n{i}. Score: {match.score:.4f}")
                    print(f"   Source: {match.metadata.get('source_path', 'Unknown')}")
                    print(f"   Content: {match.metadata.get('text', '')[:200]}...")
                
                # Test RAG response
                print(f"\nGenerating RAG response...")
                context = "\n\n".join([match.metadata.get('text', '') for match in search_results.matches[:3]])
                
                prompt = f"""Use the following context to answer the question. If you don't know the answer based on the context, say you don't know.

Context:
{context}

Question: {query}
Answer:"""
                
                response = self.llm.invoke(prompt)
                print(f"\nRAG Response: {response}")
            else:
                print("\nNo results found")
                
        except Exception as e:
            print(f"\nSearch error: {e}")
            import traceback
            traceback.print_exc()
    
    def display_index_stats(self):
        """Display current index statistics."""
        try:
            if self.index:
                stats = self.index.describe_index_stats()
        except Exception as e:
            pass
    
    def _smart_chunk_documents(self, documents: List) -> List:
        """Smart chunking based on category with intelligent chunking strategies"""
        chunked_docs = []
        
        for doc in documents:
            # Get category from custom metadata
            category = doc.metadata.get('document_category', 'general')
            source_type = doc.metadata.get('source_type', '')
            
            if category == 'terraform':
                chunks = self._chunk_terraform_doc(doc)
            elif category == 'aws-docs':
                chunks = self._chunk_aws_doc(doc)
            elif category == 'pricing':
                chunks = self._chunk_pricing_doc(doc)
            elif category == 'api-docs':
                chunks = self._chunk_api_doc(doc)
            elif category == 'tutorials':
                chunks = self._chunk_tutorials_doc(doc)
            elif source_type == 'csv':
                chunks = self._chunk_csv_doc(doc)
            elif source_type == 'github_codebase':
                chunks = self._chunk_code_doc(doc)
            else:
                chunks = self._chunk_generic_doc(doc)
            
            chunked_docs.extend(chunks)
        
        return chunked_docs
    
    def _chunk_terraform_doc(self, doc) -> List:
        """Chunk Terraform preserving complete blocks, combining small ones"""
        content = doc.page_content
        
        # Extract all Terraform blocks (resource, data, module, variable, output)
        block_patterns = [
            r'(resource\s+"[^"]+"\s+"[^"]+"\s*\{[^}]*(?:\{[^}]*\}[^}]*)*\})',
            r'(data\s+"[^"]+"\s+"[^"]+"\s*\{[^}]*(?:\{[^}]*\}[^}]*)*\})',
            r'(module\s+"[^"]+"\s*\{[^}]*(?:\{[^}]*\}[^}]*)*\})',
            r'(variable\s+"[^"]+"\s*\{[^}]*(?:\{[^}]*\}[^}]*)*\})',
            r'(output\s+"[^"]+"\s*\{[^}]*(?:\{[^}]*\}[^}]*)*\})',
            r'(locals\s*\{[^}]*(?:\{[^}]*\}[^}]*)*\})'
        ]
        
        all_blocks = []
        for pattern in block_patterns:
            blocks = re.findall(pattern, content, re.MULTILINE | re.DOTALL)
            all_blocks.extend(blocks)
        
        chunks = []
        current_chunk = []
        current_size = 0
        max_chunk_size = 1200
        
        for block in all_blocks:
            block_size = len(block)
            
            # If block is large, create its own chunk
            if block_size > max_chunk_size:
                # First, flush current chunk if it has content
                if current_chunk:
                    from langchain.schema import Document
                    chunk_doc = Document(
                        page_content='\n\n'.join(current_chunk),
                        metadata={**doc.metadata, 'chunk_type': 'terraform_combined'}
                    )
                    chunks.append(chunk_doc)
                    current_chunk = []
                    current_size = 0
                
                # Create chunk for large block
                from langchain.schema import Document
                chunk_doc = Document(
                    page_content=block,
                    metadata={
                        **doc.metadata,
                        'chunk_type': 'terraform_block',
                        'block_type': self._extract_terraform_block_type(block)
                    }
                )
                chunks.append(chunk_doc)
            
            # If adding this block would exceed limit, flush current chunk
            elif current_size + block_size > max_chunk_size and current_chunk:
                from langchain.schema import Document
                chunk_doc = Document(
                    page_content='\n\n'.join(current_chunk),
                    metadata={**doc.metadata, 'chunk_type': 'terraform_combined'}
                )
                chunks.append(chunk_doc)
                current_chunk = [block]
                current_size = block_size
            
            # Add to current chunk
            else:
                current_chunk.append(block)
                current_size += block_size
        
        # Flush remaining chunk
        if current_chunk:
            from langchain.schema import Document
            chunk_doc = Document(
                page_content='\n\n'.join(current_chunk),
                metadata={**doc.metadata, 'chunk_type': 'terraform_combined'}
            )
            chunks.append(chunk_doc)
        
        return chunks if chunks else self._chunk_generic_doc(doc)
    
    def _chunk_aws_doc(self, doc) -> List:
        """Chunk AWS docs by service features and concepts"""
        content = doc.page_content
        chunks = []
        
        # Split by AWS-specific patterns
        aws_patterns = [
            r'(## [^\n]*(?:Overview|Introduction)[^\n]*\n.*?)(?=## |$)',
            r'(## [^\n]*(?:Getting [Ss]tarted|Quick [Ss]tart)[^\n]*\n.*?)(?=## |$)',
            r'(## [^\n]*(?:Features?|Capabilities)[^\n]*\n.*?)(?=## |$)',
            r'(## [^\n]*(?:Pricing|Cost)[^\n]*\n.*?)(?=## |$)',
            r'(## [^\n]*(?:Security|IAM|Permissions)[^\n]*\n.*?)(?=## |$)'
        ]
        
        found_sections = []
        for pattern in aws_patterns:
            sections = re.findall(pattern, content, re.MULTILINE | re.DOTALL)
            found_sections.extend(sections)
        
        if found_sections:
            for section in found_sections:
                from langchain.schema import Document
                chunk_doc = Document(
                    page_content=section,
                    metadata={**doc.metadata, 'chunk_type': 'aws_feature_section'}
                )
                chunks.append(chunk_doc)
        else:
            # Split by paragraphs for AWS docs
            paragraphs = content.split('\n\n')
            current_chunk = []
            current_size = 0
            
            for para in paragraphs:
                if current_size + len(para) > 800 and current_chunk:
                    from langchain.schema import Document
                    chunk_doc = Document(
                        page_content='\n\n'.join(current_chunk),
                        metadata={**doc.metadata, 'chunk_type': 'aws_paragraph'}
                    )
                    chunks.append(chunk_doc)
                    current_chunk = [para]
                    current_size = len(para)
                else:
                    current_chunk.append(para)
                    current_size += len(para)
            
            if current_chunk:
                from langchain.schema import Document
                chunk_doc = Document(
                    page_content='\n\n'.join(current_chunk),
                    metadata={**doc.metadata, 'chunk_type': 'aws_paragraph'}
                )
                chunks.append(chunk_doc)
        
        return chunks
    
    def _chunk_csv_doc(self, doc) -> List:
        """Chunk CSV with larger chunks"""
        from langchain.text_splitter import RecursiveCharacterTextSplitter
        splitter = RecursiveCharacterTextSplitter(
            chunk_size=1500,
            chunk_overlap=50
        )
        chunks = splitter.split_text(doc.page_content)
        from langchain.schema import Document
        return [
            Document(
                page_content=chunk,
                metadata={**doc.metadata, 'chunk_type': 'csv_data'}
            )
            for chunk in chunks
        ]
    
    def _chunk_code_doc(self, doc) -> List:
        """Chunk code with smaller chunks"""
        from langchain.text_splitter import RecursiveCharacterTextSplitter
        splitter = RecursiveCharacterTextSplitter(
            chunk_size=800,
            chunk_overlap=100
        )
        chunks = splitter.split_text(doc.page_content)
        from langchain.schema import Document
        return [
            Document(
                page_content=chunk,
                metadata={**doc.metadata, 'chunk_type': 'code'}
            )
            for chunk in chunks
        ]
    
    def _chunk_generic_doc(self, doc) -> List:
        """Generic chunking"""
        from langchain.text_splitter import RecursiveCharacterTextSplitter
        splitter = RecursiveCharacterTextSplitter(
            chunk_size=self.ingestion_config.chunk_size,
            chunk_overlap=self.ingestion_config.chunk_overlap
        )
        chunks = splitter.split_text(doc.page_content)
        from langchain.schema import Document
        return [
            Document(
                page_content=chunk,
                metadata={**doc.metadata, 'chunk_type': 'generic'}
            )
            for chunk in chunks
        ]
    
    def _extract_terraform_block_type(self, block: str) -> str:
        """Extract block type from Terraform block"""
        patterns = [
            (r'resource\s+"([^"]+)"', 'resource'),
            (r'data\s+"([^"]+)"', 'data'),
            (r'module\s+"([^"]+)"', 'module'),
            (r'variable\s+"([^"]+)"', 'variable'),
            (r'output\s+"([^"]+)"', 'output'),
            (r'locals\s*\{', 'locals')
        ]
        
        for pattern, block_type in patterns:
            match = re.search(pattern, block)
            if match:
                return block_type
        return 'unknown'
    
    def _extract_terraform_resource_type(self, resource_block: str) -> str:
        """Extract resource type from Terraform block"""
        match = re.search(r'resource\s+"([^"]+)"', resource_block)
        return match.group(1) if match else 'unknown'
    
    def _chunk_pricing_doc(self, doc) -> List:
        """Chunk pricing docs by preserving pricing tables and cost information"""
        content = doc.page_content
        
        from langchain.text_splitter import RecursiveCharacterTextSplitter
        # Use smaller chunks for pricing to keep related pricing info together
        splitter = RecursiveCharacterTextSplitter(
            chunk_size=600,
            chunk_overlap=100,
            separators=["\n## ", "\n### ", "\n\n", "\n", " "]
        )
        
        chunks = []
        text_chunks = splitter.split_text(content)
        
        for chunk in text_chunks:
            from langchain.schema import Document
            chunk_doc = Document(
                page_content=chunk,
                metadata={**doc.metadata, 'chunk_type': 'pricing_data'}
            )
            chunks.append(chunk_doc)
        
        return chunks
    

    
    def _chunk_api_doc(self, doc) -> List:
        """Chunk API docs by endpoints and methods"""
        content = doc.page_content
        chunks = []
        
        # Extract API endpoints
        endpoint_patterns = [
            r'((?:GET|POST|PUT|DELETE|PATCH)\s+[^\n]*\n(?:[^\n]*\n)*?(?=(?:GET|POST|PUT|DELETE|PATCH)|$))',
            r'(### [^\n]*(?:endpoint|API|method)[^\n]*\n.*?)(?=### |## |$)'
        ]
        
        found_endpoints = []
        for pattern in endpoint_patterns:
            endpoints = re.findall(pattern, content, re.MULTILINE | re.DOTALL)
            found_endpoints.extend(endpoints)
        
        if found_endpoints:
            for endpoint in found_endpoints:
                from langchain.schema import Document
                chunk_doc = Document(
                    page_content=endpoint,
                    metadata={**doc.metadata, 'chunk_type': 'api_endpoint'}
                )
                chunks.append(chunk_doc)
        else:
            # Split by code blocks and descriptions
            parts = re.split(r'(```[^`]*```)', content)
            current_chunk = []
            
            for part in parts:
                if part.startswith('```'):
                    # Code block - keep with surrounding text
                    if current_chunk:
                        current_chunk.append(part)
                    else:
                        current_chunk = [part]
                else:
                    # Regular text
                    if len(''.join(current_chunk) + part) > 1200 and current_chunk:
                        from langchain.schema import Document
                        chunk_doc = Document(
                            page_content=''.join(current_chunk),
                            metadata={**doc.metadata, 'chunk_type': 'api_section'}
                        )
                        chunks.append(chunk_doc)
                        current_chunk = [part]
                    else:
                        current_chunk.append(part)
            
            if current_chunk:
                from langchain.schema import Document
                chunk_doc = Document(
                    page_content=''.join(current_chunk),
                    metadata={**doc.metadata, 'chunk_type': 'api_section'}
                )
                chunks.append(chunk_doc)
        
        return chunks
    
    def _chunk_tutorials_doc(self, doc) -> List:
        """Chunk tutorials by preserving complete steps"""
        content = doc.page_content
        chunks = []
        
        # Extract numbered steps and procedures
        step_patterns = [
            r'((?:Step \d+|\d+\.|\d+\))[^\n]*\n.*?)(?=(?:Step \d+|\d+\.|\d+\))|## |$)',
            r'(## [^\n]*(?:[Ss]tep|[Pp]rocedure|[Tt]ask)[^\n]*\n.*?)(?=## |$)'
        ]
        
        found_steps = []
        for pattern in step_patterns:
            steps = re.findall(pattern, content, re.MULTILINE | re.DOTALL)
            found_steps.extend(steps)
        
        if found_steps:
            # Combine small steps, keep large ones separate
            current_chunk = []
            current_size = 0
            
            for step in found_steps:
                step_size = len(step)
                
                if step_size > 1500:
                    # Large step gets its own chunk
                    if current_chunk:
                        from langchain.schema import Document
                        chunk_doc = Document(
                            page_content='\n\n'.join(current_chunk),
                            metadata={**doc.metadata, 'chunk_type': 'tutorial_steps'}
                        )
                        chunks.append(chunk_doc)
                        current_chunk = []
                        current_size = 0
                    
                    from langchain.schema import Document
                    chunk_doc = Document(
                        page_content=step,
                        metadata={**doc.metadata, 'chunk_type': 'tutorial_long_step'}
                    )
                    chunks.append(chunk_doc)
                
                elif current_size + step_size > 1200 and current_chunk:
                    # Flush current chunk
                    from langchain.schema import Document
                    chunk_doc = Document(
                        page_content='\n\n'.join(current_chunk),
                        metadata={**doc.metadata, 'chunk_type': 'tutorial_steps'}
                    )
                    chunks.append(chunk_doc)
                    current_chunk = [step]
                    current_size = step_size
                
                else:
                    # Add to current chunk
                    current_chunk.append(step)
                    current_size += step_size
            
            if current_chunk:
                from langchain.schema import Document
                chunk_doc = Document(
                    page_content='\n\n'.join(current_chunk),
                    metadata={**doc.metadata, 'chunk_type': 'tutorial_steps'}
                )
                chunks.append(chunk_doc)
        
        else:
            # No clear steps found, use section-based chunking
            sections = re.split(r'\n## ', content)
            for i, section in enumerate(sections):
                if section.strip():
                    if i > 0:
                        section = '## ' + section
                    from langchain.schema import Document
                    chunk_doc = Document(
                        page_content=section,
                        metadata={**doc.metadata, 'chunk_type': 'tutorial_section'}
                    )
                    chunks.append(chunk_doc)
        
        return chunks
    
    def _extract_aws_service_name(self, content: str) -> str:
        """Extract AWS service name from content"""
        aws_services = ['EC2', 'S3', 'RDS', 'Lambda', 'VPC', 'IAM', 'CloudWatch', 'ELB', 'Route53']
        for service in aws_services:
            if service.lower() in content.lower():
                return service
        return 'unknown'
    
    def display_processing_stats(self):
        """Display processing statistics."""
        pass
    
    # Menu methods
    def add_pdf_source(self):
        """Add PDF document source."""
        print("\nAdding PDF Document")
        pdf_path = input("Enter PDF file path: ").strip()
        if not pdf_path or not Path(pdf_path).exists():
            print("Invalid file path")
            return
        
        doc_type = input("Document type (default: pdf_document): ").strip() or "pdf_document"
        source = create_pdf_source(pdf_path, doc_type)
        self.document_sources.append(source)
        print(f"Added PDF source: {pdf_path}")
    
    def add_web_sources(self):
        """Add web document sources."""
        print("\nAdding Web Documents")
        print("Enter URLs (one per line, empty line to finish):")
        urls = []
        
        while True:
            url = input("> ").strip()
            if not url:
                break
            if url.startswith('http'):
                urls.append(url)
                print(f"  Added: {url}")
            else:
                print(f"  Invalid URL: {url}")
        
        if not urls:
            print("No valid URLs provided")
            return
        
        for url in urls:
            source = create_web_source(url, 'web_documentation')
            self.document_sources.append(source)
        
        print(f"Added {len(urls)} web sources")
    
    def add_confluence_source(self):
        """Add Confluence document source."""
        print("\nAdding Confluence Source")
        confluence_url = input("Confluence URL: ").strip()
        username = input("Username: ").strip()
        api_key = input("API Key: ").strip()
        
        if not all([confluence_url, username, api_key]):
            print("Missing required credentials")
            return
        
        page_ids_input = input("Page IDs (comma-separated, optional): ").strip()
        space_key = input("Space key (optional): ").strip()
        
        page_ids = [pid.strip() for pid in page_ids_input.split(',') if pid.strip()] if page_ids_input else None
        
        source = create_confluence_source(
            confluence_url, username, api_key, page_ids, space_key if space_key else None
        )
        
        self.document_sources.append(source)
        print(f"Added Confluence source: {confluence_url}")
    
    def add_github_source(self):
        """Add GitHub repository source for issues/PRs."""
        print("\nAdding GitHub Repository (Issues/PRs)")
        repo = input("Repository (e.g., 'owner/repo'): ").strip()
        access_token = input("GitHub access token (optional): ").strip()
        
        if not repo:
            print("Repository name is required")
            return
        
        include_prs = input("Include Pull Requests? (y/n): ").strip().lower() == 'y'
        include_issues = input("Include Issues? (y/n): ").strip().lower() == 'y'
        
        source = create_github_source(
            repo, access_token if access_token else None, include_prs, include_issues
        )
        
        self.document_sources.append(source)
        print(f"Added GitHub source: {repo}")
    
    def add_github_codebase_source(self):
        """Add GitHub codebase source."""
        print("\nAdding GitHub Codebase")
        repo = input("Repository (e.g., 'owner/repo'): ").strip()
        access_token = input("GitHub access token (optional): ").strip()
        
        if not repo:
            print("Repository name is required")
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
        print(f"Added GitHub codebase source: {repo}")
    
    def add_predefined_aws_sources(self):
        """Add predefined AWS documentation sources."""
        print("\nAdding AWS Documentation Sources")
        self.document_sources.extend(AWS_DOCUMENTATION_SOURCES)
        print(f"Added {len(AWS_DOCUMENTATION_SOURCES)} AWS documentation sources")
    
    def add_terraform_sources(self):
        """Add Terraform documentation sources."""
        print("\nAdding Terraform Documentation Sources")
        self.document_sources.extend(TERRAFORM_DOCUMENTATION_SOURCES)
        print(f"Added {len(TERRAFORM_DOCUMENTATION_SOURCES)} Terraform documentation sources")
    
    def add_csv_source(self):
        """Add CSV document source."""
        print("\nAdding CSV Document")
        csv_path = input("Enter CSV file path: ").strip()
        if not csv_path or not Path(csv_path).exists():
            print("Invalid file path")
            return
        
        doc_type = input("Document type (default: csv_document): ").strip() or "csv_document"
        source = create_csv_source(csv_path, doc_type)
        self.document_sources.append(source)
        print(f"Added CSV source: {csv_path}")
    
    def display_sources(self):
        """Display current document sources."""
        if not self.document_sources:
            print("\nNo document sources added yet")
            return
        
        print(f"\nCurrent Document Sources ({len(self.document_sources)}):")
        for i, source in enumerate(self.document_sources, 1):
            doc_type = source.metadata.get('doc_type', 'unknown')
            print(f"{i:2d}. [{source.source_type.upper()}] {source.source_path}")
            print(f"     Type: {doc_type}")
    
    def remove_source(self):
        """Remove a document source."""
        if not self.document_sources:
            print("\nNo sources to remove")
            return
        
        self.display_sources()
        
        try:
            index = int(input("Enter source number to remove: ")) - 1
            if 0 <= index < len(self.document_sources):
                removed = self.document_sources.pop(index)
                print(f"Removed: {removed.source_path}")
            else:
                print("Invalid source number")
        except ValueError:
            print("Invalid input")
    
    def display_menu(self):
        """Display main menu."""
        print("\nRAG Ingestion Menu")
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
                    print("\nGoodbye!")
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
                    print("\nInvalid option")
                    
            except KeyboardInterrupt:
                print("\n\nInterrupted by user. Goodbye!")
                break
            except Exception as e:
                print(f"\nUnexpected error: {e}")

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
                custom_metadata = source.get('customMetadata', {})
                
                if source_type == 'web':
                    web_source = create_web_source(source.get('path'), source.get('docType', 'web_document'))
                    web_source.metadata.update(custom_metadata)
                    ingestion.document_sources.append(web_source)
                elif source_type == 'github':
                    github_source = create_github_codebase_source(
                        source.get('path'), 
                        source.get('token'), 
                        source.get('extensions', []),
                        source.get('maxSize', 1024*1024)
                    )
                    # Add token to metadata for loader access, but exclude from custom metadata
                    github_source.metadata['access_token'] = source.get('token')
                    github_source.metadata.update(custom_metadata)
                    ingestion.document_sources.append(github_source)
                elif source_type == 'pdf':
                    pdf_source = create_pdf_source(source.get('path'), source.get('docType', 'pdf_document'))
                    pdf_source.metadata.update(custom_metadata)
                    ingestion.document_sources.append(pdf_source)
                elif source_type == 'csv':
                    csv_source = create_csv_source(source.get('path'), source.get('docType', 'csv_document'))
                    csv_source.metadata.update(custom_metadata)
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
            print(f"\nFatal error: {e}")
            exit(1)

if __name__ == "__main__":
    main()
