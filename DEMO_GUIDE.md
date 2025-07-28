# GenAI DevOps Assistant - MVP Demo Guide

## 🚀 Quick Start

### Prerequisites
- Docker and Docker Compose installed
- OpenAI API key
- Pinecone API key

### 1. Setup Environment

```bash
# Clone and setup
git clone <repository-url>
cd genai-devops-assistant

# Run setup script
./setup.sh

# Update .env file with your API keys
cp .env.example .env
# Edit .env with your actual API keys
```

### 2. Start Services

```bash
# Start all services
docker compose up

# Or start in background
docker compose up -d
```

### 3. Access Services

- **Frontend (Streamlit):** http://localhost:8501
- **Backend (FastAPI):** http://localhost:8000
- **API Docs:** http://localhost:8000/docs
- **Collab (Jupyter):** http://localhost:8888
- **PostgreSQL:** localhost:5432
- **Redis:** localhost:6379

## 🏗️ System Architecture

### Three-Layer Architecture

1. **Collab Folder** - Document Loading & Embedding Creation
   - LangChain comprehensive RAG pipeline
   - Multiple document sources (PDF, Web, Confluence, GitHub)
   - Pinecone vector storage

2. **Backend** - OpenAI API Calls Only
   - FastAPI with multi-tab session support
   - Redis caching for performance
   - PostgreSQL for persistent storage
   - LangChain prompt engineering demos

3. **Frontend** - Multi-Tab Chat Interface
   - Streamlit-based UI
   - Individual conversation contexts per tab
   - Source references and citations

## 📚 Demo Workflow

### Step 1: Document Ingestion (Collab Folder)

1. **Access Jupyter Interface:**
   ```
   http://localhost:8888
   ```

2. **Run Interactive Ingestion:**
   ```python
   # In Jupyter notebook or terminal
   cd /workspace
   python interactive_ingestion.py
   ```

3. **Add Document Sources:**
   - Option 5: Add AWS documentation (predefined)
   - Option 6: Add Terraform documentation
   - Option 1: Add PDF documents
   - Option 2: Add web documents

4. **Process Documents:**
   - Option 9: Process all documents
   - Wait for embedding creation and Pinecone upload

5. **Test Search:**
   - Option 10: Test search functionality
   - Try queries like "What is AWS VPC?" or "Terraform best practices"

### Step 2: Backend API Testing

1. **Check Health:**
   ```bash
   curl http://localhost:8000/health
   ```

2. **API Documentation:**
   ```
   http://localhost:8000/docs
   ```

3. **Test Chat Endpoint:**
   ```bash
   curl -X POST "http://localhost:8000/chat/tab_demo" \
        -H "Content-Type: application/json" \
        -d '{
          "query": "How do I design a cost-effective AWS VPC?",
          "tab_id": "tab_demo"
        }'
   ```

4. **Test LangChain Demos:**
   - Tools & Agents: `/demo/tools`
   - Structured Output: `/demo/structured-output`
   - LCEL Chains: `/demo/lcel-chain`

### Step 3: Frontend Multi-Tab Interface

1. **Access Frontend:**
   ```
   http://localhost:8501
   ```

2. **Create Multiple Tabs:**
   - Click "➕ New Tab"
   - Name tabs for different topics (e.g., "AWS Architecture", "Terraform")

3. **Chat in Different Tabs:**
   - Each tab maintains independent conversation context
   - Ask questions about AWS, DevOps, infrastructure
   - View source references and citations

4. **Test LangChain Demos:**
   - Go to "🧪 Demos" tab
   - Try Tools & Agents demo
   - Test Structured Output generation
   - Experiment with LCEL chains

## 🎯 Demo Scenarios

### Scenario 1: AWS Architecture Design

**Tab: "AWS Architecture"**

1. **Initial Query:**
   ```
   "I need to design a scalable web application architecture on AWS. What services should I use?"
   ```

2. **Follow-up Questions:**
   ```
   "How do I implement auto-scaling for this architecture?"
   "What are the cost implications of this design?"
   "How do I secure this architecture?"
   ```

3. **Expected Features:**
   - Contextual responses based on previous questions
   - Source references from AWS documentation
   - Specific service recommendations

### Scenario 2: Terraform Best Practices

**Tab: "Terraform"**

1. **Initial Query:**
   ```
   "What are the best practices for organizing Terraform code?"
   ```

2. **Follow-up Questions:**
   ```
   "How do I manage Terraform state in a team environment?"
   "Show me an example of a Terraform module for VPC"
   ```

3. **Expected Features:**
   - Independent context from AWS tab
   - Terraform-specific recommendations
   - Code examples and best practices

### Scenario 3: Multi-Tab Context Isolation

1. **Create 3 tabs:**
   - "AWS Basics"
   - "Advanced DevOps"
   - "Cost Optimization"

