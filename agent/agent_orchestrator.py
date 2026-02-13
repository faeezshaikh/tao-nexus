"""
Agent Orchestrator - Main logic for processing user queries.
"""
import logging
import json
import math
from typing import Dict, Any, List
from datetime import datetime, timedelta
from dateutil.relativedelta import relativedelta

from mcp_client import MCPClient
from ollama_client import OllamaClient
from models import (
    QueryResponse, ChartData, ChartDataset, TableData, ColumnDefinition,
    FinopsResponse, FinopsChartData, FinopsTableData, FinopsChartSeries
)

logger = logging.getLogger(__name__)


class AgentOrchestrator:
    """Orchestrates query processing between Ollama and MCP server."""
    
    def __init__(self):
        self.ollama_client = OllamaClient()
        self.mcp_client = MCPClient()
    
    async def process_query(self, user_query: str) -> QueryResponse:
        """
        Process a user query and return structured response.
        
        Args:
            user_query: Natural language query from user
            
        Returns:
            QueryResponse with summary, chart_data, and table_data
        """
        try:
            # Step 1: Extract intent from query using Ollama
            logger.info(f"Processing query: {user_query}")
            intent_data = await self.ollama_client.extract_query_intent(user_query)
            
            # Step 2: Connect to MCP and get data
            async with self.mcp_client.connect():
                # Get current date for date calculations
                today_result = await self.mcp_client.get_today_date()
                today_data = json.loads(today_result) if isinstance(today_result, str) else today_result
                today = datetime.strptime(today_data.get("today", datetime.now().strftime("%Y-%m-%d")), "%Y-%m-%d")
                
                # Calculate date ranges based on intent
                date_ranges = self._calculate_date_ranges(intent_data, today)
                
                # Call appropriate MCP tools based on intent
                mcp_results = await self._call_mcp_tools(intent_data, date_ranges)
            
            # Step 3: Format results for UI
            chart_data = self._format_chart_data(mcp_results, intent_data)
            table_data = self._format_table_data(mcp_results, intent_data)
            
            # Step 4: Generate summary using Ollama
            summary = await self.ollama_client.generate_summary(user_query, mcp_results)
            
            return QueryResponse(
                summary=summary,
                chart_data=chart_data,
                table_data=table_data,
                success=True
            )
            
        except Exception as e:
            logger.error(f"Error processing query: {str(e)}", exc_info=True)
            return QueryResponse(
                summary=f"I encountered an error processing your query: {str(e)}",
                chart_data=[],
                table_data=[],
                success=False,
                error=str(e)
            )
    
    def _calculate_date_ranges(self, intent_data: Dict[str, Any], today: datetime) -> Dict[str, Any]:
        """Calculate date ranges based on intent and time period."""
        time_period = intent_data.get("time_period", "last month").lower()
        
        # Use explicit dates if provided
        if "start_date" in intent_data and "end_date" in intent_data:
            return {
                "start_date": intent_data["start_date"],
                "end_date": intent_data["end_date"]
            }
        
        # Calculate based on time period description
        if "last month" in time_period:
            start_date = (today.replace(day=1) - timedelta(days=1)).replace(day=1)
            end_date = today.replace(day=1)
        elif "last 6 months" in time_period or "6 months" in time_period:
            start_date = (today - relativedelta(months=6)).replace(day=1)
            end_date = today.replace(day=1)
        elif "last 3 months" in time_period or "3 months" in time_period:
            start_date = (today - relativedelta(months=3)).replace(day=1)
            end_date = today.replace(day=1)
        elif "this month" in time_period or "current month" in time_period:
            start_date = today.replace(day=1)
            end_date = today
        else:
            # Default to last month
            start_date = (today.replace(day=1) - timedelta(days=1)).replace(day=1)
            end_date = today.replace(day=1)
        
        return {
            "start_date": start_date.strftime("%Y-%m-%d"),
            "end_date": end_date.strftime("%Y-%m-%d")
        }
    
    async def _call_mcp_tools(self, intent_data: Dict[str, Any], date_ranges: Dict[str, str]) -> Dict[str, Any]:
        """Call appropriate MCP tools based on intent."""
        intent = intent_data.get("intent", "get_costs")
        group_by = intent_data.get("group_by", "SERVICE")
        filters = intent_data.get("filters", {})
        
        # Build filter expression if filters provided
        filter_expression = None
        if filters:
            filter_expression = self._build_filter_expression(filters)
        
        if intent == "get_costs":
            result = await self.mcp_client.get_cost_and_usage(
                date_range=date_ranges,
                granularity="MONTHLY",
                group_by=group_by,
                filter_expression=filter_expression
            )
        elif intent == "compare_costs":
            # For comparisons, we need two date ranges
            comparison = intent_data.get("comparison", {})
            baseline_range = comparison.get("baseline", date_ranges)
            comparison_range = comparison.get("comparison", date_ranges)
            
            result = await self.mcp_client.get_cost_and_usage_comparisons(
                baseline_date_range=baseline_range,
                comparison_date_range=comparison_range,
                group_by=group_by,
                filter_expression=filter_expression
            )
        elif intent == "forecast_costs":
            result = await self.mcp_client.get_cost_forecast(
                date_range=date_ranges,
                granularity="MONTHLY",
                filter_expression=filter_expression
            )
        else:
            # Default to get_costs
            result = await self.mcp_client.get_cost_and_usage(
                date_range=date_ranges,
                granularity="MONTHLY",
                group_by=group_by,
                filter_expression=filter_expression
            )
        
        # Parse result if it's a string
        if isinstance(result, str):
            try:
                result = json.loads(result)
            except json.JSONDecodeError:
                logger.warning("Could not parse MCP result as JSON")
        
        return result
    
    def _build_filter_expression(self, filters: Dict[str, Any]) -> Dict[str, Any]:
        """Build MCP filter expression from filters dict."""
        filter_parts = []
        
        if "service" in filters:
            services = filters["service"] if isinstance(filters["service"], list) else [filters["service"]]
            filter_parts.append({
                "Dimensions": {
                    "Key": "SERVICE",
                    "Values": services,
                    "MatchOptions": ["EQUALS"]
                }
            })
        
        if "region" in filters:
            regions = filters["region"] if isinstance(filters["region"], list) else [filters["region"]]
            filter_parts.append({
                "Dimensions": {
                    "Key": "REGION",
                    "Values": regions,
                    "MatchOptions": ["EQUALS"]
                }
            })
        
        if "account" in filters:
            accounts = filters["account"] if isinstance(filters["account"], list) else [filters["account"]]
            filter_parts.append({
                "Dimensions": {
                    "Key": "LINKED_ACCOUNT",
                    "Values": accounts,
                    "MatchOptions": ["EQUALS"]
                }
            })
        
        if len(filter_parts) == 0:
            return None
        elif len(filter_parts) == 1:
            return filter_parts[0]
        else:
            return {"And": filter_parts}
    
    def _format_chart_data(self, mcp_results: Dict[str, Any], intent_data: Dict[str, Any]) -> List[ChartData]:
        """Format MCP results into chart data structures."""
        charts = []
        
        try:
            # Structure 1: Standard AWS ResultsByTime
            if "ResultsByTime" in mcp_results:
                results_by_time = mcp_results["ResultsByTime"]
                if not results_by_time:
                    return []
                
                # Extract labels (time periods)
                labels = [item.get("TimePeriod", {}).get("Start", "") for item in results_by_time]
                
                # Collect all unique group keys across all periods
                all_keys = set()
                for item in results_by_time:
                    for group in item.get("Groups", []):
                        key = group.get("Keys", ["Total"])[0]
                        all_keys.add(key)
                
                # Build datasets with alignment (zeros for missing data)
                datasets = []
                for idx, key in enumerate(sorted(all_keys)):
                    data_values = []
                    for item in results_by_time:
                        amount = 0.0
                        for group in item.get("Groups", []):
                            if group.get("Keys", ["Total"])[0] == key:
                                # Try common cost metric names
                                for metric_name in ["UnblendedCost", "AmortizedCost", "BlendedCost"]:
                                    if metric_name in group.get("Metrics", {}):
                                        amount = float(group["Metrics"][metric_name].get("Amount", 0))
                                        if math.isnan(amount) or math.isinf(amount):
                                            amount = 0.0
                                        break
                                break
                        data_values.append(amount)
                    
                    datasets.append(ChartDataset(
                        label=key,
                        data=data_values,
                        borderColor=self._get_color(idx)
                    ))
                
                charts.append(ChartData(
                    type="line",
                    title="Cost Trend Over Time",
                    labels=labels,
                    datasets=datasets
                ))
            
            # Structure 2: Simplified GroupedCosts (from specific MCP implementation)
            elif "GroupedCosts" in mcp_results:
                grouped_costs = mcp_results["GroupedCosts"]
                # grouped_costs is { "YYYY-MM-DD": { "Dimension": cost, ... }, ... }
                
                dates = sorted(grouped_costs.keys())
                if not dates:
                    return []
                
                all_series = set()
                for date in dates:
                    for dimension in grouped_costs[date]:
                        all_series.add(dimension)
                
                datasets = []
                for idx, series_name in enumerate(sorted(all_series)):
                    values = []
                    for date in dates:
                        val = float(grouped_costs[date].get(series_name, 0))
                        values.append(val if not (math.isnan(val) or math.isinf(val)) else 0.0)
                    
                    datasets.append(ChartDataset(
                        label=series_name,
                        data=values,
                        borderColor=self._get_color(idx)
                    ))
                
                charts.append(ChartData(
                    type="line",
                    title="AWS Cost Trends",
                    labels=dates,
                    datasets=datasets
                ))
                
                # Bar chart for most recent breakdown
                if dates:
                    last_date = dates[-1]
                    last_data = grouped_costs[last_date]
                    # Get top 10 categories
                    top_keys = sorted(last_data.keys(), key=lambda k: float(last_data[k]), reverse=True)[:10]
                    bar_values = [float(last_data[k]) for k in top_keys]
                    
                    charts.append(ChartData(
                        type="bar",
                        title=f"Breakdown for {last_date}",
                        labels=top_keys,
                        datasets=[ChartDataset(label="Cost (USD)", data=bar_values, backgroundColor="#3b82f6")]
                    ))

            # Structure 3: Forecast results
            elif "ForecastResultsByTime" in mcp_results:
                forecasts = mcp_results["ForecastResultsByTime"]
                labels = [item.get("TimePeriod", {}).get("Start", "") for item in forecasts]
                values = [float(item.get("MeanValue", 0)) for item in forecasts]
                
                charts.append(ChartData(
                    type="bar",
                    title="Cost Forecast",
                    labels=labels,
                    datasets=[ChartDataset(label="Forecasted Cost", data=values, backgroundColor="#fbbf24")]
                ))
                
        except Exception as e:
            logger.error(f"Error formatting chart data: {str(e)}")
        
        return charts
    
    def _format_table_data(self, mcp_results: Dict[str, Any], intent_data: Dict[str, Any]) -> List[TableData]:
        """Format MCP results into table data structures."""
        tables = []
        
        try:
            # Structure 1: Standard AWS ResultsByTime
            if "ResultsByTime" in mcp_results:
                results_by_time = mcp_results["ResultsByTime"]
                rows = []
                for item in results_by_time:
                    time_period = item.get("TimePeriod", {}).get("Start", "")
                    for group in item.get("Groups", []):
                        service = group.get("Keys", ["Unknown"])[0]
                        amount = 0.0
                        for metric in ["UnblendedCost", "AmortizedCost", "BlendedCost"]:
                            if metric in group.get("Metrics", {}):
                                amount = float(group["Metrics"][metric].get("Amount", 0))
                                if math.isnan(amount) or math.isinf(amount):
                                    amount = 0.0
                                break
                        
                        rows.append({
                            "Period": time_period,
                            "Category": service,
                            "Cost": round(amount, 2)
                        })
                
                if rows:
                    tables.append(TableData(
                        title="Detailed Cost Breakdown",
                        columns=[
                            ColumnDefinition(name="Period", type="string"),
                            ColumnDefinition(name="Category", type="string"),
                            ColumnDefinition(name="Cost", type="currency", format="$0,0.00")
                        ],
                        rows=rows
                    ))
            
            # Structure 2: Simplified GroupedCosts
            elif "GroupedCosts" in mcp_results:
                grouped_costs = mcp_results["GroupedCosts"]
                rows = []
                for date in sorted(grouped_costs.keys()):
                    for category, amount in grouped_costs[date].items():
                        cost_val = float(amount)
                        if math.isnan(cost_val) or math.isinf(cost_val):
                            cost_val = 0.0
                        rows.append({
                            "Period": date,
                            "Category": category,
                            "Cost": round(cost_val, 2)
                        })
                
                if rows:
                    # Sort rows by date (dec) then cost (dec)
                    rows.sort(key=lambda x: (x["Period"], x["Cost"]), reverse=True)
                    
                    tables.append(TableData(
                        title="Cost Breakdown",
                        columns=[
                            ColumnDefinition(name="Period", type="string"),
                            ColumnDefinition(name="Category", type="string"),
                            ColumnDefinition(name="Cost", type="currency", format="$0,0.00")
                        ],
                        rows=rows
                    ))
                    
        except Exception as e:
            logger.error(f"Error formatting table data: {str(e)}")
        
        return tables

    
    async def process_finops_query(self, user_query: str, username: str) -> FinopsResponse:
        """
        Process a user query for the TAO Lens frontend.
        
        Args:
            user_query: Natural language query from user
            username: User requesting the data
            
        Returns:
            FinopsResponse matching the frontend contract
        """
        # First process utilizing the standard pipeline
        query_response = await self.process_query(user_query)
        
        # If standard processing failed, return error summary
        if not query_response.success:
            return FinopsResponse(
                summary=query_response.summary or "An error occurred.",
                chart=FinopsChartData(type="bar", x=[], series=[]),
                table=FinopsTableData(columns=[], rows=[])
            )
            
        # Convert internal data models to Finops models
        finops_chart = self._convert_to_finops_chart(query_response.chart_data)
        finops_table = self._convert_to_finops_table(query_response.table_data)
        
        return FinopsResponse(
            summary=query_response.summary,
            chart=finops_chart,
            table=finops_table
        )

    def _convert_to_finops_chart(self, chart_data_list: List[ChartData]) -> FinopsChartData:
        """Convert internal ChartData to FinopsChartData."""
        if not chart_data_list:
            return FinopsChartData(type="bar", x=[], series=[])
            
        # Take the first chart (usually the most relevant one)
        chart = chart_data_list[0]
        
        # Map simple type
        chart_type = "line" if chart.type == "line" else "bar"
        
        # Map series
        series = []
        for ds in chart.datasets:
            # Sanitize NaN/Inf values to prevent JSON serialization errors
            sanitized_values = [
                v if (isinstance(v, (int, float)) and not math.isnan(v) and not math.isinf(v)) else 0.0
                for v in ds.data
            ]
            series.append(FinopsChartSeries(
                name=ds.label,
                values=sanitized_values
            ))
            
        return FinopsChartData(
            type=chart_type,
            x=chart.labels,
            series=series
        )

    def _convert_to_finops_table(self, table_data_list: List[TableData]) -> FinopsTableData:
        """Convert internal TableData to FinopsTableData."""
        if not table_data_list:
            return FinopsTableData(columns=[], rows=[])
            
        # Take the first table
        table = table_data_list[0]
        
        # Extract column names
        columns = [col.name for col in table.columns]
        
        # Extract rows as arrays ensuring order matches columns
        rows = []
        for row_dict in table.rows:
            row_values = []
            for col_name in columns:
                # Get value, default to empty string if missing
                row_values.append(row_dict.get(col_name, ""))
            rows.append(row_values)
            
        return FinopsTableData(
            columns=columns,
            rows=rows
        )

    def _get_color(self, index: int) -> str:
        """Get color for chart dataset."""
        colors = [
            "#3b82f6",  # blue
            "#10b981",  # green
            "#f59e0b",  # amber
            "#ef4444",  # red
            "#8b5cf6",  # violet
            "#ec4899",  # pink
            "#06b6d4",  # cyan
            "#84cc16",  # lime
        ]
        return colors[index % len(colors)]
