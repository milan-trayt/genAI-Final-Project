#!/usr/bin/env python3
"""
LangChain RAG chain for response generation with comprehensive prompt templates and output parsing.
"""

import asyncio
import logging
import time
from datetime import datetime
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
            
            # Create guardrail chains for each mode
            self.guardrail_chains = {}
            for mode, prompt in self.guardrail_prompts.items():
                self.guardrail_chains[mode] = prompt | self.llm
            
            # Create keyword extraction chain
            self.keyword_chain = self.keyword_extraction_prompt | self.llm
            
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
            logger.info("✅ RAG chains initialized successfully")
            
        except Exception as e:
            logger.error(f"Failed to initialize RAG chains: {e}")
            raise
    
    def _create_prompt_templates(self):
        """Create prompt templates for different query types."""
        
        # Mode-specific guardrail prompts
        self.guardrail_prompts = {
            "general": PromptTemplate(
                template="""Evaluate this question for AWS/DevOps assistance:

{question}

APPROVE if:
- About AWS services, pricing, architecture, deployment
- Cloud infrastructure or DevOps topics
- Terraform or Infrastructure-as-Code
- Follow-up requests like "give me architecture" or "create solution" when previous context mentions AWS/technical topics
- Technical questions or conversation management

REJECT if:
- About cooking, food, recipes, sports, entertainment
- Personal advice, relationships, health
- Non-technical topics with no AWS/technical context

Respond exactly "APPROVED" or "REJECTED":""",
                input_variables=["question"]
            ),
            "service_recommendation": PromptTemplate(
                template="""Evaluate this question for AWS service recommendations:

{question}

APPROVE if:
- About AWS services, architecture, or infrastructure
- Follow-up requests like "give me architecture" or "recommend services" when previous context mentions AWS/technical topics
- Contains technical terms or AWS context

REJECT if:
- About cooking, food, recipes, sports, entertainment
- Non-technical topics with no AWS/technical context

Respond exactly "APPROVED" or "REJECTED":""",
                input_variables=["question"]
            ),
            "pricing": PromptTemplate(
                template="""Evaluate this question for AWS pricing:

{question}

If the question mentions "Previous conversation context: AWS" or contains AWS context, then APPROVE requests for:
- "create invoice", "pricing invoice", "cost breakdown", "billing estimate"
- AWS pricing, costs, or billing information
- Cost optimization for AWS services

Always APPROVE if:
- About AWS pricing, costs, or billing
- Invoice/billing requests when AWS/infrastructure context is present

REJECT only if:
- About cooking, food, recipes, sports, entertainment with no AWS context

Respond exactly "APPROVED" or "REJECTED":""",
                input_variables=["question"]
            ),
            "terraform": PromptTemplate(
                template="""Evaluate this question for Terraform/Infrastructure:

{question}

APPROVE if:
- About Terraform, Infrastructure-as-Code, or deployment
- Infrastructure automation requests
- Follow-up requests like "create terraform" or "deploy this" when previous context mentions AWS/technical topics

REJECT if:
- About cooking, food, recipes, sports, entertainment
- Non-technical topics with no infrastructure context

Respond exactly "APPROVED" or "REJECTED":""",
                input_variables=["question"]
            )
        }
        
        # Mode-specific query prompts
        self.qa_prompts = {
            "general": """You are an AWS Solutions Architect providing professional guidance on AWS concepts and services. Deliver comprehensive, well-structured responses.

Context: {context}
Question: {question}

Provide a professional response that:
- Explains concepts thoroughly with relevant context
- Includes practical examples and use cases
- Demonstrates deep technical understanding
- Maintains a professional, consultative tone

Answer:""",
            
            "service_recommendation": """You are an AWS Service Recommendation Specialist providing expert guidance on optimal AWS service selection. Deliver professional, well-reasoned recommendations.

Context: {context}
Question: {question}

Provide professional service recommendations by:
- Analyzing requirements and explaining service alignment
- Detailing service integration and architecture patterns
- Presenting comprehensive benefits and trade-off analysis
- Supporting recommendations with technical rationale
- Maintaining an expert, consultative tone

Answer:""",
            
            "pricing": """You are an AWS Cost Optimization Specialist providing expert analysis on AWS pricing and cost management strategies. Deliver comprehensive cost guidance.

Context: {context}
Question: {question}

Provide professional cost analysis by:
- Analyzing pricing models and their business impact
- Delivering detailed cost breakdowns and projections
- Recommending strategic cost optimization approaches
- Supporting analysis with concrete examples and metrics
- Maintaining a professional, advisory tone

Answer:""",
            
            "terraform": """You are a Terraform Infrastructure Specialist providing expert guidance on infrastructure as code implementation. Deliver professional, production-ready solutions.

Context: {context}
Question: {question}

Provide professional Terraform guidance by:
- Demonstrating advanced Terraform concepts and architecture
- Presenting well-structured, production-ready code examples
- Recommending enterprise-grade best practices and patterns
- Explaining technical decisions with architectural reasoning
- Maintaining an expert, professional tone

Answer:"""
        }
        
        # Create PromptTemplate objects for each mode
        self.qa_prompt_templates = {}
        for mode, template in self.qa_prompts.items():
            self.qa_prompt_templates[mode] = PromptTemplate(
                template=template,
                input_variables=["context", "question"]
            )
        
        # Default prompt for backward compatibility
        self.qa_prompt = self.qa_prompt_templates["general"]
        
        # Conversational query prompt
        conversational_template = """You are an AWS Solutions Architect providing professional consultation on AWS services and infrastructure. Build upon the conversation context professionally.

Context:
{context}

Chat History:
{chat_history}

Current Question: {question}

Provide a professional response that builds on our discussion. Maintain a consultative, expert tone while being thorough and informative.

Answer:"""

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
        
        # Keyword extraction prompt
        self.keyword_extraction_prompt = PromptTemplate(
            template="""Extract 3-5 key technical keywords from this query and context for AWS document retrieval.

Query: {query}
Context: {context}

Focus on: AWS services (EC2, S3, Lambda), technical terms (serverless, container), infrastructure components, specific technologies.

Return keywords that might match both auto-generated keywords and user custom tags.

Keywords (comma-separated):""",
            input_variables=["query", "context"]
        )
    
    def _get_mode_prompts(self, query_type: str = "general"):
        """Get appropriate prompts for the given query type."""
        mode = query_type if query_type in self.guardrail_prompts else "general"
        return {
            "guardrail": self.guardrail_chains[mode],
            "qa_prompt": self.qa_prompt_templates[mode]
        }
    
    async def query_oneshot(self, question: str, query_type: str = "general", top_k: int = 5) -> QueryResult:
        """Process a one-time query without conversation history."""
        if not self._initialized:
            await self.initialize()
        
        start_time = time.time()
        
        try:
            # Step 1: Get mode-specific prompts
            mode_prompts = self._get_mode_prompts(query_type)
            
            # Step 2: Check semantic cache
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
            
            # Step 3: Extract keywords for tag-based retrieval
            try:
                keyword_result = await self.keyword_chain.ainvoke({
                    "query": question,
                    "context": ""  # No context for one-shot
                })
                keywords = [k.strip() for k in keyword_result.content.split(",") if k.strip()]
                logger.info(f"Extracted keywords: {keywords}")
                
                # Use tag-based retrieval if keywords found, otherwise regular retrieval
                if keywords:
                    source_docs = await self.query_processor.retrieve_documents_with_tags(
                        question, keywords, top_k
                    )
                    # Additional fallback check - if tag-based returns empty, try regular
                    if not source_docs:
                        logger.info("Tag-based retrieval returned no results, using regular retrieval")
                        source_docs = await self.query_processor.retrieve_documents(question, top_k)
                else:
                    source_docs = await self.query_processor.retrieve_documents(question, top_k)
                
                # Create context from retrieved documents
                context = "\n\n".join([f"Source: {doc.source_path}\n{doc.content}" for doc in source_docs])
                
                # Generate response with filtered context
                prompt_text = mode_prompts["qa_prompt"].format(context=context, question=question)
                response = await self.llm.ainvoke(prompt_text)
                
                final_response = response.content if hasattr(response, 'content') else str(response)
                
                result = {
                    'result': final_response,
                    'source_documents': []
                }
                
            except Exception as e:
                logger.warning(f"Keyword extraction failed, using regular retrieval: {e}")
                # Fallback to regular QA chain
                self.query_processor.retriever.search_kwargs = {"k": top_k}
                
                mode_qa_chain = RetrievalQA.from_chain_type(
                    llm=self.llm,
                    chain_type="stuff",
                    retriever=self.query_processor.get_retriever(),
                    chain_type_kwargs={
                        "prompt": mode_prompts["qa_prompt"],
                        "document_variable_name": "context"
                    },
                    return_source_documents=True,
                    callbacks=[self.callback_handler]
                )
                
                result = mode_qa_chain.invoke({"query": question})
                source_docs = [SourceDocument.from_langchain_document(doc, doc.metadata.get('relevance_score', 0.0)) for doc in result.get('source_documents', [])]
            
            # Extract response and sources
            response_text = result.get('result', '')
            source_documents = result.get('source_documents', [])
            
            # Ensure response is a string
            if hasattr(response_text, 'content'):
                final_response = str(response_text.content)
            else:
                final_response = str(response_text)
            
            # Use source_docs from keyword extraction or fallback
            if 'source_docs' not in locals():
                source_documents = result.get('source_documents', [])
                sources = []
                for doc in source_documents:
                    source = SourceDocument.from_langchain_document(
                        doc, 
                        doc.metadata.get('relevance_score', 0.0)
                    )
                    sources.append(source)
            else:
                sources = source_docs
            
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
    
    async def query_conversational(self, question: str, session_id: str, query_type: str = "general", top_k: int = 5) -> QueryResult:
        """Process a conversational query with history."""
        if not self._initialized:
            await self.initialize()
        
        if not self.session_manager:
            logger.warning("No session manager available, falling back to one-shot query")
            return await self.query_oneshot(question, top_k)
        
        start_time = time.time()
        
        try:
            # Step 1: Load session and get memory first
            session_loaded = await self.session_manager.load_session(session_id)
            if not session_loaded:
                logger.warning(f"Session {session_id} not found, creating new session")
                await self.session_manager.create_session("default", f"Session {session_id}")
                await self.session_manager.load_session(session_id)
            
            # Get conversation memory
            memory = self.session_manager.get_memory(session_id)
            if not memory:
                logger.error(f"Failed to get memory for session {session_id}")
                return await self.query_oneshot(question, query_type, top_k)
            
            # Ensure messages are loaded
            await self.session_manager.ensure_messages_loaded(session_id)
            
            # Debug: Check if messages are loaded
            if hasattr(memory, 'chat_memory') and memory.chat_memory.messages:
                logger.info(f"Found {len(memory.chat_memory.messages)} messages in session {session_id}")
                for i, msg in enumerate(memory.chat_memory.messages):
                    msg_type = "Human" if isinstance(msg, HumanMessage) else "AI"
                    logger.info(f"Message {i}: {msg_type} - {msg.content[:100]}...")
            else:
                logger.info(f"No messages found in session {session_id}")
            
            # Step 2: Get mode-specific prompts
            mode_prompts = self._get_mode_prompts(query_type)
            
            # Step 3: Process query based on type
            if query_type == "service_recommendation":
                # Extract keywords from query + topics
                try:
                    keyword_result = await self.keyword_chain.ainvoke({
                        "query": question,
                        "context": conversation_topics
                    })
                    keywords = [k.strip() for k in keyword_result.content.split(",") if k.strip()]
                    logger.info(f"Extracted keywords for service recommendation: {keywords}")
                    
                    # Use tag-based retrieval
                    if keywords:
                        source_docs = await self.query_processor.retrieve_documents_with_tags(
                            question, keywords, top_k
                        )
                        if not source_docs:
                            source_docs = await self.query_processor.retrieve_documents(question, top_k)
                    else:
                        source_docs = await self.query_processor.retrieve_documents(question, top_k)
                    
                    # Generate service recommendation response
                    context = "\n\n".join([f"Source: {doc.source_path}\n{doc.content}" for doc in source_docs])
                    prompt_text = mode_prompts["qa_prompt"].format(context=context, question=question)
                    response = await self.llm.ainvoke(prompt_text)
                    
                    result = {
                        "response": response.content if hasattr(response, 'content') else str(response),
                        "processing_time": time.time() - start_time,
                        "cached": False,
                        "sources": source_docs
                    }
                except Exception as e:
                    logger.error(f"Service recommendation failed: {e}")
                    result = {
                        "response": "Error processing service recommendation request.",
                        "processing_time": time.time() - start_time,
                        "cached": False,
                        "sources": []
                    }
                    
            elif query_type == "pricing":
                # Extract keywords from query + topics
                try:
                    keyword_result = await self.keyword_chain.ainvoke({
                        "query": question,
                        "context": conversation_topics
                    })
                    keywords = [k.strip() for k in keyword_result.content.split(",") if k.strip()]
                    logger.info(f"Extracted keywords for pricing: {keywords}")
                    
                    # Use tag-based retrieval
                    if keywords:
                        source_docs = await self.query_processor.retrieve_documents_with_tags(
                            question, keywords, top_k
                        )
                        if not source_docs:
                            source_docs = await self.query_processor.retrieve_documents(question, top_k)
                    else:
                        source_docs = await self.query_processor.retrieve_documents(question, top_k)
                    
                    # Generate pricing response
                    context = "\n\n".join([f"Source: {doc.source_path}\n{doc.content}" for doc in source_docs])
                    prompt_text = mode_prompts["qa_prompt"].format(context=context, question=question)
                    response = await self.llm.ainvoke(prompt_text)
                    
                    result = {
                        "response": response.content if hasattr(response, 'content') else str(response),
                        "processing_time": time.time() - start_time,
                        "cached": False,
                        "sources": source_docs
                    }
                except Exception as e:
                    logger.error(f"Pricing query failed: {e}")
                    result = {
                        "response": "Error processing pricing request.",
                        "processing_time": time.time() - start_time,
                        "cached": False,
                        "sources": []
                    }
                    
            elif query_type == "terraform":
                # Extract keywords from query + topics
                try:
                    keyword_result = await self.keyword_chain.ainvoke({
                        "query": question,
                        "context": conversation_topics
                    })
                    keywords = [k.strip() for k in keyword_result.content.split(",") if k.strip()]
                    logger.info(f"Extracted keywords for terraform: {keywords}")
                    
                    # Use tag-based retrieval
                    if keywords:
                        source_docs = await self.query_processor.retrieve_documents_with_tags(
                            question, keywords, top_k
                        )
                        if not source_docs:
                            source_docs = await self.query_processor.retrieve_documents(question, top_k)
                    else:
                        source_docs = await self.query_processor.retrieve_documents(question, top_k)
                    
                    # Generate terraform response
                    context = "\n\n".join([f"Source: {doc.source_path}\n{doc.content}" for doc in source_docs])
                    prompt_text = mode_prompts["qa_prompt"].format(context=context, question=question)
                    response = await self.llm.ainvoke(prompt_text)
                    
                    result = {
                        "response": response.content if hasattr(response, 'content') else str(response),
                        "processing_time": time.time() - start_time,
                        "cached": False,
                        "sources": source_docs
                    }
                except Exception as e:
                    logger.error(f"Terraform query failed: {e}")
                    result = {
                        "response": "Error processing terraform request.",
                        "processing_time": time.time() - start_time,
                        "cached": False,
                        "sources": []
                    }
            else:
                
                # Get conversation topics for keyword extraction (not full content)
                conversation_context = ""
                if memory and hasattr(memory, 'chat_memory') and memory.chat_memory.messages:
                    # Get only topic summaries, not full content
                    ai_messages = [msg for msg in memory.chat_memory.messages if isinstance(msg, AIMessage)]
                    if ai_messages:
                        topics = []
                        for msg in ai_messages[-2:]:
                            content_preview = msg.content[:50].replace('\n', ' ')
                            topics.append(f"Previous: {content_preview}...")
                        conversation_context = "\n".join(topics)
                
                # Extract keywords from query + context
                try:
                    keyword_result = await self.keyword_chain.ainvoke({
                        "query": question,
                        "context": conversation_context
                    })
                    keywords = [k.strip() for k in keyword_result.content.split(",") if k.strip()]
                    logger.info(f"Extracted keywords for conversational query: {keywords}")
                    
                    # Use tag-based retrieval if keywords found, otherwise regular retrieval
                    if keywords:
                        source_docs = await self.query_processor.retrieve_documents_with_tags(
                            question, keywords, top_k
                        )
                        # Additional fallback check - if tag-based returns empty, try regular
                        if not source_docs:
                            logger.info("Tag-based retrieval returned no results, using regular retrieval")
                            source_docs = await self.query_processor.retrieve_documents(question, top_k)
                    else:
                        source_docs = await self.query_processor.retrieve_documents(question, top_k)
                    
                    # Get chat history for conversational context
                    chat_history = []
                    if memory and hasattr(memory, 'chat_memory'):
                        messages = memory.chat_memory.messages
                        for i in range(0, len(messages), 2):
                            if i + 1 < len(messages):
                                human_msg = messages[i]
                                ai_msg = messages[i + 1]
                                chat_history.append((human_msg.content, ai_msg.content))
                    
                    # Create context from retrieved documents
                    context = "\n\n".join([f"Source: {doc.source_path}\n{doc.content}" for doc in source_docs])
                    
                    # Generate response with context and history
                    prompt_text = self.conversational_prompt.format(
                        context=context,
                        chat_history="\n".join([f"Human: {h}\nAssistant: {a}" for h, a in chat_history]),
                        question=question
                    )
                    response = await self.llm.ainvoke(prompt_text)
                    
                    final_response = response.content if hasattr(response, 'content') else str(response)
                    sources = source_docs
                    
                except Exception as e:
                    logger.warning(f"Keyword extraction failed, using regular conversational chain: {e}")
                    # Fallback to regular conversational chain
                    self.query_processor.retriever.search_kwargs = {"k": top_k}
                    
                    chat_history = []
                    if memory and hasattr(memory, 'chat_memory'):
                        messages = memory.chat_memory.messages
                        for i in range(0, len(messages), 2):
                            if i + 1 < len(messages):
                                human_msg = messages[i]
                                ai_msg = messages[i + 1]
                                chat_history.append((human_msg.content, ai_msg.content))
                    
                    result = self.conversational_chain.invoke({
                        "question": question,
                        "chat_history": chat_history
                    })
                    
                    response_text = result.get('answer', '')
                    final_response = response_text.content if hasattr(response_text, 'content') else str(response_text)
                    
                    source_documents = result.get('source_documents', [])
                    sources = [SourceDocument.from_langchain_document(doc, doc.metadata.get('relevance_score', 0.0)) for doc in source_documents]
                
                result = {
                    "response": final_response,
                    "processing_time": time.time() - start_time,
                    "cached": False,
                    "query_type": "general",
                    "timestamp": datetime.utcnow().isoformat()
                }
            
            # Add AI response to session for all query types
            await self.session_manager.add_ai_message(result["response"], session_id)
            
            processing_time = time.time() - start_time
            
            return QueryResult(
                response=result["response"],
                sources=result.get("sources", []),
                processing_time=processing_time,
                cached=result.get("cached", False)
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