2. **Ask similar questions in each tab:**
   - Each should maintain separate context
   - No context bleeding between tabs
   - Independent conversation history

### Scenario 4: LangChain Prompt Engineering Demos

1. **Tools & Agents Demo:**
   ```
   Query: "What is EC2 and calculate cost for t3.micro for 24 hours"
   ```
   - Should use both AWS info tool and cost calculation tool

2. **Structured Output Demo:**
   ```
   Query: "I need a scalable web application with database and caching"
   ```
   - Should return structured JSON with services, costs, complexity

3. **LCEL Chains Demo:**
   ```
   Input: "AWS Lambda is a serverless computing service that runs code without provisioning servers..."
   Chain Type: Sequential
   ```
   - Should summarize → extract points → generate questions

## 🔍 Testing Checklist

### Document Ingestion
- [ ] Jupyter interface accessible
- [ ] Interactive ingestion script runs
- [ ] AWS documentation sources added
- [ ] Terraform documentation sources added
- [ ] Documents processed successfully
- [ ] Embeddings created and stored in Pinecone
- [ ] Search functionality works

### Backend API
- [ ] Health check returns healthy status
- [ ] API documentation accessible
- [ ] Chat endpoint responds correctly
- [ ] Multi-tab sessions work independently
- [ ] Session history persisted in PostgreSQL
- [ ] Redis caching improves performance
- [ ] LangChain demos function correctly

### Frontend Interface
- [ ] Streamlit app loads successfully
- [ ] Multiple tabs can be created
- [ ] Tab switching works correctly
- [ ] Chat interface responsive
- [ ] Messages display properly
- [ ] Source references expandable
- [ ] Tab contexts remain isolated
- [ ] Demo section functional

### System Integration
- [ ] All services start successfully
- [ ] Services communicate properly
- [ ] Database connections stable
- [ ] Cache operations working
- [ ] Error handling graceful
- [ ] Logging comprehensive

## 🐛 Troubleshooting

### Common Issues

1. **Docker Build Failures:**
   ```bash
   # Clean and rebuild
   docker compose down
   docker system prune -f
   docker compose build --no-cache
   ```

2. **API Key Errors:**
   - Verify `.env` file has correct API keys
   - Ensure keys are not quoted
   - Check key permissions and quotas

3. **Database Connection Issues:**
   ```bash
   # Check PostgreSQL logs
   docker compose logs postgres
   
   # Restart database
   docker compose restart postgres
   ```

4. **Pinecone Index Issues:**
   - Verify index exists in Pinecone console
   - Check index dimensions match (1536)
   - Ensure API key has proper permissions

5. **Frontend Not Loading:**
   ```bash
   # Check frontend logs
   docker compose logs frontend
   
   # Verify backend connectivity
   curl http://localhost:8000/health
   ```

### Performance Optimization

1. **Enable Caching:**
   - Verify Redis is running
   - Check cache hit rates in `/stats/cache`

2. **Database Performance:**
   - Monitor connection pool usage
   - Check query performance in logs

3. **Memory Usage:**
   - Monitor Docker container memory usage
   - Adjust container limits if needed

## 📊 Monitoring and Metrics

### Health Endpoints

- **Overall Health:** `GET /health`
- **Database Stats:** `GET /stats/database`
- **Cache Stats:** `GET /stats/cache`

### Key Metrics

1. **Response Times:**
   - Chat responses < 5 seconds
   - Health checks < 1 second

2. **Cache Performance:**
   - Cache hit rate > 70%
   - Memory usage stable

3. **Database Performance:**
   - Connection pool utilization
   - Query response times

## 🎉 Success Criteria

The MVP demo is successful if:

1. **Document Ingestion Works:**
   - Can load AWS and Terraform documentation
   - Embeddings created and stored successfully
   - Search returns relevant results

2. **Multi-Tab Chat Functions:**
   - Multiple tabs maintain separate contexts
   - Responses include source references
   - Chat history persists across sessions

3. **LangChain Integration:**
   - Tools and agents work correctly
   - Structured output generates properly
   - LCEL chains execute successfully

4. **System Stability:**
   - All services start and run reliably
   - Error handling works gracefully
   - Performance meets requirements

## 🚀 Next Steps

After successful MVP demo:

1. **Production Deployment:**
   - Configure production environment
   - Set up monitoring and alerting
   - Implement security hardening

2. **Feature Enhancements:**
   - Add more document sources
   - Implement user authentication
   - Add advanced analytics

3. **Scaling Considerations:**
   - Horizontal scaling setup
   - Load balancing configuration
   - Database optimization

## 📞 Support

For issues or questions:
1. Check logs: `docker compose logs [service_name]`
2. Review troubleshooting section
3. Verify environment configuration
4. Test individual components

---

**Happy Demoing! 🎯**