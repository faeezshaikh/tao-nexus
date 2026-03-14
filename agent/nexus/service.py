"""
TAO Nexus — Orchestration service.

Implements the core analysis pipeline:
 1. Parse query + audience + constraints
 2. Gather facts from provider interfaces
 3. Build intermediate analysis model
 4. Generate LLM synthesis (or mock)
 5. Assemble structured response with charts, tables, action cards
"""
import logging
import time
import re
from typing import Any, Dict, List, Optional

from .schemas import (
    ActionCategory,
    ActionRecommendation,
    AssumptionItem,
    Audience,
    ChartDataset,
    ChartSpec,
    ChartType,
    ConfidenceLevel,
    ConfidenceScore,
    CostDriver,
    Environment,
    EvidenceItem,
    ForecastPoint,
    ModuleFocus,
    NarrativeSection,
    NexusAnalyzeRequest,
    NexusAnalyzeResponse,
    OptimizationOpportunity,
    RiskLevel,
    ScenarioResult,
    TableColumn,
    TableSpec,
)
from .providers.mock import (
    MockAnomalyProvider,
    MockCommitmentAdvisor,
    MockCostDataProvider,
    MockForecastProvider,
    MockOptimizationProvider,
)
from .llm import NexusLLM

logger = logging.getLogger(__name__)

# Color palette for charts
CHART_COLORS = [
    "#6366f1", "#8b5cf6", "#a78bfa", "#c4b5fd",
    "#3b82f6", "#60a5fa", "#10b981", "#34d399",
    "#f59e0b", "#fbbf24", "#ef4444", "#f87171",
]


