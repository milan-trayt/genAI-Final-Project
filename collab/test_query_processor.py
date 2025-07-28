#!/usr/bin/env python3
"""
Unit tests for QueryProcessor using LangChain chain testing frameworks.
"""

import asyncio
import pytest
from unittest.mock import AsyncMock, MagicMock, patch
import numpy as np

from langchain.schema import Document
from langchain.vectorstores import Pinecone as LangChainPinecone

from query_processor import QueryProcessor, SourceDocument, WorkingOpenAIEmbeddings, EnhancedVectorStoreRetriever
from cache_manager import CacheManager


class TestQueryProcessor:
    """Test cases for QueryProcessor."""
    
    @pytest.fixture
    def mock_config(self):
        """Mock configuration."""
        config = MagicMock()
        config.openai.embedding_model = "text-embedding-ada-002"
        config.pinecone.api_key = "test-api-key"
        config.pinecone.index_name = "test-index"
        return config
    
    @pytest.fixture
    def mock_cache_manager(self):
        """Mock cache manager."""
        cache_manager = AsyncMock(spec=CacheManager)
        cache_manager.redis_manager.get_cached_embeddings.return_value = None
        cache_manager.redis_manager.cache_embeddings.return_value = True
        return cache_manager
    
    @pytest.fixture
    def mock_pinecone_index(self):
        """Mock Pinecone index."""
        index = MagicMock()
        index.describe_index_stats.return_value = {
            'total_vector_count': 1000,
            'dimension': 1536,
            'index_fullness': 0.1,
            'namespaces': {}
        }
        index.fetch.return_value = {
            'vectors': {
                'test_doc_1': {
                    'metadata': {
                        'text': 'Test document content',
                        'source_type': 'test',
                        'source_path': 'test/path'
                    }
                }
            }
        }
        return index
    
    @pytest.fixture
    def mock_vectorstore(self):
        """Mock LangChain vectorstore."""
        vectorstore = MagicMock(spec=LangChainPinecone)
        
        # Mock similarity search with scores
        test_docs = [
            (Document(
                page_content="Test document 1",
                metadata={'source_type': 'test', 'source_path': 'test/path1', 'relevance_score': 0.9}
            ), 0.9),
            (Document(
                page_content="Test document 2", 
                metadata={'source_type': 'test', 'source_path': 'test/path2', 'relevance_score': 0.8}
            ), 0.8)
        ]
        
        vectorstore.similarity_search_with_score.return_value = test_docs
        return vectorstore
    
    @pytest.fixture
    async def query_processor(self, mock_cache_manager):
        """Create QueryProcessor with mocked dependencies."""
        processor = QueryProcessor(mock_cache_manager)
        
        # Mock the initialization to avoid actual API calls
        with patch.object(processor, '_initialized', True), \
             patch.object(processor, 'embeddings') as mock_embeddings, \
             patch.object(processor, 'vectorstore') as mock_vectorstore, \
             patch.object(processor, 'retriever') as mock_retriever, \
             patch.object(processor, 'pinecone_index') as mock_index:
            
            # Setup mock embeddings
            mock_embeddings.embed_query.return_value = [0.1] * 1536
            
            # Setup mock vectorstore
            mock_vectorstore.similarity_search_with_score.return_value = [
                (Document(page_content="Test content", metadata={'source_type': 'test', 'source_path': 'test'}), 0.9)
            ]
            
            # Setup mock retriever
            mock_retriever.get_relevant_documents.return_value = [
                Document(page_content="Test content", metadata={'source_type': 'test', 'source_path': 'test', 'relevance_score': 0.9})
            ]
            
            # Setup mock index
            mock_index.describe_index_stats.return_value = {
                'total_vector_count': 1000,
                'dimension': 1536,
                'index_fullness': 0.1
            }
            
            yield processor
    
    @pytest.mark.asyncio
    async def test_retrieve_documents(self, query_processor):
        """Test document retrieval."""
        query = "What is Python?"
        top_k = 3
        
        documents = await query_processor.retrieve_documents(query, top_k)
        
        assert len(documents) == 1
        assert isinstance(documents[0], SourceDocument)
        assert documents[0].content == "Test content"
        assert documents[0].source_type == "test"
        assert documents[0].relevance_score == 0.9
    
    @pytest.mark.asyncio
    async def test_get_query_embedding(self, query_processor):
        """Test query embedding generation."""
        query = "Test query"
        
        embedding = await query_processor.get_query_embedding(query)
        
        assert len(embedding) == 1536
        assert all(isinstance(x, float) for x in embedding)
    
    @pytest.mark.asyncio
    async def test_similarity_search_with_scores(self, query_processor):
        """Test similarity search with scores."""
        query = "Test query"
        top_k = 2
        
        results = await query_processor.similarity_search_with_scores(query, top_k)
        
        assert len(results) == 1
        doc, score = results[0]
        assert isinstance(doc, SourceDocument)
        assert isinstance(score, float)
        assert score == 0.9
    
    @pytest.mark.asyncio
    async def test_get_document_by_id(self, query_processor):
        """Test getting document by ID."""
        doc_id = "test_doc_1"
        
        # Mock the fetch response
        query_processor.pinecone_index.fetch.return_value = {
            'vectors': {
                doc_id: {
                    'metadata': {
                        'text': 'Test document content',
                        'source_type': 'test',
                        'source_path': 'test/path'
                    }
                }
            }
        }
        
        document = await query_processor.get_document_by_id(doc_id)
        
        assert document is not None
        assert isinstance(document, SourceDocument)
        assert document.content == 'Test document content'
        assert document.source_type == 'test'
        assert document.relevance_score == 1.0  # Perfect match
    
    @pytest.mark.asyncio
    async def test_get_index_stats(self, query_processor):
        """Test getting index statistics."""
        stats = await query_processor.get_index_stats()
        
        assert 'total_vectors' in stats
        assert 'dimension' in stats
        assert 'index_fullness' in stats
        assert stats['total_vectors'] == 1000
        assert stats['dimension'] == 1536
    
    @pytest.mark.asyncio
    async def test_health_check(self, query_processor):
        """Test health check."""
        is_healthy = await query_processor.health_check()
        
        assert is_healthy is True


