"""
MCP Client for AWS Cost Explorer integration.
"""
import logging
import os
from typing import Any, Dict, List, Optional
from contextlib import asynccontextmanager
from mcp import ClientSession, StdioServerParameters
from mcp.client.stdio import stdio_client

from config import settings

logger = logging.getLogger(__name__)


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
        """
        Call an MCP tool with the given arguments.
        
        Args:
            tool_name: Name of the MCP tool to call
            arguments: Tool arguments as a dictionary
            
        Returns:
            Tool result
        """
        if not self.session:
            raise RuntimeError("MCP client not connected. Use 'async with client.connect()' first.")
        
        try:
            logger.info(f"Calling MCP tool: {tool_name} with args: {arguments}")
            result = await self.session.call_tool(tool_name, arguments=arguments)
            logger.info(f"MCP tool {tool_name} completed successfully")
            return result
        except Exception as e:
            logger.error(f"Error calling MCP tool {tool_name}: {str(e)}")
            raise
    
    async def get_today_date(self) -> Dict[str, str]:
        """Get current date information."""
        result = await self.call_tool("get_today_date", {})
        return result.content[0].text if result.content else {}
    
    async def get_cost_and_usage(
        self,
        date_range: Dict[str, str],
        granularity: str = "MONTHLY",
        group_by: str = "SERVICE",
        filter_expression: Optional[Dict] = None,
        metric: str = "UnblendedCost"
    ) -> Dict[str, Any]:
        """
        Retrieve AWS cost and usage data.
        
        Args:
            date_range: Dictionary with start_date and end_date
            granularity: DAILY, MONTHLY, or HOURLY
            group_by: Dimension to group by (e.g., SERVICE, REGION)
            filter_expression: Optional filter criteria
            metric: Cost metric to use
            
        Returns:
            Cost and usage data
        """
        arguments = {
            "date_range": date_range,
            "granularity": granularity,
            "group_by": group_by,
            "metric": metric
        }
        if filter_expression:
            arguments["filter_expression"] = filter_expression
        
        result = await self.call_tool("get_cost_and_usage", arguments)
        return result.content[0].text if result.content else {}
    
    async def get_cost_forecast(
        self,
        date_range: Dict[str, str],
        granularity: str = "MONTHLY",
        filter_expression: Optional[Dict] = None,
        metric: str = "UNBLENDED_COST",
        prediction_interval_level: int = 80
    ) -> Dict[str, Any]:
        """
        Retrieve AWS cost forecasts.
        
        Args:
            date_range: Dictionary with start_date and end_date
            granularity: DAILY or MONTHLY
            filter_expression: Optional filter criteria
            metric: Cost metric to forecast
            prediction_interval_level: Confidence level (80 or 95)
            
        Returns:
            Forecast data
        """
        arguments = {
            "date_range": date_range,
            "granularity": granularity,
            "metric": metric,
            "prediction_interval_level": prediction_interval_level
        }
        if filter_expression:
            arguments["filter_expression"] = filter_expression
        
        result = await self.call_tool("get_cost_forecast", arguments)
        return result.content[0].text if result.content else {}
    
    async def get_cost_and_usage_comparisons(
        self,
        baseline_date_range: Dict[str, str],
        comparison_date_range: Dict[str, str],
        metric_for_comparison: str = "UnblendedCost",
        group_by: str = "SERVICE",
        filter_expression: Optional[Dict] = None
    ) -> Dict[str, Any]:
        """
        Compare AWS costs between two time periods.
        
        Args:
            baseline_date_range: Reference period
            comparison_date_range: Comparison period
            metric_for_comparison: Cost metric to compare
            group_by: Dimension to group by
            filter_expression: Optional filter criteria
            
        Returns:
            Comparison data with percentage changes
        """
        arguments = {
            "baseline_date_range": baseline_date_range,
            "comparison_date_range": comparison_date_range,
            "metric_for_comparison": metric_for_comparison,
            "group_by": group_by
        }
        if filter_expression:
            arguments["filter_expression"] = filter_expression
        
        result = await self.call_tool("get_cost_and_usage_comparisons", arguments)
        return result.content[0].text if result.content else {}
    
    async def get_dimension_values(
        self,
        date_range: Dict[str, str],
        dimension: str
    ) -> Dict[str, Any]:
        """
        Get available dimension values.
        
        Args:
            date_range: Dictionary with start_date and end_date
            dimension: Dimension key (e.g., SERVICE, REGION)
            
        Returns:
            Available dimension values
        """
        arguments = {
            "date_range": date_range,
            "dimension": dimension
        }
        result = await self.call_tool("get_dimension_values", arguments)
        return result.content[0].text if result.content else {}
