// ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
//  TAO Nexus — Frontend TypeScript types
//  Mirrors backend Pydantic schemas exactly.
// ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

export type Audience = "leadership" | "finance" | "engineering";
export type ModuleFocus = "lens" | "pulse" | "architect" | "planner" | "agent";
export type RiskLevel = "low" | "medium" | "high" | "critical";
export type ActionCategory =
  | "right_sizing"
  | "idle_resource"
  | "commitment"
  | "architecture"
  | "scheduling"
  | "storage_optimization"
  | "data_transfer"
  | "license"
  | "other";
export type ConfidenceLevel = "high" | "medium" | "low";
export type ChartType = "line" | "bar" | "pie" | "area" | "doughnut" | "stacked_bar";

// ── Value Objects ────────────────────────────────────────────

export interface ScenarioConstraint {
  id: string;
  label: string;
  type: "filter" | "exclusion" | "preference";
  value: string;
  active: boolean;
}

export interface ConfidenceScore {
  level: ConfidenceLevel;
  score: number;
  reasoning: string;
}

// ── Domain Entities ──────────────────────────────────────────

export interface CostDriver {
  name: string;
  current_cost: number;
  previous_cost: number;
  change_amount: number;
  change_percent: number;
  category: string;
  environment?: string;
  trend: string;
}

export interface ForecastPoint {
  period: string;
  predicted_cost: number;
  lower_bound: number;
  upper_bound: number;
  confidence: number;
}

export interface OptimizationOpportunity {
  id: string;
  title: string;
  description: string;
  category: ActionCategory;
  service: string;
  estimated_monthly_savings: number;
  estimated_annual_savings: number;
  risk_level: RiskLevel;
  effort: string;
  environment?: string;
  reversible: boolean;
  requires_code_changes: boolean;
  implementation_time: string;
  current_cost?: number;
  optimized_cost?: number;
}

export interface ActionRecommendation {
  id: string;
  title: string;
  description: string;
  category: ActionCategory;
  priority: number;
  risk_level: RiskLevel;
  estimated_monthly_savings: number;
  estimated_annual_savings: number;
  owner_suggestion: string;
  environment?: string;
  reversible: boolean;
  requires_code_changes: boolean;
  implementation_time: string;
  dependencies: string[];
  status: string;
}

// ── Presentation Models ──────────────────────────────────────

export interface NarrativeSection {
  title: string;
  content: string;
  icon: string;
  order: number;
}

export interface ChartDataset {
  label: string;
  data: (number | null)[];
  background_color?: string;
  border_color?: string;
  stack?: string;
}

export interface ChartSpec {
  id: string;
  type: ChartType;
  title: string;
  labels: string[];
  datasets: ChartDataset[];
  x_axis_label?: string;
  y_axis_label?: string;
  show_legend?: boolean;
}

export interface TableColumn {
  key: string;
  label: string;
  type: "string" | "number" | "currency" | "percent" | "date";
  sortable?: boolean;
}

export interface TableSpec {
  id: string;
  title: string;
  columns: TableColumn[];
  rows: Record<string, unknown>[];
  summary_row?: Record<string, unknown>;
}

export interface AssumptionItem {
  text: string;
  category: string;
  impact: string;
}

export interface EvidenceItem {
  source: string;
  description: string;
  data_point?: string;
  timestamp?: string;
}

export interface ScenarioResult {
  name: string;
  description: string;
  total_monthly_savings: number;
  total_annual_savings: number;
  savings_percent: number;
  actions_count: number;
  risk_profile: string;
  constraints_applied: string[];
}

// ── API Contract ─────────────────────────────────────────────

export interface NexusAnalyzeRequest {
  session_id?: string;
  query: string;
  audience: Audience;
  scenario_constraints: ScenarioConstraint[];
  module_focus?: ModuleFocus;
  conversation_history?: { role: string; content: string }[];
}

export interface NexusAnalyzeResponse {
  session_id: string;
  query: string;
  audience: Audience;
  module: ModuleFocus;
  timestamp: string;

  executive_summary: string;
  narrative_sections: NarrativeSection[];
  key_drivers: CostDriver[];
  forecast: ForecastPoint[];
  baseline_monthly_cost: number;
  target_monthly_cost: number;

  scenario?: ScenarioResult;
  recommended_plan: ActionRecommendation[];
  action_cards: OptimizationOpportunity[];

  charts: ChartSpec[];
  tables: TableSpec[];

  assumptions: AssumptionItem[];
  risks: string[];
  confidence: ConfidenceScore;
  evidence: EvidenceItem[];

  processing_time_ms?: number;
  data_freshness: string;
}

// ── Pre-built constraint presets ─────────────────────────────

export const CONSTRAINT_PRESETS: ScenarioConstraint[] = [
  { id: "c1", label: "Protect production", type: "exclusion", value: "production", active: false },
  { id: "c2", label: "Reversible actions only", type: "preference", value: "reversible", active: false },
  { id: "c3", label: "No code changes required", type: "preference", value: "no_code_changes", active: false },
  { id: "c4", label: "Non-prod environments only", type: "filter", value: "non_prod", active: false },
  { id: "c5", label: "Quick wins (< 1 week)", type: "preference", value: "quick_wins", active: false },
];

export const DEMO_QUERIES = [
  "We need to reduce AWS spend by 12% next quarter without affecting customer-facing production performance. Show me the safest plan.",
  "What are the top 5 cost optimization opportunities across all environments?",
  "Show me idle resources we're paying for but not using.",
  "What if we only optimize non-production environments?",
  "Estimate the cost of launching a new analytics platform across dev, test, and prod.",
  "What Savings Plans should we purchase to reduce our on-demand spend?",
];
