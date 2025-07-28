"""Data models for the collab folder RAG pipeline."""

from datetime import datetime
from enum import Enum
from typing import List, Optional, Dict, Any, Union
from pydantic import BaseModel, Field
from dataclasses import dataclass
import uuid


class DocumentSourceType(str, Enum):
    """Document source type enumeration."""
    PDF = "pdf"
    WEB = "web"
    GITHUB = "github"
    CONFLUENCE = "confluence"


@dataclass
class DocumentSource:
    """Document source configuration for RAG pipeline."""
    source_type: str  # 'pdf', 'web', 'github', 'confluence'
    source_path: str  # File path, URL, or identifier
    metadata: Dict[str, Any] = None
    
    def __post_init__(self):
        if self.metadata is None:
            self.metadata = {}
        
        # Add processing metadata
        self.metadata.update({
            'processed_at': datetime.utcnow().isoformat(),
            'source_id': str(uuid.uuid4())
        })


class ProcessingStats(BaseModel):
    """Statistics for document processing."""
    documents_loaded: int = 0
    chunks_created: int = 0
    embeddings_created: int = 0
    processing_time: float = 0.0
    errors: List[str] = Field(default_factory=list)
    timestamp: datetime = Field(default_factory=datetime.utcnow)


class IndexStats(BaseModel):
    """Pinecone index statistics."""
    total_vector_count: int = 0
    dimension: int = 1536
    index_fullness: float = 0.0
    namespaces: Dict[str, int] = Field(default_factory=dict)
    timestamp: datetime = Field(default_factory=datetime.utcnow)


class SearchResult(BaseModel):
    """Search result from knowledge base."""
    content: str
    metadata: Dict[str, Any]
    score: float
    source_type: str
    source_path: str


class IngestionConfig(BaseModel):
    """Configuration for document ingestion."""
    chunk_size: int = Field(default=1000, ge=100, le=2000)
    chunk_overlap: int = Field(default=200, ge=0, le=500)
    batch_size: int = Field(default=100, ge=1, le=500)
    max_documents: Optional[int] = Field(default=None, ge=1)
    filter_metadata: bool = True
    
    def validate_overlap(self):
        """Validate chunk overlap is less than chunk size."""
        if self.chunk_overlap >= self.chunk_size:
            raise ValueError("Chunk overlap must be less than chunk size")


class DocumentMetadata(BaseModel):
    """Standardized document metadata."""
    source: str
    doc_type: str
    title: Optional[str] = None
    section: Optional[str] = None
    url: Optional[str] = None
    chunk_index: int = 0
    chunk_id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    token_count: Optional[int] = None
    processed_at: datetime = Field(default_factory=datetime.utcnow)


class IngestionResult(BaseModel):
    """Result of document ingestion process."""
    success: bool
    source: DocumentSource
    documents_processed: int = 0
    chunks_created: int = 0
    embeddings_stored: int = 0
    processing_time: float = 0.0
    error: Optional[str] = None


class BatchIngestionResult(BaseModel):
    """Result of batch document ingestion."""
    total_sources: int
    successful_sources: int
    failed_sources: int
    total_documents: int = 0
    total_chunks: int = 0
    total_embeddings: int = 0
    total_time: float = 0.0
    results: List[IngestionResult] = Field(default_factory=list)
    errors: List[str] = Field(default_factory=list)


# Predefined document sources for easy setup
AWS_DOCUMENTATION_SOURCES = [
    DocumentSource(
        source_type="web",
        source_path="https://docs.aws.amazon.com/vpc/latest/userguide/what-is-amazon-vpc.html",
        metadata={"doc_type": "aws_vpc", "priority": "high"}
    ),
    DocumentSource(
        source_type="web",
        source_path="https://docs.aws.amazon.com/ec2/latest/userguide/concepts.html",
        metadata={"doc_type": "aws_ec2", "priority": "high"}
    ),
    DocumentSource(
        source_type="web",
        source_path="https://docs.aws.amazon.com/wellarchitected/latest/framework/welcome.html",
        metadata={"doc_type": "aws_well_architected", "priority": "high"}
    ),
    DocumentSource(
        source_type="web",
        source_path="https://docs.aws.amazon.com/IAM/latest/UserGuide/introduction.html",
        metadata={"doc_type": "aws_iam", "priority": "medium"}
    ),
    DocumentSource(
        source_type="web",
        source_path="https://docs.aws.amazon.com/s3/latest/userguide/Welcome.html",
        metadata={"doc_type": "aws_s3", "priority": "medium"}
    )
]

