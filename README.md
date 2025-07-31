# GenAI-Powered DevOps Cloud Assistant

[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)
[![Docker](https://img.shields.io/badge/Docker-Ready-blue.svg)](https://www.docker.com/)
[![FastAPI](https://img.shields.io/badge/FastAPI-0.104+-green.svg)](https://fastapi.tiangolo.com/)
[![React](https://img.shields.io/badge/React-18+-blue.svg)](https://reactjs.org/)

An advanced AI-powered DevOps assistant that provides intelligent AWS infrastructure guidance through conversational AI. Built with a modern three-tier architecture featuring real-time document processing, multi-modal query handling, and comprehensive session management.

## Key Features

- **Multi-Modal AI Queries**: Service recommendations, pricing analysis, Terraform generation
- **Intelligent Document Processing**: Real-time ingestion with smart chunking
- **Advanced Chat Interface**: Multi-tab sessions with persistent history
- **Smart Retrieval**: Context-aware vector search with semantic caching
- **Content Guardrails**: Intelligent query validation and filtering
- **Real-Time Updates**: WebSocket-powered live processing feedback
- **Production Ready**: Docker containerization with health monitoring

## System Architecture

The system uses a clear separation of concerns across three distinct layers:

### Frontend Layer - React Multi-Tab Interface
- Modern React 18 with multi-tab chat sessions
- Real-time WebSocket communication for live updates
- Advanced query type selection (General, Service Recommendation, Pricing, Terraform)
- Responsive design with mobile support

### Backend Layer - FastAPI RAG Engine
- High-performance async FastAPI application
- Comprehensive RAG (Retrieval-Augmented Generation) pipeline
- Multi-modal query processing with specialized handlers
- Advanced session management with hybrid storage
- Intelligent content guardrails and validation

### Processing Layer - Document Ingestion Pipeline
- Flask API server with WebSocket support
- Interactive Jupyter Lab environment for development
- Smart document chunking based on content type
- Multi-source support (Web, GitHub, PDF, CSV)
- Real-time processing updates with detailed logging

### Data Layer - Hybrid Storage System
- **PostgreSQL**: Persistent session and message storage
- **Redis**: High-performance caching and session state
- **Pinecone**: Scalable vector database for semantic search

## Quick Start

### Prerequisites
- Docker and Docker Compose (v2.0+)
- OpenAI API key with GPT-4 access
- Pinecone API key with vector database
- 8GB+ RAM recommended

### Installation

1. **Clone the repository:**
   ```bash
   git clone https://github.com/your-username/genai-devops-assistant.git
   cd genai-devops-assistant
   ```

2. **Setup environment:**
   ```bash
   # Copy environment template
   cp .env.example .env
   
   # Run setup script
   chmod +x setup.sh
   ./setup.sh
   ```

3. **Configure API keys in `.env`:**
   ```bash
   OPENAI_API_KEY=sk-your-openai-key-here
   PINECONE_API_KEY=your-pinecone-key-here
   PINECONE_INDEX_NAME=genai-devops-assistant
   ```

4. **Start the application:**
   ```bash
   # Start all services
   docker compose up -d
   
   # View logs
   docker compose logs -f
   ```

### Service Access

| Service | URL | Purpose |
|---------|-----|----------|
| **React Frontend** | http://localhost:3000 | Main chat interface |
| **FastAPI Backend** | http://localhost:8000 | API documentation |
| **Jupyter Lab** | http://localhost:8888 | Development environment |
| **Processing API** | http://localhost:8503 | Document ingestion |
| **PostgreSQL** | localhost:5432 | Database access |
| **Redis** | localhost:6379 | Cache monitoring |

### First Steps

1. **Access the application** at http://localhost:3000
2. **Ingest documents** using the "Document Ingestion" tab
3. **Start chatting** with AWS-focused queries
4. **Explore query types**: General, Service Recommendations, Pricing, Terraform

## Project Structure

```
genai-devops-assistant/
├── react-frontend/         # Modern React Interface
│   ├── src/
│   │   ├── components/
│   │   │   ├── ChatInterface.js      # Multi-tab chat system
│   │   │   ├── IngestionInterface.js # Document processing UI
│   │   │   └── QueryTypeSelector.js # Query mode selection
│   │   ├── App.js                    # Main application
│   │   └── index.js                  # Entry point
│   ├── Dockerfile.dev               # Development container
│   └── package.json                 # Dependencies
│
├── backend/                # FastAPI RAG Engine
│   ├── main.py                      # API endpoints
│   ├── rag_service.py              # Core RAG orchestration
│   ├── rag_chain.py                # LangChain implementation
│   ├── query_processor.py          # Vector search engine
│   ├── session_manager.py          # Conversation management
│   ├── aws_service_recommender.py  # AWS-specific logic
│   ├── database_manager.py         # PostgreSQL operations
│   ├── redis_manager.py            # Cache management
│   ├── cache_manager.py            # Multi-layer caching
│   ├── config.py                   # Configuration
│   ├── models.py                   # Data models
│   └── requirements.txt            # Python dependencies
│
├── collab/                 # Document Processing Pipeline
│   ├── api_server.py               # Flask API + WebSocket
│   ├── interactive_ingestion.py    # Core ingestion logic
│   ├── websocket_server.py         # Real-time communication
│   ├── selenium_web_loader.py      # Enhanced web scraping
│   ├── models.py                   # Data structures
│   ├── config.py                   # Configuration
│   └── uploads/                    # File storage
│
├── scripts/               # Database & Deployment
│   ├── init_db.sql                 # Database schema
│   ├── deploy.sh                   # Deployment script
│   └── validate_system.py          # System validation
│
├── docs/                   # Documentation
│   └── CONFIGURATION.md            # Setup guide
│
├── Infrastructure
│   ├── docker-compose.yml          # Service orchestration
│   ├── .env.example               # Environment template
│   ├── setup.sh                   # Setup automation
│   └── ARCHITECTURAL_REVIEW.md    # Technical documentation
```

## Advanced Features

### AI-Powered Query Processing

#### Multi-Modal Query Types
- **General Queries**: Comprehensive AWS/DevOps assistance with contextual responses
- **Service Recommendations**: Chain-of-Thought reasoning for optimal AWS service selection
- **Pricing Analysis**: Detailed cost breakdowns with optimization strategies
- **Terraform Generation**: Production-ready Infrastructure-as-Code creation

#### Intelligent Content Guardrails
- **Context-Aware Validation**: Considers conversation history for better filtering
- **Mode-Specific Filtering**: Tailored validation for each query type
- **Automatic Session Management**: Smart cleanup on policy violations
- **Graceful Error Handling**: User-friendly feedback with fallback options

### Advanced Document Processing

#### Smart Multi-Source Ingestion
- **Web Sources**: JavaScript-heavy sites with Selenium automation
- **GitHub Integration**: Repository code analysis with file filtering
- **Document Support**: PDF, CSV, and structured document processing
- **Real-Time Processing**: WebSocket-powered live updates with detailed logging

#### Intelligent Chunking Strategies
- **Content-Aware Segmentation**: Different strategies for code, docs, and data
- **Terraform-Specific Chunking**: Preserves complete resource blocks
- **AWS Documentation Optimization**: Service-focused content organization
- **Metadata Enhancement**: Priority, category, and custom tag systems

### Advanced Chat Interface

#### Multi-Tab Session Management
- **Independent Contexts**: Each tab maintains separate conversation history
- **Persistent Storage**: PostgreSQL-backed session persistence
- **Smart Caching**: Redis-powered fast session switching
- **Topic Generation**: AI-powered automatic tab naming

#### Enhanced User Experience
- **Real-Time Rendering**: Markdown support with syntax highlighting
- **Source References**: Clickable source citations and metadata
- **Quick Response Modal**: One-off queries without session creation
- **Mobile-Responsive Design**: Optimized for all device sizes

## Configuration

### Environment Variables

```bash
# AI Services
OPENAI_API_KEY=sk-your-openai-key-here
OPENAI_MODEL=gpt-4                           # Primary chat model
OPENAI_EMBEDDING_MODEL=text-embedding-ada-002 # Embedding model
OPENAI_TEMPERATURE=0.1                       # Response creativity
OPENAI_MAX_TOKENS=4000                       # Max response length

# Vector Database
PINECONE_API_KEY=your-pinecone-key-here
PINECONE_ENVIRONMENT=us-east-1-aws           # Pinecone region
PINECONE_INDEX_NAME=genai-devops-assistant   # Index name

# Database Configuration
POSTGRES_HOST=postgres                       # Container name
POSTGRES_PORT=5432
POSTGRES_DB=genai_devops
POSTGRES_USER=postgres
POSTGRES_PASSWORD=password

# Cache Configuration
REDIS_HOST=redis                             # Container name
REDIS_PORT=6379
REDIS_PASSWORD=                              # Optional password

# Application Settings
ENVIRONMENT=development                       # development/production
REACT_APP_BACKEND_URL=http://localhost:8000  # Backend API URL
REACT_APP_COLLAB_URL=http://localhost:8503   # Processing API URL
```

## Docker Operations

### Basic Commands

```bash
# Start all services
docker compose up -d

# View service status
docker compose ps

# View logs
docker compose logs -f                    # All services
docker compose logs -f backend frontend   # Specific services

# Stop all services
docker compose down

# Restart specific service
docker compose restart backend

# Rebuild and restart
docker compose up --build backend
```

### Development Commands

```bash
# Clean rebuild (removes containers and images)
docker compose down --volumes --rmi all
docker compose build --no-cache
docker compose up -d

# Debug container
docker compose exec backend bash         # Access backend container
docker compose exec postgres psql -U postgres genai_devops  # Database access

# Monitor resources
docker stats                              # Resource usage
docker compose top                        # Process information
```

## API Reference

### Backend API (FastAPI) - Port 8000

#### Query Processing
```bash
# Conversational query with session context
POST /query/conversational
{
  "query": "How to set up AWS VPC?",
  "session_id": "session_123",
  "query_type": "general",  # general|service_recommendation|pricing|terraform
  "top_k": 5
}

# One-time query without session
POST /query/one-time
{
  "query": "AWS Lambda pricing",
  "query_type": "pricing",
  "top_k": 3
}
```

#### Session Management
```bash
# Create new session
POST /sessions
{"session_name": "AWS Architecture Discussion"}

# List all sessions
GET /sessions

# Get session history
GET /sessions/{session_id}/history

# Update session name
PUT /sessions/{session_id}
{"session_name": "Updated Name"}

# Delete session
DELETE /sessions/{session_id}
```

#### Utilities
```bash
# Generate topic from query
POST /generate-topic
{"query": "How to deploy microservices on AWS?"}

# System health check
GET /health

# Vector index statistics
GET /stats
```

### Processing API (Flask) - Port 8503

#### Document Ingestion
```bash
# Process documents with WebSocket updates
POST /api/process
{
  "input": "{\"sources\": [...], \"config\": {}}",
  "session_id": "ingestion_123"
}

# Upload files
POST /api/upload
# Multipart form data with file

# Stop processing
POST /api/stop
{"session_id": "ingestion_123"}

# Check system status
GET /api/status

# Health check
GET /health
```

## Usage Examples

### Chat API Usage

```python
import requests
import json

# Create new chat session
response = requests.post("http://localhost:8000/sessions", 
    json={"session_name": "AWS Architecture Planning"})
session_data = response.json()
session_id = session_data["session_id"]

# Send conversational query
chat_response = requests.post("http://localhost:8000/query/conversational", 
    json={
        "query": "I need a cost-effective serverless architecture for a web API",
        "session_id": session_id,
        "query_type": "service_recommendation"
    })

print(chat_response.json()["response"])

# Get pricing estimate
pricing_response = requests.post("http://localhost:8000/query/conversational", 
    json={
        "query": "What would be the monthly cost for 10,000 requests?",
        "session_id": session_id,
        "query_type": "pricing"
    })

# Generate Terraform code
terraform_response = requests.post("http://localhost:8000/query/conversational", 
    json={
        "query": "Generate Terraform for the recommended architecture",
        "session_id": session_id,
        "query_type": "terraform"
    })
```

### Document Ingestion

```python
# Using the web interface (recommended)
# 1. Go to http://localhost:3000/ingest
# 2. Add sources (web URLs, GitHub repos, files)
# 3. Configure metadata (priority, category, tags)
# 4. Click "Start Processing" for real-time updates

# Programmatic ingestion
import requests

sources = [
    {
        "type": "web",
        "path": "https://docs.aws.amazon.com/vpc/latest/userguide/",
        "docType": "aws_documentation",
        "priority": "high",
        "category": "aws-docs",
        "tags": ["vpc", "networking", "aws"]
    },
    {
        "type": "github",
        "path": "terraform-aws-modules/terraform-aws-vpc",
        "token": "github_token_here",
        "extensions": [".tf", ".md"],
        "priority": "medium",
        "category": "terraform"
    }
]

ingestion_response = requests.post("http://localhost:8503/api/process", 
    json={
        "input": json.dumps({"sources": sources}),
        "session_id": "ingestion_session_123"
    })
```

## Troubleshooting

### Common Issues

#### Docker & Services

```bash
# Docker services not starting
docker compose down --volumes
docker system prune -f
docker compose build --no-cache
docker compose up -d

# Check service health
docker compose ps
curl http://localhost:8000/health
curl http://localhost:8503/health

# View detailed logs
docker compose logs --tail=100 backend
docker compose logs --tail=100 postgres
```

#### Database Issues

```bash
# PostgreSQL connection problems
docker compose logs postgres
docker compose exec postgres pg_isready -U postgres

# Reset database
docker compose down -v
docker compose up -d postgres
# Wait for PostgreSQL to be ready
docker compose up -d

# Manual database access
docker compose exec postgres psql -U postgres -d genai_devops
```

#### API & Configuration

```bash
# API key validation
# Verify .env file (no quotes around values)
OPENAI_API_KEY=sk-your-key-here  # Correct
OPENAI_API_KEY="sk-your-key-here"  # Wrong

# Test API connectivity
curl -H "Authorization: Bearer $OPENAI_API_KEY" \
  https://api.openai.com/v1/models

# Check Pinecone connection
python -c "import pinecone; pinecone.init(api_key='your-key'); print('Connected')"
```

#### Port Conflicts

```bash
# Check port availability
netstat -tulpn | grep :3000  # Frontend
netstat -tulpn | grep :8000  # Backend
netstat -tulpn | grep :8503  # Processing

# Kill processes using ports
sudo lsof -ti:3000 | xargs kill -9
sudo lsof -ti:8000 | xargs kill -9
```

### Performance Issues

#### Slow Query Responses

```bash
# Check Redis cache status
docker compose exec redis redis-cli info memory
docker compose exec redis redis-cli dbsize

# Monitor Pinecone index
curl http://localhost:8000/stats

# Check embedding cache hit rate
docker compose logs backend | grep "cache hit"
```

#### Memory Issues

```bash
# Monitor container resources
docker stats

# Increase Docker memory limits
# Docker Desktop: Settings > Resources > Memory > 8GB+

# Clear caches
docker compose exec redis redis-cli flushall
docker system prune -f
```

### Debug Mode

```bash
# Enable debug logging
export LOG_LEVEL=DEBUG
docker compose up -d

# Interactive debugging
docker compose exec backend python -c "import pdb; pdb.set_trace()"

# Check component health
curl http://localhost:8000/health | jq
curl http://localhost:8503/api/status | jq
```

### Getting Help

1. **Check Logs**: Always start with `docker compose logs -f`
2. **Health Endpoints**: Use `/health` endpoints for service status
3. **API Documentation**: Visit http://localhost:8000/docs
4. **System Validation**: Run `python scripts/validate_system.py`
5. **GitHub Issues**: Report bugs with logs and configuration details

## Contributing

### Development Setup

1. **Fork and Clone**:
   ```bash
   git clone https://github.com/your-username/genai-devops-assistant.git
   cd genai-devops-assistant
   ```

2. **Create Feature Branch**:
   ```bash
   git checkout -b feature/your-feature-name
   ```

3. **Development Environment**:
   ```bash
   cp .env.example .env
   # Add your API keys
   docker compose up -d
   ```

4. **Make Changes**:
   - **Frontend**: React components in `react-frontend/src/`
   - **Backend**: FastAPI endpoints in `backend/`
   - **Processing**: Document ingestion in `collab/`

5. **Test Changes**:
   ```bash
   # Run system validation
   python scripts/validate_system.py
   
   # Test API endpoints
   curl http://localhost:8000/health
   
   # Test document processing
   # Use the web interface at http://localhost:3000/ingest
   ```

6. **Submit Pull Request**:
   - Ensure all services start successfully
   - Include tests for new features
   - Update documentation as needed

### Code Style

- **Python**: Follow PEP 8, use type hints
- **JavaScript**: Use ES6+, functional components
- **Documentation**: Update README and inline comments
- **Commit Messages**: Use conventional commits format

### Areas for Contribution

- **AI Improvements**: Enhanced prompts, new query types
- **Document Loaders**: Support for new source types
- **UI/UX**: Interface improvements, mobile optimization
- **Performance**: Caching strategies, optimization
- **Security**: Authentication, authorization, input validation
- **Monitoring**: Metrics, logging, observability
- **Testing**: Unit tests, integration tests, E2E tests

## Documentation

- **[Architectural Review](ARCHITECTURAL_REVIEW.md)**: Comprehensive technical documentation
- **[Configuration Guide](docs/CONFIGURATION.md)**: Detailed setup instructions
- **[API Documentation](http://localhost:8000/docs)**: Interactive API reference
- **[Development Guide](docs/DEVELOPMENT.md)**: Development best practices

## Acknowledgments

- **LangChain**: RAG pipeline and document processing
- **OpenAI**: GPT-4 and embedding models
- **Pinecone**: Vector database and similarity search
- **FastAPI**: High-performance API framework
- **React**: Modern frontend framework

## License

This project is licensed under the MIT License - see the [LICENSE](LICENSE) file for details.

## Star History

If you find this project helpful, please consider giving it a star!

---

**Built with care for the DevOps community**