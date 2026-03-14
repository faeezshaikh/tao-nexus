"""
Mock provider implementations for TAO Nexus.

Returns realistic Discount-Tire-scale AWS billing data
for demonstration and development purposes.
"""
from typing import Any, Dict, List, Optional

from .base import (
    AnomalyProvider,
    CommitmentAdvisor,
    CostDataProvider,
    ForecastProvider,
    OptimizationProvider,
    PricingEstimator,
)

# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
#  Realistic mock data constants
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

MONTHLY_SPEND = 847_320.00  # ~$847K/month total AWS

SERVICE_BREAKDOWN = [
    {"service": "Amazon EC2", "monthly_cost": 338_928.00, "pct": 40.0, "trend": "increasing"},
    {"service": "Amazon RDS", "monthly_cost": 127_098.00, "pct": 15.0, "trend": "stable"},
    {"service": "Amazon S3", "monthly_cost": 84_732.00, "pct": 10.0, "trend": "increasing"},
    {"service": "Amazon EKS", "monthly_cost": 67_786.00, "pct": 8.0, "trend": "increasing"},
    {"service": "AWS Lambda", "monthly_cost": 42_366.00, "pct": 5.0, "trend": "increasing"},
    {"service": "Amazon CloudFront", "monthly_cost": 33_893.00, "pct": 4.0, "trend": "stable"},
    {"service": "Amazon ElastiCache", "monthly_cost": 25_420.00, "pct": 3.0, "trend": "stable"},
    {"service": "Amazon DynamoDB", "monthly_cost": 21_183.00, "pct": 2.5, "trend": "decreasing"},
    {"service": "Amazon OpenSearch", "monthly_cost": 16_947.00, "pct": 2.0, "trend": "stable"},
    {"service": "AWS Data Transfer", "monthly_cost": 12_710.00, "pct": 1.5, "trend": "increasing"},
    {"service": "Other Services", "monthly_cost": 76_257.00, "pct": 9.0, "trend": "stable"},
]

ENVIRONMENT_BREAKDOWN = [
    {"environment": "production", "monthly_cost": 508_392.00, "pct": 60.0},
    {"environment": "staging", "monthly_cost": 101_678.00, "pct": 12.0},
    {"environment": "development", "monthly_cost": 169_464.00, "pct": 20.0},
    {"environment": "test", "monthly_cost": 42_366.00, "pct": 5.0},
    {"environment": "sandbox", "monthly_cost": 25_420.00, "pct": 3.0},
]

MONTHLY_TRENDS = [
    {"month": "2025-10", "cost": 798_450.00},
    {"month": "2025-11", "cost": 812_100.00},
    {"month": "2025-12", "cost": 831_500.00},
    {"month": "2026-01", "cost": 839_210.00},
    {"month": "2026-02", "cost": 847_320.00},
    {"month": "2026-03", "cost": 852_000.00},  # partial month projected
]

