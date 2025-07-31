#!/bin/bash

# GenAI DevOps Assistant Setup Script
# This script sets up the development environment for the restructured architecture

echo "Setting up GenAI DevOps Assistant..."

# Check if .env file exists
if [ ! -f .env ]; then
    echo "Creating .env file from template..."
    cp .env.example .env
    echo "⚠️  Please update .env file with your API keys before running the application"
else
    echo ".env file already exists"
fi

# Create data directory if it doesn't exist
if [ ! -d "data" ]; then
    echo "Creating data directory..."
    mkdir -p data
fi

# Check if Docker is running
if ! docker info > /dev/null 2>&1; then
    echo "Docker is not running. Please start Docker and try again."
    exit 1
fi

echo "🐳 Building Docker containers..."
docker compose build

echo "Starting services..."
docker compose up -d postgres redis

echo "⏳ Waiting for database to be ready..."
sleep 10

echo "Services are ready!"
echo ""
echo "Service URLs:"
echo "   Backend (FastAPI):     http://localhost:8000"
echo "   Frontend (Streamlit):  http://localhost:8501"
echo "   Collab (Jupyter):      http://localhost:8888"
echo "   PostgreSQL:            localhost:5432"
echo "   Redis:                 localhost:6379"
echo ""
echo "To start all services:"
echo "   docker compose up"
echo ""
echo "To stop all services:"
echo "   docker compose down"
echo ""
echo "📖 To view logs:"
echo "   docker compose logs -f [service_name]"
echo ""
echo "⚠️  Don't forget to update your .env file with actual API keys!"