#!/usr/bin/env python3
"""
LangChain-based query processing engine with vector retrieval system.
"""

import asyncio
import logging
import time
from typing import List, Dict, Any, Optional, Tuple
from dataclasses import dataclass

from langchain_community.vectorstores import Pinecone as LangChainPinecone
from langchain_community.embeddings import OpenAIEmbeddings
from langchain.schema import Document, BaseRetriever
from langchain.callbacks.base import BaseCallbackHandler
from langchain.docstore.document import Document as LangChainDocument

import openai
import httpx
from pinecone import Pinecone

from config import get_config
from cache_manager import CacheManager, get_cache_manager

logger = logging.getLogger(__name__)


@dataclass
class QueryResult:
    """Result of a query operation."""
    response: str
    sources: List['SourceDocument']
    processing_time: float
    cached: bool = False
    query_embedding: Optional[List[float]] = None


@dataclass
class SourceDocument:
    """Source document information."""
    content: str
    metadata: Dict[str, Any]
    relevance_score: float
    source_type: str
    source_path: str
    
    @classmethod
    def from_langchain_document(cls, doc: Document, score: float = 0.0) -> 'SourceDocument':
        """Create SourceDocument from LangChain Document."""
        return cls(
            content=doc.page_content,
            metadata=doc.metadata,
            relevance_score=score,
            source_type=doc.metadata.get('source_type', 'unknown'),
            source_path=doc.metadata.get('source_path', 'unknown')
        )


class QueryCallbackHandler(BaseCallbackHandler):
    """Callback handler for query processing events."""
    
    def __init__(self, query_processor: 'QueryProcessor'):
        self.query_processor = query_processor
        self.start_time = None
        self.retrieval_time = None
        self.generation_time = None
    
    def on_retriever_start(self, serialized: Dict[str, Any], query: str, **kwargs) -> None:
        """Called when retriever starts."""
        self.start_time = time.time()
        logger.debug(f"Starting retrieval for query: {query[:50]}...")
    
    def on_retriever_end(self, documents: List[Document], **kwargs) -> None:
        """Called when retriever ends."""
        if self.start_time:
            self.retrieval_time = time.time() - self.start_time
            logger.debug(f"Retrieval completed in {self.retrieval_time:.2f}s, found {len(documents)} documents")
    
    def on_retriever_error(self, error: Exception, **kwargs) -> None:
        """Called when retriever errors."""
        logger.error(f"Retrieval error: {error}")
    
    def on_llm_start(self, serialized: Dict[str, Any], prompts: List[str], **kwargs) -> None:
        """Called when LLM starts."""
        self.generation_start = time.time()
        logger.debug("Starting response generation")
    
    def on_llm_end(self, response, **kwargs) -> None:
        """Called when LLM ends."""
        if hasattr(self, 'generation_start'):
            self.generation_time = time.time() - self.generation_start
            logger.debug(f"Response generation completed in {self.generation_time:.2f}s")


class WorkingOpenAIEmbeddings(OpenAIEmbeddings):
    """Enhanced OpenAI embeddings with caching and error handling."""
    
    def __init__(self, cache_manager: CacheManager = None, **kwargs):
        # Initialize parent class first
        config = get_config()
        super().__init__(openai_api_key=config.openai.api_key, **kwargs)
        
        # Add our custom fields
        self.cache_manager = cache_manager
        
        # Create explicit httpx client to avoid proxies issue
        http_client = httpx.Client()
        
        # Create OpenAI client with explicit http_client
        self.client = openai.OpenAI(
            api_key=config.openai.api_key,
            http_client=http_client
        )
    
    def embed_query(self, text: str) -> List[float]:
        """Embed a single query text with caching."""
        # Check cache first
        if self.cache_manager:
            try:
                loop = asyncio.get_event_loop()
                if loop.is_running():
                    # Create task for async cache lookup
                    task = asyncio.create_task(self._async_embed_query(text))
                    # For now, proceed with normal embedding
                    pass
                else:
                    cached_embedding = asyncio.run(self.cache_manager.redis_manager.get_cached_embeddings(text))
                    if cached_embedding:
                        logger.debug(f"Using cached embedding for query: {text[:50]}...")
                        return cached_embedding
            except Exception as e:
                logger.warning(f"Cache lookup failed, proceeding with fresh embedding: {e}")
        
        # Generate fresh embedding
        try:
            response = self.client.embeddings.create(
                model=self.model,
                input=text
            )
            embedding = response.data[0].embedding
            
            # Cache the result
            if self.cache_manager:
                asyncio.create_task(
                    self.cache_manager.redis_manager.cache_embeddings(text, embedding)
                )
            
            return embedding
            
        except Exception as e:
            logger.error(f"Embedding generation failed: {e}")
            raise
    
    async def _async_embed_query(self, text: str) -> Optional[List[float]]:
        """Async version of embed_query for cache operations."""
        if self.cache_manager:
            return await self.cache_manager.redis_manager.get_cached_embeddings(text)
        return None
    
    def embed_documents(self, texts: List[str]) -> List[List[float]]:
        """Embed multiple documents with caching."""
        embeddings = []
        for text in texts:
            embedding = self.embed_query(text)
            embeddings.append(embedding)
        return embeddings


