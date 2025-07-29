# Troubleshooting Guide

## 🚨 Common Issues and Solutions

### 1. Services Not Starting

**Problem**: Docker services fail to start or crash immediately.

**Solutions**:
```bash
# Check Docker is running
docker info

# View service logs
docker-compose logs [service_name]

# Restart with fresh build
docker-compose down
docker-compose up --build

# Clear Docker cache if needed
docker system prune -f
```

### 2. Frontend Not Loading (React)

**Problem**: React frontend shows blank page or connection errors.

**Solutions**:
```bash
# Check frontend logs
docker-compose logs frontend

# Verify backend is running
curl http://localhost:8000/health

# Check if port 3000 is available
lsof -i :3000

# Restart frontend service
docker-compose restart frontend
```

### 3. API Connection Errors

**Problem**: Frontend can't connect to backend APIs.

**Solutions**:
```bash
# Test backend directly
curl http://localhost:8000/health
curl http://localhost:8503/health

# Check network connectivity
docker-compose exec frontend ping backend
docker-compose exec frontend ping collab

# Verify CORS settings in backend logs
docker-compose logs backend | grep CORS
```

### 4. Document Ingestion Failures

**Problem**: Document ingestion fails or times out.

**Common Causes & Solutions**:

#### Missing API Keys
```bash
# Check environment variables
docker-compose exec collab env | grep -E "(OPENAI|PINECONE)"

# Verify .env file has correct keys
cat .env | grep -E "(OPENAI|PINECONE)"
```

#### Selenium/Chrome Issues
```bash
# Check Chrome installation in collab container
docker-compose exec collab which google-chrome

# View detailed ingestion logs
docker-compose logs collab | tail -50

# Restart collab service
docker-compose restart collab
```

#### Network/URL Issues
- Verify URLs are accessible from container
- Check for firewall/proxy issues
- Try with simpler URLs first

### 5. Database Connection Issues

**Problem**: Backend can't connect to PostgreSQL.

**Solutions**:
```bash
# Check PostgreSQL is running
docker-compose exec postgres pg_isready -U postgres

# Test database connection
docker-compose exec backend python -c "
import psycopg2
conn = psycopg2.connect(
    host='postgres', 
    database='genai_devops', 
    user='postgres', 
    password='password'
)
print('Database connection successful')
"

# Reset database if needed
docker-compose down
docker volume rm genai_postgres_data
docker-compose up -d postgres
```

### 6. Redis Connection Issues

**Problem**: Backend can't connect to Redis cache.

**Solutions**:
```bash
# Check Redis is running
docker-compose exec redis redis-cli ping

# Test Redis connection from backend
docker-compose exec backend python -c "
import redis
r = redis.Redis(host='redis', port=6379)
print(r.ping())
"

# Clear Redis cache
docker-compose exec redis redis-cli FLUSHALL
```

### 7. Memory/Performance Issues

**Problem**: Services are slow or running out of memory.

**Solutions**:
```bash
# Check Docker resource usage
docker stats

# Increase Docker memory limits (Docker Desktop)
# Settings > Resources > Advanced > Memory

# Monitor container resource usage
docker-compose exec backend top
docker-compose exec collab top

# Restart services to free memory
docker-compose restart
```

### 8. Port Conflicts

**Problem**: Ports already in use.

**Solutions**:
```bash
# Check what's using the ports
lsof -i :3000  # React frontend
lsof -i :8000  # Backend API
lsof -i :8503  # Collab API
lsof -i :8888  # Jupyter
lsof -i :5432  # PostgreSQL
lsof -i :6379  # Redis

# Kill processes using the ports
sudo kill -9 $(lsof -t -i:3000)

# Or modify docker-compose.yml to use different ports
```

### 9. Build Failures

**Problem**: Docker build fails for specific services.

**Solutions**:
```bash
# Build specific service with verbose output
docker-compose build --no-cache frontend

# Check Dockerfile syntax
docker build -f react-frontend/Dockerfile.dev react-frontend/

# Clear build cache
docker builder prune -f

# Check disk space
df -h
```

### 10. Environment Variable Issues

**Problem**: Services can't access environment variables.

**Solutions**:
```bash
# Verify .env file format (no quotes around values)
cat .env

# Check variables are loaded in containers
docker-compose exec backend env | grep OPENAI
docker-compose exec collab env | grep PINECONE

# Restart services after .env changes
docker-compose down
docker-compose up -d
```

## 🔧 Debugging Commands

### View All Service Logs
```bash
docker-compose logs -f
```

### View Specific Service Logs
```bash
docker-compose logs -f frontend
docker-compose logs -f backend
docker-compose logs -f collab
```

### Execute Commands in Containers
```bash
# Access backend container
docker-compose exec backend bash

# Access collab container
docker-compose exec collab bash

# Access database
docker-compose exec postgres psql -U postgres -d genai_devops
```

### Check Service Health
```bash
# Backend health
curl http://localhost:8000/health

# Collab health
curl http://localhost:8503/health

# Database health
docker-compose exec postgres pg_isready -U postgres
```

### Reset Everything
```bash
# Nuclear option - reset all data and containers
docker-compose down -v
docker system prune -f
docker volume prune -f
docker-compose up --build
```

## 📞 Getting Help

If you're still experiencing issues:

1. **Check the logs**: Always start with `docker-compose logs [service]`
2. **Verify prerequisites**: Ensure Docker, API keys, and network connectivity
3. **Try minimal setup**: Start with just backend and database first
4. **Check GitHub issues**: Look for similar problems in the repository
5. **Create detailed issue**: Include logs, environment details, and steps to reproduce

## 🔍 Useful Monitoring Commands

```bash
# Monitor resource usage
docker stats

# Watch logs in real-time
docker-compose logs -f --tail=100

# Check container status
docker-compose ps

# Inspect container configuration
docker-compose config

# View network information
docker network ls
docker network inspect genai_genai-network
```