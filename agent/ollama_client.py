"""
Ollama LLM Client for query understanding and response generation.
"""
import logging
import json
import re
from typing import Dict, Any, Optional
import httpx

from config import settings

logger = logging.getLogger(__name__)


class OllamaClient:
    """Client for interacting with Ollama LLM service."""
    
    def __init__(self):
        self.base_url = settings.ollama_base_url.rstrip('/')
        self.model = settings.ollama_model
        self.api_key = settings.ollama_api_key
        self.timeout = settings.ollama_timeout
        # Try different API endpoints (Ollama native, OpenAI-compatible)
        self.api_endpoints = [
            "/api/chat",           # Standard Ollama chat endpoint
            "/v1/chat/completions", # OpenAI-compatible endpoint
            "/api/generate"        # Ollama generate endpoint (fallback)
        ]
    
    async def generate(
        self,
        prompt: str,
        system_prompt: Optional[str] = None,
        temperature: float = 0.7,
        max_tokens: Optional[int] = None
    ) -> str:
        """
        Generate a response from Ollama.
        
        Args:
            prompt: User prompt
            system_prompt: Optional system prompt for context
            temperature: Sampling temperature (0.0 to 1.0)
            max_tokens: Maximum tokens to generate
            
        Returns:
            Generated text response
        """
        try:
            headers = {"Content-Type": "application/json"}
            if self.api_key:
                headers["Authorization"] = f"Bearer {self.api_key}"
            
            # Build messages
            messages = []
            if system_prompt:
                messages.append({"role": "system", "content": system_prompt})
            messages.append({"role": "user", "content": prompt})
            
            # Try different API endpoints
            last_error = None
            async with httpx.AsyncClient(timeout=self.timeout) as client:
                for endpoint in self.api_endpoints:
                    try:
                        url = f"{self.base_url}{endpoint}"
                        logger.info(f"Trying Ollama endpoint: {url}")
                        
                        # Prepare payload based on endpoint type
                        if endpoint == "/api/generate":
                            # Use generate endpoint format
                            combined_prompt = ""
                            if system_prompt:
                                combined_prompt = f"System: {system_prompt}\n\nUser: {prompt}"
                            else:
                                combined_prompt = prompt
                            
                            payload = {
                                "model": self.model,
                                "prompt": combined_prompt,
                                "stream": False,
                                "options": {"temperature": temperature}
                            }
                            if max_tokens:
                                payload["options"]["num_predict"] = max_tokens
                        elif endpoint == "/v1/chat/completions":
                            # OpenAI-compatible format
                            payload = {
                                "model": self.model,
                                "messages": messages,
                                "temperature": temperature,
                                "stream": False
                            }
                            if max_tokens:
                                payload["max_tokens"] = max_tokens
                        else:
                            # Standard Ollama chat format
                            payload = {
                                "model": self.model,
                                "messages": messages,
                                "stream": False,
                                "options": {"temperature": temperature}
                            }
                            if max_tokens:
                                payload["options"]["num_predict"] = max_tokens
                        
                        response = await client.post(url, headers=headers, json=payload)
                        response.raise_for_status()
                        
                        result = response.json()
                        
                        # Extract response based on endpoint type
                        if endpoint == "/api/generate":
                            generated_text = result.get("response", "")
                        elif endpoint == "/v1/chat/completions":
                            generated_text = result.get("choices", [{}])[0].get("message", {}).get("content", "")
                        else:
                            generated_text = result.get("message", {}).get("content", "")
                        
                        if generated_text:
                            logger.info(f"Ollama response received successfully from {endpoint}")
                            # Strip <think>...</think> blocks (DeepSeek-R1 reasoning)
                            generated_text = re.sub(r'<think>.*?</think>', '', generated_text, flags=re.DOTALL).strip()
                            return generated_text
                        else:
                            logger.warning(f"Empty response from {endpoint}")
                            continue
                            
                    except httpx.HTTPStatusError as e:
                        logger.warning(f"HTTP {e.response.status_code} from {endpoint}: {str(e)}")
                        last_error = e
                        continue
                    except Exception as e:
                        logger.warning(f"Error with {endpoint}: {str(e)}")
                        last_error = e
                        continue
                
                # If all endpoints failed, raise the last error
                if last_error:
                    raise last_error
                else:
                    raise Exception("All Ollama endpoints failed to return a response")
                
        except Exception as e:
            logger.error(f"Error calling Ollama: {str(e)}")
            raise
    
    async def extract_query_intent(self, user_query: str) -> Dict[str, Any]:
        """
        Extract intent and parameters from user query.
        
        Args:
            user_query: Natural language query from user
            
        Returns:
            Dictionary with intent, time_period, filters, etc.
        """
        from datetime import datetime as _dt
        today_str = _dt.now().strftime("%Y-%m-%d")

        system_prompt = f"""You are an AWS cost analysis assistant. Today's date is {today_str}.
Extract the intent and parameters from user queries about AWS costs.

Respond ONLY with a valid JSON object (no markdown, no code blocks, no extra text) with these fields:
- intent: One of ["get_costs", "forecast_costs", "compare_costs", "get_cost_drivers"]
- time_period: Human description (e.g. "last month", "last 6 months", "next quarter")
- start_date: YYYY-MM-DD (compute from today). For historical queries use the first day of the relevant period. For forecasts set to today.
- end_date: YYYY-MM-DD. For historical queries use the last day of the period. For forecasts set to a future date.
- granularity: "MONTHLY" or "DAILY" (default MONTHLY; use DAILY for "last 7 days" or "daily breakdown")
- filters: Object with optional keys: service (list of full AWS names), region (list), account (list)
- group_by: Dimension key to group results by (see valid list below). Default "SERVICE".
- comparison: ONLY for compare_costs / get_cost_drivers. Object with:
    - baseline: {{"start_date":"YYYY-MM-DD","end_date":"YYYY-MM-DD"}}
    - comparison: {{"start_date":"YYYY-MM-DD","end_date":"YYYY-MM-DD"}}
  Both periods MUST be exactly 1 calendar month, starting on day 1.
  Example: baseline 2026-01-01→2026-02-01, comparison 2025-12-01→2026-01-01

VALID group_by DIMENSION KEYS (use exactly as shown):
SERVICE, REGION, INSTANCE_TYPE, INSTANCE_TYPE_FAMILY, LINKED_ACCOUNT,
USAGE_TYPE, USAGE_TYPE_GROUP, OPERATION, PLATFORM, PURCHASE_TYPE,
DATABASE_ENGINE, CACHE_ENGINE, DEPLOYMENT_OPTION, OPERATING_SYSTEM,
AZ, TENANCY, RECORD_TYPE, BILLING_ENTITY, LEGAL_ENTITY_NAME, INVOICING_ENTITY

INTENT RULES:
- "get_costs": Any historical cost query (what did I spend, show costs, break down costs, top services)
- "forecast_costs": Predicting future costs. Forecasts CANNOT be grouped. Do NOT set group_by for forecasts.
- "compare_costs": Comparing two months side by side. Both periods must be exactly 1 month.
- "get_cost_drivers": Why costs changed, what caused a spike, cost increase drivers. Both periods must be exactly 1 month.

FORECAST RULES:
- start_date = today ({today_str})
- end_date MUST be in the future (after today)
- For "next month": end_date = first day of the month after next month
- For "next quarter": end_date = first day of 4th month from now
- Do NOT include group_by for forecasts (the API does not support it)

SERVICE NAME MAPPINGS (always use the full name in filters.service):
S3 → "Amazon Simple Storage Service"
EC2 → "Amazon Elastic Compute Cloud - Compute"
RDS → "Amazon Relational Database Service"
Lambda → "AWS Lambda"
CloudFront → "Amazon CloudFront"
DynamoDB → "Amazon DynamoDB"
ECS → "Amazon Elastic Container Service"
EKS → "Amazon Elastic Kubernetes Service"
SQS → "Amazon Simple Queue Service"
SNS → "Amazon Simple Notification Service"
EBS → "Amazon Elastic Block Store"
ElastiCache → "Amazon ElastiCache"
Redshift → "Amazon Redshift"
SageMaker → "Amazon SageMaker"
Route 53 → "Amazon Route 53"
CloudWatch → "Amazon CloudWatch"
KMS → "AWS Key Management Service"
Glue → "AWS Glue"
Athena → "Amazon Athena"
EMR → "Amazon EMR"
Kinesis → "Amazon Kinesis"
API Gateway → "Amazon API Gateway"
OpenSearch → "Amazon OpenSearch Service"
Step Functions → "AWS Step Functions"
Secrets Manager → "AWS Secrets Manager"
WAF → "AWS WAF"
CodeBuild → "AWS CodeBuild"
CodePipeline → "AWS CodePipeline"
ECR → "Amazon EC2 Container Registry"
Lightsail → "Amazon Lightsail"
SES → "Amazon Simple Email Service"

EXAMPLES:
1. "What were my total AWS costs last month?"
{{"intent":"get_costs","time_period":"last month","start_date":"2026-01-01","end_date":"2026-01-31","granularity":"MONTHLY","group_by":"SERVICE"}}

2. "Show EC2 costs by region for the last full month"
{{"intent":"get_costs","time_period":"last month","start_date":"2026-01-01","end_date":"2026-01-31","granularity":"MONTHLY","filters":{{"service":["Amazon Elastic Compute Cloud - Compute"]}},"group_by":"REGION"}}

3. "Show RDS costs grouped by instance type"
{{"intent":"get_costs","time_period":"last month","start_date":"2026-01-01","end_date":"2026-01-31","granularity":"MONTHLY","filters":{{"service":["Amazon Relational Database Service"]}},"group_by":"INSTANCE_TYPE"}}

4. "Forecast total AWS costs for next month"
{{"intent":"forecast_costs","time_period":"next month","start_date":"{today_str}","end_date":"2026-04-01"}}

5. "What will my S3 costs be next month?"
{{"intent":"forecast_costs","time_period":"next month","start_date":"{today_str}","end_date":"2026-04-01","filters":{{"service":["Amazon Simple Storage Service"]}}}}

6. "Compare costs between last month and the month before"
{{"intent":"compare_costs","time_period":"last 2 months","group_by":"SERVICE","comparison":{{"baseline":{{"start_date":"2025-12-01","end_date":"2026-01-01"}},"comparison":{{"start_date":"2026-01-01","end_date":"2026-02-01"}}}}}}

7. "Why did my AWS bill increase last month?"
{{"intent":"get_cost_drivers","time_period":"last 2 months","group_by":"SERVICE","comparison":{{"baseline":{{"start_date":"2025-12-01","end_date":"2026-01-01"}},"comparison":{{"start_date":"2026-01-01","end_date":"2026-02-01"}}}}}}

8. "Show daily cost breakdown for current month"
{{"intent":"get_costs","time_period":"current month","start_date":"2026-02-01","end_date":"{today_str}","granularity":"DAILY","group_by":"SERVICE"}}

9. "Show Lambda costs for last 7 days"
{{"intent":"get_costs","time_period":"last 7 days","start_date":"2026-02-05","end_date":"{today_str}","granularity":"DAILY","filters":{{"service":["AWS Lambda"]}},"group_by":"SERVICE"}}"""
        
        prompt = f"User query: {user_query}\n\nExtract the intent and parameters as JSON:"
        
        response = await self.generate(prompt, system_prompt=system_prompt, temperature=0.1)
        
        try:
            # Try to parse JSON from response
            response = response.strip()
            
            # Remove markdown code blocks if present
            if response.startswith("```"):
                lines = response.split("\n")
                response = "\n".join(lines[1:-1]) if len(lines) > 2 else response
                response = response.replace("```json", "").replace("```", "").strip()
            
            # Try direct parse first
            try:
                intent_data = json.loads(response)
                logger.info(f"Extracted intent: {intent_data}")
                return intent_data
            except json.JSONDecodeError:
                pass
            
            # Fallback: find JSON object in the response (handles nested objects)
            brace_depth = 0
            start_idx = None
            for i, ch in enumerate(response):
                if ch == '{':
                    if brace_depth == 0:
                        start_idx = i
                    brace_depth += 1
                elif ch == '}':
                    brace_depth -= 1
                    if brace_depth == 0 and start_idx is not None:
                        candidate = response[start_idx:i+1]
                        try:
                            intent_data = json.loads(candidate)
                            logger.info(f"Extracted intent (brace-match fallback): {intent_data}")
                            return intent_data
                        except json.JSONDecodeError:
                            start_idx = None
                            continue
            
            raise json.JSONDecodeError("No JSON found", response, 0)
            
        except json.JSONDecodeError as e:
            logger.error(f"Failed to parse intent JSON: {response}")
            return {
                "intent": "get_costs",
                "time_period": "last month",
                "group_by": "SERVICE"
            }
    
    async def generate_summary(
        self,
        user_query: str,
        mcp_results: Dict[str, Any]
    ) -> str:
        """
        Generate a human-friendly summary from MCP results.
        
        Args:
            user_query: Original user query
            mcp_results: Results from MCP server
            
        Returns:
            Human-friendly summary text
        """
        system_prompt = """You are an AWS cost analysis assistant. Generate clear, concise summaries of AWS cost data.

Guidelines:
- Be specific with numbers and percentages
- Highlight key insights and trends
- Use business-friendly language
- Keep it to 2-3 sentences
- Include currency symbols and proper formatting"""
        
        prompt = f"""User asked: "{user_query}"

AWS Cost Data:
{json.dumps(mcp_results, indent=2)}

Generate a clear summary of these results:"""
        
        summary = await self.generate(prompt, system_prompt=system_prompt, temperature=0.5)
        return summary.strip()
