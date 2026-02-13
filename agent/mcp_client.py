"""
MCP Client for AWS Cost Explorer integration.

Wraps the MCP protocol to call the AWS Cost Explorer MCP server tools.
Parameter formats match the MCP server exactly (awslabs/cost-explorer-mcp-server).
"""
import logging
import json
import os
from typing import Any, Dict, List, Optional
from contextlib import asynccontextmanager
from mcp import ClientSession, StdioServerParameters
from mcp.client.stdio import stdio_client

from config import settings

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
    """Client for interacting with AWS Cost Explorer MCP server."""
    
    def __init__(self):
        self.session: Optional[ClientSession] = None
        # Prepare environment variables for MCP server
        server_env = os.environ.copy()
        
        # Explicitly set AWS credentials from settings if present
        if settings.aws_profile:
            server_env["AWS_PROFILE"] = settings.aws_profile
        if settings.aws_region:
            server_env["AWS_REGION"] = settings.aws_region
        if settings.aws_access_key_id:
            server_env["AWS_ACCESS_KEY_ID"] = settings.aws_access_key_id
        if settings.aws_secret_access_key:
            server_env["AWS_SECRET_ACCESS_KEY"] = settings.aws_secret_access_key
            
        self.server_params = StdioServerParameters(
            command=settings.mcp_server_command,
            args=settings.mcp_server_args.split(),
            env=server_env
        )
    
    @asynccontextmanager
    async def connect(self):
        """Context manager for MCP server connection."""
        async with stdio_client(self.server_params) as (read, write):
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

    # ------------------------------------------------------------------ #
    #  Tool wrappers — parameter formats match MCP server exactly         #
    # ------------------------------------------------------------------ #

    async def get_today_date(self) -> Dict[str, str]:
        """Get current date info. Returns {today_date_UTC, current_month}."""
        return await self.call_tool("get_today_date", {})

    async def get_dimension_values(
        self,
        start_date: str,
        end_date: str,
        dimension: str,
    ) -> Dict[str, Any]:
        """Get valid values for a dimension (e.g. SERVICE, REGION).

        This is critical for resolving user shorthand like 'S3' to the
        actual value 'Amazon Simple Storage Service'.
        """
        return await self.call_tool("get_dimension_values", {
            "date_range": {
                "start_date": start_date,
                "end_date": end_date,
            },
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
        """Retrieve AWS cost and usage data.

        Notes from MCP server:
        - end_date is INCLUSIVE (MCP adds +1 day internally)
        - group_by can be a string key like 'SERVICE' (defaults to DIMENSION type)
        - filter_expression uses AWS CE filter format
        """
        arguments: Dict[str, Any] = {
            "date_range": {
                "start_date": start_date,
                "end_date": end_date,
            },
            "granularity": granularity,
            "group_by": group_by,
            "metric": metric,
        }
        if filter_expression:
            arguments["filter_expression"] = filter_expression
        
        return await self.call_tool("get_cost_and_usage", arguments)

    async def get_cost_forecast(
        self,
        start_date: str,
        end_date: str,
        granularity: str = "MONTHLY",
        filter_expression: Optional[Dict] = None,
        metric: str = "UNBLENDED_COST",
        prediction_interval_level: int = 80,
    ) -> Dict[str, Any]:
        """Retrieve AWS cost forecasts.

        Notes from MCP server:
        - start_date must be <= today, end_date must be in the future
        - metric uses SCREAMING_CASE: UNBLENDED_COST, AMORTIZED_COST, etc.
        - Returns: {predictions: {date: {predicted_cost, confidence_range}}, total_forecast}
        """
        arguments: Dict[str, Any] = {
            "date_range": {
                "start_date": start_date,
                "end_date": end_date,
            },
            "granularity": granularity,
            "metric": metric,
            "prediction_interval_level": prediction_interval_level,
        }
        if filter_expression:
            arguments["filter_expression"] = filter_expression
        
        return await self.call_tool("get_cost_forecast", arguments)

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
        """Compare AWS costs between two time periods.

        Notes from MCP server:
        - Both periods must be exactly 1 month
        - Dates must start on day 1 (e.g. 2025-01-01 to 2025-02-01)
        """
        arguments: Dict[str, Any] = {
            "baseline_date_range": {
                "start_date": baseline_start,
                "end_date": baseline_end,
            },
            "comparison_date_range": {
                "start_date": comparison_start,
                "end_date": comparison_end,
            },
            "metric_for_comparison": metric_for_comparison,
            "group_by": group_by,
        }
        if filter_expression:
            arguments["filter_expression"] = filter_expression
        
        return await self.call_tool("get_cost_and_usage_comparisons", arguments)

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
            "baseline_date_range": {
                "start_date": baseline_start,
                "end_date": baseline_end,
            },
            "comparison_date_range": {
                "start_date": comparison_start,
                "end_date": comparison_end,
            },
            "metric_for_comparison": metric_for_comparison,
            "group_by": group_by,
        }
        if filter_expression:
            arguments["filter_expression"] = filter_expression
        
        return await self.call_tool("get_cost_comparison_drivers", arguments)

    async def get_tag_values(
        self,
        start_date: str,
        end_date: str,
        tag_key: str,
    ) -> Dict[str, Any]:
        """Get valid values for a specific tag key (e.g. 'Environment', 'Project').

        Useful for understanding what tag-based cost allocations are available.
        """
        return await self.call_tool("get_tag_values", {
            "date_range": {
                "start_date": start_date,
                "end_date": end_date,
            },
            "tag_key": tag_key,
        })
