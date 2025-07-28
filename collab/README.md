# Interactive RAG Query System

A comprehensive interactive Python application for querying a RAG (Retrieval-Augmented Generation) model using LangChain, with support for both one-time queries and context-aware conversations.

## 🚀 Features

- **Two Query Modes**: One-time queries and context-aware conversations
- **Session Management**: Persistent chat history using PostgreSQL and Redis caching
- **LangChain Integration**: Comprehensive use of LangChain for RAG chains, memory management, and agents
- **Vector Search**: Uses existing Pinecone vector embeddings created by `interactive_ingestion.py`
- **Caching**: Multi-layer caching with Redis for performance optimization
- **Error Handling**: Robust error handling with retry mechanisms and user-friendly messages
- **Interactive CLI**: Menu-driven interface for easy testing and interaction

## 📋 Prerequisites

1. **Docker Services**: Ensure the following services are running via docker-compose:
   - PostgreSQL database
   - Redis cache
   - (Pinecone is accessed via API)

2. **Environment Variables**: Set the following environment variables:
   ```bash
   export OPENAI_API_KEY="your-openai-api-key"
   export PINECONE_API_KEY="your-pinecone-api-key"
   export PINECONE_ENVIRONMENT="your-pinecone-environment"
   export PINECONE_INDEX_NAME="your-pinecone-index-name"
   ```

3. **Vector Index**: Run `interactive_ingestion.py` first to create and populate the Pinecone vector index with documents.

## 🛠️ Installation

1. **Install Dependencies**:
   ```bash
   cd collab
   pip install -r requirements.txt
   ```

2. **Start Docker Services**:
   ```bash
   # From the project root
   docker-compose up -d postgres redis
   ```

3. **Verify Configuration**:
   ```bash
   python -c "from config import get_config; print('Config loaded successfully')"
   ```

## 🎯 Usage

### Quick Start

```bash
cd collab
python run_interactive_query.py
```

Or directly:

```bash
python interactive_rag_query.py
```

### Main Menu Options

When you start the application, you'll see the main menu:

```
🤖 Interactive RAG Query System
============================================================
1. One-time Query (no conversation history)
2. Conversational Mode (with history)
3. Session Management
4. System Settings
5. Help
0. Exit
============================================================
```

### 1. One-Time Query Mode

Perfect for quick lookups without maintaining conversation history:

```
🔍 One-time Query Mode
Enter your query (or 'back' to return to main menu):

> What is the best way to design a VPC in AWS?

🤔 Processing your query...

💬 Response:
To design a VPC in AWS effectively, consider the following best practices:

1. **CIDR Block Planning**: Choose an appropriate CIDR block that won't conflict with other networks...
2. **Subnet Strategy**: Create public and private subnets across multiple Availability Zones...
3. **Security Groups**: Configure security groups as virtual firewalls...

Sources:
1. AWS VPC User Guide - VPC Best Practices
2. AWS Well-Architected Framework - Security Pillar
```

### 2. Conversational Mode

Maintains conversation history for context-aware responses:

```
💬 Conversational Mode
Active session: session_abc123
Enter your queries (or 'back' to return to main menu):

> What is Terraform?

💬 Response:
Terraform is an Infrastructure as Code (IaC) tool that allows you to define and provision infrastructure using declarative configuration files...

> How does it work with AWS?

💬 Response:
Building on what I mentioned about Terraform, it works with AWS through the AWS Provider. This provider allows Terraform to manage AWS resources by...
```

### 3. Session Management

Manage your conversation sessions:

```
📋 Session Management
========================================
1. List sessions
2. Create new session
3. Switch session
4. Delete session
5. Session statistics
0. Back to main menu
========================================
```

## 🏗️ Architecture

### Core Components

1. **InteractiveRAGQuery**: Main application orchestrator
2. **QueryProcessor**: Handles vector retrieval using LangChain and Pinecone
3. **RAGChain**: Manages response generation with LangChain chains
4. **SessionManager**: Handles conversation sessions with LangChain memory
5. **CacheManager**: Multi-layer caching with Redis
6. **MenuSystem**: Interactive CLI interface
7. **ErrorHandler**: Comprehensive error handling with retry mechanisms

### LangChain Integration

- **RetrievalQA Chain**: For one-time queries
- **ConversationalRetrievalChain**: For context-aware conversations
- **ConversationBufferMemory**: For conversation history
- **ConversationSummaryMemory**: For long conversations
- **Custom Tools**: For menu system navigation
- **Callback Handlers**: For monitoring and error handling

### Data Flow

```
User Input → Menu System → RAG Chain → Query Processor → Pinecone
                ↓              ↓            ↓
         Session Manager → Cache Manager → Redis
                ↓
         Database Manager → PostgreSQL
```

## ⚙️ Configuration