class EnhancedVectorStoreRetriever(BaseRetriever):
    """Enhanced vector store retriever with additional features."""
    
    def __init__(self, vectorstore, callback_handler: QueryCallbackHandler = None, search_kwargs: Dict = None):
        super().__init__()
        self.vectorstore = vectorstore
        self.callback_handler = callback_handler
        self.search_kwargs = search_kwargs or {"k": 5}
    
    def _get_relevant_documents(self, query: str) -> List[Document]:
        """Get relevant documents with callback handling."""
        if self.callback_handler:
            self.callback_handler.on_retriever_start({}, query)
        
        try:
            # Use similarity search with scores for better relevance information
            docs_with_scores = self.vectorstore.similarity_search_with_score(
                query, 
                k=self.search_kwargs.get('k', 5)
            )
            
            # Convert to Document objects with score metadata
            documents = []
            for doc, score in docs_with_scores:
                # Add score to metadata
                doc.metadata['relevance_score'] = float(score)
                documents.append(doc)
            
            if self.callback_handler:
                self.callback_handler.on_retriever_end(documents)
            
            return documents
            
        except Exception as e:
            if self.callback_handler:
                self.callback_handler.on_retriever_error(e)
            raise


class QueryProcessor:
    """LangChain-based query processor with vector retrieval."""
    
    def __init__(self, cache_manager: CacheManager = None):
        self.config = get_config()
        self.cache_manager = cache_manager
        self.callback_handler = QueryCallbackHandler(self)
        
        # Initialize components
        self.embeddings: Optional[WorkingOpenAIEmbeddings] = None
        self.vectorstore: Optional[LangChainPinecone] = None
        self.retriever: Optional[EnhancedVectorStoreRetriever] = None
        self.pinecone_index = None
        
        self._initialized = False
    
    async def initialize(self):
        """Initialize the query processor."""
        if self._initialized:
            return
        
        try:
            logger.info("Initializing query processor...")
            
            # Initialize cache manager if not provided
            if not self.cache_manager:
                self.cache_manager = await get_cache_manager()
            
            # Initialize embeddings with cache
            self.embeddings = WorkingOpenAIEmbeddings(
                cache_manager=self.cache_manager,
                model=self.config.openai.embedding_model
            )
            
            # Test embeddings
            test_embedding = self.embeddings.embed_query("test")
            logger.info(f"✅ OpenAI embeddings working (dimension: {len(test_embedding)})")
            
            # Initialize Pinecone
            pc = Pinecone(api_key=self.config.pinecone.api_key)
            
            # Get existing index
            index_name = self.config.pinecone.index_name
            existing_indexes = [index.name for index in pc.list_indexes()]
            
            if index_name not in existing_indexes:
                raise ValueError(f"Pinecone index '{index_name}' not found. Please run interactive_ingestion.py first to create and populate the index.")
            
            self.pinecone_index = pc.Index(index_name)
            logger.info("✅ Connected to existing Pinecone index")
            
            # Create LangChain Pinecone vectorstore
            self.vectorstore = LangChainPinecone(
                index=self.pinecone_index,
                embedding=self.embeddings,
                text_key="text"  # The metadata key where document text is stored
            )
            
            # Create enhanced retriever
            self.retriever = EnhancedVectorStoreRetriever(
                vectorstore=self.vectorstore,
                callback_handler=self.callback_handler,
                search_kwargs={"k": 5}  # Default top-k
            )
            
            self._initialized = True
            logger.info("✅ Query processor initialized successfully")
            
        except Exception as e:
            logger.error(f"Failed to initialize query processor: {e}")
            raise
    
    async def retrieve_documents(self, query: str, top_k: int = 5) -> List[SourceDocument]:
        """Retrieve relevant documents for a query."""
        if not self._initialized:
            await self.initialize()
        
        try:
            # Update retriever search parameters
            self.retriever.search_kwargs = {"k": top_k}
            
            # Get relevant documents
            documents = self.retriever.get_relevant_documents(query)
            
            # Convert to SourceDocument objects
            source_docs = []
            for doc in documents:
                score = doc.metadata.get('relevance_score', 0.0)
                source_doc = SourceDocument.from_langchain_document(doc, score)
                source_docs.append(source_doc)
            
            # Sort by relevance score (higher is better for cosine similarity)
            source_docs.sort(key=lambda x: x.relevance_score, reverse=True)
            
            logger.info(f"Retrieved {len(source_docs)} documents for query: {query[:50]}...")
            return source_docs
            
        except Exception as e:
            logger.error(f"Document retrieval failed: {e}")
            return []
    
    async def get_query_embedding(self, query: str) -> List[float]:
        """Get embedding for a query."""
        if not self._initialized:
            await self.initialize()
        
        try:
            return self.embeddings.embed_query(query)
        except Exception as e:
            logger.error(f"Query embedding failed: {e}")
            return []
    
    async def similarity_search_with_scores(self, query: str, top_k: int = 5) -> List[Tuple[SourceDocument, float]]:
        """Perform similarity search and return documents with scores."""
        if not self._initialized:
            await self.initialize()
        
        try:
            # Use vectorstore directly for similarity search with scores
            docs_with_scores = self.vectorstore.similarity_search_with_score(query, k=top_k)
            
            results = []
            for doc, score in docs_with_scores:
                source_doc = SourceDocument.from_langchain_document(doc, float(score))
                results.append((source_doc, float(score)))
            
            return results
            
        except Exception as e:
            logger.error(f"Similarity search failed: {e}")
            return []
    
    async def get_document_by_id(self, doc_id: str) -> Optional[SourceDocument]:
        """Get a specific document by ID."""
        if not self._initialized:
            await self.initialize()
        
        try:
            # Query Pinecone directly for specific document
            result = self.pinecone_index.fetch(ids=[doc_id])
            
            if doc_id in result['vectors']:
                vector_data = result['vectors'][doc_id]
                metadata = vector_data.get('metadata', {})
                
                return SourceDocument(
                    content=metadata.get('text', ''),
                    metadata=metadata,
                    relevance_score=1.0,  # Perfect match
                    source_type=metadata.get('source_type', 'unknown'),
                    source_path=metadata.get('source_path', 'unknown')
                )
            
            return None
            
        except Exception as e:
            logger.error(f"Document fetch failed for ID {doc_id}: {e}")
            return None
    
    async def get_index_stats(self) -> Dict[str, Any]:
        """Get statistics about the vector index."""
        if not self._initialized:
            await self.initialize()
        
        try:
            stats = self.pinecone_index.describe_index_stats()
            return {
                'total_vectors': stats.get('total_vector_count', 0),
                'dimension': stats.get('dimension', 1536),
                'index_fullness': stats.get('index_fullness', 0),
                'namespaces': stats.get('namespaces', {}),
                'timestamp': time.time()
            }
        except Exception as e:
            logger.error(f"Failed to get index stats: {e}")
            return {'error': str(e)}
    
    def get_retriever(self) -> Optional[EnhancedVectorStoreRetriever]:
        """Get the LangChain retriever for use in chains."""
        return self.retriever if self._initialized else None
    
    def get_vectorstore(self) -> Optional[LangChainPinecone]:
        """Get the LangChain vectorstore for direct access."""
        return self.vectorstore if self._initialized else None
    
    async def health_check(self) -> bool:
        """Check if the query processor is healthy."""
        try:
            if not self._initialized:
                return False
            
            # Test embedding generation
            test_embedding = self.embeddings.embed_query("health check")
            if not test_embedding or len(test_embedding) != 1536:
                return False
            
            # Test Pinecone connection
            stats = self.pinecone_index.describe_index_stats()
            if not stats:
                return False
            
            return True
            
        except Exception as e:
            logger.error(f"Health check failed: {e}")
            return False
    
    async def close(self):
        """Clean up query processor resources."""
        self._initialized = False
        self.embeddings = None
        self.vectorstore = None
        self.retriever = None
        self.pinecone_index = None
        logger.info("Query processor closed")


# Global query processor instance
_query_processor = None


async def get_query_processor() -> QueryProcessor:
    """Get or create query processor instance."""
    global _query_processor
    
    if _query_processor is None:
        _query_processor = QueryProcessor()
        await _query_processor.initialize()
    
    return _query_processor


async def close_query_processor():
    """Close query processor."""
    global _query_processor
    
    if _query_processor:
        await _query_processor.close()
        _query_processor = None