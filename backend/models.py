"""Pydantic models for FastAPI RAG service."""

from datetime import datetime
from typing import Optional, List
from pydantic import BaseModel, Field
from enum import Enum


class QueryType(str, Enum):
    """Query type enumeration."""
    ONE_TIME = "one_time"
    CONVERSATIONAL = "conversational"


# Request Models
class OneTimeQueryRequest(BaseModel):
    """Request model for one-time queries."""
    query: str = Field(..., min_length=1, max_length=2000, description="The query text")
    top_k: Optional[int] = Field(default=5, ge=1, le=20, description="Number of documents to retrieve")


class ConversationalQueryRequest(BaseModel):
    """Request model for conversational queries."""
    query: str = Field(..., min_length=1, max_length=2000, description="The query text")
    session_id: str = Field(..., min_length=1, description="Session ID for conversation context")
    top_k: Optional[int] = Field(default=5, ge=1, le=20, description="Number of documents to retrieve")


class SessionCreateRequest(BaseModel):
    """Request model for creating a new session."""
    session_name: Optional[str] = Field(default=None, max_length=100, description="Optional session name")


# Response Models
class QueryResponse(BaseModel):
    """Response model for queries."""
    response: str = Field(..., description="The generated response")
    processing_time: float = Field(..., description="Processing time in seconds")
    cached: bool = Field(default=False, description="Whether the response was cached")
    timestamp: datetime = Field(default_factory=datetime.utcnow, description="Response timestamp")


class SessionInfo(BaseModel):
    """Session information model."""
    session_id: str = Field(..., description="Session ID")
    session_name: Optional[str] = Field(default=None, description="Session name")
    created_at: datetime = Field(..., description="Session creation timestamp")
    updated_at: datetime = Field(..., description="Last update timestamp")
    message_count: int = Field(default=0, description="Number of messages in session")


class SessionCreateResponse(BaseModel):
    """Response model for session creation."""
    session_id: str = Field(..., description="Created session ID")
    session_name: Optional[str] = Field(default=None, description="Session name")
    created_at: datetime = Field(default_factory=datetime.utcnow, description="Creation timestamp")


class SessionListResponse(BaseModel):
    """Response model for listing sessions."""
    sessions: List[SessionInfo] = Field(default_factory=list, description="List of sessions")
    total_count: int = Field(..., description="Total number of sessions")


class HealthResponse(BaseModel):
    """Health check response model."""
    status: str = Field(..., description="Overall health status")
    timestamp: datetime = Field(default_factory=datetime.utcnow, description="Health check timestamp")
    components: dict = Field(default_factory=dict, description="Component health status")
    version: str = Field(default="1.0.0", description="API version")


class ErrorResponse(BaseModel):
    """Error response model."""
    error: str = Field(..., description="Error message")
    detail: Optional[str] = Field(default=None, description="Detailed error information")
    timestamp: datetime = Field(default_factory=datetime.utcnow, description="Error timestamp")


class IndexStatsResponse(BaseModel):
    """Vector index statistics response."""
    total_vectors: int = Field(..., description="Total number of vectors in index")
    dimension: int = Field(..., description="Vector dimension")
    index_fullness: float = Field(..., description="Index fullness percentage")
    timestamp: datetime = Field(default_factory=datetime.utcnow, description="Stats timestamp")