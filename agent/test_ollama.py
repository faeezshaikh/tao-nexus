"""
Test script to check Ollama API endpoint availability.
"""
import httpx
import asyncio
import json


async def test_ollama_endpoints():
    """Test various Ollama API endpoints to find the correct one."""
    base_url = "https://ollama.services.tirescorp.com"
    
    endpoints_to_test = [
        ("/api/chat", "POST", {
            "model": "llama2",
            "messages": [{"role": "user", "content": "Hello"}],
            "stream": False
        }),
        ("/api/generate", "POST", {
            "model": "llama2",
            "prompt": "Hello",
            "stream": False
        }),
        ("/api/tags", "GET", None),
        ("/api/version", "GET", None),
        ("/v1/chat/completions", "POST", {
            "model": "llama2",
            "messages": [{"role": "user", "content": "Hello"}]
        }),
        ("/", "GET", None),
    ]
    
    print(f"Testing Ollama endpoints at: {base_url}\n")
    
    async with httpx.AsyncClient(timeout=30.0) as client:
        for endpoint, method, payload in endpoints_to_test:
            url = f"{base_url}{endpoint}"
            print(f"Testing {method} {url}")
            
            try:
                if method == "GET":
                    response = await client.get(url)
                else:
                    response = await client.post(
                        url,
                        json=payload,
                        headers={"Content-Type": "application/json"}
                    )
                
                print(f"  ✅ Status: {response.status_code}")
                
                if response.status_code == 200:
                    try:
                        data = response.json()
                        print(f"  Response preview: {json.dumps(data, indent=2)[:200]}...")
                    except:
                        print(f"  Response text: {response.text[:200]}...")
                else:
                    print(f"  Response: {response.text[:200]}")
                    
            except httpx.HTTPStatusError as e:
                print(f"  ❌ HTTP Error: {e.response.status_code}")
            except httpx.RequestError as e:
                print(f"  ❌ Request Error: {str(e)}")
            except Exception as e:
                print(f"  ❌ Error: {str(e)}")
            
            print()


if __name__ == "__main__":
    asyncio.run(test_ollama_endpoints())