OPTIMIZATION_OPPORTUNITIES = [
    {
        "id": "opt-001",
        "title": "Right-size 47 over-provisioned EC2 instances in dev/test",
        "description": "47 EC2 instances across dev and test environments are running at <15% average CPU utilization. Downsizing from m5.2xlarge to m5.large would maintain performance while reducing cost.",
        "category": "right_sizing",
        "service": "Amazon EC2",
        "estimated_monthly_savings": 18_240.00,
        "estimated_annual_savings": 218_880.00,
        "risk_level": "low",
        "effort": "low",
        "environment": "development",
        "reversible": True,
        "requires_code_changes": False,
        "implementation_time": "1-2 days",
        "current_cost": 28_200.00,
        "optimized_cost": 9_960.00,
    },
    {
        "id": "opt-002",
        "title": "Purchase 1-year Compute Savings Plan (additional $120K commitment)",
        "description": "Current Savings Plan coverage is 42%. Increasing commitment by $120K/year would cover 68% of eligible compute spend, saving an estimated $31K/month.",
        "category": "commitment",
        "service": "Amazon EC2",
        "estimated_monthly_savings": 31_200.00,
        "estimated_annual_savings": 374_400.00,
        "risk_level": "low",
        "effort": "low",
        "environment": None,
        "reversible": False,
        "requires_code_changes": False,
        "implementation_time": "1 day",
        "current_cost": 338_928.00,
        "optimized_cost": 307_728.00,
    },
    {
        "id": "opt-003",
        "title": "Implement S3 Intelligent-Tiering for cold data buckets",
        "description": "8 S3 buckets containing log archives and historical data (62TB) are stored in S3 Standard. Moving to Intelligent-Tiering would automatically optimize storage costs.",
        "category": "storage_optimization",
        "service": "Amazon S3",
        "estimated_monthly_savings": 12_480.00,
        "estimated_annual_savings": 149_760.00,
        "risk_level": "low",
        "effort": "low",
        "environment": None,
        "reversible": True,
        "requires_code_changes": False,
        "implementation_time": "2-3 days",
        "current_cost": 22_100.00,
        "optimized_cost": 9_620.00,
    },
    {
        "id": "opt-004",
        "title": "Delete 23 idle non-prod RDS instances",
        "description": "23 RDS instances in dev/test environments have had zero connections in the past 30 days. These appear to be leftover from completed projects.",
        "category": "idle_resource",
        "service": "Amazon RDS",
        "estimated_monthly_savings": 14_760.00,
        "estimated_annual_savings": 177_120.00,
        "risk_level": "low",
        "effort": "low",
        "environment": "development",
        "reversible": False,
        "requires_code_changes": False,
        "implementation_time": "1 day",
        "current_cost": 14_760.00,
        "optimized_cost": 0.00,
    },
    {
        "id": "opt-005",
        "title": "Schedule non-prod EKS clusters to stop outside business hours",
        "description": "Dev and staging EKS clusters run 24/7 but are only used during business hours (8am-8pm CT). Implementing cluster scheduling would reduce compute by ~50%.",
        "category": "scheduling",
        "service": "Amazon EKS",
        "estimated_monthly_savings": 16_950.00,
        "estimated_annual_savings": 203_400.00,
        "risk_level": "low",
        "effort": "medium",
        "environment": "development",
        "reversible": True,
        "requires_code_changes": False,
        "implementation_time": "3-5 days",
        "current_cost": 33_900.00,
        "optimized_cost": 16_950.00,
    },
    {
        "id": "opt-006",
        "title": "Optimize Lambda memory allocation across 120+ functions",
        "description": "Power Tuning analysis shows 120+ Lambda functions are over-provisioned on memory by 40-60%. Right-sizing memory reduces both duration charges and memory charges.",
        "category": "right_sizing",
        "service": "AWS Lambda",
        "estimated_monthly_savings": 8_460.00,
        "estimated_annual_savings": 101_520.00,
        "risk_level": "low",
        "effort": "medium",
        "environment": None,
        "reversible": True,
        "requires_code_changes": False,
        "implementation_time": "1-2 weeks",
        "current_cost": 42_366.00,
        "optimized_cost": 33_906.00,
    },
    {
        "id": "opt-007",
        "title": "Consolidate 3 under-utilized ElastiCache clusters",
        "description": "3 ElastiCache clusters in staging are running at <10% utilization. Consolidating to 1 cluster would reduce node count from 9 to 3.",
        "category": "right_sizing",
        "service": "Amazon ElastiCache",
        "estimated_monthly_savings": 4_230.00,
        "estimated_annual_savings": 50_760.00,
        "risk_level": "medium",
        "effort": "medium",
        "environment": "staging",
        "reversible": True,
        "requires_code_changes": True,
        "implementation_time": "1-2 weeks",
        "current_cost": 6_345.00,
        "optimized_cost": 2_115.00,
    },
    {
        "id": "opt-008",
        "title": "Enable CloudFront caching improvements for static assets",
        "description": "CloudFront cache-hit ratio is 61%. Improving cache behaviors and TTLs for static assets could increase cache-hit ratio to 85%, reducing origin requests and costs.",
        "category": "architecture",
        "service": "Amazon CloudFront",
        "estimated_monthly_savings": 5_080.00,
        "estimated_annual_savings": 60_960.00,
        "risk_level": "low",
        "effort": "medium",
        "environment": "production",
        "reversible": True,
        "requires_code_changes": True,
        "implementation_time": "3-5 days",
        "current_cost": 33_893.00,
        "optimized_cost": 28_813.00,
    },
]


# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
#  Mock Implementations
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━


class MockCostDataProvider(CostDataProvider):
    async def get_current_monthly_spend(self) -> Dict[str, Any]:
        return {
            "total_monthly_cost": MONTHLY_SPEND,
            "month": "2026-03",
            "currency": "USD",
            "month_to_date": MONTHLY_SPEND * 0.42,
            "projected_full_month": MONTHLY_SPEND,
        }

    async def get_cost_by_service(self, months: int = 3) -> List[Dict[str, Any]]:
        return SERVICE_BREAKDOWN

    async def get_cost_by_environment(self) -> List[Dict[str, Any]]:
        return ENVIRONMENT_BREAKDOWN

    async def get_cost_trends(self, months: int = 6) -> List[Dict[str, Any]]:
        return MONTHLY_TRENDS[-months:]