TERRAFORM_DOCUMENTATION_SOURCES = [
    DocumentSource(
        source_type="web",
        source_path="https://registry.terraform.io/providers/hashicorp/aws/latest/docs",
        metadata={"doc_type": "terraform_aws_provider", "priority": "high"}
    ),
    DocumentSource(
        source_type="web",
        source_path="https://registry.terraform.io/modules/terraform-aws-modules/vpc/aws/latest",
        metadata={"doc_type": "terraform_vpc_module", "priority": "high"}
    ),
    DocumentSource(
        source_type="web",
        source_path="https://registry.terraform.io/modules/terraform-aws-modules/ec2-instance/aws/latest",
        metadata={"doc_type": "terraform_ec2_module", "priority": "medium"}
    )
]


# Utility functions
def create_pdf_source(file_path: str, doc_type: str = "pdf_document") -> DocumentSource:
    """Create a PDF document source."""
    return DocumentSource(
        source_type="pdf",
        source_path=file_path,
        metadata={"doc_type": doc_type}
    )


def create_web_source(url: str, doc_type: str = "web_document") -> DocumentSource:
    """Create a web document source."""
    return DocumentSource(
        source_type="web",
        source_path=url,
        metadata={"doc_type": doc_type}
    )


def create_github_source(repo: str, access_token: Optional[str] = None, 
                        include_prs: bool = True, include_issues: bool = True) -> DocumentSource:
    """Create a GitHub repository source for issues and PRs."""
    return DocumentSource(
        source_type="github",
        source_path=repo,
        metadata={
            "doc_type": "github_issues",
            "access_token": access_token,
            "include_prs": include_prs,
            "include_issues": include_issues
        }
    )


def create_github_codebase_source(repo: str, access_token: Optional[str] = None,
                                 file_extensions: Optional[List[str]] = None,
                                 include_documentation: bool = True,
                                 max_file_size: int = 1024 * 1024) -> DocumentSource:
    """Create a GitHub repository codebase source."""
    return DocumentSource(
        source_type="github_codebase",
        source_path=repo,
        metadata={
            "doc_type": "github_codebase",
            "access_token": access_token,
            "file_extensions": file_extensions,
            "include_documentation": include_documentation,
            "max_file_size": max_file_size
        }
    )


def create_confluence_source(url: str, username: str, api_key: str,
                           page_ids: Optional[List[str]] = None,
                           space_key: Optional[str] = None) -> DocumentSource:
    """Create a Confluence document source."""
    return DocumentSource(
        source_type="confluence",
        source_path=url,
        metadata={
            "doc_type": "confluence",
            "username": username,
            "api_key": api_key,
            "page_ids": page_ids,
            "space_key": space_key
        }
    )


def filter_complex_metadata(metadata: Dict[str, Any]) -> Dict[str, Any]:
    """Filter out complex metadata that can't be serialized."""
    filtered = {}
    
    for key, value in metadata.items():
        # Only keep simple types that can be serialized
        if isinstance(value, (str, int, float, bool, type(None))):
            filtered[key] = value
        elif isinstance(value, (list, dict)):
            try:
                # Try to serialize to check if it's simple enough
                import json
                json.dumps(value)
                filtered[key] = value
            except (TypeError, ValueError):
                # Skip complex objects
                continue
        else:
            # Convert to string for other types
            filtered[key] = str(value)
    
    return filtered


# Example configurations
DEFAULT_INGESTION_CONFIG = IngestionConfig(
    chunk_size=1000,
    chunk_overlap=200,
    batch_size=100,
    filter_metadata=True
)

LARGE_DOCUMENT_CONFIG = IngestionConfig(
    chunk_size=1500,
    chunk_overlap=300,
    batch_size=50,
    filter_metadata=True
)

SMALL_DOCUMENT_CONFIG = IngestionConfig(
    chunk_size=500,
    chunk_overlap=100,
    batch_size=200,
    filter_metadata=True
)