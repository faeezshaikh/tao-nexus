# Example API Queries

This file contains example queries you can send to the FastAPI agent.

## Using PowerShell

### Health Check
```powershell
Invoke-WebRequest -Uri http://localhost:8000/health -Method GET
```

### Query: Last Month's Costs
```powershell
$body = @{
    query = "What were my AWS costs last month?"
} | ConvertTo-Json

Invoke-WebRequest -Uri http://localhost:8000/api/query -Method POST -Body $body -ContentType "application/json"
```

### Query: Last 6 Months
```powershell
$body = @{
    query = "Show me costs for the last 6 months"
} | ConvertTo-Json

Invoke-WebRequest -Uri http://localhost:8000/api/query -Method POST -Body $body -ContentType "application/json"
```

### Query: EC2 Costs
```powershell
$body = @{
    query = "What are my EC2 costs?"
} | ConvertTo-Json

Invoke-WebRequest -Uri http://localhost:8000/api/query -Method POST -Body $body -ContentType "application/json"
```

### Query: Cost Comparison
```powershell
$body = @{
    query = "Compare January vs December costs"
} | ConvertTo-Json

Invoke-WebRequest -Uri http://localhost:8000/api/query -Method POST -Body $body -ContentType "application/json"
```

### Query: Cost Forecast
```powershell
$body = @{
    query = "What will my costs be next month?"
} | ConvertTo-Json

Invoke-WebRequest -Uri http://localhost:8000/api/query -Method POST -Body $body -ContentType "application/json"
```

### Query: Cost Anomalies
```powershell
$body = @{
    query = "Were there any cost anomalies in the last 30 days?"
} | ConvertTo-Json

Invoke-WebRequest -Uri http://localhost:8000/api/query -Method POST -Body $body -ContentType "application/json"
```

### Query: Budget Status
```powershell
$body = @{
    query = "Am I on track with my AWS budgets?"
} | ConvertTo-Json

Invoke-WebRequest -Uri http://localhost:8000/api/query -Method POST -Body $body -ContentType "application/json"
```

### Query: Free Tier Usage
```powershell
$body = @{
    query = "Am I about to exceed any free tier limits?"
} | ConvertTo-Json

Invoke-WebRequest -Uri http://localhost:8000/api/query -Method POST -Body $body -ContentType "application/json"
```

### Query: Reserved Instance Coverage
```powershell
$body = @{
    query = "Show my Reserved Instance coverage"
} | ConvertTo-Json

Invoke-WebRequest -Uri http://localhost:8000/api/query -Method POST -Body $body -ContentType "application/json"
```

### Query: Savings Plans Recommendations
```powershell
$body = @{
    query = "What Savings Plans should I purchase?"
} | ConvertTo-Json

Invoke-WebRequest -Uri http://localhost:8000/api/query -Method POST -Body $body -ContentType "application/json"
```

### Query: EC2 Right-Sizing
```powershell
$body = @{
    query = "Which EC2 instances should I right-size?"
} | ConvertTo-Json

Invoke-WebRequest -Uri http://localhost:8000/api/query -Method POST -Body $body -ContentType "application/json"
```

### Query: Idle Resources
```powershell
$body = @{
    query = "Show idle resources I'm paying for"
} | ConvertTo-Json

Invoke-WebRequest -Uri http://localhost:8000/api/query -Method POST -Body $body -ContentType "application/json"
```

## Using Python Test Script

```bash
# Make sure the agent is running first
python test_agent.py
```

## Using curl (Git Bash or WSL)

### Health Check
```bash
curl -X GET http://localhost:8000/health
```

### Query Example
```bash
curl -X POST http://localhost:8000/api/query \
  -H "Content-Type: application/json" \
  -d '{"query": "What were my AWS costs last month?"}'
```

## Using Postman or Insomnia

1. Import the following request:
   - **Method**: POST
   - **URL**: `http://localhost:8000/api/query`
   - **Headers**: `Content-Type: application/json`
   - **Body** (JSON):
     ```json
     {
       "query": "What were my AWS costs last month?"
     }
     ```

## Expected Response Format

```json
{
  "summary": "Your AWS costs for January 2026 were $1,200.50...",
  "chart_data": [
    {
      "type": "line",
      "title": "Cost Trend Over Time",
      "labels": ["2026-01"],
      "datasets": [
        {
          "label": "Amazon Elastic Compute Cloud - Compute",
          "data": [850.25],
          "borderColor": "#3b82f6"
        }
      ],
      "metadata": {
        "unit": "USD",
        "granularity": "monthly"
      }
    }
  ],
  "table_data": [
    {
      "title": "Detailed Cost Breakdown",
      "columns": [
        {"name": "Period", "type": "string"},
        {"name": "Service", "type": "string"},
        {"name": "Cost", "type": "currency", "format": "$0,0.00"}
      ],
      "rows": [
        {
          "Period": "2026-01",
          "Service": "Amazon Elastic Compute Cloud - Compute",
          "Cost": 850.25
        }
      ],
      "metadata": {
        "total_rows": 1,
        "total_cost": 850.25
      }
    }
  ],
  "success": true
}
```
