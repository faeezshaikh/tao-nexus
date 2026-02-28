"""
MCP Client for AWS Billing & Cost Management integration.

Wraps the MCP protocol to call the AWS Billing & Cost Management MCP server tools.
Supports all tools from awslabs/billing-cost-management-mcp-server including:
- Cost Explorer (cost & usage, forecasts, comparisons, anomalies)
- Budgets, Free Tier, Pricing
- Compute Optimizer, Cost Optimization Hub
- Savings Plans & Reserved Instances
"""
import logging
import json
import os
from typing import Any, Dict, List, Optional
from contextlib import asynccontextmanager
from mcp import ClientSession, StdioServerParameters
from mcp.client.stdio import stdio_client

from config import settings
from aws_sso_refresh import ensure_sso_credentials

logger = logging.getLogger(__name__)


def _parse_mcp_result(result) -> Any:
    """Parse an MCP tool result into a Python object.
    
    The MCP SDK returns a CallToolResult whose .content is a list of
    TextContent objects. We extract the first text block and try to
    JSON-parse it. Returns raw text if JSON parsing fails.
    """
    if not result or not result.content:
        return {}
    
    text = result.content[0].text
    if not text:
        return {}
    
    try:
        return json.loads(text)
    except (json.JSONDecodeError, TypeError):
        return text