class NexusService:
    """Orchestrates the end-to-end Nexus analysis pipeline."""

    def __init__(self, *, use_mock: bool = True):
        self.use_mock = use_mock

        # Initialize providers (mock for now)
        self.cost_provider = MockCostDataProvider()
        self.forecast_provider = MockForecastProvider()
        self.optimization_provider = MockOptimizationProvider()
        self.anomaly_provider = MockAnomalyProvider()
        self.commitment_advisor = MockCommitmentAdvisor()
        self.llm = NexusLLM(use_mock=use_mock)

        # In-memory session store
        self._sessions: Dict[str, List[Dict[str, str]]] = {}

    async def analyze(self, request: NexusAnalyzeRequest) -> NexusAnalyzeResponse:
        """Run the full Nexus analysis pipeline."""
        start = time.monotonic()

        # 1. Session management
        session_id = request.session_id or ""
        if session_id and session_id in self._sessions:
            conversation = self._sessions[session_id]
        else:
            session_id = ""  # will be auto-generated in response
            conversation = []

        # 2. Parse target from query
        target_pct = self._extract_savings_target(request.query)

        # 3. Gather facts from providers
        cost_data = await self.cost_provider.get_current_monthly_spend()
        service_costs = await self.cost_provider.get_cost_by_service()
        env_costs = await self.cost_provider.get_cost_by_environment()
        trends = await self.cost_provider.get_cost_trends(months=6)
        forecast = await self.forecast_provider.get_forecast(months_ahead=3)
        opportunities = await self.optimization_provider.get_opportunities()
        anomalies = await self.anomaly_provider.get_recent_anomalies()
        commitment_data = await self.commitment_advisor.get_sp_coverage()

        baseline_cost = cost_data["total_monthly_cost"]

        # 4. Apply constraint filters
        constraints_text = [c.label for c in request.scenario_constraints if c.active]
        filtered_opps = self._apply_constraints(opportunities, request.scenario_constraints)

        # 5. Calculate totals
        total_monthly_savings = sum(o["estimated_monthly_savings"] for o in filtered_opps)
        total_annual_savings = sum(o["estimated_annual_savings"] for o in filtered_opps)
        savings_pct = (total_monthly_savings / baseline_cost * 100) if baseline_cost else 0

        # 6. Generate adjusted forecast
        adjusted_forecast = await self.forecast_provider.get_forecast_with_savings(
            filtered_opps, months_ahead=3
        )

        # 7. Generate LLM content
        exec_summary = await self.llm.generate_executive_summary(
            query=request.query,
            audience=request.audience.value,
            baseline_cost=baseline_cost,
            target_savings_pct=target_pct,
            total_identified_savings=total_monthly_savings,
            top_actions=[
                {"title": o["title"], "savings": o["estimated_monthly_savings"]}
                for o in sorted(filtered_opps, key=lambda x: x["estimated_monthly_savings"], reverse=True)[:5]
            ],
            constraints=constraints_text,
        )

        narrative_data = await self.llm.generate_narrative_sections(
            query=request.query,
            audience=request.audience.value,
            analysis_data={
                "baseline_cost": baseline_cost,
                "savings": total_monthly_savings,
                "savings_pct": savings_pct,
                "top_services": service_costs[:5],
            },
        )

        # 8. Build domain models
        key_drivers = self._build_key_drivers(service_costs, trends)
        forecast_points = self._build_forecast_points(forecast)
        action_cards = self._build_optimization_cards(filtered_opps)
        recommended_plan = self._build_recommended_plan(filtered_opps, request.audience)
        narrative_sections = self._build_narrative_sections(narrative_data, request.audience)

        # 9. Build visualizations
        charts = self._build_charts(
            service_costs, trends, forecast, adjusted_forecast, filtered_opps
        )
        tables = self._build_tables(filtered_opps, service_costs, env_costs)

        # 10. Build scenario result
        scenario = ScenarioResult(
            name="Recommended Optimization Plan",
            description=f"Low-risk savings plan targeting {savings_pct:.1f}% cost reduction",
            total_monthly_savings=round(total_monthly_savings, 2),
            total_annual_savings=round(total_annual_savings, 2),
            savings_percent=round(savings_pct, 1),
            actions_count=len(filtered_opps),
            risk_profile="conservative" if all(
                o.get("risk_level") == "low" for o in filtered_opps
            ) else "moderate",
            constraints_applied=constraints_text,
        )

        # 11. Build supporting info
        assumptions = [
            AssumptionItem(text="Cost data is based on the last 6 months of AWS billing", category="data"),
            AssumptionItem(text="Savings estimates assume immediate implementation", category="timing"),
            AssumptionItem(text="Utilization metrics are averaged over 30-day period", category="data"),
            AssumptionItem(text="Forecast assumes current growth trajectory continues", category="model"),
            AssumptionItem(text="Production environments are excluded from right-sizing actions", category="scope", impact="high"),
        ]

        risks = [
            "Savings Plan commitment requires 1-year term — non-refundable",
            "EKS scheduling may require updating CI/CD pipelines for off-hours deployments",
            "Lambda memory optimization requires staged rollout to validate performance",
        ]

        evidence = [
            EvidenceItem(source="AWS Cost Explorer", description="6-month cost trends by service", data_point=f"${baseline_cost:,.0f}/month"),
            EvidenceItem(source="AWS Compute Optimizer", description="EC2 right-sizing recommendations for 47 instances"),
            EvidenceItem(source="AWS Cost Optimization Hub", description="Idle resource detection (23 RDS instances)"),
            EvidenceItem(source="CloudWatch Metrics", description="Average CPU utilization <15% on target instances"),
        ]

        elapsed = (time.monotonic() - start) * 1000

        # 12. Update session
        response_kwargs = {
            "query": request.query,
            "audience": request.audience,
            "module": request.module_focus or ModuleFocus.PLANNER,
            "executive_summary": exec_summary,
            "narrative_sections": narrative_sections,
            "key_drivers": key_drivers,
            "forecast": forecast_points,
            "baseline_monthly_cost": round(baseline_cost, 2),
            "target_monthly_cost": round(baseline_cost - total_monthly_savings, 2),
            "scenario": scenario,
            "recommended_plan": recommended_plan,
            "action_cards": action_cards,
            "charts": charts,
            "tables": tables,
            "assumptions": assumptions,
            "risks": risks,
            "confidence": ConfidenceScore(
                level=ConfidenceLevel.MEDIUM,
                score=0.78,
                reasoning="Based on 6 months of historical billing data and AWS Compute Optimizer recommendations. Confidence is medium due to mock data — will increase with live AWS MCP integration.",
            ),
            "evidence": evidence,
            "processing_time_ms": round(elapsed, 1),
        }
        
        if session_id:
            response_kwargs["session_id"] = session_id
            
        response = NexusAnalyzeResponse(**response_kwargs)
        # Persist to session
        sid = response.session_id
        if sid not in self._sessions:
            self._sessions[sid] = []
        self._sessions[sid].append({"role": "user", "content": request.query})
        self._sessions[sid].append({"role": "assistant", "content": exec_summary[:500]})

        return response

    # ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
    #  Helpers
    # ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

    @staticmethod
    def _extract_savings_target(query: str) -> float:
        """Extract a percentage target from the user query (default 12%)."""
        match = re.search(r'(\d+(?:\.\d+)?)\s*%', query)
        return float(match.group(1)) if match else 12.0

    @staticmethod
    def _apply_constraints(
        opportunities: List[Dict[str, Any]],
        constraints,
    ) -> List[Dict[str, Any]]:
        """Filter opportunities based on user constraints."""
        result = list(opportunities)
        for c in constraints:
            if not c.active:
                continue
            label = c.label.lower()
            if "production" in label or "prod" in label:
                result = [o for o in result if o.get("environment") != "production"]
            if "reversible" in label:
                result = [o for o in result if o.get("reversible", True)]
            if "code change" in label or "no code" in label:
                result = [o for o in result if not o.get("requires_code_changes", False)]
            if "non-prod" in label or "non prod" in label:
                result = [o for o in result if o.get("environment") != "production"]
        return result

    @staticmethod
    def _build_key_drivers(
        service_costs: List[Dict], trends: List[Dict]
    ) -> List[CostDriver]:
        """Build key cost driver models."""
        drivers = []
        for svc in service_costs[:8]:
            prev_cost = svc["monthly_cost"] * 0.97  # approximate
            change = svc["monthly_cost"] - prev_cost
            drivers.append(CostDriver(
                name=svc["service"],
                current_cost=svc["monthly_cost"],
                previous_cost=round(prev_cost, 2),
                change_amount=round(change, 2),
                change_percent=round(change / prev_cost * 100, 1) if prev_cost else 0,
                category="service",
                trend=svc.get("trend", "stable"),
            ))
        return drivers

    @staticmethod
    def _build_forecast_points(forecast: List[Dict]) -> List[ForecastPoint]:
        return [
            ForecastPoint(
                period=f["period"],
                predicted_cost=f["predicted_cost"],
                lower_bound=f["lower_bound"],
                upper_bound=f["upper_bound"],
                confidence=f.get("confidence", 0.8),
            )
            for f in forecast
        ]

    @staticmethod
    def _build_optimization_cards(
        opportunities: List[Dict],
    ) -> List[OptimizationOpportunity]:
        return [
            OptimizationOpportunity(
                id=o.get("id", ""),
                title=o["title"],
                description=o["description"],
                category=ActionCategory(o["category"]),
                service=o["service"],
                estimated_monthly_savings=o["estimated_monthly_savings"],
                estimated_annual_savings=o["estimated_annual_savings"],
                risk_level=RiskLevel(o["risk_level"]),
                effort=o.get("effort", "low"),
                environment=Environment(o["environment"]) if o.get("environment") else None,
                reversible=o.get("reversible", True),
                requires_code_changes=o.get("requires_code_changes", False),
                implementation_time=o.get("implementation_time", "1-2 days"),
                current_cost=o.get("current_cost"),
                optimized_cost=o.get("optimized_cost"),
            )
            for o in opportunities
        ]

    @staticmethod
    def _build_recommended_plan(
        opportunities: List[Dict], audience: Audience
    ) -> List[ActionRecommendation]:
        """Build prioritized action recommendations."""
        sorted_opps = sorted(
            opportunities,
            key=lambda x: (
                0 if x.get("risk_level") == "low" else 1,
                -x.get("estimated_monthly_savings", 0),
            ),
        )

        owner_map = {
            "right_sizing": "Platform Engineering",
            "commitment": "IT Finance / FinOps",
            "storage_optimization": "Platform Engineering",
            "idle_resource": "Application Teams",
            "scheduling": "DevOps / SRE",
            "architecture": "Application Architecture",
        }

        plan = []
        for i, o in enumerate(sorted_opps):
            plan.append(ActionRecommendation(
                id=o.get("id", f"act-{i+1:03d}"),
                title=o["title"],
                description=o["description"],
                category=ActionCategory(o["category"]),
                priority=i + 1,
                risk_level=RiskLevel(o["risk_level"]),
                estimated_monthly_savings=o["estimated_monthly_savings"],
                estimated_annual_savings=o["estimated_annual_savings"],
                owner_suggestion=owner_map.get(o["category"], "Platform Engineering"),
                environment=Environment(o["environment"]) if o.get("environment") else None,
                reversible=o.get("reversible", True),
                requires_code_changes=o.get("requires_code_changes", False),
                implementation_time=o.get("implementation_time", "1-2 days"),
            ))
        return plan

    @staticmethod
    def _build_narrative_sections(
        sections_data: List[Dict], audience: Audience
    ) -> List[NarrativeSection]:
        return [
            NarrativeSection(
                title=s["title"],
                content=s["content"],
                icon=s.get("icon", "📊"),
                order=s.get("order", i),
            )
            for i, s in enumerate(sections_data)
        ]

    def _build_charts(
        self,
        service_costs: List[Dict],
        trends: List[Dict],
        forecast: List[Dict],
        adjusted_forecast: List[Dict],
        opportunities: List[Dict],
    ) -> List[ChartSpec]:
        """Build chart specifications for the response."""
        charts = []

        # Chart 1: Cost trend + forecast
        trend_labels = [t["month"] for t in trends]
        trend_values = [t["cost"] for t in trends]
        forecast_labels = [f["period"] for f in forecast]
        forecast_values = [f["predicted_cost"] for f in forecast]
        adjusted_values = [f["predicted_cost"] for f in adjusted_forecast]

        all_labels = trend_labels + forecast_labels
        historical_padded = trend_values + [None] * len(forecast_labels)
        forecast_padded = [None] * (len(trend_labels) - 1) + [trend_values[-1]] + forecast_values
        adjusted_padded = [None] * (len(trend_labels) - 1) + [trend_values[-1]] + adjusted_values

        charts.append(ChartSpec(
            type=ChartType.LINE,
            title="Cost Trend & Forecast",
            labels=all_labels,
            datasets=[
                ChartDataset(
                    label="Historical",
                    data=historical_padded,
                    border_color="#6366f1",
                    background_color="rgba(99, 102, 241, 0.1)",
                ),
                ChartDataset(
                    label="Forecast (Baseline)",
                    data=forecast_padded,
                    border_color="#f59e0b",
                    background_color="rgba(245, 158, 11, 0.1)",
                ),
                ChartDataset(
                    label="Forecast (With Savings)",
                    data=adjusted_padded,
                    border_color="#10b981",
                    background_color="rgba(16, 185, 129, 0.1)",
                ),
            ],
            x_axis_label="Month",
            y_axis_label="Monthly Cost (USD)",
        ))

        # Chart 2: Cost by service (top 8)
        top_services = service_costs[:8]
        charts.append(ChartSpec(
            type=ChartType.DOUGHNUT,
            title="Cost Breakdown by Service",
            labels=[s["service"] for s in top_services],
            datasets=[
                ChartDataset(
                    label="Monthly Cost",
                    data=[s["monthly_cost"] for s in top_services],
                    background_color=None,  # use default palette
                ),
            ],
        ))

        # Chart 3: Savings by category (bar)
        category_savings: Dict[str, float] = {}
        for o in opportunities:
            cat = o.get("category", "other")
            category_savings[cat] = category_savings.get(cat, 0) + o["estimated_monthly_savings"]

        cats = sorted(category_savings.items(), key=lambda x: -x[1])
        cat_labels_map = {
            "right_sizing": "Right-Sizing",
            "commitment": "Commitments (RI/SP)",
            "storage_optimization": "Storage",
            "idle_resource": "Idle Resources",
            "scheduling": "Scheduling",
            "architecture": "Architecture",
        }

        charts.append(ChartSpec(
            type=ChartType.BAR,
            title="Savings Opportunities by Category",
            labels=[cat_labels_map.get(c[0], c[0].replace("_", " ").title()) for c in cats],
            datasets=[
                ChartDataset(
                    label="Monthly Savings (USD)",
                    data=[round(c[1], 2) for c in cats],
                    background_color="#6366f1",
                    border_color="#4f46e5",
                ),
            ],
            y_axis_label="Monthly Savings (USD)",
        ))

        return charts

    @staticmethod
    def _build_tables(
        opportunities: List[Dict],
        service_costs: List[Dict],
        env_costs: List[Dict],
    ) -> List[TableSpec]:
        """Build table specifications."""
        tables = []

        # Table 1: Savings action plan
        opp_rows = []
        for o in sorted(opportunities, key=lambda x: -x["estimated_monthly_savings"]):
            opp_rows.append({
                "action": o["title"],
                "service": o["service"],
                "monthly_savings": o["estimated_monthly_savings"],
                "annual_savings": o["estimated_annual_savings"],
                "risk": o["risk_level"],
                "effort": o.get("effort", "low"),
                "reversible": "Yes" if o.get("reversible") else "No",
            })

        total_monthly = sum(r["monthly_savings"] for r in opp_rows)
        total_annual = sum(r["annual_savings"] for r in opp_rows)

        tables.append(TableSpec(
            title="Recommended Savings Actions",
            columns=[
                TableColumn(key="action", label="Action", type="string"),
                TableColumn(key="service", label="Service", type="string"),
                TableColumn(key="monthly_savings", label="Monthly Savings", type="currency"),
                TableColumn(key="annual_savings", label="Annual Savings", type="currency"),
                TableColumn(key="risk", label="Risk", type="string"),
                TableColumn(key="effort", label="Effort", type="string"),
                TableColumn(key="reversible", label="Reversible", type="string"),
            ],
            rows=opp_rows,
            summary_row={
                "action": f"TOTAL ({len(opp_rows)} actions)",
                "service": "",
                "monthly_savings": round(total_monthly, 2),
                "annual_savings": round(total_annual, 2),
                "risk": "",
                "effort": "",
                "reversible": "",
            },
        ))

        # Table 2: Cost by service
        svc_rows = [
            {
                "service": s["service"],
                "monthly_cost": s["monthly_cost"],
                "pct_of_total": s["pct"],
                "trend": s.get("trend", "stable"),
            }
            for s in service_costs
        ]
        tables.append(TableSpec(
            title="Current Cost by Service",
            columns=[
                TableColumn(key="service", label="Service", type="string"),
                TableColumn(key="monthly_cost", label="Monthly Cost", type="currency"),
                TableColumn(key="pct_of_total", label="% of Total", type="percent"),
                TableColumn(key="trend", label="Trend", type="string"),
            ],
            rows=svc_rows,
        ))

        return tables
