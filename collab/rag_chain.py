#!/usr/bin/env python3
"""
LangChain RAG chain for response generation with comprehensive prompt templates and output parsing.
"""

import asyncio
import logging
import time
from typing import List, Dict, Any, Optional, Union

from langchain.chains import RetrievalQA, ConversationalRetrievalChain
from langchain.chains.base import Chain
from langchain.chains.combine_documents import create_stuff_documents_chain
from langchain.chains.retrieval import create_retrieval_chain
from langchain.prompts import PromptTemplate, ChatPromptTemplate, MessagesPlaceholder
from langchain.schema import BaseMessage, HumanMessage, AIMessage, Document
from langchain.schema.output_parser import BaseOutputParser, OutputParserException
from langchain.memory import ConversationBufferMemory, ConversationSummaryMemory
from langchain.callbacks.base import BaseCallbackHandler
from langchain.llms.base import BaseLLM
from langchain_openai import ChatOpenAI

import openai
import httpx
import json
import re

from config import get_config
from query_processor import QueryProcessor, SourceDocument, QueryResult
from session_manager import SessionManager
from cache_manager import CacheManager

logger = logging.getLogger(__name__)


class SourceCitationParser(BaseOutputParser):
    """Output parser for structured source citations."""
    
    def parse(self, text: str) -> Dict[str, Any]:
        """Parse response text to extract answer and sources."""
        try:
            # Try to find structured response with sources
            answer_match = re.search(r'Answer:\s*(.*?)(?=Sources:|$)', text, re.DOTALL)
            sources_match = re.search(r'Sources:\s*(.*)', text, re.DOTALL)
            
            answer = answer_match.group(1).strip() if answer_match else text.strip()
            sources_text = sources_match.group(1).strip() if sources_match else ""
            
            # Parse sources if found
            sources = []
            if sources_text:
                # Look for numbered sources like "1. Source name - description"
                source_lines = re.findall(r'\d+\.\s*([^\n]+)', sources_text)
                sources = [line.strip() for line in source_lines]
            
            return {
                'answer': answer,
                'sources': sources,
                'raw_response': text
            }
            
        except Exception as e:
            logger.warning(f"Failed to parse response: {e}")
            return {
                'answer': text,
                'sources': [],
                'raw_response': text
            }
    
    @property
    def _type(self) -> str:
        return "source_citation"


class WorkingChatOpenAI(ChatOpenAI):
    """Enhanced ChatOpenAI with custom client to avoid proxy issues."""
    
    def __init__(self, **kwargs):
        config = get_config()
        # Initialize with the API key from config
        super().__init__(
            openai_api_key=config.openai.api_key,
            **kwargs
        )


class RAGCallbackHandler(BaseCallbackHandler):
    """Callback handler for RAG chain events."""
    
    def __init__(self, rag_chain: 'RAGChain'):
        self.rag_chain = rag_chain
        self.start_time = None
        self.retrieval_time = None
        self.generation_time = None
        self.total_tokens = 0
    
    def on_chain_start(self, serialized: Dict[str, Any], inputs: Dict[str, Any], **kwargs) -> None:
        """Called when chain starts."""
        self.start_time = time.time()
        query = inputs.get('question', inputs.get('query', 'Unknown'))
        logger.debug(f"Starting RAG chain for query: {query[:50]}...")
    
    def on_chain_end(self, outputs: Dict[str, Any], **kwargs) -> None:
        """Called when chain ends."""
        if self.start_time:
            total_time = time.time() - self.start_time
            logger.debug(f"RAG chain completed in {total_time:.2f}s")
    
    def on_chain_error(self, error: Exception, **kwargs) -> None:
        """Called when chain errors."""
        logger.error(f"RAG chain error: {error}")
    
    def on_llm_start(self, serialized: Dict[str, Any], prompts: List[str], **kwargs) -> None:
        """Called when LLM starts."""
        self.generation_start = time.time()
        logger.debug("Starting response generation")
    
    def on_llm_end(self, response, **kwargs) -> None:
        """Called when LLM ends."""
        if hasattr(self, 'generation_start'):
            self.generation_time = time.time() - self.generation_start
            logger.debug(f"Response generation completed in {self.generation_time:.2f}s")
            
            # Track token usage if available
            if hasattr(response, 'llm_output') and response.llm_output:
                token_usage = response.llm_output.get('token_usage', {})
                self.total_tokens += token_usage.get('total_tokens', 0)


