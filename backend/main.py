"""
FastAPI REST API service for Interactive RAG Query System.
"""

import logging
import sys
from contextlib import asynccontextmanager
from datetime import datetime

from fastapi import FastAPI, HTTPException, Depends
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from models import (
    OneTimeQueryRequest, ConversationalQueryRequest, SessionCreateRequest,
    QueryResponse, SessionCreateResponse, SessionListResponse, HealthResponse,
    ErrorResponse, IndexStatsResponse
)
from pydantic import BaseModel

class TopicGenerationRequest(BaseModel):
    query: str

class TopicGenerationResponse(BaseModel):
    topic: str
from rag_service import RAGService, get_rag_service, close_rag_service

# Setup logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.StreamHandler(sys.stdout)
    ]
)

logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Application lifespan manager."""
    # Startup
    logger.info("🚀 Starting FastAPI RAG Service...")
    try:
        # Initialize RAG service
        rag_service = await get_rag_service()
        logger.info("✅ RAG Service initialized successfully")
        yield
    except Exception as e:
        logger.error(f"Failed to initialize RAG service: {e}")
        raise
    finally:
        # Shutdown
        logger.info("🛑 Shutting down FastAPI RAG Service...")
        await close_rag_service()
        logger.info("✅ Shutdown completed")


# Create FastAPI app
app = FastAPI(
    title="Interactive RAG Query API",
    description="REST API for Interactive RAG Query System with conversational and one-time query modes",
    version="1.0.0",
    lifespan=lifespan
)

# Add CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # Configure appropriately for production
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# Exception handler
@app.exception_handler(Exception)
async def global_exception_handler(request, exc):
    """Global exception handler."""
    logger.error(f"Unhandled exception: {exc}")
    return JSONResponse(
        status_code=500,
        content=ErrorResponse(
            error="Internal server error",
            detail=str(exc),
            timestamp=datetime.utcnow()
        ).dict()
    )


# Health check endpoint
@app.get("/health", response_model=HealthResponse)
async def health_check(rag_service: RAGService = Depends(get_rag_service)):
    """Health check endpoint."""
    try:
        health_status = await rag_service.get_health_status()
        return HealthResponse(**health_status)
    except Exception as e:
        logger.error(f"Health check failed: {e}")
        raise HTTPException(status_code=500, detail="Health check failed")


# Index statistics endpoint
@app.get("/stats", response_model=IndexStatsResponse)
async def get_index_stats(rag_service: RAGService = Depends(get_rag_service)):
    """Get vector index statistics."""
    try:
        stats = await rag_service.get_index_stats()
        return IndexStatsResponse(**stats)
    except Exception as e:
        logger.error(f"Stats retrieval failed: {e}")
        raise HTTPException(status_code=500, detail="Failed to retrieve statistics")


# One-time query endpoint
@app.post("/query/one-time", response_model=QueryResponse)
async def one_time_query(
    request: OneTimeQueryRequest,
    rag_service: RAGService = Depends(get_rag_service)
):
    """Process a one-time query without conversation history."""
    try:
        logger.info(f"Processing one-time query: {request.query[:50]}...")
        
        result = await rag_service.process_one_time_query(
            query=request.query,
            top_k=request.top_k
        )
        
        return QueryResponse(**result)
        
    except Exception as e:
        logger.error(f"One-time query failed: {e}")
        raise HTTPException(status_code=500, detail=f"Query processing failed: {str(e)}")


# Conversational query endpoint
@app.post("/query/conversational", response_model=QueryResponse)
async def conversational_query(
    request: ConversationalQueryRequest,
    rag_service: RAGService = Depends(get_rag_service)
):
    """Process a conversational query with session context."""
    try:
        logger.info(f"Processing conversational query for session {request.session_id}: {request.query[:50]}...")
        
        result = await rag_service.process_conversational_query(
            query=request.query,
            session_id=request.session_id,
            top_k=request.top_k
        )
        
        return QueryResponse(**result)
        
    except Exception as e:
        logger.error(f"Conversational query failed: {e}")
        raise HTTPException(status_code=500, detail=f"Query processing failed: {str(e)}")


# Session management endpoints
@app.post("/sessions", response_model=SessionCreateResponse)
async def create_session(
    request: SessionCreateRequest,
    rag_service: RAGService = Depends(get_rag_service)
):
    """Create a new conversation session."""
    try:
        logger.info(f"Creating new session: {request.session_name}")
        
        result = await rag_service.create_session(request.session_name)
        
        return SessionCreateResponse(**result)
        
    except Exception as e:
        logger.error(f"Session creation failed: {e}")
        raise HTTPException(status_code=500, detail=f"Session creation failed: {str(e)}")


@app.get("/sessions", response_model=SessionListResponse)
async def list_sessions(rag_service: RAGService = Depends(get_rag_service)):
    """List all available sessions."""
    try:
        logger.info("Listing all sessions")
        
        result = await rag_service.list_sessions()
        
        return SessionListResponse(**result)
        
    except Exception as e:
        logger.error(f"Session listing failed: {e}")
        raise HTTPException(status_code=500, detail=f"Session listing failed: {str(e)}")


@app.delete("/sessions/{session_id}")
async def delete_session(
    session_id: str,
    rag_service: RAGService = Depends(get_rag_service)
):
    """Delete a session."""
    try:
        logger.info(f"Deleting session: {session_id}")
        
        success = await rag_service.delete_session(session_id)
        
        if success:
            return {"message": f"Session {session_id} deleted successfully"}
        else:
            raise HTTPException(status_code=404, detail="Session not found")
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Session deletion failed: {e}")
        raise HTTPException(status_code=500, detail=f"Session deletion failed: {str(e)}")


@app.post("/generate-topic", response_model=TopicGenerationResponse)
async def generate_topic(
    request: TopicGenerationRequest,
    rag_service: RAGService = Depends(get_rag_service)
):
    """Generate a topic from a query."""
    try:
        logger.info(f"Generating topic for query: {request.query[:50]}...")
        
        topic = await rag_service.generate_topic_from_query(request.query)
        
        return TopicGenerationResponse(topic=topic)
        
    except Exception as e:
        logger.error(f"Topic generation failed: {e}")
        raise HTTPException(status_code=500, detail=f"Topic generation failed: {str(e)}")


@app.get("/sessions/{session_id}/history")
async def get_session_history(
    session_id: str,
    rag_service: RAGService = Depends(get_rag_service)
):
    """Get conversation history for a session."""
    try:
        logger.info(f"Getting history for session: {session_id}")
        
        history = await rag_service.get_session_history(session_id)
        
        return {"messages": history}
        
    except Exception as e:
        logger.error(f"Getting session history failed: {e}")
        raise HTTPException(status_code=500, detail=f"Getting session history failed: {str(e)}")


class SessionUpdateRequest(BaseModel):
    session_name: str

@app.put("/sessions/{session_id}")
async def update_session(
    session_id: str,
    request: SessionUpdateRequest,
    rag_service: RAGService = Depends(get_rag_service)
):
    """Update session name."""
    try:
        logger.info(f"Updating session {session_id} name to: {request.session_name}")
        
        success = await rag_service.update_session_name(session_id, request.session_name)
        
        if success:
            return {"message": "Session updated successfully"}
        else:
            raise HTTPException(status_code=404, detail="Session not found")
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Session update failed: {e}")
        raise HTTPException(status_code=500, detail=f"Session update failed: {str(e)}")


# Root endpoint
@app.get("/")
async def root():
    """Root endpoint with API information."""
    return {
        "message": "Interactive RAG Query API",
        "version": "1.0.0",
        "docs": "/docs",
        "health": "/health",
        "endpoints": {
            "one_time_query": "POST /query/one-time",
            "conversational_query": "POST /query/conversational",
            "create_session": "POST /sessions",
            "list_sessions": "GET /sessions",
            "delete_session": "DELETE /sessions/{session_id}",
            "get_session_history": "GET /sessions/{session_id}/history",
            "update_session": "PUT /sessions/{session_id}",
            "stats": "GET /stats"
        }
    }


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(
        "main:app",
        host="0.0.0.0",
        port=8000,
        reload=True,
        log_level="info"
    )