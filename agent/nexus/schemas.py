"""
TAO Nexus — Domain models and API contracts.

All Pydantic schemas for the Nexus analysis pipeline:
request/response shapes, domain entities, enums, and value objects.
"""
from __future__ import annotations

import uuid
from datetime import datetime
from enum import Enum
from typing import Any, Dict, List, Optional

from pydantic import BaseModel, Field


# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
#  Enums
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━


class Audience(str, Enum):
    LEADERSHIP = "leadership"
    FINANCE = "finance"
    ENGINEERING = "engineering"


class ModuleFocus(str, Enum):
    LENS = "lens"           # Conversational cost exploration
    PULSE = "pulse"         # Anomalies, forecast movement, root cause
    ARCHITECT = "architect" # Pre-spend estimation, architecture comparison
    PLANNER = "planner"     # Savings portfolio builder, scenario simulator
    AGENT = "agent"         # Action-plan generation, workflow readiness


class RiskLevel(str, Enum):
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    CRITICAL = "critical"


class ActionCategory(str, Enum):
    RIGHT_SIZING = "right_sizing"
    IDLE_RESOURCE = "idle_resource"
    COMMITMENT = "commitment"          # RI / SP
    ARCHITECTURE = "architecture"
    SCHEDULING = "scheduling"
    STORAGE_OPTIMIZATION = "storage_optimization"
    DATA_TRANSFER = "data_transfer"
    LICENSE = "license"
    OTHER = "other"


class ConfidenceLevel(str, Enum):
    HIGH = "high"
    MEDIUM = "medium"
    LOW = "low"


class ChartType(str, Enum):
    LINE = "line"
    BAR = "bar"
    PIE = "pie"
    AREA = "area"
    DOUGHNUT = "doughnut"
    STACKED_BAR = "stacked_bar"


class Environment(str, Enum):
    PRODUCTION = "production"
    STAGING = "staging"
    DEVELOPMENT = "development"
    TEST = "test"
    SANDBOX = "sandbox"
    SHARED = "shared"


# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
#  Value Objects
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━


class CostMetric(BaseModel):
    """A single cost measurement."""
    amount: float = Field(..., description="Cost amount in USD")
    currency: str = Field(default="USD")
    period: str = Field(default="monthly", description="e.g. monthly, quarterly, annual")


class ConfidenceScore(BaseModel):
    """Confidence assessment for a data point or recommendation."""
    level: ConfidenceLevel = Field(default=ConfidenceLevel.MEDIUM)
    score: float = Field(default=0.7, ge=0.0, le=1.0, description="0.0 to 1.0")
    reasoning: str = Field(default="Based on historical data patterns and current trends")


class ScenarioConstraint(BaseModel):
    """A user-specified constraint for scenario analysis."""
    id: str = Field(default_factory=lambda: str(uuid.uuid4())[:8])
    label: str = Field(..., description="Human-readable constraint label")
    type: str = Field(default="filter", description="filter, exclusion, preference")
    value: str = Field(default="", description="Constraint value")
    active: bool = Field(default=True)


# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
#  Domain Entities
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━


class CostDriver(BaseModel):
    """A key cost driver (service, resource type, etc.)."""
    name: str
    current_cost: float
    previous_cost: float
    change_amount: float
    change_percent: float
    category: str = Field(default="service")
    environment: Optional[Environment] = None
    trend: str = Field(default="stable", description="increasing, decreasing, stable, spike")


class ForecastPoint(BaseModel):
    """A single forecast data point."""
    period: str = Field(..., description="e.g. 2026-04, 2026-Q2")
    predicted_cost: float
    lower_bound: float
    upper_bound: float
    confidence: float = Field(default=0.8, ge=0.0, le=1.0)


class OptimizationOpportunity(BaseModel):
    """A specific cost optimization opportunity."""
    id: str = Field(default_factory=lambda: str(uuid.uuid4())[:8])
    title: str
    description: str
    category: ActionCategory
    service: str
    estimated_monthly_savings: float
    estimated_annual_savings: float
    risk_level: RiskLevel
    effort: str = Field(default="low", description="low, medium, high")
    environment: Optional[Environment] = None
    reversible: bool = Field(default=True)
    requires_code_changes: bool = Field(default=False)
    implementation_time: str = Field(default="1-2 days")
    current_cost: Optional[float] = None
    optimized_cost: Optional[float] = None


class ActionRecommendation(BaseModel):
    """A recommended action in the savings plan."""
    id: str = Field(default_factory=lambda: str(uuid.uuid4())[:8])
    title: str
    description: str
    category: ActionCategory
    priority: int = Field(default=1, ge=1, le=10, description="1 = highest priority")
    risk_level: RiskLevel
    estimated_monthly_savings: float
    estimated_annual_savings: float
    owner_suggestion: str = Field(default="Platform Engineering")
    environment: Optional[Environment] = None
    reversible: bool = Field(default=True)
    requires_code_changes: bool = Field(default=False)
    implementation_time: str = Field(default="1-2 days")
    dependencies: List[str] = Field(default_factory=list)
    status: str = Field(default="proposed", description="proposed, approved, in_progress, completed")


# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
#  Presentation Models
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━


