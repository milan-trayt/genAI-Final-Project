#!/usr/bin/env python3
"""
Comprehensive error handling system with LangChain callbacks and retry mechanisms.
"""

import asyncio
import logging
import traceback
import time
from typing import Dict, Any, List, Optional, Union, Callable
from enum import Enum
from dataclasses import dataclass
from datetime import datetime

from langchain.callbacks.base import BaseCallbackHandler
from langchain.schema import LLMResult, AgentAction, AgentFinish
from langchain.prompts import PromptTemplate
from langchain.schema.output_parser import OutputParserException
from langchain_openai import ChatOpenAI

import openai
import asyncpg
import redis
from pinecone import PineconeException

from config import get_config

logger = logging.getLogger(__name__)


class ErrorType(Enum):
    """Error type enumeration."""
    CONNECTION_ERROR = "connection_error"
    PROCESSING_ERROR = "processing_error"
    VALIDATION_ERROR = "validation_error"
    TIMEOUT_ERROR = "timeout_error"
    AUTHENTICATION_ERROR = "authentication_error"
    RATE_LIMIT_ERROR = "rate_limit_error"
    UNKNOWN_ERROR = "unknown_error"


class ErrorSeverity(Enum):
    """Error severity levels."""
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    CRITICAL = "critical"


@dataclass
class ErrorContext:
    """Error context information."""
    error_type: ErrorType
    severity: ErrorSeverity
    message: str
    component: str
    operation: str
    timestamp: datetime
    traceback: Optional[str] = None
    metadata: Dict[str, Any] = None
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary."""
        return {
            'error_type': self.error_type.value,
            'severity': self.severity.value,
            'message': self.message,
            'component': self.component,
            'operation': self.operation,
            'timestamp': self.timestamp.isoformat(),
            'traceback': self.traceback,
            'metadata': self.metadata or {}
        }


class RetryConfig:
    """Configuration for retry mechanisms."""
    
    def __init__(self, max_attempts: int = 3, base_delay: float = 1.0, max_delay: float = 60.0, exponential_base: float = 2.0):
        self.max_attempts = max_attempts
        self.base_delay = base_delay
        self.max_delay = max_delay
        self.exponential_base = exponential_base
    
    def get_delay(self, attempt: int) -> float:
        """Get delay for a specific attempt."""
        delay = self.base_delay * (self.exponential_base ** (attempt - 1))
        return min(delay, self.max_delay)


class ErrorCallbackHandler(BaseCallbackHandler):
    """LangChain callback handler for error tracking and handling."""
    
    def __init__(self, error_handler: 'ErrorHandler'):
        self.error_handler = error_handler
        self.operation_stack: List[str] = []
        self.start_times: Dict[str, float] = {}
    
    def on_llm_start(self, serialized: Dict[str, Any], prompts: List[str], **kwargs) -> None:
        """Called when LLM starts running."""
        operation = f"llm_{serialized.get('name', 'unknown')}"
        self.operation_stack.append(operation)
        self.start_times[operation] = time.time()
        logger.debug(f"LLM operation started: {operation}")
    
    def on_llm_end(self, response: LLMResult, **kwargs) -> None:
        """Called when LLM ends running."""
        if self.operation_stack:
            operation = self.operation_stack.pop()
            duration = time.time() - self.start_times.pop(operation, time.time())
            logger.debug(f"LLM operation completed: {operation} in {duration:.2f}s")
    
    def on_llm_error(self, error: Union[Exception, KeyboardInterrupt], **kwargs) -> None:
        """Called when LLM errors."""
        operation = self.operation_stack.pop() if self.operation_stack else "llm_unknown"
        
        error_context = ErrorContext(
            error_type=self._classify_error(error),
            severity=ErrorSeverity.HIGH,
            message=str(error),
            component="llm",
            operation=operation,
            timestamp=datetime.now(),
            traceback=traceback.format_exc(),
            metadata={'error_class': error.__class__.__name__}
        )
        
        self.error_handler.handle_error(error_context)
    
    def on_chain_start(self, serialized: Dict[str, Any], inputs: Dict[str, Any], **kwargs) -> None:
        """Called when chain starts."""
        operation = f"chain_{serialized.get('name', 'unknown')}"
        self.operation_stack.append(operation)
        self.start_times[operation] = time.time()
        logger.debug(f"Chain operation started: {operation}")
    
    def on_chain_end(self, outputs: Dict[str, Any], **kwargs) -> None:
        """Called when chain ends."""
        if self.operation_stack:
            operation = self.operation_stack.pop()
            duration = time.time() - self.start_times.pop(operation, time.time())
            logger.debug(f"Chain operation completed: {operation} in {duration:.2f}s")
    
    def on_chain_error(self, error: Union[Exception, KeyboardInterrupt], **kwargs) -> None:
        """Called when chain errors."""
        operation = self.operation_stack.pop() if self.operation_stack else "chain_unknown"
        
        error_context = ErrorContext(
            error_type=self._classify_error(error),
            severity=ErrorSeverity.HIGH,
            message=str(error),
            component="chain",
            operation=operation,
            timestamp=datetime.now(),
            traceback=traceback.format_exc(),
            metadata={'error_class': error.__class__.__name__}
        )
        
        self.error_handler.handle_error(error_context)
    
    def on_tool_start(self, serialized: Dict[str, Any], input_str: str, **kwargs) -> None:
        """Called when tool starts."""
        operation = f"tool_{serialized.get('name', 'unknown')}"
        self.operation_stack.append(operation)
        self.start_times[operation] = time.time()
        logger.debug(f"Tool operation started: {operation}")
    
    def on_tool_end(self, output: str, **kwargs) -> None:
        """Called when tool ends."""
        if self.operation_stack:
            operation = self.operation_stack.pop()
            duration = time.time() - self.start_times.pop(operation, time.time())
            logger.debug(f"Tool operation completed: {operation} in {duration:.2f}s")
    
    def on_tool_error(self, error: Union[Exception, KeyboardInterrupt], **kwargs) -> None:
        """Called when tool errors."""
        operation = self.operation_stack.pop() if self.operation_stack else "tool_unknown"
        
        error_context = ErrorContext(
            error_type=self._classify_error(error),
            severity=ErrorSeverity.MEDIUM,
            message=str(error),
            component="tool",
            operation=operation,
            timestamp=datetime.now(),
            traceback=traceback.format_exc(),
            metadata={'error_class': error.__class__.__name__}
        )
        
        self.error_handler.handle_error(error_context)
    
    def on_agent_action(self, action: AgentAction, **kwargs) -> None:
        """Called when agent takes an action."""
        logger.debug(f"Agent action: {action.tool} with input: {action.tool_input}")
    
    def on_agent_finish(self, finish: AgentFinish, **kwargs) -> None:
        """Called when agent finishes."""
        logger.debug(f"Agent finished with output: {finish.return_values}")
    
    def _classify_error(self, error: Exception) -> ErrorType:
        """Classify error type based on exception."""
        if isinstance(error, (ConnectionError, asyncpg.PostgresConnectionError, redis.ConnectionError)):
            return ErrorType.CONNECTION_ERROR
        elif isinstance(error, (TimeoutError, asyncio.TimeoutError)):
            return ErrorType.TIMEOUT_ERROR
        elif isinstance(error, (openai.AuthenticationError, PermissionError)):
            return ErrorType.AUTHENTICATION_ERROR
        elif isinstance(error, openai.RateLimitError):
            return ErrorType.RATE_LIMIT_ERROR
        elif isinstance(error, (ValueError, TypeError, OutputParserException)):
            return ErrorType.VALIDATION_ERROR
        elif isinstance(error, (PineconeException, openai.OpenAIError)):
            return ErrorType.PROCESSING_ERROR
        else:
            return ErrorType.UNKNOWN_ERROR


class ErrorHandler:
    """Comprehensive error handler with LangChain integration."""
    
    def __init__(self):
        self.config = get_config()
        self.callback_handler = ErrorCallbackHandler(self)
        self.error_history: List[ErrorContext] = []
        self.retry_configs: Dict[str, RetryConfig] = {
            'default': RetryConfig(),
            'connection': RetryConfig(max_attempts=5, base_delay=2.0),
            'rate_limit': RetryConfig(max_attempts=3, base_delay=5.0, max_delay=120.0),
            'timeout': RetryConfig(max_attempts=2, base_delay=1.0)
        }
        
        # User-friendly error messages
        self.error_messages = {
            ErrorType.CONNECTION_ERROR: "Connection issue detected. Please check your network connection and try again.",
            ErrorType.PROCESSING_ERROR: "Processing error occurred. The system is working to resolve this.",
            ErrorType.VALIDATION_ERROR: "Invalid input detected. Please check your query and try again.",
            ErrorType.TIMEOUT_ERROR: "Operation timed out. Please try again with a simpler query.",
            ErrorType.AUTHENTICATION_ERROR: "Authentication failed. Please check your API keys and permissions.",
            ErrorType.RATE_LIMIT_ERROR: "Rate limit exceeded. Please wait a moment before trying again.",
            ErrorType.UNKNOWN_ERROR: "An unexpected error occurred. Please try again or contact support."
        }
        
        # Initialize error message generator
        self.llm = None
        self._initialize_llm()
    
    def _initialize_llm(self):
        """Initialize LLM for generating user-friendly error messages."""
        try:
            config = get_config()
            self.llm = ChatOpenAI(
                model=config.openai.model,
                temperature=0.1,
                max_tokens=200
            )
        except Exception as e:
            logger.warning(f"Failed to initialize error message LLM: {e}")
    
    def handle_error(self, error_context: ErrorContext) -> str:
        """Handle an error and return user-friendly message."""
        # Log the error
        self._log_error(error_context)
        
        # Add to history
        self.error_history.append(error_context)
        
        # Keep only recent errors (last 100)
        if len(self.error_history) > 100:
            self.error_history = self.error_history[-100:]
        
        # Generate user-friendly message
        user_message = self._generate_user_message(error_context)
        
        # Handle critical errors
        if error_context.severity == ErrorSeverity.CRITICAL:
            self._handle_critical_error(error_context)
        
        return user_message
    
    def _log_error(self, error_context: ErrorContext):
        """Log error with appropriate level."""
        log_message = f"[{error_context.component}:{error_context.operation}] {error_context.message}"
        
        if error_context.severity == ErrorSeverity.CRITICAL:
            logger.critical(log_message, extra={'error_context': error_context.to_dict()})
        elif error_context.severity == ErrorSeverity.HIGH:
            logger.error(log_message, extra={'error_context': error_context.to_dict()})
        elif error_context.severity == ErrorSeverity.MEDIUM:
            logger.warning(log_message, extra={'error_context': error_context.to_dict()})
        else:
            logger.info(log_message, extra={'error_context': error_context.to_dict()})
    
    def _generate_user_message(self, error_context: ErrorContext) -> str:
        """Generate user-friendly error message."""
        base_message = self.error_messages.get(error_context.error_type, self.error_messages[ErrorType.UNKNOWN_ERROR])
        
        # Try to generate a more specific message using LLM
        if self.llm and error_context.severity in [ErrorSeverity.HIGH, ErrorSeverity.CRITICAL]:
            try:
                prompt = PromptTemplate(
                    template="""Generate a helpful, user-friendly error message for the following technical error:

