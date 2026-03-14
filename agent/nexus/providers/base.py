"""
Abstract provider interfaces for TAO Nexus.

These define the contracts that real AWS MCP adapters
and mock implementations must satisfy.
"""
from abc import ABC, abstractmethod
from typing import Any, Dict, List, Optional


class CostDataProvider(ABC):
    """Retrieves historical and current cloud spend data."""

    @abstractmethod
    async def get_current_monthly_spend(self) -> Dict[str, Any]:
        """Total current month-to-date spend."""
        ...

    @abstractmethod
    async def get_cost_by_service(
        self, months: int = 3
    ) -> List[Dict[str, Any]]:
        """Cost breakdown by AWS service over N months."""
        ...

    @abstractmethod
    async def get_cost_by_environment(self) -> List[Dict[str, Any]]:
        """Cost breakdown by environment (prod, dev, staging, etc.)."""
        ...

    @abstractmethod
    async def get_cost_trends(
        self, months: int = 6
    ) -> List[Dict[str, Any]]:
        """Monthly cost trend data."""
        ...


class ForecastProvider(ABC):
    """Generates cost forecasts."""

    @abstractmethod
    async def get_forecast(
        self, months_ahead: int = 3
    ) -> List[Dict[str, Any]]:
        """Baseline cost forecast for next N months."""
        ...

    @abstractmethod
    async def get_forecast_with_savings(
        self, savings_actions: List[Dict[str, Any]], months_ahead: int = 3
    ) -> List[Dict[str, Any]]:
        """Forecast adjusted for planned savings actions."""
        ...


class OptimizationProvider(ABC):
    """Discovers optimization opportunities."""

    @abstractmethod
    async def get_opportunities(
        self,
        environment_filter: Optional[str] = None,
        category_filter: Optional[str] = None,
    ) -> List[Dict[str, Any]]:
        """List of optimization opportunities."""
        ...

    @abstractmethod
    async def get_idle_resources(self) -> List[Dict[str, Any]]:
        """Idle resources that can be stopped or deleted."""
        ...

    @abstractmethod
    async def get_rightsizing_recommendations(self) -> List[Dict[str, Any]]:
        """Right-sizing recommendations for compute resources."""
        ...


class AnomalyProvider(ABC):
    """Cost anomaly detection."""

    @abstractmethod
    async def get_recent_anomalies(
        self, days: int = 30
    ) -> List[Dict[str, Any]]:
        """Recent cost anomalies."""
        ...


class CommitmentAdvisor(ABC):
    """Reserved Instance and Savings Plan analysis."""

    @abstractmethod
    async def get_ri_coverage(self) -> Dict[str, Any]:
        """Current RI coverage and recommendations."""
        ...

    @abstractmethod
    async def get_sp_coverage(self) -> Dict[str, Any]:
        """Current Savings Plans coverage and recommendations."""
        ...

    @abstractmethod
    async def get_commitment_recommendations(self) -> List[Dict[str, Any]]:
        """Purchase recommendations for RIs and SPs."""
        ...


class PricingEstimator(ABC):
    """Pre-spend architecture cost estimation."""

    @abstractmethod
    async def estimate_workload_cost(
        self, workload_spec: Dict[str, Any]
    ) -> Dict[str, Any]:
        """Estimate monthly cost for a workload specification."""
        ...
