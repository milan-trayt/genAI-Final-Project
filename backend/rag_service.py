"""
RAG Service - Core service class that orchestrates all RAG components.
"""

import asyncio
import logging
from typing import Optional, Dict, Any, List
from datetime import datetime

from config import get_config
from database_manager import DatabaseManager, get_database_manager
from redis_manager import RedisManager, get_redis_manager
from session_manager import SessionManager, get_session_manager
from query_processor import QueryProcessor, get_query_processor
from rag_chain import RAGChain, get_rag_chain
from cache_manager import CacheManager, get_cache_manager
from error_handler import ErrorHandler, get_error_handler
from aws_service_recommender import AWSServiceRecommender


logger = logging.getLogger(__name__)


class RAGService:
    """Core RAG service that orchestrates all components."""
    
    def __init__(self):
        self.config = get_config()
        self.error_handler = get_error_handler()
        
        # Component instances
        self.database_manager: Optional[DatabaseManager] = None
        self.redis_manager: Optional[RedisManager] = None
        self.session_manager: Optional[SessionManager] = None
        self.query_processor: Optional[QueryProcessor] = None
        self.rag_chain: Optional[RAGChain] = None
        self.cache_manager: Optional[CacheManager] = None
        self.aws_recommender: Optional[AWSServiceRecommender] = None

        
        self._initialized = False
    
    async def initialize(self) -> bool:
        """Initialize all RAG components."""
        if self._initialized:
            return True
        
        try:
            self.database_manager = await get_database_manager()
            self.redis_manager = await get_redis_manager()
            self.cache_manager = await get_cache_manager()
            self.query_processor = await get_query_processor()
            self.session_manager = await get_session_manager()
            self.rag_chain = await get_rag_chain(
                self.query_processor,
                self.session_manager,
                self.cache_manager
            )
            self.aws_recommender = AWSServiceRecommender(
                llm=self.rag_chain.llm,
                retriever=self.query_processor.get_retriever()
            )
            self._initialized = True
            return True
            
        except Exception as e:
            logger.error(f"Failed to initialize RAG service: {e}")
            return False
    
    async def process_one_time_query(self, query: str, query_type: str = "general", top_k: int = 5) -> Dict[str, Any]:
        """Process a one-time query without conversation history."""
        if not self._initialized:
            await self.initialize()
        
        try:
            # Apply guardrail validation for ALL query types
            guardrail_result = await self._validate_query_with_guardrail(query, None, query_type)
            if guardrail_result:
                return guardrail_result
            
            if not self.rag_chain:
                await self.initialize()
            result = await self.rag_chain.query_oneshot(query, query_type, top_k)
            
            return {
                "response": str(result.response),
                "processing_time": float(result.processing_time),
                "cached": bool(result.cached),
                "timestamp": datetime.utcnow().isoformat()
            }
            
        except Exception as e:
            logger.error(f"One-time query failed: {e}")
            raise
    
    async def process_conversational_query(self, query: str, session_id: str, query_type: str = "general", filters: Optional[Dict] = None, top_k: int = 5) -> Dict[str, Any]:
        """Process a conversational query with session context."""
        if not self._initialized:
            await self.initialize()
        
        try:
            # Apply guardrail validation for ALL query types
            guardrail_result = await self._validate_query_with_guardrail(query, session_id, query_type)
            if guardrail_result:
                return guardrail_result
            
            try:
                await self.session_manager.add_user_message(query, session_id, query_type)
            except Exception as e:
                logger.error(f"Failed to save user message: {e}")
            
            # Route query based on type
            if query_type == "service_recommendation":
                result = await self._handle_service_recommendation(query, session_id, filters)
            elif query_type == "pricing":
                result = await self._handle_pricing_query(query, session_id)
            elif query_type == "terraform":
                result = await self._handle_terraform_query(query, session_id)
            else:
                if not self.rag_chain:
                    await self.initialize()
                result = await self.rag_chain.query_conversational(query, session_id, query_type, top_k)
                result = {
                    "response": str(result.response),
                    "processing_time": float(result.processing_time),
                    "cached": bool(result.cached),
                    "query_type": "general",
                    "timestamp": datetime.utcnow().isoformat()
                }
            
            return result
            
        except Exception as e:
            logger.error(f"Conversational query failed: {e}")
            raise
    
    async def _validate_query_with_guardrail(self, query: str, session_id: Optional[str], query_type: str) -> Optional[Dict[str, Any]]:
        """Validate query with guardrail for all query types."""
        try:
            if not self.rag_chain:
                await self.initialize()
            
            # Get mode-specific guardrail prompt
            mode_prompts = self.rag_chain._get_mode_prompts(query_type)
            
            # Get conversation context if session exists
            conversation_topics = ""
            if session_id and self.session_manager:
                try:
                    # Ensure session is loaded first
                    await self.session_manager.load_session(session_id)
                    await self.session_manager.ensure_messages_loaded(session_id)
                    
                    memory = self.session_manager.get_memory(session_id)
                    if memory and hasattr(memory, 'chat_memory') and memory.chat_memory.messages:
                        from langchain.schema import AIMessage, HumanMessage
                        recent_messages = memory.chat_memory.messages[-6:]  # Last 3 exchanges
                        
                        aws_keywords = ['aws', 'lambda', 'ec2', 's3', 'rds', 'vpc', 'terraform', 'infrastructure', 'cloud', 'deploy', 'architecture', 'cost', 'minimal function', 'pricing', 'invoice', 'billing', 'estimate', 'service recommendation', 'dynamodb', 'api gateway', 'cloudwatch']
                        
                        logger.info(f"Checking {len(recent_messages)} recent messages for AWS context")
                        for i, msg in enumerate(recent_messages):
                            if isinstance(msg, (HumanMessage, AIMessage)):
                                content_lower = msg.content.lower()
                                logger.info(f"Message {i}: {content_lower[:100]}...")
                                if any(keyword in content_lower for keyword in aws_keywords):
                                    conversation_topics = "AWS/Infrastructure discussion with service recommendations and pricing context"
                                    logger.info(f"Found AWS context in message {i}")
                                    break
                        
                        if conversation_topics:
                            logger.info(f"Context detected: {conversation_topics}")
                        else:
                            logger.info("No AWS context found in recent messages")
                except Exception as e:
                    logger.warning(f"Could not get conversation context for guardrail: {e}")
            
            # Create contextual input for guardrail
            if conversation_topics:
                contextual_input = f"""Previous conversation context: {conversation_topics}

Current question: {query}"""
            else:
                contextual_input = query
            
            # Guardrail validation
            validation_result = await mode_prompts["guardrail"].ainvoke({"question": contextual_input})
            validation_response = validation_result.content.strip().upper()
            
            logger.info(f"Guardrail validation for '{query}' in {query_type} mode with context '{conversation_topics}': {validation_response}")
            
            if "REJECTED" in validation_response or "REJECT" in validation_response:
                # Handle session cleanup for first message rejection
                response_prefix = "GUARDRAIL_REJECTED:"
                if session_id and self.session_manager:
                    try:
                        memory = self.session_manager.get_memory(session_id)
                        is_first_message = False
                        if memory and hasattr(memory, 'chat_memory'):
                            is_first_message = len(memory.chat_memory.messages) == 0
                        
                        if is_first_message:
                            await self.session_manager.delete_session(session_id)
                            logger.info(f"Session {session_id} removed due to guardrail rejection on first message")
                            response_prefix = "GUARDRAIL_REJECTED_DELETE:"
                    except Exception as e:
                        logger.error(f"Failed to check/remove session {session_id}: {e}")
                
                # Mode-specific rejection messages
                rejection_messages = {
                    "general": "I can only help with AWS cloud infrastructure, DevOps, and software development topics. Please ask about AWS services, pricing, architecture, or technical questions.",
                    "service_recommendation": "I can only provide AWS service recommendations and architecture guidance. Please ask about AWS services, infrastructure design, or technical solutions.",
                    "pricing": "I can only help with AWS pricing, cost optimization, and billing questions. Please ask about AWS costs, pricing estimates, or cost-effective solutions.",
                    "terraform": "I can only help with Terraform, Infrastructure-as-Code, and AWS deployment automation. Please ask about Terraform configurations or infrastructure deployment."
                }
                
                rejection_message = rejection_messages.get(query_type, rejection_messages["general"])
                
                return {
                    "response": f"{response_prefix} {rejection_message}",
                    "processing_time": 0.1,
                    "cached": False,
                    "query_type": query_type,
                    "timestamp": datetime.utcnow().isoformat()
                }
            
            return None  # Query passed guardrail validation
            
        except Exception as e:
            logger.error(f"Guardrail validation failed: {e}")
            return {
                "response": "I apologize, but I encountered an error processing your request. Please try again.",
                "processing_time": 0.1,
                "cached": False,
                "query_type": query_type,
                "timestamp": datetime.utcnow().isoformat()
            }
    
    async def _handle_service_recommendation(self, query: str, session_id: str, filters: Optional[Dict] = None) -> Dict[str, Any]:
        """Handle service recommendation queries with CoT reasoning"""
        try:

            
            conversation_context = ""
            try:
                history = await self.get_session_history(session_id)
                if history:
                    ai_messages = [msg for msg in history if msg.get('role') == 'assistant']
                    if ai_messages:
                        recent_messages = ai_messages[-2:]
                        context_parts = [msg['content'] for msg in recent_messages]
                        conversation_context = "\n\n".join(context_parts)
            except Exception as e:
                logger.warning(f"Could not get conversation context: {e}")
            
            recommendation = await self.aws_recommender.recommend_services(query, filters, conversation_context)
            if "error" in recommendation:
                return {
                    "response": str(recommendation["error"]),
                    "processing_time": 0.5,
                    "cached": False,
                    "query_type": "service_recommendation",
                    "timestamp": datetime.utcnow().isoformat()
                }
            
            # Use the direct response from the LLM
            response = recommendation.get("response", "No response available")
        except Exception as e:
            logger.error(f"Service recommendation failed: {e}")
            return {
                "response": "I apologize, but I encountered an error processing your service recommendation request. Please try again.",
                "processing_time": 0.5,
                "cached": False,
                "query_type": "service_recommendation",
                "timestamp": datetime.utcnow().isoformat()
            }
        
        # No need for complex formatting since LLM returns formatted response directly
        
        try:
            await self.session_manager.add_ai_message(str(response), session_id, "service_recommendation")
        except Exception as e:
            logger.error(f"Failed to save response to session: {e}")
        
        return {
            "response": str(response),
            "processing_time": 0.5,
            "cached": False,
            "query_type": "service_recommendation",
            "timestamp": datetime.utcnow().isoformat()
        }
    
    async def _handle_pricing_query(self, query: str, session_id: str) -> Dict[str, Any]:
        """Handle pricing estimation queries"""
        try:
            conversation_context = ""
            try:
                history = await self.get_session_history(session_id)
                if history:
                    ai_messages = [msg for msg in history if msg.get('role') == 'assistant']
                    if ai_messages:
                        recent_messages = ai_messages[-2:]
                        context_parts = [msg['content'] for msg in recent_messages]
                        conversation_context = "\n\n".join(context_parts)
            except Exception as e:
                logger.warning(f"Could not get conversation context: {e}")
            
            services = self._extract_services_from_query(query)
            usage_params = self._extract_usage_params(query)
            usage_params['usage_pattern'] = 'mid'  # Default to mid usage
            
            pricing = await self.aws_recommender.get_pricing_estimate(services, usage_params, conversation_context, query)
            
            if "error" in pricing:
                return {
                    "response": str(pricing["error"]),
                    "processing_time": 0.5,
                    "cached": False,
                    "query_type": "pricing",
                    "timestamp": datetime.utcnow().isoformat()
                }
            
            # Use the direct response from the LLM
            response = pricing.get("response", "No pricing information available")
            
            try:
                await self.session_manager.add_ai_message(str(response), session_id, "pricing")
            except Exception as e:
                logger.error(f"Failed to save response to session: {e}")
            
            return {
                "response": str(response),
                "processing_time": 0.5,
                "cached": False,
                "query_type": "pricing",
                "timestamp": datetime.utcnow().isoformat()
            }
        except Exception as e:
            logger.error(f"Pricing query failed: {e}")
            return {
                "response": "I apologize, but I encountered an error processing your pricing request. Please try again.",
                "processing_time": 0.5,
                "cached": False,
                "query_type": "pricing",
                "timestamp": datetime.utcnow().isoformat()
            }
    
    async def _handle_terraform_query(self, query: str, session_id: str) -> Dict[str, Any]:
        """Handle Terraform code generation queries"""
        try:
            conversation_context = ""
            try:
                history = await self.get_session_history(session_id)
                if history:
                    ai_messages = [msg for msg in history if msg.get('role') == 'assistant']
                    if ai_messages:
                        recent_messages = ai_messages[-2:]
                        context_parts = [msg['content'] for msg in recent_messages]
                        conversation_context = "\n\n".join(context_parts)
            except Exception as e:
                logger.warning(f"Could not get conversation context: {e}")
            
            services = self._extract_services_from_query(query)
            requirements = self._extract_requirements_from_query(query)
            
            terraform_result = await self.aws_recommender.generate_terraform_code(services, requirements, conversation_context)
            
            # Use the direct response from the LLM
            response = terraform_result.get("response", "No Terraform code available")
            
            try:
                await self.session_manager.add_ai_message(str(response), session_id, "terraform")
            except Exception as e:
                logger.error(f"Failed to save response to session: {e}")
            
            return {
                "response": str(response),
                "processing_time": 0.5,
                "cached": False,
                "query_type": "terraform",
                "timestamp": datetime.utcnow().isoformat()
            }
        except Exception as e:
            logger.error(f"Terraform query failed: {e}")
            return {
                "response": "I apologize, but I encountered an error generating Terraform code. Please try again.",
                "processing_time": 0.5,
                "cached": False,
                "query_type": "terraform",
                "timestamp": datetime.utcnow().isoformat()
            }
    
    def _extract_services_from_query(self, query: str) -> List[str]:
        """Extract AWS services mentioned in query"""
        services = []
        query_lower = query.lower()
        
        aws_services = {
            'compute': ['EC2', 'Lambda', 'ECS', 'EKS', 'Fargate'],
            'storage': ['S3', 'EBS', 'EFS', 'FSx'],
            'database': ['RDS', 'DynamoDB', 'ElastiCache', 'DocumentDB'],
            'networking': ['VPC', 'CloudFront', 'Route53', 'ELB', 'API Gateway'],
            'security': ['IAM', 'KMS', 'Secrets Manager', 'WAF'],
            'monitoring': ['CloudWatch', 'X-Ray', 'CloudTrail']
        }
        
        for category, service_list in aws_services.items():
            for service in service_list:
                if service.lower() in query_lower:
                    services.append(service)
        
        return services
    
    def _extract_usage_params(self, query: str) -> Dict[str, Any]:
        """Extract usage parameters from query"""
        import re
        params = {}
        
        # Extract numbers that might be usage metrics
        numbers = re.findall(r'\d+', query)
        if numbers:
            params['estimated_usage'] = numbers[0]
        
        # Extract environment indicators
        query_lower = query.lower()
        if 'production' in query_lower:
            params['environment'] = 'production'
        elif 'development' in query_lower or 'dev' in query_lower:
            params['environment'] = 'development'
        
        return params
    
    def _extract_requirements_from_query(self, query: str) -> Dict[str, Any]:
        """Extract requirements from query"""
        requirements = {}
        
        query_lower = query.lower()
        if 'production' in query_lower:
            requirements['environment'] = 'production'
        elif 'development' in query_lower or 'dev' in query_lower:
            requirements['environment'] = 'development'
        
        if 'high availability' in query_lower or 'ha' in query_lower:
            requirements['high_availability'] = True
        
        return requirements
    
    async def generate_topic_from_query(self, query: str) -> str:
        """Generate a short topic description from the first query."""
        if not self._initialized:
            await self.initialize()
        
        try:
            # Use OpenAI to generate a concise topic
            from langchain.prompts import PromptTemplate
            
            topic_prompt = PromptTemplate(
                template="Generate a short, descriptive topic title (max 4-5 words) for this question: {query}\n\nTopic:",
                input_variables=["query"]
            )
            
            prompt_text = topic_prompt.format(query=query)
            response = await self.rag_chain.llm.ainvoke(prompt_text)
            topic = response.content if hasattr(response, 'content') else str(response)
            
            # Clean up the response
            topic = topic.strip().replace('"', '').replace("'", "")
            
            # Fallback if generation fails or is too long
            if len(topic) > 50 or not topic:
                words = query.split()[:4]
                topic = " ".join(words) + ("..." if len(query.split()) > 4 else "")
            
            return topic
            
        except Exception as e:
            logger.error(f"Topic generation failed: {e}")
            # Fallback to first few words of query
            words = query.split()[:4]
            return " ".join(words) + ("..." if len(query.split()) > 4 else "")
    
    async def create_session(self, session_name: Optional[str] = None) -> Dict[str, Any]:
        """Create a new conversation session."""
        if not self._initialized:
            await self.initialize()
        
        try:
            session_name = session_name or f"API Session {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}"
            session_id = await self.session_manager.create_session("api", session_name)
            
            return {
                "session_id": session_id,
                "session_name": session_name,
                "created_at": datetime.utcnow().isoformat()
            }
            
        except Exception as e:
            logger.error(f"Session creation failed: {e}")
            raise
    
    async def list_sessions(self) -> Dict[str, Any]:
        """List all available sessions."""
        if not self._initialized:
            await self.initialize()
        
        try:
            sessions = await self.session_manager.list_sessions()
            
            session_info = []
            for session in sessions:
                # Handle both dict and asyncpg.Record objects
                if hasattr(session, 'get'):
                    session_data = session
                else:
                    session_data = dict(session)
                
                session_info.append({
                    "session_id": session_data["session_id"],
                    "session_name": session_data.get("tab_name", "Unnamed Session"),
                    "created_at": session_data["created_at"],
                    "updated_at": session_data["updated_at"],
                    "message_count": session_data.get("message_count", 0)
                })
            
            return {
                "sessions": session_info,
                "total_count": len(session_info)
            }
            
        except Exception as e:
            logger.error(f"Session listing failed: {e}")
            return {
                "sessions": [],
                "total_count": 0
            }
    
    async def delete_session(self, session_id: str) -> bool:
        """Delete a session."""
        if not self._initialized:
            await self.initialize()
        
        try:
            return await self.session_manager.delete_session(session_id)
        except Exception as e:
            logger.error(f"Session deletion failed: {e}")
            return False
    
    async def get_session_history(self, session_id: str) -> List[Dict[str, Any]]:
        """Get conversation history for a session."""
        if not self._initialized:
            await self.initialize()
        
        try:
            # Load the session first
            await self.session_manager.load_session(session_id)
            
            # Get message history
            history = self.session_manager.get_message_history(session_id)
            if not history:
                return []
            
            # Ensure messages are loaded
            await self.session_manager.ensure_messages_loaded(session_id)
            
            # Convert messages to API format
            messages = []
            for message in history.messages:
                try:
                    role = "user" if message.__class__.__name__ == "HumanMessage" else "assistant"
                    content = message.content if hasattr(message, 'content') else str(message)
                    
                    # Get query_type from additional_kwargs metadata
                    query_type = 'general'
                    if hasattr(message, 'additional_kwargs') and isinstance(message.additional_kwargs, dict):
                        query_type = message.additional_kwargs.get('query_type', 'general')
                    
                    messages.append({
                        "role": role,
                        "content": content,
                        "query_type": query_type,
                        "timestamp": datetime.utcnow().isoformat()
                    })
                except Exception as msg_error:
                    logger.warning(f"Skipping malformed message: {msg_error}")
                    continue
            
            return messages
            
        except Exception as e:
            logger.error(f"Getting session history failed: {e}")
            return []
    
    async def update_session_name(self, session_id: str, session_name: str) -> bool:
        """Update session name in database."""
        if not self._initialized:
            await self.initialize()
        
        try:
            return await self.database_manager.update_session_name(session_id, session_name)
        except Exception as e:
            logger.error(f"Session name update failed: {e}")
            return False
    
    async def get_health_status(self) -> Dict[str, Any]:
        """Get health status of all components."""
        if not self._initialized:
            return {
                "status": "unhealthy",
                "components": {"service": {"status": "not_initialized"}},
                "timestamp": datetime.utcnow().isoformat(),
                "version": "1.0.0"
            }
        
        try:
            components = {}
            
            # Check database
            if self.database_manager:
                db_healthy = await self.database_manager.health_check()
                components["database"] = {"status": "healthy" if db_healthy else "unhealthy"}
            
            # Check Redis
            if self.redis_manager:
                redis_healthy = await self.redis_manager.health_check()
                components["redis"] = {"status": "healthy" if redis_healthy else "unhealthy"}
            
            # Check query processor
            if self.query_processor:
                qp_healthy = await self.query_processor.health_check()
                components["query_processor"] = {"status": "healthy" if qp_healthy else "unhealthy"}
            
            # Overall status
            all_healthy = all(comp.get("status") == "healthy" for comp in components.values())
            overall_status = "healthy" if all_healthy else "unhealthy"
            
            return {
                "status": overall_status,
                "components": components,
                "timestamp": datetime.utcnow().isoformat(),
                "version": "1.0.0"
            }
            
        except Exception as e:
            logger.error(f"Health check failed: {e}")
            return {
                "status": "unhealthy",
                "components": {"error": str(e)},
                "timestamp": datetime.utcnow().isoformat(),
                "version": "1.0.0"
            }
    
    async def get_index_stats(self) -> Dict[str, Any]:
        """Get vector index statistics."""
        if not self._initialized:
            await self.initialize()
        
        try:
            stats = await self.query_processor.get_index_stats()
            return {
                "total_vectors": stats.get("total_vectors", 0),
                "dimension": stats.get("dimension", 1536),
                "index_fullness": stats.get("index_fullness", 0.0),
                "timestamp": datetime.utcnow().isoformat()
            }
        except Exception as e:
            logger.error(f"Index stats failed: {e}")
            return {
                "total_vectors": 0,
                "dimension": 1536,
                "index_fullness": 0.0,
                "timestamp": datetime.utcnow().isoformat()
            }
    
    async def close(self):
        """Clean up service resources."""
        if not self._initialized:
            return
        
        try:
            # Close components in reverse order
            if self.rag_chain:
                await self.rag_chain.close()
            
            if self.session_manager:
                await self.session_manager.close()
            
            if self.query_processor:
                await self.query_processor.close()
            
            if self.cache_manager:
                await self.cache_manager.close()
            
            if self.redis_manager:
                await self.redis_manager.close()
            
            if self.database_manager:
                await self.database_manager.close()
            
            self._initialized = False
            
        except Exception as e:
            logger.error(f"Error during service shutdown: {e}")


# Global service instance
_rag_service = None


async def get_rag_service() -> RAGService:
    """Get or create RAG service instance."""
    global _rag_service
    
    if _rag_service is None:
        _rag_service = RAGService()
        await _rag_service.initialize()
    
    return _rag_service


async def close_rag_service():
    """Close RAG service."""
    global _rag_service
    
    if _rag_service:
        await _rag_service.close()
        _rag_service = None