class MockForecastProvider(ForecastProvider):
    async def get_forecast(self, months_ahead: int = 3) -> List[Dict[str, Any]]:
        base = MONTHLY_SPEND
        growth_rate = 0.018  # ~1.8% monthly growth
        forecasts = []
        month_names = ["2026-04", "2026-05", "2026-06", "2026-07", "2026-08", "2026-09"]
        for i in range(min(months_ahead, len(month_names))):
            predicted = base * (1 + growth_rate) ** (i + 1)
            forecasts.append({
                "period": month_names[i],
                "predicted_cost": round(predicted, 2),
                "lower_bound": round(predicted * 0.92, 2),
                "upper_bound": round(predicted * 1.08, 2),
                "confidence": 0.80,
            })
        return forecasts

    async def get_forecast_with_savings(
        self, savings_actions: List[Dict[str, Any]], months_ahead: int = 3
    ) -> List[Dict[str, Any]]:
        total_monthly_savings = sum(a.get("estimated_monthly_savings", 0) for a in savings_actions)
        baseline = await self.get_forecast(months_ahead)
        adjusted = []
        for point in baseline:
            adjusted.append({
                **point,
                "predicted_cost": round(point["predicted_cost"] - total_monthly_savings, 2),
                "lower_bound": round(point["lower_bound"] - total_monthly_savings, 2),
                "upper_bound": round(point["upper_bound"] - total_monthly_savings, 2),
            })
        return adjusted


class MockOptimizationProvider(OptimizationProvider):
    async def get_opportunities(
        self,
        environment_filter: Optional[str] = None,
        category_filter: Optional[str] = None,
    ) -> List[Dict[str, Any]]:
        results = OPTIMIZATION_OPPORTUNITIES
        if environment_filter:
            results = [o for o in results if o.get("environment") == environment_filter or o.get("environment") is None]
        if category_filter:
            results = [o for o in results if o.get("category") == category_filter]
        return results

    async def get_idle_resources(self) -> List[Dict[str, Any]]:
        return [o for o in OPTIMIZATION_OPPORTUNITIES if o["category"] == "idle_resource"]

    async def get_rightsizing_recommendations(self) -> List[Dict[str, Any]]:
        return [o for o in OPTIMIZATION_OPPORTUNITIES if o["category"] == "right_sizing"]


class MockAnomalyProvider(AnomalyProvider):
    async def get_recent_anomalies(self, days: int = 30) -> List[Dict[str, Any]]:
        return [
            {
                "id": "anom-001",
                "date": "2026-03-05",
                "service": "Amazon EC2",
                "expected_cost": 11_200.00,
                "actual_cost": 14_890.00,
                "impact": 3_690.00,
                "root_cause": "Auto-scaling event triggered by traffic surge during flash sale",
                "status": "resolved",
            },
            {
                "id": "anom-002",
                "date": "2026-03-10",
                "service": "AWS Data Transfer",
                "expected_cost": 420.00,
                "actual_cost": 1_850.00,
                "impact": 1_430.00,
                "root_cause": "Cross-region replication misconfiguration in staging environment",
                "status": "investigating",
            },
        ]


class MockCommitmentAdvisor(CommitmentAdvisor):
    async def get_ri_coverage(self) -> Dict[str, Any]:
        return {
            "coverage_percentage": 38.0,
            "covered_cost": 128_800.00,
            "on_demand_cost": 210_128.00,
            "potential_savings_with_max_coverage": 58_200.00,
        }

    async def get_sp_coverage(self) -> Dict[str, Any]:
        return {
            "coverage_percentage": 42.0,
            "covered_cost": 142_300.00,
            "uncovered_cost": 196_628.00,
            "current_commitment": 142_300.00,
        }

    async def get_commitment_recommendations(self) -> List[Dict[str, Any]]:
        return [
            {
                "type": "Compute Savings Plan",
                "term": "1 year",
                "payment": "No Upfront",
                "monthly_commitment": 120_000.00,
                "estimated_monthly_savings": 31_200.00,
                "coverage_increase": "42% → 68%",
            },
            {
                "type": "EC2 Reserved Instances",
                "term": "1 year",
                "payment": "Partial Upfront",
                "monthly_commitment": 45_000.00,
                "estimated_monthly_savings": 14_400.00,
                "coverage_increase": "38% → 52%",
            },
        ]


class MockPricingEstimator(PricingEstimator):
    async def estimate_workload_cost(
        self, workload_spec: Dict[str, Any]
    ) -> Dict[str, Any]:
        return {
            "estimated_monthly_cost": 28_500.00,
            "services": [
                {"service": "Amazon EC2", "monthly_cost": 12_000.00},
                {"service": "Amazon RDS", "monthly_cost": 8_500.00},
                {"service": "Amazon S3", "monthly_cost": 3_200.00},
                {"service": "AWS Lambda", "monthly_cost": 2_800.00},
                {"service": "Amazon CloudFront", "monthly_cost": 2_000.00},
            ],
            "assumptions": [
                "Production environment with multi-AZ deployment",
                "Estimated traffic: 50K requests/hour peak",
                "Data storage: ~5TB initial, growing 500GB/month",
            ],
        }