Component: {component}
Operation: {operation}
Error Type: {error_type}
Technical Message: {technical_message}

Provide a clear, non-technical explanation that helps the user understand what went wrong and what they can do about it. Keep it concise and reassuring.

User-friendly message:""",
                    input_variables=["component", "operation", "error_type", "technical_message"]
                )
                
                response = self.llm.predict(prompt.format(
                    component=error_context.component,
                    operation=error_context.operation,
                    error_type=error_context.error_type.value,
                    technical_message=error_context.message
                ))
                
                return response.strip()
                
            except Exception as e:
                logger.warning(f"Failed to generate custom error message: {e}")
        
        return base_message
    
    def _handle_critical_error(self, error_context: ErrorContext):
        """Handle critical errors that may require system shutdown."""
        logger.critical(f"Critical error in {error_context.component}: {error_context.message}")
        
        # Could implement additional critical error handling here
        # such as sending alerts, graceful shutdown, etc.
    
    async def retry_with_backoff(self, 
                                operation: Callable,
                                operation_name: str,
                                retry_config: Optional[RetryConfig] = None,
                                *args, **kwargs) -> Any:
        """Retry an operation with exponential backoff."""
        config = retry_config or self.retry_configs['default']
        last_error = None
        
        for attempt in range(1, config.max_attempts + 1):
            try:
                if asyncio.iscoroutinefunction(operation):
                    return await operation(*args, **kwargs)
                else:
                    return operation(*args, **kwargs)
                    
            except Exception as e:
                last_error = e
                
                # Create error context
                error_context = ErrorContext(
                    error_type=self.callback_handler._classify_error(e),
                    severity=ErrorSeverity.MEDIUM,
                    message=f"Attempt {attempt}/{config.max_attempts} failed: {str(e)}",
                    component="retry_handler",
                    operation=operation_name,
                    timestamp=datetime.now(),
                    metadata={'attempt': attempt, 'max_attempts': config.max_attempts}
                )
                
                self._log_error(error_context)
                
                # Don't retry on certain error types
                if error_context.error_type in [ErrorType.AUTHENTICATION_ERROR, ErrorType.VALIDATION_ERROR]:
                    break
                
                # If this was the last attempt, don't wait
                if attempt == config.max_attempts:
                    break
                
                # Wait before retrying
                delay = config.get_delay(attempt)
                logger.info(f"Retrying {operation_name} in {delay:.1f}s (attempt {attempt + 1}/{config.max_attempts})")
                await asyncio.sleep(delay)
        
        # All attempts failed
        final_error_context = ErrorContext(
            error_type=self.callback_handler._classify_error(last_error),
            severity=ErrorSeverity.HIGH,
            message=f"All {config.max_attempts} attempts failed. Last error: {str(last_error)}",
            component="retry_handler",
            operation=operation_name,
            timestamp=datetime.now(),
            traceback=traceback.format_exc()
        )
        
        user_message = self.handle_error(final_error_context)
        raise Exception(user_message)
    
    def get_callback_handler(self) -> ErrorCallbackHandler:
        """Get the LangChain callback handler."""
        return self.callback_handler
    
    def get_error_statistics(self) -> Dict[str, Any]:
        """Get error statistics."""
        if not self.error_history:
            return {'total_errors': 0}
        
        # Count errors by type
        error_counts = {}
        severity_counts = {}
        component_counts = {}
        
        for error in self.error_history:
            error_counts[error.error_type.value] = error_counts.get(error.error_type.value, 0) + 1
            severity_counts[error.severity.value] = severity_counts.get(error.severity.value, 0) + 1
            component_counts[error.component] = component_counts.get(error.component, 0) + 1
        
        # Recent errors (last hour)
        recent_errors = [
            error for error in self.error_history
            if (datetime.now() - error.timestamp).total_seconds() < 3600
        ]
        
        return {
            'total_errors': len(self.error_history),
            'recent_errors': len(recent_errors),
            'error_types': error_counts,
            'severity_distribution': severity_counts,
            'component_distribution': component_counts,
            'last_error': self.error_history[-1].to_dict() if self.error_history else None
        }
    
    def clear_error_history(self):
        """Clear error history."""
        self.error_history.clear()
        logger.info("Error history cleared")
    
    def get_recent_errors(self, limit: int = 10) -> List[Dict[str, Any]]:
        """Get recent errors."""
        return [error.to_dict() for error in self.error_history[-limit:]]


# Utility functions for common error handling patterns

async def handle_connection_error(operation: Callable, operation_name: str, error_handler: ErrorHandler, *args, **kwargs):
    """Handle connection errors with retry."""
    return await error_handler.retry_with_backoff(
        operation, 
        operation_name, 
        error_handler.retry_configs['connection'],
        *args, **kwargs
    )


async def handle_rate_limit_error(operation: Callable, operation_name: str, error_handler: ErrorHandler, *args, **kwargs):
    """Handle rate limit errors with appropriate backoff."""
    return await error_handler.retry_with_backoff(
        operation, 
        operation_name, 
        error_handler.retry_configs['rate_limit'],
        *args, **kwargs
    )


def create_error_context(error: Exception, component: str, operation: str, severity: ErrorSeverity = ErrorSeverity.MEDIUM) -> ErrorContext:
    """Create error context from exception."""
    error_handler = ErrorHandler()
    error_type = error_handler.callback_handler._classify_error(error)
    
    return ErrorContext(
        error_type=error_type,
        severity=severity,
        message=str(error),
        component=component,
        operation=operation,
        timestamp=datetime.now(),
        traceback=traceback.format_exc(),
        metadata={'error_class': error.__class__.__name__}
    )


# Global error handler instance
_error_handler = None


def get_error_handler() -> ErrorHandler:
    """Get or create error handler instance."""
    global _error_handler
    
    if _error_handler is None:
        _error_handler = ErrorHandler()
    
    return _error_handler