# GenAI-Powered DevOps Cloud Assistant

A restructured full-stack application designed to help DevOps and platform engineers design cost-effective AWS architectures through a conversational interface with clear separation of concerns.

## 🏗️ Architecture

The system uses a clear separation of concerns across three distinct layers:

### 1. **Collab Folder** - Document Loading & Embedding Creation
- Uses LangChain comprehensively for document processing
- Supports PDF, web, Confluence, and GitHub sources
- Creates embeddings using OpenAI text-embedding-ada-002
- Stores vectors in Pinecone using LangChain's PineconeVectorStore

### 2. **Backend** - OpenAI API Calls Only
- FastAPI application focused solely on OpenAI API calls
- Retrieves knowledge from Pinecone vector database
- Uses Redis for caching and performance optimization
- PostgreSQL for persistent chat history storage
- Multi-tab session management

### 3. **Frontend** - Multi-Tab Chat Interface
- Streamlit-based interface with multiple chat tabs
- Each tab maintains its own conversation context
- Individual session management per tab
- Source references and expandable citations

## 🚀 Quick Start

### Prerequisites
- Docker and Docker Compose
- OpenAI API key
- Pinecone API key

### Setup

1. **Clone and setup environment:**
   ```bash
   git clone <repository-url>
   cd genai-devops-assistant
   ./setup.sh
   ```

2. **Update environment variables:**
   ```bash
   cp .env.example .env
   # Edit .env file with your API keys
   ```

3. **Start all services:**
   ```bash
   docker-compose up
   ```

### Service URLs
- **Backend (FastAPI):** http://localhost:8000
- **Frontend (Streamlit):** http://localhost:8501  
- **Collab (Jupyter):** http://localhost:8888
- **PostgreSQL:** localhost:5432
- **Redis:** localhost:6379

## 📁 Project Structure

```
├── collab/                    # LangChain RAG Pipeline
│   ├── langchain_rag_pipeline.py
│   ├── interactive_rag_ingestion.py
│   ├── requirements.txt
│   └── Dockerfile
├── backend/                   # FastAPI Backend
│   ├── main.py
│   ├── config.py
│   ├── models.py
│   ├── rag_engine.py
│   ├── requirements.txt
│   └── Dockerfile
├── frontend/                  # Streamlit Frontend
│   ├── app.py
│   ├── requirements.txt
│   └── Dockerfile
├── scripts/
│   └── init_db.sql           # Database initialization
├── docker-compose.yml
├── .env.example
└── setup.sh
```

## 🔧 Development Workflow

### 1. Document Ingestion (Collab Folder)
```bash
# Access Jupyter interface
open http://localhost:8888

# Run interactive ingestion
python collab/interactive_rag_ingestion.py
```

### 2. Backend Development
```bash
# View API documentation
open http://localhost:8000/docs

# Check health status
curl http://localhost:8000/health
```

### 3. Frontend Development
```bash
# Access multi-tab chat interface
open http://localhost:8501
```

## 🛠️ Key Features

### LangChain Integration
- **Document Loaders:** PyPDFLoader, WebBaseLoader, ConfluenceLoader, GitHubIssuesLoader
- **Text Processing:** RecursiveCharacterTextSplitter for optimal chunking
- **Embeddings:** OpenAI text-embedding-ada-002 via LangChain
- **Vector Store:** PineconeVectorStore for seamless integration
- **Chat Models:** ChatOpenAI with prompt templates and output parsers

### Multi-Tab Chat Interface
- Create, switch, and close chat tabs
- Independent conversation contexts per tab
- Persistent chat history via PostgreSQL
- Real-time message rendering with source references

### Performance Optimization
- Redis caching for responses and embeddings
- Session state caching for quick tab switching
- Connection pooling for database operations

## 📊 Database Schema

### Chat Sessions
```sql
CREATE TABLE chat_sessions (
    session_id VARCHAR(255) PRIMARY KEY,
    tab_id VARCHAR(255) NOT NULL,
    tab_name VARCHAR(255),
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    metadata JSONB
);
```

### Chat Messages
```sql
CREATE TABLE chat_messages (
    id SERIAL PRIMARY KEY,
    session_id VARCHAR(255) REFERENCES chat_sessions(session_id),
    role VARCHAR(50) NOT NULL CHECK (role IN ('user', 'assistant')),
    content TEXT NOT NULL,
    sources JSONB,
    timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    metadata JSONB
);
```

## 🔑 Environment Variables

```bash
# OpenAI Configuration
OPENAI_API_KEY=your_openai_api_key_here
OPENAI_MODEL=gpt-4
OPENAI_EMBEDDING_MODEL=text-embedding-ada-002

# Pinecone Configuration
PINECONE_API_KEY=your_pinecone_api_key_here
PINECONE_ENVIRONMENT=us-east-1-aws
PINECONE_INDEX_NAME=genai-devops-assistant

# Database Configuration
POSTGRES_HOST=localhost
POSTGRES_PORT=5432
POSTGRES_DB=genai_devops
POSTGRES_USER=postgres
POSTGRES_PASSWORD=password

# Redis Configuration
REDIS_HOST=localhost
REDIS_PORT=6379
```

## 🐳 Docker Commands

```bash
# Build all services
docker-compose build

# Start all services
docker-compose up -d

# View logs
docker-compose logs -f [service_name]

# Stop all services
docker-compose down

# Rebuild and restart specific service
docker-compose up --build [service_name]
```

## 🔍 API Endpoints

### Backend (FastAPI)
- `POST /chat/{tab_id}` - Send chat message to specific tab
- `POST /sessions/{tab_id}/new` - Create new session for tab
- `GET /sessions/{tab_id}/history` - Get chat history for tab
- `GET /health` - Health check for all services

## 📝 Usage Examples

### 1. Document Ingestion
```python
# In Jupyter (collab folder)
from interactive_rag_ingestion import InteractiveRAGIngestion

ingestion = InteractiveRAGIngestion()
ingestion.run()
```

### 2. Chat API Usage
```python
import requests

# Create new chat session
response = requests.post("http://localhost:8000/sessions/tab_1/new")
session_id = response.json()["session_id"]

# Send chat message
chat_data = {
    "query": "How do I design a cost-effective AWS VPC?",
    "session_id": session_id
}
response = requests.post("http://localhost:8000/chat/tab_1", json=chat_data)
```

## 🚨 Troubleshooting

### Common Issues

1. **Docker services not starting:**
   ```bash
   docker-compose down
   docker system prune -f
   docker-compose up --build
   ```

2. **Database connection issues:**
   ```bash
   docker-compose logs postgres
   # Check if PostgreSQL is ready
   ```

3. **API key errors:**
   - Verify `.env` file has correct API keys
   - Ensure keys are not quoted in `.env` file

4. **Port conflicts:**
   - Check if ports 8000, 8501, 8888, 5432, 6379 are available
   - Modify `docker-compose.yml` port mappings if needed

## 🤝 Contributing

1. Fork the repository
2. Create a feature branch
3. Make your changes
4. Test with `docker-compose up`
5. Submit a pull request

## 📄 License

This project is licensed under the MIT License.