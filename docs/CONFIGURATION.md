# Configuration Guide

This guide covers all configuration options for the GenAI DevOps Assistant, including environment variables, service configurations, and deployment settings.

## Table of Contents

- [Overview](#overview)
- [Environment Variables](#environment-variables)
- [Configuration Files](#configuration-files)
- [Environment-Specific Settings](#environment-specific-settings)
- [Validation and Startup Checks](#validation-and-startup-checks)
- [Security Considerations](#security-considerations)
- [Troubleshooting](#troubleshooting)

## Overview

The GenAI DevOps Assistant uses a hierarchical configuration system that supports:

- **Environment Variables**: Primary configuration method
- **JSON Configuration Files**: Alternative configuration method
- **Environment-Specific Defaults**: Different settings for development, testing, and production
- **Validation**: Comprehensive validation of all configuration values
- **Security**: Secure handling of API keys and sensitive data

### Configuration Priority

1. Environment variables (highest priority)
2. Configuration files
3. Default values (lowest priority)

## Environment Variables

### Required Configuration

These variables must be set for the application to function:

#### OpenAI Configuration

```bash
# OpenAI API Key (Required)
OPENAI_API_KEY=sk-your-openai-api-key-here

# Model Configuration (Optional)
OPENAI_MODEL=gpt-4                    # Default: gpt-4
OPENAI_EMBEDDING_MODEL=text-embedding-ada-002  # Default: text-embedding-ada-002
OPENAI_TEMPERATURE=0.1                # Default: 0.1 (0.0-2.0)
OPENAI_MAX_TOKENS=2000                # Default: 2000 (1-4000)
OPENAI_TIMEOUT=30                     # Default: 30 seconds
OPENAI_MAX_RETRIES=3                  # Default: 3
```

#### Pinecone Configuration

```bash
# Pinecone API Key (Required)
PINECONE_API_KEY=your-pinecone-api-key-here

# Pinecone Environment (Required)
PINECONE_ENVIRONMENT=us-west1-gcp     # Your Pinecone environment

# Index Configuration
PINECONE_INDEX_NAME=genai-devops-assistant  # Default: genai-devops-assistant
PINECONE_DIMENSION=1536               # Default: 1536 (for ada-002)
PINECONE_METRIC=cosine                # Default: cosine
PINECONE_TIMEOUT=30                   # Default: 30 seconds
PINECONE_MAX_RETRIES=3                # Default: 3
```

### Optional Configuration

#### Redis Configuration

```bash
# Redis Connection
REDIS_HOST=redis                      # Default: localhost
REDIS_PORT=6379                       # Default: 6379
REDIS_PASSWORD=                       # Default: empty
REDIS_DB=0                           # Default: 0
REDIS_SSL=false                      # Default: false
REDIS_TIMEOUT=30                     # Default: 30 seconds
REDIS_MAX_CONNECTIONS=10             # Default: 10
```

#### Application Settings

```bash
# Environment
ENVIRONMENT=development              # development, testing, production
APP_VERSION=1.0.0                   # Application version

# Logging
LOG_LEVEL=INFO                       # DEBUG, INFO, WARNING, ERROR, CRITICAL
LOG_FORMAT=%(asctime)s - %(name)s - %(levelname)s - %(message)s
LOG_FILE_PATH=                       # Optional log file path
LOG_MAX_FILE_SIZE=10485760          # 10MB default
LOG_BACKUP_COUNT=5                   # Number of backup log files
ENABLE_JSON_LOGGING=false            # Enable structured JSON logging

# API Limits
MAX_QUERY_LENGTH=2000                # Maximum characters in query
MAX_HISTORY_LENGTH=50                # Maximum conversation history length
RESPONSE_TIMEOUT=30                  # Response timeout in seconds
MAX_CONTEXT_LENGTH=4000              # Maximum context length
TOP_K_RETRIEVAL=5                    # Number of documents to retrieve

# Security
RATE_LIMIT_PER_MINUTE=60            # API rate limit per minute
SESSION_TIMEOUT=3600                 # Session timeout in seconds
CORS_ORIGINS=http://localhost:8501   # Comma-separated CORS origins
ALLOWED_HOSTS=localhost,127.0.0.1    # Comma-separated allowed hosts
API_KEY_HEADER=X-API-Key            # API key header name
ENABLE_RATE_LIMITING=true           # Enable/disable rate limiting

# Performance
CACHE_TTL=3600                      # Cache time-to-live in seconds
ENABLE_CACHING=true                 # Enable/disable caching
ENABLE_MONITORING=true              # Enable/disable monitoring
HEALTH_CHECK_INTERVAL=30            # Health check interval in seconds
```

## Configuration Files

You can also use JSON configuration files instead of environment variables:

### Loading from Configuration File

```python
from config import load_config_from_file

config = load_config_from_file("config/production.json")
```

### Configuration File Format

```json
{
  "environment": "production",
  "version": "1.0.0",
  "debug": false,
  "openai": {
    "api_key": "sk-your-openai-api-key",
    "model": "gpt-4",
    "embedding_model": "text-embedding-ada-002",
    "temperature": 0.1,
    "max_tokens": 2000,
    "timeout": 30,
    "max_retries": 3
  },
  "pinecone": {
    "api_key": "your-pinecone-api-key",
    "environment": "us-west1-gcp",
    "index_name": "genai-devops-assistant",
    "dimension": 1536,
    "metric": "cosine",
    "timeout": 30,
    "max_retries": 3
  },
  "redis": {
    "host": "localhost",
    "port": 6379,
    "db": 0,
    "password": null,
    "ssl": false,
    "timeout": 30,
    "max_connections": 10
  },
  "security": {
    "rate_limit_per_minute": 60,
    "max_query_length": 2000,
    "max_history_length": 50,
    "session_timeout": 3600,
    "cors_origins": ["http://localhost:8501"],
    "allowed_hosts": ["localhost"],
    "api_key_header": "X-API-Key",
    "enable_rate_limiting": true
  },
  "application": {
    "response_timeout": 30,
    "max_context_length": 4000,
    "top_k_retrieval": 5,
    "cache_ttl": 3600,
    "enable_caching": true,
    "enable_monitoring": true,
    "health_check_interval": 30
  },
  "logging": {
    "level": "INFO",
    "format": "%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    "file_path": null,
    "max_file_size": 10485760,
    "backup_count": 5,
    "enable_json_logging": false
  }
}
```

### Saving Configuration

```python
from config import save_config_to_file, get_config

config = get_config()
save_config_to_file("config/current.json", config)
```

**Note**: Sensitive information (API keys, passwords) is automatically redacted when saving to files.

## Environment-Specific Settings

### Development Environment

```bash
ENVIRONMENT=development
```

**Automatic Adjustments**:
- `debug = True`
- `LOG_LEVEL = DEBUG` (if not explicitly set)
- More permissive CORS origins
- Higher rate limits for testing

**Recommended Settings**:
```bash
LOG_LEVEL=DEBUG
RATE_LIMIT_PER_MINUTE=100
ENABLE_RATE_LIMITING=false
CORS_ORIGINS=http://localhost:8501,http://localhost:3000
```

### Testing Environment

```bash
ENVIRONMENT=testing
```

**Automatic Adjustments**:
- `cache_ttl = 60` (shorter cache for tests)
- `rate_limit_per_minute = 1000` (higher limit for tests)
- Reduced timeouts for faster test execution

**Recommended Settings**:
```bash
LOG_LEVEL=WARNING
ENABLE_CACHING=false
ENABLE_MONITORING=false
REDIS_DB=1
```

### Production Environment

```bash
ENVIRONMENT=production
```

**Automatic Validations**:
- Debug mode must be disabled
- Localhost not allowed in CORS origins
- Debug logging not allowed
- SSL recommended for Redis

**Required Settings**:
```bash
LOG_LEVEL=INFO
CORS_ORIGINS=https://your-domain.com
ALLOWED_HOSTS=your-domain.com,api.your-domain.com
REDIS_SSL=true
ENABLE_JSON_LOGGING=true
LOG_FILE_PATH=/var/log/genai-devops-assistant/app.log
```

## Validation and Startup Checks

### Configuration Validation

Use the configuration validator to check your setup:

```bash
# Validate current configuration
python backend/config_validator.py

# Validate specific configuration file
python backend/config_validator.py --config config/production.json

# Show configuration summary
python backend/config_validator.py --summary

# Validate and setup logging
python backend/config_validator.py --setup-logging
```

### Validation Checks

The validator performs these checks:

1. **Configuration Loading**: Loads and parses configuration
2. **Basic Validation**: Validates all configuration values
3. **API Keys**: Checks API key presence and format
4. **Network Connectivity**: Tests connectivity to external services
5. **Redis Connection**: Validates Redis connectivity and operations
6. **File Permissions**: Checks log file and directory permissions
7. **Environment Requirements**: Validates environment-specific requirements

### Programmatic Validation

```python
from config import get_config, validate_config

# Load and validate configuration
config = get_config()
is_valid = validate_config(config)

if not is_valid:
    print("Configuration validation failed!")
    exit(1)
```

## Security Considerations

### API Key Management

1. **Never commit API keys to version control**
2. **Use environment variables or secure secret management**
3. **Rotate API keys regularly**
4. **Use different API keys for different environments**

### Environment Variables

```bash
# Good - using environment variables
export OPENAI_API_KEY="sk-your-key-here"

# Bad - hardcoding in files
OPENAI_API_KEY=sk-your-key-here  # Don't do this in committed files
```

### Secret Management

For production deployments, consider using:

- **AWS Secrets Manager**
- **Azure Key Vault**
- **Google Secret Manager**
- **HashiCorp Vault**
- **Kubernetes Secrets**

### Configuration File Security

- Store configuration files outside the web root
- Set appropriate file permissions (600 or 640)
- Use encrypted storage for sensitive configuration files
- Regularly audit configuration file access

## Troubleshooting

### Common Issues

#### 1. Missing API Keys

**Error**: `OpenAI API key is required`

**Solution**:
```bash
export OPENAI_API_KEY="sk-your-actual-api-key-here"
```

#### 2. Invalid API Key Format

**Error**: `OpenAI API key must start with 'sk-'`

**Solution**: Ensure your OpenAI API key starts with `sk-` and is complete.

#### 3. Pinecone Connection Issues

**Error**: `Pinecone environment is required`

**Solution**:
```bash
export PINECONE_ENVIRONMENT="us-west1-gcp"  # Your actual environment
export PINECONE_INDEX_NAME="your-index-name"
```

#### 4. Redis Connection Failed

**Error**: `Redis connection failed`

**Solutions**:
- Check if Redis is running: `redis-cli ping`
- Verify Redis host and port: `REDIS_HOST=localhost REDIS_PORT=6379`
- Check Redis password if required: `REDIS_PASSWORD=your-password`

#### 5. Production Validation Errors

**Error**: `Debug mode should not be enabled in production`

**Solution**: Ensure production environment variables:
```bash
ENVIRONMENT=production
DEBUG=false
LOG_LEVEL=INFO
CORS_ORIGINS=https://your-domain.com
```

#### 6. File Permission Issues

**Error**: `Cannot write to log file`

**Solution**:
```bash
# Create log directory
sudo mkdir -p /var/log/genai-devops-assistant
sudo chown $USER:$USER /var/log/genai-devops-assistant

# Or use a user-writable location
LOG_FILE_PATH=./logs/app.log
```

### Debugging Configuration

#### Enable Debug Logging

```bash
LOG_LEVEL=DEBUG
python backend/config_validator.py
```

#### Check Configuration Values

```python
from config import get_config, print_config_summary

config = get_config()
print_config_summary(config)
```

#### Validate Specific Components

```python
from config import get_config

config = get_config()

# Check OpenAI configuration
print(f"OpenAI Model: {config.openai.model}")
print(f"OpenAI Temperature: {config.openai.temperature}")

# Check Pinecone configuration
print(f"Pinecone Environment: {config.pinecone.environment}")
print(f"Pinecone Index: {config.pinecone.index_name}")

# Check Redis configuration
print(f"Redis Host: {config.redis.host}:{config.redis.port}")
```

### Getting Help

If you're still having configuration issues:

1. Run the configuration validator with debug logging
2. Check the application logs for detailed error messages
3. Verify all required environment variables are set
4. Test individual service connections (Redis, OpenAI, Pinecone)
5. Review the environment-specific requirements

For additional support, please refer to the main documentation or create an issue in the project repository.