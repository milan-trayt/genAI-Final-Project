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
            'terraform', 'provision', 'resource', 'backend', 'cloud'
        ]
        
        query_lower = query.lower()
        return any(keyword in query_lower for keyword in aws_keywords)
    
    def recommend_services(self, scenario: str, filters: Optional[Dict] = None) -> Dict[str, Any]:
        """Recommend AWS services with CoT reasoning"""
        
        # Simple validation - handled in prompt
        if not self.is_valid_query(scenario):
            return {
                "error": "I specialize in AWS cloud infrastructure, service recommendations, pricing estimates, and Terraform code generation. Please ask about AWS services, architecture, or infrastructure needs."
            }
        
        # Retrieve relevant context
        context_docs = self.retriever.get_relevant_documents(scenario)
        context = self._filter_context(context_docs, filters)
        
        # Enhanced CoT prompt with guardrails
        cot_prompt = f"""
You are an expert AWS Solutions Architect. ONLY respond to AWS cloud infrastructure, service recommendations, pricing, and Terraform questions. If the query is not related to these topics, respond with: "I can only help with AWS infrastructure, service recommendations, pricing, and Terraform code generation."

IMPORTANT: Do NOT include any "Sources:" section or reference to sources in your response. Provide direct, authoritative answers without citing sources.

User Scenario: {scenario}

If this is an AWS-related query, analyze using this approach:

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

Provide response in JSON format:
{{
    "analysis": "Requirements analysis",
    "recommended_services": [
        {{
            "service": "AWS Service Name",
            "purpose": "Function and value",
            "reasoning": "Technical justification"
        }}
    ],
    "architecture_overview": "How services work together",
    "cost_factors": ["Cost considerations"],
    "terraform_needed": ["Required resources"]
}}
"""
        
        response = self.llm.invoke(cot_prompt)
        return self._parse_recommendation_response(response)
    
    def get_pricing_estimate(self, services: List[str], usage_params: Dict) -> Dict[str, Any]:
        """Get pricing estimates for recommended services"""
        
        pricing_prompt = f"""
You are an AWS cost specialist. ONLY provide pricing for AWS services. If not AWS-related, respond: "I only provide AWS pricing information."

IMPORTANT: Do NOT include any "Sources:" section or reference to sources in your response. Provide direct pricing information without citing sources.

AWS Services: {services}
Usage: {json.dumps(usage_params)}

For each AWS service:

PRICING MODEL:
- Optimal model (On-Demand, Reserved, Spot)
- Cost-effectiveness scenarios

COST FACTORS:
- Main drivers (compute, storage, transfer)
- Variable vs fixed costs

ESTIMATION:
- Monthly cost ranges
- Scaling implications

OPTIMIZATION:
- Cost reduction strategies
- Monitoring recommendations

JSON format:
{{
    "service_name": {{
        "pricing_model": "Optimal approach",
        "cost_factors": ["Cost drivers"],
        "estimated_monthly_cost": "Range with assumptions",
        "optimization_tips": ["Strategies"]
    }}
}}
"""
        
        response = self.llm.invoke(pricing_prompt)
        return self._parse_pricing_response(response)
    
    def generate_terraform_code(self, services: List[str], requirements: Dict) -> str:
        """Generate Terraform code for recommended services"""
        
        # Get Terraform examples from context
        terraform_context = self.retriever.get_relevant_documents(
            f"terraform {' '.join(services)} configuration example"
        )
        
        terraform_examples = "\n".join([
            doc.page_content for doc in terraform_context 
            if 'terraform' in doc.metadata.get('source_type', '').lower()
        ])
        
        terraform_prompt = f"""
You are a DevOps Engineer. ONLY generate Terraform for AWS resources. If not AWS-related, respond: "I only generate Terraform for AWS infrastructure."

IMPORTANT: Do NOT include any "Sources:" section or reference to sources in your response. Provide clean Terraform code without citing sources.

AWS Services: {services}
Requirements: {json.dumps(requirements)}

Examples:
{terraform_examples}

Generate production-ready Terraform with:
- Security best practices
- Proper naming and tagging
- Variable definitions
- Resource outputs
- Meaningful outputs for integration

SECURITY CONSIDERATIONS:
- Least privilege access principles
- Encryption at rest and in transit
- Network security and isolation
- Secrets management best practices

CODE STRUCTURE:
1. Provider and version constraints
2. Local values and data sources
3. Resource definitions with dependencies
4. Variable definitions with descriptions and validation
5. Output definitions for important resource attributes

STANDARDS:
- Consistent naming convention (environment-project-resource)
- Comprehensive tagging strategy
- Resource organization and grouping
- Comments explaining complex configurations

Provide clean, well-documented Terraform code:
"""
        
        return self.llm.invoke(terraform_prompt)
    
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
            json_match = re.search(r'\{.*\}', response, re.DOTALL)
            if json_match:
                return json.loads(json_match.group())
        except:
            pass
        
        return {"error": "Could not parse pricing information"}