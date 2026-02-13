"""
Agent Orchestrator - Main logic for processing user queries.

Handles the full pipeline:
1. Extract intent from user query via Ollama
2. Resolve ambiguous service names via MCP get_dimension_values
3. Calculate correct date ranges
4. Call the right MCP tool with correct parameters
5. Parse MCP response format (GroupedCosts, predictions, comparisons, drivers)
6. Format data for the frontend (charts + tables)
7. Generate a human-friendly summary via Ollama
"""
import asyncio
import logging
import json
import math
from typing import Dict, Any, List, Optional
from datetime import datetime, timedelta
from dateutil.relativedelta import relativedelta

from mcp_client import MCPClient
from ollama_client import OllamaClient
from models import (
    QueryResponse, ChartData, ChartDataset, TableData, ColumnDefinition,
    FinopsResponse, FinopsChartData, FinopsTableData, FinopsChartSeries
)

logger = logging.getLogger(__name__)


# ------------------------------------------------------------------ #
#  Constants — must match MCP server's VALID_GROUP_BY_DIMENSIONS      #
# ------------------------------------------------------------------ #
VALID_GROUP_BY_DIMENSIONS = {
    "AZ", "INSTANCE_TYPE", "LEGAL_ENTITY_NAME", "INVOICING_ENTITY",
    "LINKED_ACCOUNT", "OPERATION", "PLATFORM", "PURCHASE_TYPE",
    "SERVICE", "TENANCY", "RECORD_TYPE", "USAGE_TYPE", "REGION",
    "DATABASE_ENGINE", "INSTANCE_TYPE_FAMILY", "OPERATING_SYSTEM",
    "CACHE_ENGINE", "DEPLOYMENT_OPTION", "BILLING_ENTITY",
}

# ------------------------------------------------------------------ #
#  Fast local fallback map — used when get_dimension_values is slow   #
# ------------------------------------------------------------------ #
SERVICE_ALIAS_MAP = {
    "s3": "Amazon Simple Storage Service",
    "ec2": "Amazon Elastic Compute Cloud - Compute",
    "rds": "Amazon Relational Database Service",
    "lambda": "AWS Lambda",
    "cloudfront": "Amazon CloudFront",
    "dynamodb": "Amazon DynamoDB",
    "ecs": "Amazon Elastic Container Service",
    "eks": "Amazon Elastic Kubernetes Service",
    "sqs": "Amazon Simple Queue Service",
    "sns": "Amazon Simple Notification Service",
    "ebs": "Amazon Elastic Block Store",
    "elasticache": "Amazon ElastiCache",
    "redshift": "Amazon Redshift",
    "sagemaker": "Amazon SageMaker",
    "route53": "Amazon Route 53",
    "route 53": "Amazon Route 53",
    "cloudwatch": "Amazon CloudWatch",
    "kms": "AWS Key Management Service",
    "glue": "AWS Glue",
    "athena": "Amazon Athena",
    "emr": "Amazon EMR",
    "kinesis": "Amazon Kinesis",
    "api gateway": "Amazon API Gateway",
    "apigateway": "Amazon API Gateway",
    "secrets manager": "AWS Secrets Manager",
    "waf": "AWS WAF",
    "codebuild": "AWS CodeBuild",
    "codepipeline": "AWS CodePipeline",
    "ecr": "Amazon EC2 Container Registry",
    "lightsail": "Amazon Lightsail",
    "ses": "Amazon Simple Email Service",
    "opensearch": "Amazon OpenSearch Service",
    "elasticsearch": "Amazon OpenSearch Service",
    "step functions": "AWS Step Functions",
}