class NarrativeSection(BaseModel):
    """A narrative section in the analysis response."""
    title: str
    content: str = Field(..., description="Markdown-formatted content")
    icon: str = Field(default="📊")
    order: int = Field(default=0)
    audience_relevance: List[Audience] = Field(
        default_factory=lambda: [Audience.LEADERSHIP, Audience.FINANCE, Audience.ENGINEERING]
    )


class ChartDataset(BaseModel):
    """Dataset for a chart."""
    label: str
    data: List[Optional[float]]
    background_color: Optional[str] = None
    border_color: Optional[str] = None
    stack: Optional[str] = None


class ChartSpec(BaseModel):
    """Specification for a chart visualization."""
    id: str = Field(default_factory=lambda: str(uuid.uuid4())[:8])
    type: ChartType
    title: str
    labels: List[str]
    datasets: List[ChartDataset]
    x_axis_label: str = Field(default="")
    y_axis_label: str = Field(default="Cost (USD)")
    show_legend: bool = Field(default=True)


class TableColumn(BaseModel):
    """Column definition for a table."""
    key: str
    label: str
    type: str = Field(default="string", description="string, number, currency, percent, date")
    sortable: bool = Field(default=True)


class TableSpec(BaseModel):
    """Specification for a data table."""
    id: str = Field(default_factory=lambda: str(uuid.uuid4())[:8])
    title: str
    columns: List[TableColumn]
    rows: List[Dict[str, Any]]
    summary_row: Optional[Dict[str, Any]] = None


class AssumptionItem(BaseModel):
    """An assumption underlying the analysis."""
    text: str
    category: str = Field(default="data", description="data, model, scope, timing")
    impact: str = Field(default="medium", description="low, medium, high")


class EvidenceItem(BaseModel):
    """A piece of evidence supporting the analysis."""
    source: str
    description: str
    data_point: Optional[str] = None
    timestamp: Optional[str] = None


class ScenarioResult(BaseModel):
    """Results of a scenario analysis."""
    name: str = Field(default="Recommended Plan")
    description: str = Field(default="")
    total_monthly_savings: float = Field(default=0.0)
    total_annual_savings: float = Field(default=0.0)
    savings_percent: float = Field(default=0.0)
    actions_count: int = Field(default=0)
    risk_profile: str = Field(default="conservative")
    constraints_applied: List[str] = Field(default_factory=list)


# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
#  API Request / Response
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━


class NexusAnalyzeRequest(BaseModel):
    """Request body for POST /api/v1/nexus/analyze."""
    session_id: Optional[str] = Field(default=None, description="Session ID for conversation continuity")
    query: str = Field(..., min_length=1, description="User's natural-language question")
    audience: Audience = Field(default=Audience.LEADERSHIP)
    scenario_constraints: List[ScenarioConstraint] = Field(default_factory=list)
    module_focus: Optional[ModuleFocus] = None
    conversation_history: List[Dict[str, str]] = Field(
        default_factory=list,
        description="Previous Q&A pairs for context: [{role, content}, ...]"
    )

    class Config:
        json_schema_extra = {
            "example": {
                "query": "We need to reduce AWS spend by 12% next quarter without affecting customer-facing production performance. Show me the safest plan.",
                "audience": "leadership",
                "scenario_constraints": [
                    {"label": "Protect production", "type": "exclusion", "value": "production"},
                    {"label": "Reversible actions only", "type": "preference", "value": "reversible"}
                ]
            }
        }


class NexusAnalyzeResponse(BaseModel):
    """Response body for POST /api/v1/nexus/analyze."""
    # --- Identifiers ---
    session_id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    query: str
    audience: Audience
    module: ModuleFocus = Field(default=ModuleFocus.PLANNER)
    timestamp: str = Field(default_factory=lambda: datetime.utcnow().isoformat() + "Z")

    # --- Executive Summary ---
    executive_summary: str = Field(default="", description="Markdown executive summary")

    # --- Narrative Sections ---
    narrative_sections: List[NarrativeSection] = Field(default_factory=list)

    # --- Key Cost Drivers ---
    key_drivers: List[CostDriver] = Field(default_factory=list)

    # --- Forecast ---
    forecast: List[ForecastPoint] = Field(default_factory=list)
    baseline_monthly_cost: float = Field(default=0.0)
    target_monthly_cost: float = Field(default=0.0)

    # --- Scenario ---
    scenario: Optional[ScenarioResult] = None

    # --- Recommended Plan ---
    recommended_plan: List[ActionRecommendation] = Field(default_factory=list)

    # --- Action Cards ---
    action_cards: List[OptimizationOpportunity] = Field(default_factory=list)

    # --- Visualizations ---
    charts: List[ChartSpec] = Field(default_factory=list)
    tables: List[TableSpec] = Field(default_factory=list)

    # --- Supporting Information ---
    assumptions: List[AssumptionItem] = Field(default_factory=list)
    risks: List[str] = Field(default_factory=list)
    confidence: ConfidenceScore = Field(default_factory=ConfidenceScore)
    evidence: List[EvidenceItem] = Field(default_factory=list)

    # --- Metadata ---
    processing_time_ms: Optional[float] = None
    data_freshness: str = Field(default="Mock data — connect AWS MCP for live data")
