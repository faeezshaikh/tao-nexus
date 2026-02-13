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
        system_prompt = """You are an AWS cost analysis assistant. Extract the intent and parameters from user queries about AWS costs.

Respond ONLY with a valid JSON object (no markdown, no code blocks) with these fields:
- intent: One of ["get_costs", "compare_costs", "forecast_costs", "get_breakdown"]
- time_period: Describe the time period (e.g., "last month", "last 6 months")
- start_date: Start date in YYYY-MM-DD format (if determinable)
- end_date: End date in YYYY-MM-DD format (if determinable)
- filters: Object with optional filters (service, region, account)
- group_by: What to group by (SERVICE, REGION, LINKED_ACCOUNT, etc.)
- comparison: For comparisons, object with baseline and comparison periods

Example:
{"intent": "get_costs", "time_period": "last month", "group_by": "SERVICE"}"""
        
        prompt = f"User query: {user_query}\n\nExtract the intent and parameters:"
        
        response = await self.generate(prompt, system_prompt=system_prompt, temperature=0.3)
        
        try:
            # Try to parse JSON from response
            response = response.strip()
            
            # Strip <think>...</think> blocks (e.g., from DeepSeek models)
            response = re.sub(r'<think>.*?</think>', '', response, flags=re.DOTALL).strip()
            
            # Remove markdown code blocks if present
            if response.startswith("```"):
                # Extract content between code blocks
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
            
            # Fallback: find the first JSON object in the response
            json_match = re.search(r'\{[^{}]*(?:\{[^{}]*\}[^{}]*)*\}', response)
            if json_match:
                intent_data = json.loads(json_match.group())
                logger.info(f"Extracted intent (regex fallback): {intent_data}")
                return intent_data
            
            raise json.JSONDecodeError("No JSON found", response, 0)
            
        except json.JSONDecodeError as e:
            logger.error(f"Failed to parse intent JSON: {response}")
            # Return default intent
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
