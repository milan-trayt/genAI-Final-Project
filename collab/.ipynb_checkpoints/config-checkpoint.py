"""Configuration for collab folder RAG pipeline."""

import os
from dataclasses import dataclass
from enum import Enum
from typing import Optional


class Environment(Enum):
    """Environment enumeration."""
    DEVELOPMENT = "development"
    PRODUCTION = "production"
    TESTING = "testing"


@dataclass
class OpenAIConfig:
    """OpenAI configuration."""
    api_key: str
    model: str = "gpt-4"
    embedding_model: str = "text-embedding-ada-002"
    temperature: float = 0.1
    max_tokens: int = 2000


@dataclass
class PineconeConfig:
    """Pinecone configuration."""
    api_key: str
    environment: str = "us-east-1-aws"
    index_name: str = "genai-devops-assistant"
    dimension: int = 1536
    metric: str = "cosine"


@dataclass
class RedisConfig:
    """Redis configuration."""
    host: str = "localhost"
    port: int = 6379
    db: int = 0
    password: str = None
    ssl: bool = False
    timeout: int = 30
    max_connections: int = 10
    retry_on_timeout: bool = True


@dataclass
class PostgreSQLConfig:
    """PostgreSQL configuration."""
    host: str = "localhost"
    port: int = 5432
    database: str = "genai_devops"
    user: str = "postgres"
    password: str = "password"
    ssl_mode: str = "prefer"
    timeout: int = 30
    max_connections: int = 10
    min_connections: int = 1


@dataclass
class Config:
    """Main configuration for collab RAG pipeline."""
    openai: OpenAIConfig
    pinecone: PineconeConfig
    redis: RedisConfig
    postgresql: PostgreSQLConfig
    environment: Environment = Environment.DEVELOPMENT


def get_config() -> Config:
    """Get configuration from environment variables."""
    
    # OpenAI configuration
    openai_api_key = os.getenv("OPENAI_API_KEY")
    if not openai_api_key:
        raise ValueError("OPENAI_API_KEY environment variable is required")
    
    openai_config = OpenAIConfig(
        api_key=openai_api_key,
        model=os.getenv("OPENAI_MODEL", "gpt-4"),
        embedding_model=os.getenv("OPENAI_EMBEDDING_MODEL", "text-embedding-ada-002"),
        temperature=float(os.getenv("OPENAI_TEMPERATURE", "0.1")),
        max_tokens=int(os.getenv("OPENAI_MAX_TOKENS", "2000"))
    )
    
    # Pinecone configuration
    pinecone_api_key = os.getenv("PINECONE_API_KEY")
    if not pinecone_api_key:
        raise ValueError("PINECONE_API_KEY environment variable is required")
    
    pinecone_config = PineconeConfig(
        api_key=pinecone_api_key,
        environment=os.getenv("PINECONE_ENVIRONMENT", "us-east-1-aws"),
        index_name=os.getenv("PINECONE_INDEX_NAME", "genai-devops-assistant"),
        dimension=int(os.getenv("PINECONE_DIMENSION", "1536")),
        metric=os.getenv("PINECONE_METRIC", "cosine")
    )
    
    # Redis configuration
    redis_config = RedisConfig(
        host=os.getenv("REDIS_HOST", "localhost"),
        port=int(os.getenv("REDIS_PORT", "6379")),
        db=int(os.getenv("REDIS_DB", "0")),
        password=os.getenv("REDIS_PASSWORD"),
        ssl=os.getenv("REDIS_SSL", "false").lower() == "true",
        timeout=int(os.getenv("REDIS_TIMEOUT", "30")),
        max_connections=int(os.getenv("REDIS_MAX_CONNECTIONS", "10")),
        retry_on_timeout=os.getenv("REDIS_RETRY_ON_TIMEOUT", "true").lower() == "true"
    )
    
    # PostgreSQL configuration
    postgresql_config = PostgreSQLConfig(
        host=os.getenv("POSTGRES_HOST", "localhost"),
        port=int(os.getenv("POSTGRES_PORT", "5432")),
        database=os.getenv("POSTGRES_DB", "genai_devops"),
        user=os.getenv("POSTGRES_USER", "postgres"),
        password=os.getenv("POSTGRES_PASSWORD", "password"),
        ssl_mode=os.getenv("POSTGRES_SSL_MODE", "prefer"),
        timeout=int(os.getenv("POSTGRES_TIMEOUT", "30")),
        max_connections=int(os.getenv("POSTGRES_MAX_CONNECTIONS", "10")),
        min_connections=int(os.getenv("POSTGRES_MIN_CONNECTIONS", "1"))
    )
    
    # Environment
    env_name = os.getenv("ENVIRONMENT", "development")
    environment = Environment(env_name)
    
    return Config(
        openai=openai_config,
        pinecone=pinecone_config,
        redis=redis_config,
        postgresql=postgresql_config,
        environment=environment
    )