class RAGChain:
    """Comprehensive RAG chain with multiple modes and configurations."""
    
    def __init__(self, 
                 query_processor: QueryProcessor,
                 session_manager: SessionManager = None,
                 cache_manager: CacheManager = None):
        self.config = get_config()
        self.query_processor = query_processor
        self.session_manager = session_manager
        self.cache_manager = cache_manager
        self.callback_handler = RAGCallbackHandler(self)
        
        # Initialize LLM
        self.llm = WorkingChatOpenAI(
            model=self.config.openai.model,
            temperature=self.config.openai.temperature,
            max_tokens=self.config.openai.max_tokens,
            callbacks=[self.callback_handler]
        )
        
        # Initialize chains
        self.qa_chain: Optional[RetrievalQA] = None
        self.conversational_chain: Optional[ConversationalRetrievalChain] = None
        self.output_parser = SourceCitationParser()
        
        self._initialized = False
    
    async def initialize(self):
        """Initialize RAG chains."""
        if self._initialized:
            return
        
        try:
            logger.info("Initializing RAG chains...")
            
            # Ensure query processor is initialized
            if not self.query_processor._initialized:
                await self.query_processor.initialize()
            
            # Create prompt templates
            self._create_prompt_templates()
            
            # Create QA chain for one-time queries
            self.qa_chain = RetrievalQA.from_chain_type(
                llm=self.llm,
                chain_type="stuff",
                retriever=self.query_processor.get_retriever(),
                chain_type_kwargs={
                    "prompt": self.qa_prompt,
                    "document_variable_name": "context"
                },
                return_source_documents=True,
                callbacks=[self.callback_handler]
            )
            
            # Create conversational chain for context-aware queries
            self.conversational_chain = ConversationalRetrievalChain.from_llm(
                llm=self.llm,
                retriever=self.query_processor.get_retriever(),
                combine_docs_chain_kwargs={
                    "prompt": self.conversational_prompt
                },
                return_source_documents=True,
                callbacks=[self.callback_handler]
            )
            
            self._initialized = True
            logger.info("RAG chains initialized successfully")
            
        except Exception as e:
            logger.error(f"Failed to initialize RAG chains: {e}")
            raise
    
    def _create_prompt_templates(self):
        """Create prompt templates for different query types."""
        
        # One-time query prompt
        qa_template = """You are a helpful AI assistant specializing in DevOps, cloud infrastructure, and software development. Use the following context to answer the question accurately and comprehensively.

Context:
{context}

Question: {question}

Instructions:
1. Provide a clear, detailed answer based on the context provided
2. If the context doesn't contain enough information, say so clearly
3. Include specific examples or code snippets when relevant
4. Cite the sources you used from the context

Answer: [Your detailed answer here]"""

        self.qa_prompt = PromptTemplate(
            template=qa_template,
            input_variables=["context", "question"]
        )
        
        # Conversational query prompt
        conversational_template = """You are a helpful AI assistant specializing in DevOps, cloud infrastructure, and software development. You have access to a knowledge base and can see the conversation history.

Use the following context and conversation history to answer the question accurately and comprehensively.

Context:
{context}

Chat History:
{chat_history}

Current Question: {question}

Instructions:
1. Consider the conversation history for context and continuity
2. Use the provided context to give accurate, detailed answers
3. If referring to previous parts of the conversation, be explicit
4. If the context doesn't contain enough information, say so clearly
5. Include specific examples or code snippets when relevant
6. Maintain a helpful and professional tone

Answer: [Your detailed answer here]

Sources:
[List the sources you referenced from the context, numbered 1, 2, 3, etc.]"""

        self.conversational_prompt = PromptTemplate(
            template=conversational_template,
            input_variables=["context", "chat_history", "question"]
        )
        
        # Streaming prompt for real-time responses
        self.streaming_prompt = ChatPromptTemplate.from_messages([
            ("system", """You are a helpful AI assistant specializing in DevOps, cloud infrastructure, and software development. 
            
Use the provided context to answer questions accurately. Always cite your sources and provide practical examples when possible."""),
            MessagesPlaceholder(variable_name="chat_history"),
            ("human", "{question}"),
            ("system", "Context: {context}")
        ])
    
    async def query_oneshot(self, question: str, top_k: int = 5) -> QueryResult:
        """Process a one-time query without conversation history."""
        if not self._initialized:
            await self.initialize()
        
        start_time = time.time()
        
        try:
            # Check semantic cache first
            if self.cache_manager:
                semantic_cache = self.cache_manager.get_semantic_cache()
                query_embedding = await self.query_processor.get_query_embedding(question)
                cached_response = await semantic_cache.get_similar_response(query_embedding, question)
                
                if cached_response:
                    logger.info(f"Using cached response for query: {question[:50]}...")
                    return QueryResult(
                        response=cached_response,
                        sources=[],
                        processing_time=time.time() - start_time,
                        cached=True,
                        query_embedding=query_embedding
                    )
            
            # Update retriever search parameters
            self.query_processor.retriever.search_kwargs = {"k": top_k}
            
            # Run QA chain
            result = self.qa_chain.invoke({"query": question})
            
            # Extract response and sources
            response_text = result.get('result', '')
            source_documents = result.get('source_documents', [])
            
            # Parse response for structured output
            parsed_output = self.output_parser.parse(response_text)
            final_response = parsed_output['answer']
            
            # Convert source documents
            sources = []
            for doc in source_documents:
                source = SourceDocument.from_langchain_document(
                    doc, 
                    doc.metadata.get('relevance_score', 0.0)
                )
                sources.append(source)
            
            processing_time = time.time() - start_time
            
            # Cache the response
            if self.cache_manager:
                semantic_cache = self.cache_manager.get_semantic_cache()
                query_embedding = await self.query_processor.get_query_embedding(question)
                await semantic_cache.cache_semantic_response(
                    query_embedding, question, final_response
                )
            
            logger.info(f"One-shot query completed in {processing_time:.2f}s")
            
            return QueryResult(
                response=final_response,
                sources=sources,
                processing_time=processing_time,
                cached=False,
                query_embedding=query_embedding if 'query_embedding' in locals() else None
            )
            
        except Exception as e:
            logger.error(f"One-shot query failed: {e}")
            return QueryResult(
                response=f"I apologize, but I encountered an error processing your query: {str(e)}",
                sources=[],
                processing_time=time.time() - start_time,
                cached=False
            )
    
    async def query_conversational(self, question: str, session_id: str, top_k: int = 5) -> QueryResult:
        """Process a conversational query with history."""
        if not self._initialized:
            await self.initialize()
        
        if not self.session_manager:
            logger.warning("No session manager available, falling back to one-shot query")
            return await self.query_oneshot(question, top_k)
        
        start_time = time.time()
        
        try:
            # Get conversation memory
            memory = self.session_manager.get_memory(session_id)
            if not memory:
                logger.warning(f"No memory found for session {session_id}, creating new session")
                await self.session_manager.create_session("default", f"Session {session_id}")
                memory = self.session_manager.get_memory(session_id)
            
            # Update retriever search parameters
            self.query_processor.retriever.search_kwargs = {"k": top_k}
            
            # Get chat history for the chain
            chat_history = []
            if memory and hasattr(memory, 'chat_memory'):
                messages = memory.chat_memory.messages
                for i in range(0, len(messages) - 1, 2):  # Process pairs of human/ai messages
                    if i + 1 < len(messages):
                        human_msg = messages[i]
                        ai_msg = messages[i + 1]
                        chat_history.append((human_msg.content, ai_msg.content))
            
            # Run conversational chain
            result = self.conversational_chain.invoke({
                "question": question,
                "chat_history": chat_history
            })
            
            # Extract response and sources
            response_text = result.get('answer', '')
            source_documents = result.get('source_documents', [])
            
            # Parse response for structured output
            parsed_output = self.output_parser.parse(response_text)
            final_response = parsed_output['answer']
            
            # Convert source documents
            sources = []
            for doc in source_documents:
                source = SourceDocument.from_langchain_document(
                    doc, 
                    doc.metadata.get('relevance_score', 0.0)
                )
                sources.append(source)
            
            # Add messages to session
            await self.session_manager.add_user_message(question, session_id)
            await self.session_manager.add_ai_message(final_response, session_id)
            
            processing_time = time.time() - start_time
            
            logger.info(f"Conversational query completed in {processing_time:.2f}s")
            
            return QueryResult(
                response=final_response,
                sources=sources,
                processing_time=processing_time,
                cached=False
            )
            
        except Exception as e:
            logger.error(f"Conversational query failed: {e}")
            return QueryResult(
                response=f"I apologize, but I encountered an error processing your query: {str(e)}",
                sources=[],
                processing_time=time.time() - start_time,
                cached=False
            )
    
    async def stream_response(self, question: str, session_id: str = None):
        """Stream response for real-time interaction."""
        if not self._initialized:
            await self.initialize()
        
        try:
            # Get relevant documents
            sources = await self.query_processor.retrieve_documents(question)
            context = "\n\n".join([f"Source: {s.source_path}\n{s.content}" for s in sources[:3]])
            
            # Get chat history if session provided
            chat_history = []
            if session_id and self.session_manager:
                context_str = await self.session_manager.get_conversation_context(session_id, max_messages=6)
                if context_str:
                    # Parse context into message pairs
                    lines = context_str.split('\n')
                    for line in lines:
                        if line.startswith('Human: '):
                            chat_history.append(HumanMessage(content=line[7:]))
                        elif line.startswith('Assistant: '):
                            chat_history.append(AIMessage(content=line[11:]))
            
            # Create streaming chain (simplified for demo)
            prompt_value = self.streaming_prompt.format_prompt(
                question=question,
                context=context,
                chat_history=chat_history
            )
            
            # Stream response (this is a simplified version)
            response = self.llm.predict(prompt_value.to_string())
            
            # Yield response in chunks (simulate streaming)
            words = response.split()
            for i, word in enumerate(words):
                yield word + (" " if i < len(words) - 1 else "")
                await asyncio.sleep(0.05)  # Simulate streaming delay
                
        except Exception as e:
            logger.error(f"Streaming response failed: {e}")
            yield f"Error: {str(e)}"
    
    def get_chain_stats(self) -> Dict[str, Any]:
        """Get statistics about chain performance."""
        return {
            'total_tokens': self.callback_handler.total_tokens,
            'retrieval_time': self.callback_handler.retrieval_time,
            'generation_time': self.callback_handler.generation_time,
            'initialized': self._initialized,
            'timestamp': time.time()
        }
    
    async def close(self):
        """Clean up RAG chain resources."""
        self._initialized = False
        self.qa_chain = None
        self.conversational_chain = None
        logger.info("RAG chain closed")


# Global RAG chain instance
_rag_chain = None


async def get_rag_chain(query_processor: QueryProcessor = None, 
                       session_manager: SessionManager = None,
                       cache_manager: CacheManager = None) -> RAGChain:
    """Get or create RAG chain instance."""
    global _rag_chain
    
    if _rag_chain is None:
        if not query_processor:
            from query_processor import get_query_processor
            query_processor = await get_query_processor()
        
        _rag_chain = RAGChain(query_processor, session_manager, cache_manager)
        await _rag_chain.initialize()
    
    return _rag_chain


async def close_rag_chain():
    """Close RAG chain."""
    global _rag_chain
    
    if _rag_chain:
        await _rag_chain.close()
        _rag_chain = None