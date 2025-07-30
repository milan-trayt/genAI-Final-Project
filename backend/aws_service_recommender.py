#!/usr/bin/env python3
"""
AWS Service Recommender with CoT reasoning and guardrails
"""

from typing import List, Dict, Any, Optional
import json
import re

class AWSServiceRecommender:
    def __init__(self, llm, retriever):
        self.llm = llm
        self.retriever = retriever
        self.aws_services = {
            'compute': ['EC2', 'Lambda', 'ECS', 'EKS', 'Fargate'],
            'storage': ['S3', 'EBS', 'EFS', 'FSx'],
            'database': ['RDS', 'DynamoDB', 'ElastiCache', 'DocumentDB'],
            'networking': ['VPC', 'CloudFront', 'Route53', 'ELB', 'API Gateway'],
            'security': ['IAM', 'KMS', 'Secrets Manager', 'WAF'],
            'monitoring': ['CloudWatch', 'X-Ray', 'CloudTrail']
        }
    
    def is_valid_query(self, query: str) -> bool:
        """Simple AWS keyword validation"""
        aws_keywords = [
            'aws', 'ec2', 's3', 'rds', 'lambda', 'vpc', 'iam', 'cloudwatch', 'elb', 'api gateway',
            'dynamodb', 'elasticache', 'ecs', 'eks', 'fargate', 'cloudfront', 'route53',
            'infrastructure', 'architecture', 'deploy', 'deployment', 'host', 'hosting',
            'database', 'storage', 'compute', 'server', 'application', 'microservice',
            'container', 'serverless', 'cost', 'pricing', 'price', 'estimate', 'budget',
            'terraform', 'provision', 'resource', 'backend', 'cloud', 'recommendation',
            'recommend', 'service', 'final', 'requirements'
        ]
        
        query_lower = query.lower()
        return any(keyword in query_lower for keyword in aws_keywords)
    
    async def recommend_services(self, scenario: str, filters: Optional[Dict] = None, conversation_context: str = "") -> Dict[str, Any]:
        """Recommend AWS services with CoT reasoning"""
        
        # Let the LLM handle validation through prompts instead of keyword matching
        
        # Retrieve relevant context
        context_docs = self.retriever.invoke(scenario)
        context = self._filter_context(context_docs, filters)
        
        # Add conversation context if available
        if conversation_context:
            context = f"Previous conversation context:\n{conversation_context}\n\nAWS Documentation:\n{context}"
        
        # Enhanced CoT prompt with guardrails
        cot_prompt = f"""
You are an expert AWS Solutions Architect. ONLY respond to AWS cloud infrastructure, service recommendations, pricing, and Terraform questions.

IMPORTANT: Do NOT include any "Sources:" section or reference to sources in your response. Provide direct, authoritative answers without citing sources.

PREVIOUS CONTEXT: {conversation_context}

CURRENT REQUEST: {scenario}

IMPORTANT: If there is previous context about specific requirements (like "small backend", "cost-effective", "minimal resources"), use that context to provide targeted recommendations. Do NOT ignore the previous discussion.

Analyze using this approach:

REQUIREMENT ANALYSIS:
- Core business and technical needs
- Performance, scalability, availability requirements
- Budget and operational constraints

SERVICE SELECTION:
- Primary AWS services for the requirements
- Supporting services needed
- Alternative options

JUSTIFICATION:
- Why each service is optimal
- Comparison with alternatives
- Specific benefits

ARCHITECTURE:
- Service integration and data flow
- Key architectural considerations

COST OPTIMIZATION:
- Main cost drivers
- Optimization strategies
- Pricing models

AWS Documentation Context:
{context}

Provide response in this EXACT markdown format:

## AWS Service Recommendation

### Analysis
[Your requirements analysis here]

### Recommended Services

**Service Name**
- Purpose: [Function and value]
- Reasoning: [Technical justification]

[Repeat for each service]

### Architecture Overview
[How services work together]

### Cost Considerations
- [Cost factor 1]
- [Cost factor 2]

Do NOT use JSON format. Use the markdown format above.
"""
        
        response = self.llm.invoke(cot_prompt)
        # Ensure response is a string
        if hasattr(response, 'content'):
            response_text = str(response.content)
        else:
            response_text = str(response)
        
        # Check if response was truncated and continue if needed
        full_response = await self._handle_continuation(response, cot_prompt, response_text)
        
        # Return the response directly without parsing
        return {"response": full_response}
    
    async def get_pricing_estimate(self, services: List[str], usage_params: Dict, conversation_context: str = "", scenario: str = "") -> Dict[str, Any]:
        """Get pricing estimates for recommended services"""
        
        pricing_prompt = f"""
You are an AWS cost specialist. ONLY provide pricing for AWS services.

IMPORTANT: Do NOT include any "Sources:" section or reference to sources in your response. Provide direct pricing information without citing sources.

PREVIOUS CONTEXT: {conversation_context}

AWS Services: {services}
Usage Parameters: {json.dumps(usage_params)}
User Request: {scenario}

IMPORTANT: If there is previous context about specific services or requirements (like "small backend", "Lambda + API Gateway + DynamoDB"), provide pricing specifically for those services mentioned in the context. Do NOT provide generic pricing for unrelated services.

CURRENT REQUEST: {scenario}

If the request asks for "invoice", "tabular format", "table", or "billing format", provide response as a detailed invoice table. Otherwise use standard markdown format.

For INVOICE/TABLE format, use:

# AWS PRICING INVOICE
 
**Billing Period:** Monthly

| Service | Description | Quantity | Unit Price | Monthly Cost |
|---------|-------------|----------|------------|-------------|
| [Service] | [Details] | [Amount] | [Rate] | [Cost] |

**TOTAL MONTHLY COST: $[Amount]**

For STANDARD format, use:

## AWS Pricing Estimate

### Cost Analysis
[Brief analysis]

### Service Pricing
**Service Name**
- Pricing Model: [Model]
- Estimated Monthly Cost: [Cost]

Do NOT respond to non-AWS queries like cooking, tea, sports, etc. If not AWS-related, respond: "I only provide AWS pricing information."
"""
        
        response = self.llm.invoke(pricing_prompt)
        # Ensure response is a string
        if hasattr(response, 'content'):
            response_text = str(response.content)
        else:
            response_text = str(response)
        
        # Check if response was truncated and continue if needed
        full_response = await self._handle_continuation(response, pricing_prompt, response_text)
        
        # Return the response directly without parsing
        return {"response": full_response}
    
    async def generate_terraform_code(self, services: List[str], requirements: Dict, conversation_context: str = "") -> Dict[str, Any]:
        """Generate Terraform code for recommended services"""
        
        # Get Terraform examples from context
        terraform_context = self.retriever.invoke(
            f"terraform {' '.join(services)} configuration example"
        )
        
        terraform_examples = "\n".join([
            doc.page_content for doc in terraform_context 
            if 'terraform' in doc.metadata.get('source_type', '').lower()
        ])
        
        terraform_prompt = f"""
You are a DevOps Engineer. ONLY generate Terraform for AWS resources.

IMPORTANT: Do NOT include any "Sources:" section or reference to sources in your response. Provide clean Terraform code without citing sources.

PREVIOUS CONTEXT: {conversation_context}

AWS Services: {services}
Requirements: {json.dumps(requirements)}

IMPORTANT: If there is previous context about specific services or architecture (like "Lambda + API Gateway + DynamoDB", "small backend"), generate Terraform specifically for those services mentioned in the context.

Examples:
{terraform_examples}

Provide response in this EXACT markdown format:

## Terraform Configuration

### Architecture Overview
[Brief description of what this Terraform will create]

### Terraform Code

```hcl
[Your complete Terraform configuration here]
```

### Key Features
- [Feature 1]
- [Feature 2]
- [Feature 3]

### Deployment Instructions
1. [Step 1]
2. [Step 2]
3. [Step 3]

Do NOT provide just code. Use the markdown format above.
"""
        
        response = self.llm.invoke(terraform_prompt)
        # Ensure response is a string
        if hasattr(response, 'content'):
            response_text = str(response.content)
        else:
            response_text = str(response)
        
        # Check if response was truncated and continue if needed
        full_response = await self._handle_continuation(response, terraform_prompt, response_text)
        
        # Return the response directly without parsing
        return {"response": full_response}
    
    def _filter_context(self, docs: List, filters: Optional[Dict]) -> str:
        """Filter context based on metadata"""
        if not filters:
            return "\n".join([doc.page_content for doc in docs[:5]])
        
        filtered_docs = []
        for doc in docs:
            metadata = doc.metadata
            
            # Filter by service type
            if filters.get('service_type'):
                service_type = filters['service_type'].lower()
                if service_type not in metadata.get('service_name', '').lower():
                    continue
            
            # Filter by document source
            if filters.get('source'):
                if filters['source'] not in metadata.get('source_type', ''):
                    continue
            
            filtered_docs.append(doc)
        
        return "\n".join([doc.page_content for doc in filtered_docs[:5]])
    
    def _parse_recommendation_response(self, response: str) -> Dict[str, Any]:
        """Parse LLM response for service recommendations"""
        try:
            # Try to extract JSON from response
            json_match = re.search(r'\{.*\}', response, re.DOTALL)
            if json_match:
                return json.loads(json_match.group())
        except:
            pass
        
        # Fallback parsing
        return {
            "analysis": "Analysis not available",
            "recommended_services": [],
            "architecture_overview": response,
            "cost_factors": [],
            "terraform_needed": []
        }
    
    def _parse_pricing_response(self, response: str) -> Dict[str, Any]:
        """Parse pricing response"""
        try:
            # Try to extract JSON from response
            json_match = re.search(r'\{.*\}', response, re.DOTALL)
            if json_match:
                return json.loads(json_match.group())
        except Exception as e:
            logger.warning(f"Failed to parse pricing JSON: {e}")
        
        # Fallback: create structured response from text
        return {
            "lambda": {
                "pricing_model": "Pay-per-request and duration",
                "estimated_monthly_cost": "$5-50 for small workloads",
                "optimization_tips": ["Use ARM processors", "Optimize memory allocation"]
            },
            "api_gateway": {
                "pricing_model": "Pay-per-request",
                "estimated_monthly_cost": "$3-30 for moderate traffic",
                "optimization_tips": ["Use caching", "Optimize request size"]
            },
            "dynamodb": {
                "pricing_model": "On-demand or provisioned",
                "estimated_monthly_cost": "$2-25 for small datasets",
                "optimization_tips": ["Use on-demand for variable workloads", "Optimize queries"]
            }
        }
    
    async def _handle_continuation(self, response, original_prompt: str, response_text: str) -> str:
        """Handle response continuation if max tokens were hit"""
        try:
            # Check if response was likely truncated
            is_truncated = (
                hasattr(response, 'response_metadata') and 
                response.response_metadata.get('finish_reason') == 'length'
            ) or (
                # Fallback checks for truncation
                len(response_text) > 3500 and  # Close to max tokens
                not response_text.rstrip().endswith(('.', '!', '?', '```', '**'))
            )
            
            if not is_truncated:
                return response_text
            
            # Continue the response
            continuation_prompt = f"""
Continue the following response from where it left off. Do not repeat any content, just continue:

{response_text}

Continue:
"""
            
            continuation_response = self.llm.invoke(continuation_prompt)
            if hasattr(continuation_response, 'content'):
                continuation_text = str(continuation_response.content)
            else:
                continuation_text = str(continuation_response)
            
            # Combine responses
            full_response = response_text + continuation_text
            
            # Check if we need another continuation (recursive)
            if (
                hasattr(continuation_response, 'response_metadata') and 
                continuation_response.response_metadata.get('finish_reason') == 'length'
            ):
                return await self._handle_continuation(continuation_response, original_prompt, full_response)
            
            return full_response
            
        except Exception as e:
            import logging
            logger = logging.getLogger(__name__)
            logger.warning(f"Failed to handle continuation: {e}")
            return response_text  # Return original if continuation fails