class MCPClient:
    """Client for interacting with AWS Billing & Cost Management MCP server."""
    
    def __init__(self):
        self.session: Optional[ClientSession] = None
    
    def _build_server_params(self) -> StdioServerParameters:
        """Build fresh server params with current environment.
        
        Called before each connection so that refreshed SSO tokens
        in the environment / cache are picked up by the subprocess.
        """
        server_env = os.environ.copy()
        
        if settings.aws_profile:
            server_env["AWS_PROFILE"] = settings.aws_profile
        if settings.aws_region:
            server_env["AWS_REGION"] = settings.aws_region
        if settings.aws_access_key_id:
            server_env["AWS_ACCESS_KEY_ID"] = settings.aws_access_key_id
        if settings.aws_secret_access_key:
            server_env["AWS_SECRET_ACCESS_KEY"] = settings.aws_secret_access_key
        
        # Set FASTMCP_LOG_LEVEL to reduce noise from the MCP server
        server_env.setdefault("FASTMCP_LOG_LEVEL", "ERROR")
            
        return StdioServerParameters(
            command=settings.mcp_server_command,
            args=settings.mcp_server_args.split(),
            env=server_env
        )
    
    @asynccontextmanager
    async def connect(self):
        """Context manager for MCP server connection.
        
        Ensures SSO credentials are fresh before spawning the
        MCP subprocess.
        """
        # Refresh SSO credentials BEFORE launching the MCP subprocess
        sso_region = settings.aws_region or "us-west-2"
        profile = settings.aws_profile or "DtcReadOnly-017521386069"
        ok = ensure_sso_credentials(sso_region, profile)
        if not ok:
            logger.error(
                "SSO credentials could not be refreshed. "
                "MCP connection may fail."
            )
        
        # Build fresh server params (picks up refreshed cache)
        server_params = self._build_server_params()
        async with stdio_client(server_params) as (read, write):
            async with ClientSession(read, write) as session:
                await session.initialize()
                self.session = session
                logger.info("Connected to MCP server")
                try:
                    yield self
                finally:
                    self.session = None
                    logger.info("Disconnected from MCP server")
    
    async def call_tool(self, tool_name: str, arguments: Dict[str, Any]) -> Any:
        """Call an MCP tool and return parsed result."""
        if not self.session:
            raise RuntimeError("MCP client not connected. Use 'async with client.connect()' first.")
        
        try:
            logger.info(f"Calling MCP tool: {tool_name} with args: {json.dumps(arguments, default=str)}")
            result = await self.session.call_tool(tool_name, arguments=arguments)
            parsed = _parse_mcp_result(result)
            logger.info(f"MCP tool {tool_name} completed successfully")
            return parsed
        except Exception as e:
            logger.error(f"Error calling MCP tool {tool_name}: {str(e)}")
            raise

    # ================================================================== #
    #  Cost Explorer  (tool: "cost-explorer")                              #
    #  All operations go through the unified "cost-explorer" tool          #
    #  with an "operation" parameter.                                      #
    # ================================================================== #

    async def get_today_date(self) -> Dict[str, str]:
        """Get current date info. Returns {today_date_UTC, current_month}."""
        return await self.call_tool("get_today_date", {})

    async def get_dimension_values(
        self,
        start_date: str,
        end_date: str,
        dimension: str,
    ) -> Dict[str, Any]:
        """Get valid values for a dimension (e.g. SERVICE, REGION)."""
        return await self.call_tool("cost-explorer", {
            "operation": "getDimensionValues",
            "start_date": start_date,
            "end_date": end_date,
            "dimension": dimension,
        })

    async def get_cost_and_usage(
        self,
        start_date: str,
        end_date: str,
        granularity: str = "MONTHLY",
        group_by: str = "SERVICE",
        filter_expression: Optional[Dict] = None,
        metric: str = "UnblendedCost",
    ) -> Dict[str, Any]:
        """Retrieve AWS cost and usage data."""
        arguments: Dict[str, Any] = {
            "operation": "getCostAndUsage",
            "start_date": start_date,
            "end_date": end_date,
            "granularity": granularity,
            "group_by": json.dumps([{"Type": "DIMENSION", "Key": group_by}]),
            "metrics": json.dumps([metric]),
        }
        if filter_expression:
            arguments["filter"] = json.dumps(filter_expression)
        
        return await self.call_tool("cost-explorer", arguments)

    async def get_cost_forecast(
        self,
        start_date: str,
        end_date: str,
        granularity: str = "MONTHLY",
        filter_expression: Optional[Dict] = None,
        metric: str = "UNBLENDED_COST",
        prediction_interval_level: int = 80,
    ) -> Dict[str, Any]:
        """Retrieve AWS cost forecasts."""
        arguments: Dict[str, Any] = {
            "operation": "getCostForecast",
            "start_date": start_date,
            "end_date": end_date,
            "granularity": granularity,
            "metric": metric,
            "prediction_interval_level": prediction_interval_level,
        }
        if filter_expression:
            arguments["filter"] = json.dumps(filter_expression)
        
        return await self.call_tool("cost-explorer", arguments)

    # ================================================================== #
    #  Cost Comparison  (tool: "cost-comparison")                          #
    # ================================================================== #

    async def get_cost_and_usage_comparisons(
        self,
        baseline_start: str,
        baseline_end: str,
        comparison_start: str,
        comparison_end: str,
        metric_for_comparison: str = "UnblendedCost",
        group_by: str = "SERVICE",
        filter_expression: Optional[Dict] = None,
    ) -> Dict[str, Any]:
        """Compare AWS costs between two time periods."""
        arguments: Dict[str, Any] = {
            "operation": "getCostAndUsageComparisons",
            "baseline_start_date": baseline_start,
            "baseline_end_date": baseline_end,
            "comparison_start_date": comparison_start,
            "comparison_end_date": comparison_end,
            "metric_for_comparison": metric_for_comparison,
            "group_by": json.dumps([{"Type": "DIMENSION", "Key": group_by}]),
        }
        if filter_expression:
            arguments["filter"] = json.dumps(filter_expression)
        
        return await self.call_tool("cost-comparison", arguments)

    async def get_cost_comparison_drivers(
        self,
        baseline_start: str,
        baseline_end: str,
        comparison_start: str,
        comparison_end: str,
        metric_for_comparison: str = "UnblendedCost",
        group_by: str = "SERVICE",
        filter_expression: Optional[Dict] = None,
    ) -> Dict[str, Any]:
        """Analyze top 10 cost change drivers between two periods."""
        arguments: Dict[str, Any] = {
            "operation": "getCostComparisonDrivers",
            "baseline_start_date": baseline_start,
            "baseline_end_date": baseline_end,
            "comparison_start_date": comparison_start,
            "comparison_end_date": comparison_end,
            "metric_for_comparison": metric_for_comparison,
            "group_by": json.dumps([{"Type": "DIMENSION", "Key": group_by}]),
        }
        if filter_expression:
            arguments["filter"] = json.dumps(filter_expression)
        
        return await self.call_tool("cost-comparison", arguments)

    async def get_tag_values(
        self,
        start_date: str,
        end_date: str,
        tag_key: str,
    ) -> Dict[str, Any]:
        """Get valid values for a specific tag key."""
        return await self.call_tool("cost-explorer", {
            "operation": "getTagValues",
            "start_date": start_date,
            "end_date": end_date,
            "tag_key": tag_key,
        })

    # ================================================================== #
    # ================================================================== #
    #  NEW: Cost anomaly detection  (tool: "cost-anomaly")                #
    # ================================================================== #

    async def get_anomalies(
        self,
        start_date: str = None,
        end_date: str = None,
    ) -> Dict[str, Any]:
        """Retrieve cost anomalies detected by AWS Cost Anomaly Detection."""
        args: Dict[str, Any] = {}
        if start_date:
            args["start_date"] = start_date
        if end_date:
            args["end_date"] = end_date
        return await self.call_tool("cost-anomaly", args)

    # ================================================================== #
    #  NEW: Budgets  (tool: "budgets")                                    #
    # ================================================================== #

    async def describe_budgets(self) -> Dict[str, Any]:
        """Describe all AWS budgets and their status."""
        return await self.call_tool("budgets", {})

    # ================================================================== #
    #  NEW: Free Tier  (tool: "free-tier-usage")                          #
    # ================================================================== #

    async def get_free_tier_usage(self) -> Dict[str, Any]:
        """Get AWS Free Tier usage across all services."""
        return await self.call_tool("free-tier-usage", {})

    # ================================================================== #
    #  NEW: Reserved Instances  (tool: "ri-performance")                  #
    # ================================================================== #

    async def get_reservation_coverage(
        self,
        start_date: str = None,
        end_date: str = None,
        granularity: str = "MONTHLY",
    ) -> Dict[str, Any]:
        """Analyze Reserved Instance coverage."""
        args: Dict[str, Any] = {
            "operation": "get_reservation_coverage",
            "granularity": granularity,
        }
        if start_date:
            args["start_date"] = start_date
        if end_date:
            args["end_date"] = end_date
        return await self.call_tool("ri-performance", args)

    async def get_reservation_utilization(
        self,
        start_date: str = None,
        end_date: str = None,
        granularity: str = "MONTHLY",
    ) -> Dict[str, Any]:
        """Analyze Reserved Instance utilization."""
        args: Dict[str, Any] = {
            "operation": "get_reservation_utilization",
            "granularity": granularity,
        }
        if start_date:
            args["start_date"] = start_date
        if end_date:
            args["end_date"] = end_date
        return await self.call_tool("ri-performance", args)

    async def get_reservation_purchase_recommendation(
        self,
        service: str = "Amazon Elastic Compute Cloud - Compute",
        term_in_years: str = "ONE_YEAR",
        payment_option: str = "NO_UPFRONT",
        lookback_period: str = "SIXTY_DAYS",
    ) -> Dict[str, Any]:
        """Get Reserved Instance purchase recommendations."""
        return await self.call_tool("ri-performance", {
            "operation": "get_reservation_purchase_recommendation",
            "service": service,
            "term_in_years": term_in_years,
            "payment_option": payment_option,
            "lookback_period": lookback_period,
        })

    # ================================================================== #
    #  NEW: Savings Plans  (tool: "sp-performance")                       #
    # ================================================================== #

    async def get_savings_plans_coverage(
        self,
        start_date: str = None,
        end_date: str = None,
        granularity: str = "MONTHLY",
    ) -> Dict[str, Any]:
        """Analyze Savings Plans coverage."""
        args: Dict[str, Any] = {
            "operation": "get_savings_plans_coverage",
            "granularity": granularity,
        }
        if start_date:
            args["start_date"] = start_date
        if end_date:
            args["end_date"] = end_date
        return await self.call_tool("sp-performance", args)

    async def get_savings_plans_utilization(
        self,
        start_date: str = None,
        end_date: str = None,
        granularity: str = "MONTHLY",
    ) -> Dict[str, Any]:
        """Analyze Savings Plans utilization."""
        args: Dict[str, Any] = {
            "operation": "get_savings_plans_utilization",
            "granularity": granularity,
        }
        if start_date:
            args["start_date"] = start_date
        if end_date:
            args["end_date"] = end_date
        return await self.call_tool("sp-performance", args)

    async def get_savings_plans_purchase_recommendation(
        self,
        savings_plans_type: str = "COMPUTE_SP",
        term_in_years: str = "ONE_YEAR",
        payment_option: str = "NO_UPFRONT",
        lookback_period: str = "SIXTY_DAYS",
    ) -> Dict[str, Any]:
        """Get Savings Plans purchase recommendations."""
        return await self.call_tool("sp-performance", {
            "operation": "get_savings_plans_purchase_recommendation",
            "savings_plans_type": savings_plans_type,
            "term_in_years": term_in_years,
            "payment_option": payment_option,
            "lookback_period": lookback_period,
        })

    # ================================================================== #
    #  NEW: Compute Optimizer  (tool: "compute-optimizer")                #
    # ================================================================== #

    async def get_compute_optimizer_recommendations(
        self,
        operation: str = "get_ec2_instance_recommendations",
    ) -> Dict[str, Any]:
        """Get recommendations from AWS Compute Optimizer.
        
        operation: one of get_ec2_instance_recommendations,
            get_ebs_volume_recommendations, get_lambda_function_recommendations,
            get_rds_recommendations, get_ecs_service_recommendations,
            get_auto_scaling_group_recommendations
        """
        return await self.call_tool("compute-optimizer", {
            "operation": operation,
        })

    # ================================================================== #
    #  NEW: Cost Optimization Hub  (tool: "cost-optimization")            #
    # ================================================================== #

    async def list_optimization_recommendations(
        self,
        filters: str = None,
        max_results: int = None,
    ) -> Dict[str, Any]:
        """List cost optimization recommendations (idle resources, rightsizing, etc.)."""
        args: Dict[str, Any] = {
            "operation": "list_recommendations",
        }
        if filters:
            args["filters"] = filters
        if max_results:
            args["max_results"] = max_results
        return await self.call_tool("cost-optimization", args)

    async def get_optimization_summaries(
        self,
        group_by: str = "ResourceType",
    ) -> Dict[str, Any]:
        """Get summarised cost optimization recommendations grouped by a dimension."""
        return await self.call_tool("cost-optimization", {
            "operation": "list_recommendation_summaries",
            "group_by": group_by,
        })

    async def get_recommendation_details(
        self,
        recommendation_id: str,
    ) -> Dict[str, Any]:
        """Get detailed recommendation from Cost Optimization Hub + Compute Optimizer."""
        return await self.call_tool("rec-details", {
            "recommendation_id": recommendation_id,
        })

