"""
Test script for the FastAPI agent.
"""
import requests
import json


BASE_URL = "http://10.103.30.81:8000"


def test_health():
    """Test health endpoint."""
    print("Testing /health endpoint...")
    response = requests.get(f"{BASE_URL}/health")
    print(f"Status: {response.status_code}")
    print(f"Response: {json.dumps(response.json(), indent=2)}")
    print()


def test_query(query: str):
    """Test query endpoint."""
    print(f"Testing query: {query}")
    response = requests.post(
        f"{BASE_URL}/api/query",
        json={"query": query}
    )
    print(f"Status: {response.status_code}")
    result = response.json()
    
    print("\n=== SUMMARY ===")
    print(result.get("summary", "No summary"))
    
    print("\n=== CHART DATA ===")
    for chart in result.get("chart_data", []):
        print(f"- {chart.get('title')} ({chart.get('type')})")
    
    print("\n=== TABLE DATA ===")
    for table in result.get("table_data", []):
        print(f"- {table.get('title')} ({len(table.get('rows', []))} rows)")
    
    print("\n" + "="*50 + "\n")


if __name__ == "__main__":
    # Test health endpoint
    test_health()
    
    # Test example queries
    queries = [
        "What were my AWS costs last month?",
        "Show me costs for the last 6 months",
        "What are my EC2 costs?",
    ]
    
    for query in queries:
        try:
            test_query(query)
        except Exception as e:
            print(f"Error: {e}\n")