### Environment Variables

| Variable | Description | Default |
|----------|-------------|---------|
| `OPENAI_API_KEY` | OpenAI API key | Required |
| `OPENAI_MODEL` | OpenAI model name | `gpt-4` |
| `OPENAI_EMBEDDING_MODEL` | Embedding model | `text-embedding-ada-002` |
| `PINECONE_API_KEY` | Pinecone API key | Required |
| `PINECONE_ENVIRONMENT` | Pinecone environment | Required |
| `PINECONE_INDEX_NAME` | Pinecone index name | `genai-devops-assistant` |
| `REDIS_HOST` | Redis host | `localhost` |
| `REDIS_PORT` | Redis port | `6379` |
| `POSTGRES_HOST` | PostgreSQL host | `localhost` |
| `POSTGRES_PORT` | PostgreSQL port | `5432` |
| `POSTGRES_DB` | Database name | `genai_devops` |
| `POSTGRES_USER` | Database user | `postgres` |
| `POSTGRES_PASSWORD` | Database password | `password` |

### Docker Compose Setup

The application expects the following services to be running:

```yaml
services:
  postgres:
    image: postgres:15-alpine
    environment:
      POSTGRES_DB: genai_devops
      POSTGRES_USER: postgres
      POSTGRES_PASSWORD: password
    ports:
      - "5432:5432"

  redis:
    image: redis:7-alpine
    ports:
      - "6379:6379"
```

## 🧪 Testing

### Run Unit Tests

```bash
cd collab
pytest test_session_manager.py -v
pytest test_query_processor.py -v
pytest test_cache_manager.py -v
```

### Run Integration Tests

```bash
pytest test_integration.py -v
```

### Run All Tests

```bash
pytest -v
```

## 🔧 Development

### Project Structure

```
collab/
├── interactive_rag_query.py      # Main application
├── run_interactive_query.py      # Launcher script
├── config.py                     # Configuration management
├── models.py                     # Data models
├── database_manager.py           # PostgreSQL integration
├── redis_manager.py              # Redis integration
├── session_manager.py            # Session management with LangChain memory
├── query_processor.py            # Vector retrieval with LangChain
├── rag_chain.py                  # RAG chains for response generation
├── cache_manager.py              # Caching layer
├── menu_system.py                # Interactive CLI interface
├── error_handler.py              # Error handling and retry logic
├── requirements.txt              # Python dependencies
├── test_*.py                     # Test files
└── README.md                     # This file
```

### Adding New Features

1. **New Query Types**: Extend `RAGChain` class
2. **New Menu Options**: Add tools to `MenuSystem`
3. **New Storage Backends**: Implement new managers following existing patterns
4. **New LangChain Components**: Integrate via existing callback system

## 🐛 Troubleshooting

### Common Issues

1. **"Pinecone index not found"**
   - Run `interactive_ingestion.py` first to create the index
   - Verify `PINECONE_INDEX_NAME` environment variable

2. **"Database connection failed"**
   - Ensure PostgreSQL is running: `docker-compose up -d postgres`
   - Check connection parameters in environment variables

3. **"Redis connection failed"**
   - Ensure Redis is running: `docker-compose up -d redis`
   - Check Redis host and port configuration

4. **"OpenAI API error"**
   - Verify `OPENAI_API_KEY` is set correctly
   - Check API key has sufficient credits/permissions

5. **"No documents found"**
   - Ensure vector index has been populated with documents
   - Check Pinecone index statistics in System Settings

### Debug Mode

Enable debug logging:

```bash
export LOG_LEVEL=DEBUG
python interactive_rag_query.py
```

### Health Check

Check system health from the Settings menu (option 4 → option 1):

```
📊 System Status:
Query Processor     : ✅ Ready
Session Manager     : ✅ Ready
RAG Chain          : ✅ Ready
Cache Manager      : ✅ Ready

📈 Vector Index Stats:
Total Vectors      : 1,234
Dimension          : 1536
Index Fullness     : 12.34%
```

## 📊 Performance Tips

1. **Use Conversational Mode** for related queries to benefit from context
2. **Enable Caching** (enabled by default) for faster repeated queries
3. **Monitor Memory Usage** with long conversations - use summary memory for very long sessions
4. **Batch Similar Queries** when possible to benefit from caching

## 🤝 Contributing

1. Follow the existing code structure and patterns
2. Add comprehensive tests for new features
3. Update documentation for any new functionality
4. Use LangChain components where possible for consistency

## 📝 License

This project is part of the GenAI DevOps Assistant system.

## 🆘 Support

For issues and questions:

1. Check the troubleshooting section above
2. Review the logs in `interactive_rag_query.log`
3. Use the built-in help system (main menu option 5)
4. Check system status in Settings menu

---

**Happy Querying! 🚀**