"""
Pydantic models for FastAPI request/response validation.
"""
from typing import List, Dict, Any, Optional, Literal
from pydantic import BaseModel, Field


class QueryRequest(BaseModel):
    """Request model for user queries."""
    query: str = Field(..., description="User's natural language query about AWS costs")
    
    class Config:
        json_schema_extra = {
            "example": {
                "query": "What were my AWS costs last month?"
            }
        }


class ChartDataset(BaseModel):
    """Dataset for chart visualization."""
    label: str = Field(..., description="Dataset label")
    data: List[float] = Field(..., description="Data values")
    backgroundColor: Optional[str] = Field(None, description="Background color")
    borderColor: Optional[str] = Field(None, description="Border color")


class ChartData(BaseModel):
    """Chart data structure for UI visualization."""
    type: Literal["line", "bar", "pie", "area", "doughnut"] = Field(..., description="Chart type")
    title: str = Field(..., description="Chart title")
    labels: List[str] = Field(..., description="X-axis labels or categories")
    datasets: List[ChartDataset] = Field(..., description="Data series")
    metadata: Optional[Dict[str, Any]] = Field(default_factory=dict, description="Additional context")
    
    class Config:
        json_schema_extra = {
            "example": {
                "type": "line",
                "title": "AWS Costs Over Time",
                "labels": ["Jan", "Feb", "Mar"],
                "datasets": [
                    {
                        "label": "Total Cost",
                        "data": [1200.50, 1350.75, 1180.25],
                        "borderColor": "#3b82f6"
                    }
                ],
                "metadata": {
                    "unit": "USD",
                    "period": "monthly"
                }
            }
        }


class ColumnDefinition(BaseModel):
    """Column definition for table data."""
    name: str = Field(..., description="Column name")
    type: Literal["string", "number", "currency", "date"] = Field(..., description="Data type")
    format: Optional[str] = Field(None, description="Display format (e.g., '$0,0.00' for currency)")


class TableData(BaseModel):
    """Table data structure for UI rendering."""
    title: str = Field(..., description="Table title")
    columns: List[ColumnDefinition] = Field(..., description="Column definitions")
    rows: List[Dict[str, Any]] = Field(..., description="Row data")
    metadata: Optional[Dict[str, Any]] = Field(default_factory=dict, description="Additional context")
    
    class Config:
        json_schema_extra = {
            "example": {
                "title": "Cost Breakdown by Service",
                "columns": [
                    {"name": "Service", "type": "string"},
                    {"name": "Cost", "type": "currency", "format": "$0,0.00"}
                ],
                "rows": [
                    {"Service": "EC2", "Cost": 850.25},
                    {"Service": "S3", "Cost": 125.50}
                ],
                "metadata": {
                    "total_rows": 2,
                    "total_cost": 975.75
                }
            }
        }


class QueryResponse(BaseModel):
    """Response model for query results."""
    summary: str = Field(..., description="Human-friendly summary of results")
    chart_data: List[ChartData] = Field(default_factory=list, description="Data for chart visualization")
    table_data: List[TableData] = Field(default_factory=list, description="Data for table rendering")
    success: bool = Field(True, description="Whether the query was successful")
    error: Optional[str] = Field(None, description="Error message if query failed")
    
    class Config:
        json_schema_extra = {
            "example": {
                "summary": "Your AWS costs for January 2026 were $1,200.50, representing a 12% increase from December.",
                "chart_data": [
                    {
                        "type": "line",
                        "title": "Monthly Cost Trend",
                        "labels": ["Dec", "Jan"],
                        "datasets": [
                            {
                                "label": "Total Cost",
                                "data": [1071.88, 1200.50]
                            }
                        ]
                    }
                ],
                "table_data": [
                    {
                        "title": "Service Breakdown",
                        "columns": [
                            {"name": "Service", "type": "string"},
                            {"name": "Cost", "type": "currency"}
                        ],
                        "rows": [
                            {"Service": "EC2", "Cost": 850.25}
                        ]
                    }
                ],
                "success": True
            }
        }


# --- TAO Lens / Finops Frontend Integration Models ---

class FinopsQueryRequest(BaseModel):
    """Request model for TAO Lens frontend."""
    question: str = Field(..., description="User's natural language question")
    username: str = Field(..., description="User requesting the data")


class FinopsChartSeries(BaseModel):
    name: str
    values: List[float]


class FinopsChartData(BaseModel):
    type: Literal["line", "bar"]
    x: List[str]
    series: List[FinopsChartSeries]


class FinopsTableData(BaseModel):
    columns: List[str]
    rows: List[List[Any]]


class FinopsResponse(BaseModel):
    """Response model matching TAO Lens frontend expectation."""
    table: FinopsTableData
    chart: FinopsChartData
    summary: str
