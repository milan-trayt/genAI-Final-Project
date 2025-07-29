#!/usr/bin/env python3
"""
Semantic document chunker for AWS docs and Terraform examples
"""

from typing import List, Dict, Any
from langchain.schema import Document
from langchain.text_splitter import RecursiveCharacterTextSplitter
import re

class SemanticDocumentChunker:
    def __init__(self):
        self.aws_splitter = RecursiveCharacterTextSplitter(
            chunk_size=1200,
            chunk_overlap=200,
            separators=["\n## ", "\n### ", "\n#### ", "\n\n", "\n", " ", ""]
        )
        
        self.terraform_splitter = RecursiveCharacterTextSplitter(
            chunk_size=800,
            chunk_overlap=100,
            separators=["\nresource ", "\ndata ", "\nmodule ", "\nvariable ", "\noutput ", "\n\n", "\n"]
        )
    
    def chunk_documents(self, documents: List[Document]) -> List[Document]:
        """Chunk documents based on their type and structure"""
        chunked_docs = []
        
        for doc in documents:
            source_type = doc.metadata.get('source_type', '')
            
            if 'terraform' in source_type.lower() or '.tf' in doc.metadata.get('file_name', ''):
                chunks = self._chunk_terraform_doc(doc)
            elif 'aws' in doc.metadata.get('source_path', '').lower():
                chunks = self._chunk_aws_doc(doc)
            else:
                chunks = self._chunk_generic_doc(doc)
            
            chunked_docs.extend(chunks)
        
        return chunked_docs
    
    def _chunk_terraform_doc(self, doc: Document) -> List[Document]:
        """Chunk Terraform documents preserving resource blocks"""
        content = doc.page_content
        
        # Extract complete resource blocks
        resource_pattern = r'(resource\s+"[^"]+"\s+"[^"]+"\s*\{[^}]*(?:\{[^}]*\}[^}]*)*\})'
        resources = re.findall(resource_pattern, content, re.MULTILINE | re.DOTALL)
        
        chunks = []
        for resource in resources:
            chunk_doc = Document(
                page_content=resource,
                metadata={
                    **doc.metadata,
                    'chunk_type': 'terraform_resource',
                    'resource_type': self._extract_terraform_resource_type(resource)
                }
            )
            chunks.append(chunk_doc)
        
        # Handle remaining content
        remaining_content = content
        for resource in resources:
            remaining_content = remaining_content.replace(resource, '')
        
        if remaining_content.strip():
            remaining_chunks = self.terraform_splitter.split_text(remaining_content)
            for chunk in remaining_chunks:
                if chunk.strip():
                    chunk_doc = Document(
                        page_content=chunk,
                        metadata={**doc.metadata, 'chunk_type': 'terraform_other'}
                    )
                    chunks.append(chunk_doc)
        
        return chunks
    
    def _chunk_aws_doc(self, doc: Document) -> List[Document]:
        """Chunk AWS documentation preserving service sections"""
        content = doc.page_content
        
        # Split by AWS service sections
        service_pattern = r'(## [^#\n]*(?:Service|API|Resource)[^#\n]*\n.*?)(?=## |$)'
        service_sections = re.findall(service_pattern, content, re.MULTILINE | re.DOTALL)
        
        chunks = []
        for section in service_sections:
            if len(section) > 2000:
                # Further split large sections
                sub_chunks = self.aws_splitter.split_text(section)
                for sub_chunk in sub_chunks:
                    chunk_doc = Document(
                        page_content=sub_chunk,
                        metadata={
                            **doc.metadata,
                            'chunk_type': 'aws_service_section',
                            'service_name': self._extract_aws_service_name(sub_chunk)
                        }
                    )
                    chunks.append(chunk_doc)
            else:
                chunk_doc = Document(
                    page_content=section,
                    metadata={
                        **doc.metadata,
                        'chunk_type': 'aws_service_section',
                        'service_name': self._extract_aws_service_name(section)
                    }
                )
                chunks.append(chunk_doc)
        
        return chunks if chunks else self._chunk_generic_doc(doc)
    
    def _chunk_generic_doc(self, doc: Document) -> List[Document]:
        """Generic chunking for other documents"""
        chunks = self.aws_splitter.split_text(doc.page_content)
        return [
            Document(
                page_content=chunk,
                metadata={**doc.metadata, 'chunk_type': 'generic'}
            )
            for chunk in chunks
        ]
    
    def _extract_terraform_resource_type(self, resource_block: str) -> str:
        """Extract resource type from Terraform block"""
        match = re.search(r'resource\s+"([^"]+)"', resource_block)
        return match.group(1) if match else 'unknown'
    
    def _extract_aws_service_name(self, content: str) -> str:
        """Extract AWS service name from content"""
        aws_services = ['EC2', 'S3', 'RDS', 'Lambda', 'VPC', 'IAM', 'CloudWatch', 'ELB', 'Route53']
        for service in aws_services:
            if service.lower() in content.lower():
                return service
        return 'unknown'