class TestWorkingOpenAIEmbeddings:
    """Test cases for WorkingOpenAIEmbeddings."""
    
    @pytest.fixture
    def mock_cache_manager(self):
        """Mock cache manager."""
        cache_manager = AsyncMock(spec=CacheManager)
        cache_manager.redis_manager.get_cached_embeddings.return_value = None
        cache_manager.redis_manager.cache_embeddings.return_value = True
        return cache_manager
    
    @pytest.fixture
    def embeddings(self, mock_cache_manager):
        """Create WorkingOpenAIEmbeddings with mocked dependencies."""
        with patch('openai.OpenAI') as mock_openai:
            # Mock OpenAI client response
            mock_response = MagicMock()
            mock_response.data = [MagicMock()]
            mock_response.data[0].embedding = [0.1] * 1536
            
            mock_client = MagicMock()
            mock_client.embeddings.create.return_value = mock_response
            mock_openai.return_value = mock_client
            
            embeddings = WorkingOpenAIEmbeddings(cache_manager=mock_cache_manager)
            embeddings.client = mock_client
            
            return embeddings
    
    def test_embed_query(self, embeddings):
        """Test embedding a single query."""
        query = "What is machine learning?"
        
        embedding = embeddings.embed_query(query)
        
        assert len(embedding) == 1536
        assert all(isinstance(x, float) for x in embedding)
        assert embedding[0] == 0.1
    
    def test_embed_documents(self, embeddings):
        """Test embedding multiple documents."""
        texts = ["Document 1", "Document 2", "Document 3"]
        
        embeddings_list = embeddings.embed_documents(texts)
        
        assert len(embeddings_list) == 3
        for embedding in embeddings_list:
            assert len(embedding) == 1536
            assert all(isinstance(x, float) for x in embedding)


class TestEnhancedVectorStoreRetriever:
    """Test cases for EnhancedVectorStoreRetriever."""
    
    @pytest.fixture
    def mock_vectorstore(self):
        """Mock vectorstore."""
        vectorstore = MagicMock()
        
        # Mock similarity search with scores
        test_docs_with_scores = [
            (Document(
                page_content="Test document 1",
                metadata={'source_type': 'test', 'source_path': 'test/path1'}
            ), 0.9),
            (Document(
                page_content="Test document 2",
                metadata={'source_type': 'test', 'source_path': 'test/path2'}
            ), 0.8)
        ]
        
        vectorstore.similarity_search_with_score.return_value = test_docs_with_scores
        return vectorstore
    
    @pytest.fixture
    def retriever(self, mock_vectorstore):
        """Create EnhancedVectorStoreRetriever."""
        return EnhancedVectorStoreRetriever(
            vectorstore=mock_vectorstore,
            search_kwargs={"k": 5}
        )
    
    def test_get_relevant_documents(self, retriever, mock_vectorstore):
        """Test getting relevant documents."""
        query = "Test query"
        
        documents = retriever.get_relevant_documents(query)
        
        assert len(documents) == 2
        for doc in documents:
            assert isinstance(doc, Document)
            assert 'relevance_score' in doc.metadata
        
        # Check that scores were added to metadata
        assert documents[0].metadata['relevance_score'] == 0.9
        assert documents[1].metadata['relevance_score'] == 0.8
        
        # Verify vectorstore was called correctly
        mock_vectorstore.similarity_search_with_score.assert_called_once_with(query, k=5)


class TestSourceDocument:
    """Test cases for SourceDocument."""
    
    def test_from_langchain_document(self):
        """Test creating SourceDocument from LangChain Document."""
        langchain_doc = Document(
            page_content="Test content",
            metadata={
                'source_type': 'web',
                'source_path': 'https://example.com',
                'title': 'Test Document'
            }
        )
        
        source_doc = SourceDocument.from_langchain_document(langchain_doc, score=0.85)
        
        assert source_doc.content == "Test content"
        assert source_doc.source_type == "web"
        assert source_doc.source_path == "https://example.com"
        assert source_doc.relevance_score == 0.85
        assert source_doc.metadata['title'] == 'Test Document'
    
    def test_from_langchain_document_with_defaults(self):
        """Test creating SourceDocument with default values."""
        langchain_doc = Document(
            page_content="Test content",
            metadata={}
        )
        
        source_doc = SourceDocument.from_langchain_document(langchain_doc)
        
        assert source_doc.content == "Test content"
        assert source_doc.source_type == "unknown"
        assert source_doc.source_path == "unknown"
        assert source_doc.relevance_score == 0.0


if __name__ == "__main__":
    # Run tests
    pytest.main([__file__, "-v"])