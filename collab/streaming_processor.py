#!/usr/bin/env python3
"""
Streaming document processor with real-time logging and batching
"""

import json
import sys
import time
from typing import List, Dict, Any
from interactive_ingestion import InteractiveRAGIngestion

class StreamingProcessor:
    def __init__(self, emit_func=None):
        self.emit = emit_func or print
        self.ingestion = None
        
    def log(self, message: str, log_type: str = "info"):
        """Emit log message"""
        self.emit({
            'type': 'log',
            'level': log_type,
            'message': message,
            'timestamp': time.time()
        })
    
    def process_sources_batch(self, sources: List[Dict], batch_size: int = 5):
        """Process sources in batches with real-time logging"""
        try:
            self.log("🔧 Initializing RAG pipeline...")
            self.ingestion = InteractiveRAGIngestion()
            self.log("✅ Pipeline initialized successfully")
            
            total_sources = len(sources)
            self.log(f"📊 Processing {total_sources} sources in batches of {batch_size}")
            
            # Process in batches
            for batch_start in range(0, total_sources, batch_size):
                batch_end = min(batch_start + batch_size, total_sources)
                batch = sources[batch_start:batch_end]
                batch_num = (batch_start // batch_size) + 1
                total_batches = (total_sources + batch_size - 1) // batch_size
                
                self.log(f"🔄 Processing batch {batch_num}/{total_batches} ({len(batch)} sources)")
                
                # Add sources to ingestion
                self.ingestion.document_sources = []
                for source in batch:
                    self._add_source_to_ingestion(source)
                
                # Process this batch
                self._process_current_batch(batch_num, total_batches)
                
                # Small delay between batches
                if batch_end < total_sources:
                    self.log(f"⏳ Waiting before next batch...")
                    time.sleep(2)
            
            self.log("🎉 All batches processed successfully!")
            self.emit({'type': 'complete', 'status': 'success'})
            
        except Exception as e:
            self.log(f"❌ Processing failed: {str(e)}", "error")
            self.emit({'type': 'complete', 'status': 'error', 'message': str(e)})
    
    def _add_source_to_ingestion(self, source: Dict):
        """Add a source to the ingestion pipeline"""
        from models import create_web_source, create_github_codebase_source, create_pdf_source, create_csv_source
        
        try:
            source_type = source.get('type')
            path = source.get('path')
            
            if source_type == 'web':
                doc_source = create_web_source(path, source.get('docType', 'web_document'))
            elif source_type == 'github':
                doc_source = create_github_codebase_source(
                    path, 
                    source.get('token'), 
                    source.get('extensions', []),
                    source.get('maxSize', 1024*1024)
                )
            elif source_type == 'pdf':
                doc_source = create_pdf_source(path, source.get('docType', 'pdf_document'))
            elif source_type == 'csv':
                doc_source = create_csv_source(path, source.get('docType', 'csv_document'))
            else:
                self.log(f"⚠️ Unsupported source type: {source_type}", "warning")
                return
            
            self.ingestion.document_sources.append(doc_source)
            self.log(f"➕ Added {source_type}: {source.get('name', path)}")
            
        except Exception as e:
            self.log(f"❌ Failed to add source {source.get('name', 'unknown')}: {str(e)}", "error")
    
    def _process_current_batch(self, batch_num: int, total_batches: int):
        """Process the current batch with detailed logging"""
        try:
            if not self.ingestion.document_sources:
                self.log("⚠️ No valid sources in this batch", "warning")
                return
            
            self.log(f"📄 Loading documents from {len(self.ingestion.document_sources)} sources...")
            
            # Load documents with individual source logging
            all_documents = []
            for i, source in enumerate(self.ingestion.document_sources):
                try:
                    self.log(f"📖 Loading: {source.source_type} - {source.source_path}")
                    docs = self.ingestion._load_documents_from_source(source)
                    if docs:
                        all_documents.extend(docs)
                        self.log(f"✅ Loaded {len(docs)} documents")
                    else:
                        self.log(f"⚠️ No documents loaded from this source", "warning")
                except Exception as e:
                    self.log(f"❌ Error loading source: {str(e)}", "error")
            
            if not all_documents:
                self.log("❌ No documents loaded from any source in this batch", "error")
                return
            
            self.log(f"📝 Splitting {len(all_documents)} documents into chunks...")
            
            # Split documents
            from langchain.text_splitter import RecursiveCharacterTextSplitter
            text_splitter = RecursiveCharacterTextSplitter(
                chunk_size=1000,
                chunk_overlap=200
            )
            texts = text_splitter.split_documents(all_documents)
            self.log(f"✅ Created {len(texts)} text chunks")
            
            # Create embeddings
            self.log(f"🔗 Creating embeddings for {len(texts)} chunks...")
            text_contents = [doc.page_content for doc in texts]
            embeddings = self.ingestion.embeddings.embed_documents(text_contents)
            
            # Prepare vectors
            vectors_to_upsert = []
            import uuid
            for i, (doc, embedding) in enumerate(zip(texts, embeddings)):
                filtered_metadata = self.ingestion._filter_metadata(doc.metadata)
                filtered_metadata['text'] = doc.page_content
                filtered_metadata['batch'] = batch_num
                
                vectors_to_upsert.append({
                    'id': f'batch_{batch_num}_doc_{i}_{uuid.uuid4().hex[:8]}',
                    'values': embedding,
                    'metadata': filtered_metadata
                })
            
            # Upload to Pinecone
            self.log(f"⬆️ Uploading {len(vectors_to_upsert)} vectors to Pinecone...")
            upload_batch_size = 100
            for i in range(0, len(vectors_to_upsert), upload_batch_size):
                batch_vectors = vectors_to_upsert[i:i + upload_batch_size]
                self.ingestion.index.upsert(vectors=batch_vectors)
                self.log(f"📤 Uploaded {len(batch_vectors)} vectors")
            
            self.log(f"✅ Batch {batch_num}/{total_batches} completed successfully!")
            
        except Exception as e:
            self.log(f"❌ Batch {batch_num} failed: {str(e)}", "error")
            raise

def main():
    if len(sys.argv) < 2:
        print("Usage: python streaming_processor.py '<json_input>'")
        sys.exit(1)
    
    try:
        input_data = json.loads(sys.argv[1])
        sources = input_data.get('sources', [])
        batch_size = input_data.get('batch_size', 5)
        
        processor = StreamingProcessor()
        processor.process_sources_batch(sources, batch_size)
        
    except Exception as e:
        print(f"ERROR: {str(e)}")
        sys.exit(1)

if __name__ == "__main__":
    main()