class AgentOrchestrator:
    """Orchestrates query processing between Ollama and MCP server."""
    
    def __init__(self):
        self.ollama_client = OllamaClient()
        self.mcp_client = MCPClient()
    
    # ================================================================ #
    #  Main Entry Point                                                 #
    # ================================================================ #

    async def process_query(self, user_query: str) -> QueryResponse:
        """Process a user query end-to-end and return structured response."""
        try:
            # Step 1: Extract intent from query using Ollama
            logger.info(f"Processing query: {user_query}")
            intent_data = await self.ollama_client.extract_query_intent(user_query)
            logger.info(f"Extracted intent: {intent_data}")
            
            # Step 2: Connect to MCP and execute
            async with self.mcp_client.connect():
                # 2a. Get today's date from MCP
                today = await self._get_today(intent_data)
                
                # 2b. Resolve service names (map abbreviations → real AWS names)
                intent_data = await self._resolve_service_names(intent_data, today)
                logger.info(f"Resolved intent: {intent_data}")
                
                # 2c. Validate and fix group_by
                intent_data = self._validate_group_by(intent_data)
                
                # 2d. Calculate date ranges
                date_ranges = self._calculate_date_ranges(intent_data, today)
                logger.info(f"Date ranges: {date_ranges}")
                
                # 2e. Call the right MCP tool
                intent = intent_data.get("intent", "get_costs")
                mcp_results = await self._call_mcp_tool(intent, intent_data, date_ranges, today)
                logger.info(f"MCP results keys: {list(mcp_results.keys()) if isinstance(mcp_results, dict) else type(mcp_results)}")
            
            # Step 3: Check for MCP errors
            error_msg = self._check_mcp_error(mcp_results)
            if error_msg:
                logger.warning(f"MCP error: {error_msg}")
                return QueryResponse(
                    summary=error_msg,
                    chart_data=[], table_data=[],
                    success=False, error=error_msg
                )
            
            # Step 4: Format results for UI
            chart_data = self._format_chart_data(mcp_results, intent_data)
            table_data = self._format_table_data(mcp_results, intent_data)
            
            # Step 5: Generate summary using Ollama
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
                chart_data=[], table_data=[],
                success=False, error=str(e)
            )

    # ================================================================ #
    #  Date & Service Resolution                                        #
    # ================================================================ #

    async def _get_today(self, intent_data: Dict) -> datetime:
        """Get today's date from MCP server."""
        try:
            today_result = await self.mcp_client.get_today_date()
            # MCP returns {"today_date_UTC": "2026-02-13", "current_month": "2026-02"}
            date_str = today_result.get("today_date_UTC") or today_result.get("today", "")
            if date_str:
                return datetime.strptime(date_str, "%Y-%m-%d")
        except Exception as e:
            logger.warning(f"Failed to get date from MCP, using local: {e}")
        return datetime.now()

    async def _resolve_service_names(
        self, intent_data: Dict[str, Any], today: datetime
    ) -> Dict[str, Any]:
        """Resolve user shorthand service names to actual AWS Cost Explorer names.
        
        Strategy:
        1. First try the local alias map (fast, covers 90% of cases)
        2. If no local match, call get_dimension_values to fuzzy-match against
           real AWS service names
        """
        filters = intent_data.get("filters", {})
        if not filters or "service" not in filters:
            return intent_data
        
        services = filters["service"]
        if isinstance(services, str):
            services = [services]
        
        resolved = []
        for svc in services:
            svc_lower = svc.lower().strip()
            
            # 1. Try local alias map
            if svc_lower in SERVICE_ALIAS_MAP:
                mapped = SERVICE_ALIAS_MAP[svc_lower]
                logger.info(f"Local map: '{svc}' -> '{mapped}'")
                resolved.append(mapped)
                continue
            
            # 2. Check if it already looks like a full name
            if len(svc) > 15:
                resolved.append(svc)
                continue
            
            # 3. Fall back to MCP dimension lookup for fuzzy match
            try:
                start = (today - relativedelta(months=1)).strftime("%Y-%m-%d")
                end = today.strftime("%Y-%m-%d")
                dim_result = await self.mcp_client.get_dimension_values(start, end, "SERVICE")
                
                valid_services = dim_result.get("DimensionValues", dim_result.get("values", []))
                if isinstance(valid_services, list):
                    matches = [v for v in valid_services if svc_lower in str(v).lower()]
                    if matches:
                        best = matches[0]
                        logger.info(f"Dimension lookup: '{svc}' -> '{best}'")
                        resolved.append(str(best))
                        continue
                
                logger.warning(f"Could not resolve service name: '{svc}', using as-is")
                resolved.append(svc)
            except Exception as e:
                logger.warning(f"Dimension lookup failed for '{svc}': {e}, using as-is")
                resolved.append(svc)
        
        filters["service"] = resolved
        intent_data["filters"] = filters
        return intent_data

    def _validate_group_by(self, intent_data: Dict[str, Any]) -> Dict[str, Any]:
        """Validate group_by against known valid dimensions. Fall back to SERVICE."""
        intent = intent_data.get("intent", "get_costs")
        
        # Forecasts do NOT support group_by
        if intent == "forecast_costs":
            intent_data.pop("group_by", None)
            return intent_data
        
        group_by = intent_data.get("group_by", "SERVICE")
        if isinstance(group_by, str):
            group_by = group_by.upper().strip()
        
        if group_by not in VALID_GROUP_BY_DIMENSIONS:
            logger.warning(f"Invalid group_by '{group_by}', falling back to SERVICE")
            group_by = "SERVICE"
        
        intent_data["group_by"] = group_by
        return intent_data

    # ================================================================ #
    #  Date Range Calculation                                           #
    # ================================================================ #

    def _calculate_date_ranges(self, intent_data: Dict[str, Any], today: datetime) -> Dict[str, str]:
        """Calculate date ranges based on intent and time period."""
        # Use explicit dates if LLM provided them (and they look valid)
        if "start_date" in intent_data and "end_date" in intent_data:
            try:
                start = datetime.strptime(intent_data["start_date"], "%Y-%m-%d")
                end = datetime.strptime(intent_data["end_date"], "%Y-%m-%d")
                if start < end:
                    return {
                        "start_date": intent_data["start_date"],
                        "end_date": intent_data["end_date"]
                    }
            except (ValueError, TypeError):
                logger.warning("LLM-provided dates invalid, computing from time_period")
        
        time_period = intent_data.get("time_period", "last month").lower()
        
        if "last month" in time_period or "last full month" in time_period:
            # First day of previous month to last day of previous month
            first_of_this = today.replace(day=1)
            end = first_of_this - timedelta(days=1)  # last day of prev month
            start = end.replace(day=1)                # first day of prev month
        elif "6 months" in time_period:
            start = (today - relativedelta(months=6)).replace(day=1)
            end = (today.replace(day=1) - timedelta(days=1))
        elif "3 months" in time_period:
            start = (today - relativedelta(months=3)).replace(day=1)
            end = (today.replace(day=1) - timedelta(days=1))
        elif "this month" in time_period or "current month" in time_period:
            start = today.replace(day=1)
            end = today
        elif "last 7 days" in time_period or "7 days" in time_period:
            start = today - timedelta(days=7)
            end = today - timedelta(days=1)
        elif "last 30 days" in time_period or "30 days" in time_period:
            start = today - timedelta(days=30)
            end = today - timedelta(days=1)
        elif "year to date" in time_period or "ytd" in time_period:
            start = today.replace(month=1, day=1)
            end = today - timedelta(days=1)
        elif "last year" in time_period:
            start = today.replace(year=today.year - 1, month=1, day=1)
            end = today.replace(month=1, day=1) - timedelta(days=1)
        elif "last quarter" in time_period or "quarter" in time_period:
            q_month = ((today.month - 1) // 3) * 3 + 1
            start = today.replace(month=q_month, day=1) - relativedelta(months=3)
            end = today.replace(month=q_month, day=1) - timedelta(days=1)
        else:
            # Default to last month
            first_of_this = today.replace(day=1)
            end = first_of_this - timedelta(days=1)
            start = end.replace(day=1)
        
        return {
            "start_date": start.strftime("%Y-%m-%d"),
            "end_date": end.strftime("%Y-%m-%d"),
        }

    # ================================================================ #
    #  MCP Tool Routing                                                 #
    # ================================================================ #

    async def _call_mcp_tool(
        self,
        intent: str,
        intent_data: Dict[str, Any],
        date_ranges: Dict[str, str],
        today: datetime,
    ) -> Dict[str, Any]:
        """Route to the correct MCP tool based on intent."""
        group_by = intent_data.get("group_by", "SERVICE")
        filters = intent_data.get("filters", {})
        filter_expr = self._build_filter_expression(filters) if filters else None
        
        if intent == "forecast_costs":
            return await self._call_forecast(intent_data, date_ranges, today, filter_expr)
        
        if intent == "compare_costs":
            return await self._call_comparison(intent_data, date_ranges, today, group_by, filter_expr)
        
        if intent == "get_cost_drivers":
            return await self._call_cost_drivers(intent_data, date_ranges, today, group_by, filter_expr)
        
        # Default: get_costs / get_breakdown
        granularity = intent_data.get("granularity", "MONTHLY").upper()
        if granularity not in ("DAILY", "MONTHLY", "HOURLY"):
            granularity = "MONTHLY"
        
        return await self.mcp_client.get_cost_and_usage(
            start_date=date_ranges["start_date"],
            end_date=date_ranges["end_date"],
            granularity=granularity,
            group_by=group_by,
            filter_expression=filter_expr,
        )

    async def _call_forecast(
        self,
        intent_data: Dict,
        date_ranges: Dict[str, str],
        today: datetime,
        filter_expr: Optional[Dict],
    ) -> Dict[str, Any]:
        """Call get_cost_forecast with correct date handling.
        
        MCP server requires:
        - start_date <= today
        - end_date must be in the future (after today)
        """
        # start_date = today
        start_date = today.strftime("%Y-%m-%d")
        
        # Calculate forecast end based on the LLM's end_date or time_period
        end_date = None
        
        # First try LLM-provided end_date
        if "end_date" in intent_data:
            try:
                llm_end = datetime.strptime(intent_data["end_date"], "%Y-%m-%d")
                if llm_end > today:
                    end_date = intent_data["end_date"]
            except (ValueError, TypeError):
                pass
        
        # If no valid end_date, compute from time_period
        if not end_date:
            time_period = intent_data.get("time_period", "next month").lower()
            if "quarter" in time_period or "3 months" in time_period:
                end = (today.replace(day=1) + relativedelta(months=4))
            elif "6 months" in time_period:
                end = (today.replace(day=1) + relativedelta(months=7))
            elif "year" in time_period or "12 months" in time_period:
                end = (today.replace(day=1) + relativedelta(months=13))
            else:
                # Default: next month → first day of month after next
                end = (today.replace(day=1) + relativedelta(months=2))
            end_date = end.strftime("%Y-%m-%d")
        
        # Safety: ensure end_date is at least 2 days after today
        end_dt = datetime.strptime(end_date, "%Y-%m-%d")
        if end_dt <= today + timedelta(days=1):
            end_date = (today + timedelta(days=30)).strftime("%Y-%m-%d")
        
        logger.info(f"Forecast: start={start_date}, end={end_date}")
        
        return await self.mcp_client.get_cost_forecast(
            start_date=start_date,
            end_date=end_date,
            granularity="MONTHLY",
            filter_expression=filter_expr,
        )

    async def _call_comparison(
        self,
        intent_data: Dict,
        date_ranges: Dict[str, str],
        today: datetime,
        group_by: str,
        filter_expr: Optional[Dict],
    ) -> Dict[str, Any]:
        """Call get_cost_and_usage_comparisons with correct 1-month periods.

        MCP requires both periods to be exactly 1 month, starting on day 1.
        Dates are: start = YYYY-MM-01, end = first of next month.
        """
        comparison = intent_data.get("comparison", {})
        
        if comparison.get("baseline") and comparison.get("comparison"):
            baseline = comparison["baseline"]
            comp = comparison["comparison"]
        else:
            # Default: compare last month vs previous month
            # Comparison period = last full month
            comp_start = (today.replace(day=1) - timedelta(days=1)).replace(day=1)
            comp_end = today.replace(day=1)
            # Baseline period = month before that
            baseline_start = (comp_start - timedelta(days=1)).replace(day=1)
            baseline_end = comp_start
            
            baseline = {"start_date": baseline_start.strftime("%Y-%m-%d"), "end_date": baseline_end.strftime("%Y-%m-%d")}
            comp = {"start_date": comp_start.strftime("%Y-%m-%d"), "end_date": comp_end.strftime("%Y-%m-%d")}
        
        logger.info(f"Comparison: baseline={baseline}, comp={comp}")
        
        return await self.mcp_client.get_cost_and_usage_comparisons(
            baseline_start=baseline["start_date"],
            baseline_end=baseline["end_date"],
            comparison_start=comp["start_date"],
            comparison_end=comp["end_date"],
            group_by=group_by,
            filter_expression=filter_expr,
        )

    async def _call_cost_drivers(
        self,
        intent_data: Dict,
        date_ranges: Dict[str, str],
        today: datetime,
        group_by: str,
        filter_expr: Optional[Dict],
    ) -> Dict[str, Any]:
        """Call get_cost_comparison_drivers to analyze what drove cost changes.

        MCP requires both periods to be exactly 1 month, starting on day 1.
        Returns top 10 most significant cost change drivers.
        """
        comparison = intent_data.get("comparison", {})
        
        if comparison.get("baseline") and comparison.get("comparison"):
            baseline = comparison["baseline"]
            comp = comparison["comparison"]
        else:
            # Default: compare last month vs previous month
            comp_start = (today.replace(day=1) - timedelta(days=1)).replace(day=1)
            comp_end = today.replace(day=1)
            baseline_start = (comp_start - timedelta(days=1)).replace(day=1)
            baseline_end = comp_start
            
            baseline = {"start_date": baseline_start.strftime("%Y-%m-%d"), "end_date": baseline_end.strftime("%Y-%m-%d")}
            comp = {"start_date": comp_start.strftime("%Y-%m-%d"), "end_date": comp_end.strftime("%Y-%m-%d")}
        
        logger.info(f"Cost drivers: baseline={baseline}, comp={comp}")
        
        return await self.mcp_client.get_cost_comparison_drivers(
            baseline_start=baseline["start_date"],
            baseline_end=baseline["end_date"],
            comparison_start=comp["start_date"],
            comparison_end=comp["end_date"],
            group_by=group_by,
            filter_expression=filter_expr,
        )

    # ================================================================ #
    #  Filter Building                                                  #
    # ================================================================ #

    def _build_filter_expression(self, filters: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        """Build AWS Cost Explorer filter expression from intent filters."""
        parts = []
        
        if "service" in filters:
            services = filters["service"] if isinstance(filters["service"], list) else [filters["service"]]
            parts.append({
                "Dimensions": {
                    "Key": "SERVICE",
                    "Values": services,
                    "MatchOptions": ["EQUALS"]
                }
            })
        
        if "region" in filters:
            regions = filters["region"] if isinstance(filters["region"], list) else [filters["region"]]
            parts.append({
                "Dimensions": {
                    "Key": "REGION",
                    "Values": regions,
                    "MatchOptions": ["EQUALS"]
                }
            })
        
        if "account" in filters:
            accounts = filters["account"] if isinstance(filters["account"], list) else [filters["account"]]
            parts.append({
                "Dimensions": {
                    "Key": "LINKED_ACCOUNT",
                    "Values": accounts,
                    "MatchOptions": ["EQUALS"]
                }
            })
        
        if len(parts) == 0:
            return None
        elif len(parts) == 1:
            return parts[0]
        else:
            return {"And": parts}

    # ================================================================ #
    #  Error Detection                                                  #
    # ================================================================ #

    def _check_mcp_error(self, mcp_results: Any) -> Optional[str]:
        """Check if MCP results contain an error instead of cost data."""
        if not mcp_results:
            return "No data returned from AWS Cost Explorer."
        
        if isinstance(mcp_results, dict):
            if "error" in mcp_results:
                error_text = mcp_results["error"]
                logger.error(f"MCP returned error: {error_text}")
                return f"AWS Cost Explorer error: {error_text}"
            
            # Check for empty results with message
            if "message" in mcp_results and "GroupedCosts" in mcp_results:
                if not mcp_results["GroupedCosts"]:
                    return mcp_results["message"]
        
        if isinstance(mcp_results, str):
            lower = mcp_results.lower()
            if "error" in lower or "expired" in lower or "denied" in lower:
                return f"AWS returned an error: {mcp_results[:300]}"
        
        return None

    # ================================================================ #
    #  Response Formatting — Charts                                     #
    # ================================================================ #

    def _format_chart_data(self, mcp_results: Dict[str, Any], intent_data: Dict[str, Any]) -> List[ChartData]:
        """Format MCP results into chart data structures."""
        charts = []
        
        try:
            # Format 1: GroupedCosts (standard get_cost_and_usage response)
            if "GroupedCosts" in mcp_results:
                chart = self._chart_from_grouped_costs(mcp_results["GroupedCosts"], intent_data)
                if chart:
                    charts.append(chart)
            
            # Format 2: Forecast predictions
            elif "predictions" in mcp_results:
                chart = self._chart_from_forecast(mcp_results)
                if chart:
                    charts.append(chart)
            
            # Format 3: Comparison data
            elif "comparison_data" in mcp_results or "GroupedComparisons" in mcp_results:
                chart = self._chart_from_comparison(mcp_results)
                if chart:
                    charts.append(chart)
            
            # Format 4: Cost drivers
            elif "drivers" in mcp_results or "cost_drivers" in mcp_results:
                chart = self._chart_from_drivers(mcp_results)
                if chart:
                    charts.append(chart)
            
            # Format 5: AWS raw ResultsByTime (legacy / fallback)
            elif "ResultsByTime" in mcp_results:
                chart = self._chart_from_results_by_time(mcp_results["ResultsByTime"])
                if chart:
                    charts.append(chart)
                    
        except Exception as e:
            logger.error(f"Error formatting chart data: {str(e)}", exc_info=True)
        
        return charts

    def _chart_from_grouped_costs(self, grouped_costs: Dict, intent_data: Dict[str, Any] = None) -> Optional[ChartData]:
        """Build chart from MCP GroupedCosts format.
        
        GroupedCosts is a dict like:
        {
            "2025-08-01": {"Amazon S3": 10.5, "Amazon EC2": 50.2, ...},
            "2025-09-01": {"Amazon S3": 12.1, "Amazon EC2": 48.0, ...},
            ...,
            "Service Total": {...},
            "Total UnblendedCost": {...}
        }
        """
        if not grouped_costs:
            return None
        
        # Separate date columns from total/summary columns
        date_keys = []
        for k in grouped_costs.keys():
            if k and len(k) == 10 and k[4] == '-' and k[7] == '-':
                date_keys.append(k)
        
        if not date_keys:
            date_keys = [k for k in grouped_costs.keys() if "total" not in k.lower()]
        
        date_keys.sort()
        if not date_keys:
            return None
        
        # Collect all series names across all dates (excluding total rows)
        all_series = set()
        for dk in date_keys:
            data = grouped_costs[dk]
            if isinstance(data, dict):
                for key in data.keys():
                    if "total" not in key.lower():
                        all_series.add(key)
        
        # Build datasets
        datasets = []
        for idx, series_name in enumerate(sorted(all_series)):
            values = []
            for dk in date_keys:
                data = grouped_costs[dk]
                val = 0.0
                if isinstance(data, dict) and series_name in data:
                    raw = data[series_name]
                    try:
                        val = float(raw)
                        if math.isnan(val) or math.isinf(val):
                            val = 0.0
                    except (TypeError, ValueError):
                        val = 0.0
                values.append(round(val, 2))
            
            datasets.append(ChartDataset(
                label=series_name,
                data=values,
                borderColor=self._get_color(idx),
            ))
        
        chart_type = "bar" if len(date_keys) <= 2 else "line"
        group_by = intent_data.get("group_by", "SERVICE") if intent_data else "SERVICE"
        title = f"AWS Costs by {group_by.replace('_', ' ').title()}"
        
        return ChartData(
            type=chart_type,
            title=title,
            labels=date_keys,
            datasets=datasets,
        )

    def _chart_from_forecast(self, mcp_results: Dict) -> Optional[ChartData]:
        """Build chart from MCP forecast response."""
        predictions = mcp_results.get("predictions", {})
        if not predictions:
            return None
        
        dates = sorted(predictions.keys())
        values = []
        lower = []
        upper = []
        for d in dates:
            pred = predictions[d]
            val = self._safe_float(pred.get("predicted_cost", 0))
            values.append(round(val, 2))
            cr = pred.get("confidence_range", {})
            lower.append(round(self._safe_float(cr.get("lower_bound", 0)), 2))
            upper.append(round(self._safe_float(cr.get("upper_bound", 0)), 2))
        
        datasets = [
            ChartDataset(label="Forecasted Cost (USD)", data=values, backgroundColor="#fbbf24", borderColor="#f59e0b"),
            ChartDataset(label="Lower Bound", data=lower, backgroundColor="rgba(16,185,129,0.2)", borderColor="#10b981"),
            ChartDataset(label="Upper Bound", data=upper, backgroundColor="rgba(239,68,68,0.2)", borderColor="#ef4444"),
        ]
        
        return ChartData(
            type="bar",
            title="Cost Forecast",
            labels=dates,
            datasets=datasets,
        )

    def _chart_from_comparison(self, mcp_results: Dict) -> Optional[ChartData]:
        """Build chart from comparison response."""
        # The comparison handler returns a complex structure; extract what we can
        comparisons = mcp_results.get("comparison_data", mcp_results.get("GroupedComparisons", {}))
        if not comparisons:
            return None
        
        labels = []
        baseline_vals = []
        comparison_vals = []
        
        for key, data in comparisons.items():
            if "total" in key.lower():
                continue
            labels.append(key)
            if isinstance(data, dict):
                baseline_vals.append(round(self._safe_float(data.get("baseline_cost", data.get("baseline", 0))), 2))
                comparison_vals.append(round(self._safe_float(data.get("comparison_cost", data.get("comparison", 0))), 2))
            else:
                baseline_vals.append(0.0)
                comparison_vals.append(0.0)
        
        if not labels:
            return None
        
        # Sort by comparison value descending, take top 10
        combined = sorted(zip(labels, baseline_vals, comparison_vals), key=lambda x: x[2], reverse=True)[:10]
        labels = [c[0] for c in combined]
        baseline_vals = [c[1] for c in combined]
        comparison_vals = [c[2] for c in combined]
        
        return ChartData(
            type="bar",
            title="Cost Comparison",
            labels=labels,
            datasets=[
                ChartDataset(label="Baseline Period", data=baseline_vals, backgroundColor="#3b82f6"),
                ChartDataset(label="Comparison Period", data=comparison_vals, backgroundColor="#f59e0b"),
            ],
        )

    def _chart_from_drivers(self, mcp_results: Dict) -> Optional[ChartData]:
        """Build chart from cost drivers response."""
        drivers = mcp_results.get("drivers", mcp_results.get("cost_drivers", []))
        if not drivers:
            return None
        
        labels = []
        changes = []
        
        if isinstance(drivers, list):
            for d in drivers[:10]:
                name = d.get("name", d.get("key", "Unknown"))
                change = self._safe_float(d.get("absolute_change", d.get("change", 0)))
                labels.append(name)
                changes.append(round(change, 2))
        elif isinstance(drivers, dict):
            for key, data in list(drivers.items())[:10]:
                labels.append(key)
                if isinstance(data, dict):
                    changes.append(round(self._safe_float(data.get("absolute_change", data.get("change", 0))), 2))
                else:
                    changes.append(round(self._safe_float(data), 2))
        
        if not labels:
            return None
        
        colors = ["#ef4444" if v > 0 else "#10b981" for v in changes]
        
        return ChartData(
            type="bar",
            title="Top Cost Change Drivers",
            labels=labels,
            datasets=[
                ChartDataset(label="Cost Change (USD)", data=changes, backgroundColor=colors[0]),
            ],
        )

    def _chart_from_results_by_time(self, results_by_time: List) -> Optional[ChartData]:
        """Build chart from raw AWS ResultsByTime format (fallback)."""
        if not results_by_time:
            return None
        
        labels = [item.get("TimePeriod", {}).get("Start", "") for item in results_by_time]
        
        all_keys = set()
        for item in results_by_time:
            for group in item.get("Groups", []):
                key = group.get("Keys", ["Total"])[0]
                all_keys.add(key)
        
        datasets = []
        for idx, key in enumerate(sorted(all_keys)):
            data_values = []
            for item in results_by_time:
                amount = 0.0
                for group in item.get("Groups", []):
                    if group.get("Keys", ["Total"])[0] == key:
                        for metric_name in ["UnblendedCost", "AmortizedCost", "BlendedCost"]:
                            if metric_name in group.get("Metrics", {}):
                                amount = self._safe_float(group["Metrics"][metric_name].get("Amount", 0))
                                break
                        break
                data_values.append(round(amount, 2))
            
            datasets.append(ChartDataset(
                label=key,
                data=data_values,
                borderColor=self._get_color(idx),
            ))
        
        return ChartData(
            type="line",
            title="Cost Trend Over Time",
            labels=labels,
            datasets=datasets,
        )

    # ================================================================ #
    #  Response Formatting — Tables                                     #
    # ================================================================ #

    def _format_table_data(self, mcp_results: Dict[str, Any], intent_data: Dict[str, Any]) -> List[TableData]:
        """Format MCP results into table data structures."""
        tables = []
        
        try:
            if "GroupedCosts" in mcp_results:
                table = self._table_from_grouped_costs(mcp_results["GroupedCosts"], intent_data)
                if table:
                    tables.append(table)
            
            elif "predictions" in mcp_results:
                table = self._table_from_forecast(mcp_results)
                if table:
                    tables.append(table)
            
            elif "comparison_data" in mcp_results or "GroupedComparisons" in mcp_results:
                table = self._table_from_comparison(mcp_results)
                if table:
                    tables.append(table)
            
            elif "drivers" in mcp_results or "cost_drivers" in mcp_results:
                table = self._table_from_drivers(mcp_results)
                if table:
                    tables.append(table)
            
            elif "ResultsByTime" in mcp_results:
                table = self._table_from_results_by_time(mcp_results["ResultsByTime"])
                if table:
                    tables.append(table)
                    
        except Exception as e:
            logger.error(f"Error formatting table data: {str(e)}", exc_info=True)
        
        return tables

    def _table_from_grouped_costs(self, grouped_costs: Dict, intent_data: Dict[str, Any] = None) -> Optional[TableData]:
        """Build table from GroupedCosts format."""
        rows = []
        group_by = intent_data.get("group_by", "SERVICE") if intent_data else "SERVICE"
        category_label = group_by.replace("_", " ").title()
        
        for date_key in sorted(grouped_costs.keys()):
            if "total" in date_key.lower():
                continue
            
            data = grouped_costs[date_key]
            if not isinstance(data, dict):
                continue
            
            for category, amount in data.items():
                if "total" in category.lower():
                    continue
                cost_val = self._safe_float(amount)
                
                rows.append({
                    "Period": date_key,
                    category_label: category,
                    "Cost (USD)": round(cost_val, 2),
                })
        
        if not rows:
            return None
        
        # Sort by date desc, then cost desc
        rows.sort(key=lambda x: (x["Period"], -x["Cost (USD)"]), reverse=True)
        
        return TableData(
            title="Cost Breakdown",
            columns=[
                ColumnDefinition(name="Period", type="string"),
                ColumnDefinition(name=category_label, type="string"),
                ColumnDefinition(name="Cost (USD)", type="currency", format="$0,0.00"),
            ],
            rows=rows,
        )

    def _table_from_forecast(self, mcp_results: Dict) -> Optional[TableData]:
        """Build table from forecast response."""
        predictions = mcp_results.get("predictions", {})
        if not predictions:
            return None
        
        rows = []
        for date_key in sorted(predictions.keys()):
            pred = predictions[date_key]
            cr = pred.get("confidence_range", {})
            rows.append({
                "Period": date_key,
                "Predicted Cost": round(self._safe_float(pred.get("predicted_cost", 0)), 2),
                "Lower Bound": round(self._safe_float(cr.get("lower_bound", 0)), 2),
                "Upper Bound": round(self._safe_float(cr.get("upper_bound", 0)), 2),
            })
        
        # Add total row
        total = mcp_results.get("total_forecast", {})
        if total:
            tcr = total.get("confidence_range", {})
            rows.append({
                "Period": "TOTAL",
                "Predicted Cost": round(self._safe_float(total.get("predicted_cost", 0)), 2),
                "Lower Bound": round(self._safe_float(tcr.get("lower_bound", 0)), 2),
                "Upper Bound": round(self._safe_float(tcr.get("upper_bound", 0)), 2),
            })
        
        return TableData(
            title="Cost Forecast",
            columns=[
                ColumnDefinition(name="Period", type="string"),
                ColumnDefinition(name="Predicted Cost", type="currency", format="$0,0.00"),
                ColumnDefinition(name="Lower Bound", type="currency", format="$0,0.00"),
                ColumnDefinition(name="Upper Bound", type="currency", format="$0,0.00"),
            ],
            rows=rows,
        )

    def _table_from_comparison(self, mcp_results: Dict) -> Optional[TableData]:
        """Build table from comparison response."""
        comparisons = mcp_results.get("comparison_data", mcp_results.get("GroupedComparisons", {}))
        if not comparisons:
            return None
        
        rows = []
        for key, data in comparisons.items():
            if "total" in key.lower():
                continue
            if isinstance(data, dict):
                baseline = self._safe_float(data.get("baseline_cost", data.get("baseline", 0)))
                comparison = self._safe_float(data.get("comparison_cost", data.get("comparison", 0)))
                pct = self._safe_float(data.get("percentage_change", data.get("pct_change", 0)))
                abs_change = self._safe_float(data.get("absolute_change", data.get("change", comparison - baseline)))
                rows.append({
                    "Service": key,
                    "Baseline": round(baseline, 2),
                    "Comparison": round(comparison, 2),
                    "Change": round(abs_change, 2),
                    "% Change": round(pct, 1),
                })
        
        if not rows:
            return None
        
        rows.sort(key=lambda x: abs(x["Change"]), reverse=True)
        
        return TableData(
            title="Cost Comparison",
            columns=[
                ColumnDefinition(name="Service", type="string"),
                ColumnDefinition(name="Baseline", type="currency", format="$0,0.00"),
                ColumnDefinition(name="Comparison", type="currency", format="$0,0.00"),
                ColumnDefinition(name="Change", type="currency", format="$0,0.00"),
                ColumnDefinition(name="% Change", type="number", format="0.0%"),
            ],
            rows=rows,
        )

    def _table_from_drivers(self, mcp_results: Dict) -> Optional[TableData]:
        """Build table from cost drivers response."""
        drivers = mcp_results.get("drivers", mcp_results.get("cost_drivers", []))
        if not drivers:
            return None
        
        rows = []
        if isinstance(drivers, list):
            for d in drivers[:10]:
                rows.append({
                    "Driver": d.get("name", d.get("key", "Unknown")),
                    "Baseline Cost": round(self._safe_float(d.get("baseline_cost", 0)), 2),
                    "Comparison Cost": round(self._safe_float(d.get("comparison_cost", 0)), 2),
                    "Change": round(self._safe_float(d.get("absolute_change", d.get("change", 0))), 2),
                    "% Change": round(self._safe_float(d.get("percentage_change", d.get("pct_change", 0))), 1),
                })
        elif isinstance(drivers, dict):
            for key, data in list(drivers.items())[:10]:
                if isinstance(data, dict):
                    rows.append({
                        "Driver": key,
                        "Baseline Cost": round(self._safe_float(data.get("baseline_cost", 0)), 2),
                        "Comparison Cost": round(self._safe_float(data.get("comparison_cost", 0)), 2),
                        "Change": round(self._safe_float(data.get("absolute_change", data.get("change", 0))), 2),
                        "% Change": round(self._safe_float(data.get("percentage_change", data.get("pct_change", 0))), 1),
                    })
        
        if not rows:
            return None
        
        return TableData(
            title="Cost Change Drivers",
            columns=[
                ColumnDefinition(name="Driver", type="string"),
                ColumnDefinition(name="Baseline Cost", type="currency", format="$0,0.00"),
                ColumnDefinition(name="Comparison Cost", type="currency", format="$0,0.00"),
                ColumnDefinition(name="Change", type="currency", format="$0,0.00"),
                ColumnDefinition(name="% Change", type="number", format="0.0%"),
            ],
            rows=rows,
        )

    def _table_from_results_by_time(self, results_by_time: List) -> Optional[TableData]:
        """Build table from raw AWS ResultsByTime."""
        rows = []
        for item in results_by_time:
            period = item.get("TimePeriod", {}).get("Start", "")
            for group in item.get("Groups", []):
                service = group.get("Keys", ["Unknown"])[0]
                amount = 0.0
                for metric in ["UnblendedCost", "AmortizedCost", "BlendedCost"]:
                    if metric in group.get("Metrics", {}):
                        amount = self._safe_float(group["Metrics"][metric].get("Amount", 0))
                        break
                rows.append({"Period": period, "Category": service, "Cost (USD)": round(amount, 2)})
        
        if not rows:
            return None
        
        return TableData(
            title="Detailed Cost Breakdown",
            columns=[
                ColumnDefinition(name="Period", type="string"),
                ColumnDefinition(name="Category", type="string"),
                ColumnDefinition(name="Cost (USD)", type="currency", format="$0,0.00"),
            ],
            rows=rows,
        )

    # ================================================================ #
    #  Finops Frontend Conversion                                       #
    # ================================================================ #

    async def process_finops_query(self, user_query: str, username: str) -> FinopsResponse:
        """Process a user query for the TAO Lens frontend."""
        query_response = await self.process_query(user_query)
        
        if not query_response.success:
            return FinopsResponse(
                summary=query_response.summary or "An error occurred.",
                chart=FinopsChartData(type="bar", x=[], series=[]),
                table=FinopsTableData(columns=[], rows=[]),
            )
        
        finops_chart = self._convert_to_finops_chart(query_response.chart_data)
        finops_table = self._convert_to_finops_table(query_response.table_data)
        
        return FinopsResponse(
            summary=query_response.summary,
            chart=finops_chart,
            table=finops_table,
        )

    async def process_finops_query_stream(
        self, user_query: str, username: str, progress_queue: asyncio.Queue
    ) -> FinopsResponse:
        """Process query with real-time progress events pushed to queue.
        
        Each event is a dict: {step, total, message, emoji}
        A None sentinel signals completion of progress events.
        """
        TOTAL_STEPS = 8

        async def report(step: int, message: str, emoji: str = "⏳"):
            await progress_queue.put(
                {"step": step, "total": TOTAL_STEPS, "message": message, "emoji": emoji}
            )

        try:
            # Step 1: Extract intent
            await report(1, "Understanding your question…", "🧠")
            intent_data = await self.ollama_client.extract_query_intent(user_query)
            logger.info(f"[stream] Extracted intent: {intent_data}")

            # Step 2: Connect to MCP
            await report(2, "Connecting to AWS Cost Explorer…", "🔌")
            async with self.mcp_client.connect():
                today = await self._get_today(intent_data)

                # Step 3: Resolve service names
                await report(3, "Resolving service names…", "🔍")
                intent_data = await self._resolve_service_names(intent_data, today)

                # Step 4: Calculate date ranges
                await report(4, "Calculating date ranges…", "📅")
                intent_data = self._validate_group_by(intent_data)
                date_ranges = self._calculate_date_ranges(intent_data, today)

                # Step 5: Call MCP tool
                intent = intent_data.get("intent", "get_costs")
                tool_name_map = {
                    "forecast_costs": "get_cost_forecast",
                    "compare_costs": "get_cost_and_usage_comparisons",
                    "get_cost_drivers": "get_cost_comparison_drivers",
                }
                tool_display = tool_name_map.get(intent, "get_cost_and_usage")
                await report(5, f"Querying {tool_display}…", "⚡")
                mcp_results = await self._call_mcp_tool(intent, intent_data, date_ranges, today)

            # Step 6: Check for errors
            error_msg = self._check_mcp_error(mcp_results)
            if error_msg:
                await report(TOTAL_STEPS, "Done!", "⚠️")
                await progress_queue.put(None)
                return FinopsResponse(
                    summary=error_msg,
                    chart=FinopsChartData(type="bar", x=[], series=[]),
                    table=FinopsTableData(columns=[], rows=[]),
                )

            # Step 6: Format results
            await report(6, "Building charts & tables…", "📊")
            chart_data = self._format_chart_data(mcp_results, intent_data)
            table_data = self._format_table_data(mcp_results, intent_data)

            # Step 7: Generate summary
            await report(7, "Generating summary with AI…", "✍️")
            summary = await self.ollama_client.generate_summary(user_query, mcp_results)

            # Step 8: Done!
            await report(TOTAL_STEPS, "Done!", "✅")
            await progress_queue.put(None)  # sentinel

            query_response = QueryResponse(
                summary=summary,
                chart_data=chart_data,
                table_data=table_data,
                success=True,
            )

            finops_chart = self._convert_to_finops_chart(query_response.chart_data)
            finops_table = self._convert_to_finops_table(query_response.table_data)

            return FinopsResponse(
                summary=query_response.summary,
                chart=finops_chart,
                table=finops_table,
            )

        except Exception as e:
            logger.error(f"[stream] Error: {str(e)}", exc_info=True)
            await report(TOTAL_STEPS, f"Error: {str(e)}", "❌")
            await progress_queue.put(None)
            return FinopsResponse(
                summary=f"I encountered an error processing your query: {str(e)}",
                chart=FinopsChartData(type="bar", x=[], series=[]),
                table=FinopsTableData(columns=[], rows=[]),
            )

    def _convert_to_finops_chart(self, chart_data_list: List[ChartData]) -> FinopsChartData:
        """Convert internal ChartData to FinopsChartData."""
        if not chart_data_list:
            return FinopsChartData(type="bar", x=[], series=[])
        
        chart = chart_data_list[0]
        chart_type = "line" if chart.type == "line" else "bar"
        
        series = []
        for ds in chart.datasets:
            sanitized = [
                round(v, 2) if (isinstance(v, (int, float)) and not math.isnan(v) and not math.isinf(v)) else 0.0
                for v in ds.data
            ]
            series.append(FinopsChartSeries(name=ds.label, values=sanitized))
        
        return FinopsChartData(type=chart_type, x=chart.labels, series=series)

    def _convert_to_finops_table(self, table_data_list: List[TableData]) -> FinopsTableData:
        """Convert internal TableData to FinopsTableData."""
        if not table_data_list:
            return FinopsTableData(columns=[], rows=[])
        
        table = table_data_list[0]
        columns = [col.name for col in table.columns]
        
        rows = []
        for row_dict in table.rows:
            row_values = [row_dict.get(col, "") for col in columns]
            rows.append(row_values)
        
        return FinopsTableData(columns=columns, rows=rows)

    # ================================================================ #
    #  Utilities                                                        #
    # ================================================================ #

    def _safe_float(self, value: Any) -> float:
        """Safely convert a value to float, returning 0.0 on failure."""
        try:
            val = float(value)
            if math.isnan(val) or math.isinf(val):
                return 0.0
            return val
        except (TypeError, ValueError):
            return 0.0

    def _get_color(self, index: int) -> str:
        """Get color for chart dataset."""
        colors = [
            "#3b82f6", "#10b981", "#f59e0b", "#ef4444",
            "#8b5cf6", "#ec4899", "#06b6d4", "#84cc16",
            "#f43f5e", "#14b8a6", "#a855f7", "#eab308",
        ]
        return colors[index % len(colors)]
