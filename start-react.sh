#!/bin/bash

echo "🚀 Starting GenAI DevOps Assistant with React Frontend..."
echo "=================================================="

# Check if .env file exists
if [ ! -f ".env" ]; then
    echo "❌ .env file not found!"
    echo "Please copy .env.example to .env and configure your API keys:"
    echo "  cp .env.example .env"
    echo "  # Edit .env with your OpenAI and Pinecone API keys"
    exit 1
fi

# Check if Docker is running
if ! docker info > /dev/null 2>&1; then
    echo "❌ Docker is not running!"
    echo "Please start Docker and try again."
    exit 1
fi

echo "✅ Environment check passed"
echo ""

# Build and start services
echo "🔧 Building and starting services..."
docker-compose up --build -d

echo ""
echo "⏳ Waiting for services to be ready..."
sleep 10

# Check service health
echo "🔍 Checking service health..."

# Check backend
if curl -s http://localhost:8000/health > /dev/null; then
    echo "✅ Backend (FastAPI) - Ready"
else
    echo "⚠️  Backend (FastAPI) - Starting up..."
fi

# Check collab
if curl -s http://localhost:8503/health > /dev/null; then
    echo "✅ Collab (Ingestion API) - Ready"
else
    echo "⚠️  Collab (Ingestion API) - Starting up..."
fi

# Check frontend
if curl -s http://localhost:3000 > /dev/null; then
    echo "✅ Frontend (React) - Ready"
else
    echo "⚠️  Frontend (React) - Starting up..."
fi

echo ""
echo "🌐 Service URLs:"
echo "  Frontend (React):     http://localhost:3000"
echo "  Backend API:          http://localhost:8000"
echo "  API Documentation:    http://localhost:8000/docs"
echo "  Collab/Ingestion:     http://localhost:8503"
echo "  Jupyter Notebook:     http://localhost:8888"
echo ""
echo "📋 Quick Start:"
echo "  1. Open http://localhost:3000 in your browser"
echo "  2. Create a new chat session"
echo "  3. Try asking: 'How do I design a cost-effective AWS VPC?'"
echo "  4. Use the Document Ingestion tab to add your own knowledge sources"
echo ""
echo "🛑 To stop all services: docker-compose down"
echo "📊 To view logs: docker-compose logs -f [service_name]"
echo ""
echo "🎉 GenAI DevOps Assistant is ready!"