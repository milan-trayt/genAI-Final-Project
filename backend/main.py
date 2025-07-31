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
from typing import Dict, Any, Optional
from pydantic import BaseModel
from typing import List

class TopicGenerationRequest(BaseModel):
    query: str

class TopicGenerationResponse(BaseModel):
    topic: str
from rag_service import RAGService, get_rag_service, close_rag_service

logging.basicConfig(level=logging.WARNING)
logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Application lifespan manager."""
    try:
        rag_service = await get_rag_service()
        yield
    except Exception as e:
        logger.error(f"Failed to initialize RAG service: {e}")
        raise
    finally:
        await close_rag_service()


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
    allow_origins=[
        "http://localhost:3000", 
        "http://localhost:3001",
        "http://frontend:3000",
        "http://genai-frontend:3000"
    ],
    allow_credentials=True,
    allow_methods=["GET", "POST", "PUT", "DELETE", "OPTIONS"],
    allow_headers=["*"],
)


# Exception handler
@app.exception_handler(Exception)
async def global_exception_handler(request, exc):
    """Global exception handler."""
    logger.error(f"Unhandled exception: {exc}")
    return JSONResponse(
        status_code=500,
content={
            "error": "Internal server error",
            "detail": str(exc),
            "timestamp": datetime.utcnow().isoformat()
        }
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
        result = await rag_service.process_one_time_query(
            query=request.query,
            query_type=getattr(request, 'query_type', 'general'),
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
        query_type = getattr(request, 'query_type', 'general')
        result = await rag_service.process_conversational_query(
            query=request.query,
            session_id=request.session_id,
            query_type=query_type,
            filters=None,
            top_k=request.top_k
        )
        
        response_data = {
            "response": str(result["response"]),
            "processing_time": float(result["processing_time"]),
            "cached": bool(result["cached"]),
            "timestamp": str(result["timestamp"]),
            "query_type": str(result.get("query_type", "general")),
            "metadata": {
                "recommendation": result.get("recommendation"),
                "pricing": result.get("pricing"),
                "terraform_code": result.get("terraform_code")
            }
        }
        return QueryResponse(**response_data)
        
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
        result = await rag_service.create_session(request.session_name)
        return SessionCreateResponse(**result)
        
    except Exception as e:
        logger.error(f"Session creation failed: {e}")
        raise HTTPException(status_code=500, detail=f"Session creation failed: {str(e)}")


@app.get("/sessions", response_model=SessionListResponse)
async def list_sessions(rag_service: RAGService = Depends(get_rag_service)):
    """List all available sessions."""
    try:
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
        history = await rag_service.get_session_history(session_id)
        return {"messages": history}
        
    except Exception as e:
        logger.error(f"Getting session history failed: {e}")
        raise HTTPException(status_code=500, detail=f"Getting session history failed: {str(e)}")


@app.post("/ingest")
async def ingest_documents(request: dict):
    """Process document ingestion using collab scripts."""
    try:
        import subprocess
        import json
        

        
        # Create input file for Python script
        input_data = {
            "sources": request.get("sources", []),
            "config": request.get("config", {})
        }
        
        # Call the Python ingestion script
        # Make HTTP request to collab container
        import httpx
        
        collab_response = httpx.post(
            "http://collab:8503/api/ingest",
            json=input_data,
            timeout=300.0
        )
        
        if collab_response.status_code == 200:
            return {"status": "success", "message": "Documents processed successfully"}
        else:
            return {"status": "error", "message": f"Collab processing failed: {collab_response.text}"}
        

            
    except Exception as e:
        logger.error(f"Document ingestion failed: {e}")
        raise HTTPException(status_code=500, detail=f"Document ingestion failed: {str(e)}")


class SessionUpdateRequest(BaseModel):
    session_name: str

class IngestionRequest(BaseModel):
    sources: list
    config: dict = {}

@app.put("/sessions/{session_id}")
async def update_session(
    session_id: str,
    request: SessionUpdateRequest,
    rag_service: RAGService = Depends(get_rag_service)
):
    """Update session name."""
    try:
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