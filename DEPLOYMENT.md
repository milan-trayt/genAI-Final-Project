# GenAI DevOps Assistant - Deployment Guide

This guide covers the deployment of the GenAI DevOps Assistant using Docker and Docker Compose.

## Table of Contents

- [Prerequisites](#prerequisites)
- [Quick Start](#quick-start)
- [Environment Configuration](#environment-configuration)
- [Deployment Environments](#deployment-environments)
- [Service Architecture](#service-architecture)
- [Monitoring and Logging](#monitoring-and-logging)
- [Troubleshooting](#troubleshooting)
- [Maintenance](#maintenance)

## Prerequisites

### System Requirements

- **Operating System**: Linux, macOS, or Windows with WSL2
- **Docker**: Version 20.10 or higher
- **Docker Compose**: Version 2.0 or higher
- **Memory**: Minimum 4GB RAM (8GB recommended)
- **Storage**: Minimum 10GB free space
- **Network**: Internet access for API calls and image downloads

### Required API Keys

- **OpenAI API Key**: For GPT-4 and embedding models
- **Pinecone API Key**: For vector database operations
- **GitHub Token** (Optional): For enhanced document ingestion

## Quick Start

### 1. Clone and Setup

```bash
git clone <repository-url>
cd genai-devops-assistant

# Copy environment template
cp .env.example .env

# Edit .env with your API keys
nano .env
```

### 2. Deploy Development Environment

```bash
# Make deploy script executable
chmod +x scripts/deploy.sh

# Start development environment
./scripts/deploy.sh development up
```

### 3. Access the Application

- **Frontend**: http://localhost:8501
- **Backend API**: http://localhost:8000
- **API Documentation**: http://localhost:8000/docs
- **Health Check**: http://localhost:8000/health

### 4. Run Knowledge Ingestion

```bash
# Run interactive ingestion
./scripts/deploy.sh development ingestion
```

## Environment Configuration

### Environment Variables

Edit the `.env` file with your configuration:

```bash
# Required - OpenAI Configuration
OPENAI_API_KEY=your_openai_api_key_here
OPENAI_MODEL=gpt-4
OPENAI_EMBEDDING_MODEL=text-embedding-ada-002

# Required - Pinecone Configuration
PINECONE_API_KEY=your_pinecone_api_key_here
PINECONE_ENVIRONMENT=your_pinecone_environment_here
PINECONE_INDEX_NAME=genai-devops-assistant

# Optional - GitHub Token for enhanced ingestion
GITHUB_TOKEN=your_github_token_here

# Application Settings
LOG_LEVEL=INFO
RATE_LIMIT_PER_MINUTE=60
MAX_QUERY_LENGTH=2000
```

### Configuration Validation

The system will validate your configuration on startup. Check logs if services fail to start:

```bash
./scripts/deploy.sh development logs
```

## Deployment Environments

### Development Environment

**Purpose**: Local development with hot reload and debugging

**Features**:
- Hot reload for code changes
- Debug logging enabled
- Development tools included
- Direct port access

**Usage**:
```bash
./scripts/deploy.sh development up
```

**Services**:
- Backend: http://localhost:8000
- Frontend: http://localhost:8501
- Redis: localhost:6379
- Redis Commander: http://localhost:8081 (with tools profile)

### Production Environment

**Purpose**: Production deployment with optimizations

**Features**:
- Multiple worker processes
- Nginx reverse proxy
- SSL/TLS support
- Monitoring and logging
- Resource limits
- Health checks

**Usage**:
```bash
./scripts/deploy.sh production up
```

**Services**:
- Application: http://localhost (via Nginx)
- Monitoring: http://localhost:3000 (Grafana)
- Metrics: http://localhost:9090 (Prometheus)

### Testing Environment

**Purpose**: Automated testing and CI/CD

**Usage**:
```bash
./scripts/deploy.sh testing up
```

## Service Architecture

### Core Services

#### Backend API
- **Image**: Custom Python FastAPI application
- **Port**: 8000
- **Health Check**: `/health` endpoint
- **Dependencies**: Redis, OpenAI API, Pinecone

#### Frontend
- **Image**: Custom Streamlit application
- **Port**: 8501
- **Health Check**: `/_stcore/health` endpoint
- **Dependencies**: Backend API

#### Redis
- **Image**: redis:7-alpine
- **Port**: 6379
- **Purpose**: Caching and session management
- **Persistence**: Volume mounted data

#### Knowledge Ingestion
- **Image**: Custom Python application
- **Purpose**: Process and embed documents
- **Usage**: On-demand execution
- **Dependencies**: OpenAI API, Pinecone, GitHub API

### Optional Services (Production)

#### Nginx
- **Image**: nginx:alpine
- **Port**: 80, 443
- **Purpose**: Reverse proxy and load balancing
- **Features**: SSL termination, rate limiting, compression

#### Prometheus
- **Image**: prom/prometheus:latest
- **Port**: 9090
- **Purpose**: Metrics collection and monitoring

#### Grafana
- **Image**: grafana/grafana:latest
- **Port**: 3000
- **Purpose**: Metrics visualization and dashboards

## Monitoring and Logging

### Health Checks

All services include health checks:

```bash
# Check service health
./scripts/deploy.sh development health

# View service status
./scripts/deploy.sh development status
```

### Logging

Centralized logging with structured JSON format:

```bash
# View all logs
./scripts/deploy.sh development logs

# View specific service logs
docker-compose logs -f backend
docker-compose logs -f frontend
```

### Metrics

Production environment includes Prometheus metrics:

- **Application Metrics**: Request rates, response times, error rates
- **System Metrics**: CPU, memory, disk usage
- **Service Metrics**: Redis performance, API response times

Access Grafana at http://localhost:3000 (admin/admin123)

## Troubleshooting

### Common Issues

#### Services Won't Start

1. **Check API Keys**:
   ```bash
   # Verify .env file
   cat .env | grep -E "(OPENAI|PINECONE)_API_KEY"
   ```

2. **Check Docker Resources**:
   ```bash
   # Ensure Docker has enough memory
   docker system df
   docker system prune -f
   ```

3. **Check Port Conflicts**:
   ```bash
   # Check if ports are in use
   netstat -tulpn | grep -E "(8000|8501|6379)"
   ```

#### Backend API Errors

1. **Check Backend Logs**:
   ```bash
   docker-compose logs backend
   ```

2. **Verify External Services**:
   ```bash
   # Test OpenAI API
   curl -H "Authorization: Bearer $OPENAI_API_KEY" https://api.openai.com/v1/models
   
   # Test Pinecone (replace with your values)
   curl -H "Api-Key: $PINECONE_API_KEY" https://your-index.svc.pinecone.io/describe_index_stats
   ```

#### Frontend Connection Issues

1. **Check Backend Connectivity**:
   ```bash
   # From within frontend container
   docker-compose exec frontend curl http://backend:8000/health
   ```

2. **Verify Environment Variables**:
   ```bash
   docker-compose exec frontend env | grep BACKEND_URL
   ```

#### Redis Connection Issues

1. **Check Redis Status**:
   ```bash
   docker-compose exec redis redis-cli ping
   ```

2. **Check Redis Logs**:
   ```bash
   docker-compose logs redis
   ```

### Debug Mode

Enable debug mode for detailed logging:

```bash
# Set in .env file
LOG_LEVEL=DEBUG
DEBUG=true

# Restart services
./scripts/deploy.sh development restart
```

## Maintenance

### Backup and Restore

#### Create Backup
```bash
./scripts/deploy.sh development backup
```

#### Manual Backup
```bash
# Backup Redis data
docker-compose exec redis redis-cli BGSAVE
docker cp $(docker-compose ps -q redis):/data/dump.rdb ./backup/

# Backup application data
cp -r ./data ./backup/
cp -r ./logs ./backup/
```

#### Restore from Backup
```bash
# Stop services
./scripts/deploy.sh development down

# Restore data
cp ./backup/dump.rdb ./data/redis/
cp -r ./backup/data/* ./data/

# Start services
./scripts/deploy.sh development up
```

### Updates and Upgrades

#### Update Application
```bash
# Pull latest code
git pull origin main

# Rebuild images
./scripts/deploy.sh development build

# Restart services
./scripts/deploy.sh development restart
```

#### Update Dependencies
```bash
# Update Python packages
docker-compose exec backend pip install --upgrade -r requirements.txt
docker-compose exec frontend pip install --upgrade -r requirements.txt

# Rebuild images
./scripts/deploy.sh development build
```

### Cleanup

#### Remove All Containers and Volumes
```bash
./scripts/deploy.sh development clean
```

#### Clean Docker System
```bash
# Remove unused images and containers
docker system prune -a -f

# Remove unused volumes
docker volume prune -f
```

### Performance Tuning

#### Production Optimizations

1. **Increase Worker Processes**:
   ```yaml
   # In docker-compose.prod.yml
   environment:
     - WORKERS=4  # Adjust based on CPU cores
   ```

2. **Configure Resource Limits**:
   ```yaml
   deploy:
     resources:
       limits:
         memory: 2G
         cpus: '1.0'
   ```

3. **Enable Caching**:
   ```bash
   # In .env file
   ENABLE_CACHING=true
   CACHE_TTL=1800
   ```

#### Monitoring Performance

1. **Check Resource Usage**:
   ```bash
   docker stats
   ```

2. **Monitor API Performance**:
   ```bash
   # Check response times
   curl -w "@curl-format.txt" -o /dev/null -s http://localhost:8000/health
   ```

3. **Redis Performance**:
   ```bash
   docker-compose exec redis redis-cli --latency-history
   ```

## Security Considerations

### Production Security

1. **Use HTTPS**: Configure SSL certificates in Nginx
2. **Secure API Keys**: Use Docker secrets or external key management
3. **Network Security**: Use Docker networks and firewall rules
4. **Regular Updates**: Keep base images and dependencies updated
5. **Access Control**: Implement authentication and authorization
6. **Monitoring**: Set up security monitoring and alerting

### Environment Isolation

- Use separate environments for development, staging, and production
- Implement proper secret management
- Regular security audits and vulnerability scanning
- Network segmentation and access controls

## Support

For issues and questions:

1. Check the troubleshooting section above
2. Review application logs
3. Check service health endpoints
4. Consult the API documentation at `/docs`

## Additional Resources

- [Docker Documentation](https://docs.docker.com/)
- [Docker Compose Documentation](https://docs.docker.com/compose/)
- [FastAPI Documentation](https://fastapi.tiangolo.com/)
- [Streamlit Documentation](https://docs.streamlit.io/)
- [OpenAI API Documentation](https://platform.openai.com/docs)
- [Pinecone Documentation](https://docs.pinecone.io/)