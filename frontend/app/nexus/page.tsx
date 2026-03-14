"use client";

import "./nexus.css";
import { useState, useCallback } from "react";
import Link from "next/link";
import ReactMarkdown from "react-markdown";
import {
  Chart as ChartJS,
  CategoryScale,
  LinearScale,
  PointElement,
  LineElement,
  BarElement,
  ArcElement,
  Tooltip,
  Legend,
  Filler,
} from "chart.js";
import { Line, Bar, Doughnut } from "react-chartjs-2";
import { analyzeQuery } from "../../lib/nexus-api";
import type {
  Audience,
  NexusAnalyzeResponse,
  ScenarioConstraint,
  ChartSpec,
  TableSpec,
  ActionRecommendation,
  OptimizationOpportunity,
  NarrativeSection as NarrativeSectionT,
  AssumptionItem,
  EvidenceItem,
} from "../../types/nexus";
import { CONSTRAINT_PRESETS, DEMO_QUERIES } from "../../types/nexus";

ChartJS.register(
  CategoryScale,
  LinearScale,
  PointElement,
  LineElement,
  BarElement,
  ArcElement,
  Tooltip,
  Legend,
  Filler
);

// ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
//  Color palette
// ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

const CHART_COLORS = [
  "#6366f1", "#8b5cf6", "#3b82f6", "#06b6d4",
  "#10b981", "#f59e0b", "#ef4444", "#ec4899",
  "#a78bfa", "#34d399", "#fbbf24", "#f87171",
];

const RISK_COLORS: Record<string, string> = {
  low: "#10b981",
  medium: "#f59e0b",
  high: "#ef4444",
  critical: "#dc2626",
};

const AUDIENCE_CONFIG: Record<Audience, { label: string; icon: string; color: string }> = {
  leadership: { label: "Leadership", icon: "👔", color: "#6366f1" },
  finance: { label: "Finance", icon: "💰", color: "#10b981" },
  engineering: { label: "Engineering", icon: "⚙️", color: "#3b82f6" },
};

const MODULE_ITEMS = [
  { key: "lens", label: "Lens", icon: "🔍", desc: "Cost Exploration" },
  { key: "pulse", label: "Pulse", icon: "💓", desc: "Anomalies & Trends" },
  { key: "architect", label: "Architect", icon: "🏗️", desc: "Cost Estimation" },
  { key: "planner", label: "Planner", icon: "📋", desc: "Savings Portfolio" },
  { key: "agent", label: "Agent", icon: "🤖", desc: "Action Plans" },
];

// ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
//  Helper functions
// ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

function formatCurrency(value: number): string {
  if (value >= 1_000_000) return `$${(value / 1_000_000).toFixed(1)}M`;
  if (value >= 1_000) return `$${(value / 1_000).toFixed(1)}K`;
  return `$${value.toFixed(0)}`;
}

function formatCurrencyFull(value: number): string {
  return new Intl.NumberFormat("en-US", { style: "currency", currency: "USD" }).format(value);
}

// ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
//  Main Page Component
// ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

export default function NexusPage() {
  const [query, setQuery] = useState("");
  const [audience, setAudience] = useState<Audience>("leadership");
  const [constraints, setConstraints] = useState<ScenarioConstraint[]>(
    CONSTRAINT_PRESETS.map((c) => ({ ...c }))
  );
  const [loading, setLoading] = useState(false);
  const [result, setResult] = useState<NexusAnalyzeResponse | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [sessionId, setSessionId] = useState<string | null>(null);
  const [sidebarOpen, setSidebarOpen] = useState(true);
  const [activeModule, setActiveModule] = useState("planner");
  const [expandedSections, setExpandedSections] = useState<Set<number>>(new Set([0, 1, 2]));

  const toggleConstraint = useCallback((id: string) => {
    setConstraints((prev) =>
      prev.map((c) => (c.id === id ? { ...c, active: !c.active } : c))
    );
  }, []);

  const toggleSection = useCallback((idx: number) => {
    setExpandedSections((prev) => {
      const next = new Set(prev);
      if (next.has(idx)) next.delete(idx);
      else next.add(idx);
      return next;
    });
  }, []);

  const handleSubmit = useCallback(async () => {
    if (!query.trim()) return;
    setLoading(true);
    setError(null);
    setResult(null);

    try {
      const resp = await analyzeQuery({
        query: query.trim(),
        audience,
        scenario_constraints: constraints.filter((c) => c.active),
        session_id: sessionId || undefined,
      });
      setResult(resp);
      setSessionId(resp.session_id);
    } catch (err: unknown) {
      setError(err instanceof Error ? err.message : "Something went wrong");
    } finally {
      setLoading(false);
    }
  }, [query, audience, constraints, sessionId]);

  const selectDemoQuery = (q: string) => {
    setQuery(q);
  };

  return (
    <div className="nexus-shell">
      {/* ─── Sidebar ─── */}
      <aside className={`nexus-sidebar ${sidebarOpen ? "open" : "collapsed"}`}>
        <div className="sidebar-header">
          <div className="sidebar-brand" onClick={() => setSidebarOpen(!sidebarOpen)}>
            <span className="brand-icon">◆</span>
            {sidebarOpen && <span className="brand-text">TAO NEXUS</span>}
          </div>
        </div>

        {sidebarOpen && (
          <>
            <nav className="sidebar-nav">
              {MODULE_ITEMS.map((m) => (
                <button
                  key={m.key}
                  className={`nav-item ${activeModule === m.key ? "active" : ""}`}
                  onClick={() => setActiveModule(m.key)}
                >
                  <span className="nav-icon">{m.icon}</span>
                  <div className="nav-text">
                    <span className="nav-label">{m.label}</span>
                    <span className="nav-desc">{m.desc}</span>
                  </div>
                </button>
              ))}
            </nav>

            <div className="sidebar-footer">
              <Link href="/" className="back-to-lens">
                ← Back to TAO Lens
              </Link>
            </div>
          </>
        )}
      </aside>

      {/* ─── Main Content ─── */}
      <main className="nexus-main">
        {/* Top Bar */}
        <header className="nexus-topbar">
          <div className="topbar-left">
            <button className="sidebar-toggle" onClick={() => setSidebarOpen(!sidebarOpen)}>
              ☰
            </button>
            <h1 className="topbar-title">
              <span className="title-tao">TAO</span>
              <span className="title-nexus">NEXUS</span>
            </h1>
            <span className="topbar-subtitle">AI Cloud Economics Operating System</span>
          </div>
          <div className="topbar-right">
            {/* Audience Switcher */}
            <div className="audience-switcher">
              {(Object.keys(AUDIENCE_CONFIG) as Audience[]).map((a) => (
                <button
                  key={a}
                  className={`audience-btn ${audience === a ? "active" : ""}`}
                  onClick={() => setAudience(a)}
                  style={audience === a ? { borderColor: AUDIENCE_CONFIG[a].color } : {}}
                >
                  <span>{AUDIENCE_CONFIG[a].icon}</span>
                  <span>{AUDIENCE_CONFIG[a].label}</span>
                </button>
              ))}
            </div>
          </div>
        </header>

        {/* Prompt Composer */}
        <section className="prompt-section">
          <div className="prompt-composer">
            <textarea
              className="prompt-input"
              placeholder="Ask a strategic question about your cloud costs..."
              value={query}
              onChange={(e) => setQuery(e.target.value)}
              onKeyDown={(e) => {
                if (e.key === "Enter" && (e.metaKey || e.ctrlKey)) handleSubmit();
              }}
              rows={2}
            />
            <button
              className="prompt-submit"
              onClick={handleSubmit}
              disabled={loading || !query.trim()}
            >
              {loading ? (
                <span className="loading-dots">Analyzing<span className="dot">.</span><span className="dot">.</span><span className="dot">.</span></span>
              ) : (
                "Analyze →"
              )}
            </button>
          </div>

          {/* Scenario Constraints */}
          <div className="constraints-bar">
            <span className="constraints-label">Constraints:</span>
            {constraints.map((c) => (
              <button
                key={c.id}
                className={`constraint-chip ${c.active ? "active" : ""}`}
                onClick={() => toggleConstraint(c.id)}
              >
                {c.active ? "✓ " : ""}{c.label}
              </button>
            ))}
          </div>

          {/* Demo queries */}
          {!result && !loading && (
            <div className="demo-queries">
              <span className="demo-label">Try:</span>
              <div className="demo-list">
                {DEMO_QUERIES.slice(0, 3).map((q, i) => (
                  <button key={i} className="demo-btn" onClick={() => selectDemoQuery(q)}>
                    &quot;{q.length > 80 ? q.slice(0, 80) + "…" : q}&quot;
                  </button>
                ))}
              </div>
            </div>
          )}
        </section>

        {/* Error State */}
        {error && (
          <div className="nexus-error">
            <span>⚠️ {error}</span>
          </div>
        )}

        {/* Loading State */}
        {loading && <LoadingState />}

        {/* Results */}
        {result && (
          <div className="nexus-results">
            {/* KPI Strip */}
            <KPIStrip result={result} />

            {/* Executive Summary */}
            <section className="result-section summary-section">
              <div className="section-header">
                <h2>📋 Executive Summary</h2>
                <div className="confidence-badge" data-level={result.confidence.level}>
                  {result.confidence.level === "high" ? "🟢" : result.confidence.level === "medium" ? "🟡" : "🔴"}
                  {Math.round(result.confidence.score * 100)}% confidence
                </div>
              </div>
              <div className="summary-content prose-nexus">
                <ReactMarkdown>{result.executive_summary}</ReactMarkdown>
              </div>
            </section>

            {/* Two-column layout: Narrative + Actions */}
            <div className="results-grid">
              {/* Left: Narrative & Charts */}
              <div className="results-left">
                {/* Narrative Sections */}
                {result.narrative_sections.map((section, idx) => (
                  <section key={idx} className="result-section narrative-card">
                    <button className="section-header clickable" onClick={() => toggleSection(idx)}>
                      <h3>{section.icon} {section.title}</h3>
                      <span className="chevron">{expandedSections.has(idx) ? "▾" : "▸"}</span>
                    </button>
                    {expandedSections.has(idx) && (
                      <div className="narrative-content prose-nexus">
                        <ReactMarkdown>{section.content}</ReactMarkdown>
                      </div>
                    )}
                  </section>
                ))}

                {/* Charts */}
                {result.charts.map((chart, idx) => (
                  <section key={chart.id || idx} className="result-section chart-card">
                    <h3>📊 {chart.title}</h3>
                    <div className="chart-container">
                      <NexusChart chart={chart} />
                    </div>
                  </section>
                ))}

                {/* Tables */}
                {result.tables.map((table, idx) => (
                  <section key={table.id || idx} className="result-section table-card">
                    <h3>📋 {table.title}</h3>
                    <NexusTable table={table} />
                  </section>
                ))}
              </div>

              {/* Right: Action Panel */}
              <div className="results-right">
                {/* Scenario Summary */}
                {result.scenario && (
                  <div className="scenario-card">
                    <h3>🎯 {result.scenario.name}</h3>
                    <div className="scenario-stats">
                      <div className="stat">
                        <span className="stat-value">{formatCurrency(result.scenario.total_monthly_savings)}</span>
                        <span className="stat-label">Monthly Savings</span>
                      </div>
                      <div className="stat">
                        <span className="stat-value">{result.scenario.savings_percent}%</span>
                        <span className="stat-label">Reduction</span>
                      </div>
                      <div className="stat">
                        <span className="stat-value">{result.scenario.actions_count}</span>
                        <span className="stat-label">Actions</span>
                      </div>
                    </div>
                    {result.scenario.constraints_applied.length > 0 && (
                      <div className="scenario-constraints">
                        {result.scenario.constraints_applied.map((c, i) => (
                          <span key={i} className="applied-constraint">✓ {c}</span>
                        ))}
                      </div>
                    )}
                  </div>
                )}

                {/* Recommended Actions */}
                <div className="actions-panel">
                  <h3>⚡ Recommended Actions</h3>
                  {result.recommended_plan.map((action) => (
                    <ActionCard key={action.id} action={action} />
                  ))}
                </div>

                {/* Assumptions & Evidence */}
                <AssumptionsPanel
                  assumptions={result.assumptions}
                  risks={result.risks}
                  evidence={result.evidence}
                />
              </div>
            </div>

            {/* Footer metadata */}
            <div className="results-footer">
              <span>⏱️ {result.processing_time_ms?.toFixed(0)}ms</span>
              <span>📡 {result.data_freshness}</span>
              <span>🔗 Session: {result.session_id.slice(0, 8)}...</span>
            </div>
          </div>
        )}

        {/* Empty state */}
        {!result && !loading && !error && (
          <div className="nexus-empty">
            <div className="empty-icon">◆</div>
            <h2>TAO Nexus</h2>
            <p>Ask one business question. Get the answer, the why, the forecast,<br />the options, the tradeoffs, and the recommended plan.</p>
          </div>
        )}
      </main>
    </div>
  );
}

// ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
//  Sub-Components
// ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

function KPIStrip({ result }: { result: NexusAnalyzeResponse }) {
  return (
    <div className="kpi-strip">
      <div className="kpi-card">
        <span className="kpi-label">Current Monthly Spend</span>
        <span className="kpi-value">{formatCurrency(result.baseline_monthly_cost)}</span>
      </div>
      <div className="kpi-card accent">
        <span className="kpi-label">Target Monthly Spend</span>
        <span className="kpi-value">{formatCurrency(result.target_monthly_cost)}</span>
      </div>
      <div className="kpi-card success">
        <span className="kpi-label">Identified Savings</span>
        <span className="kpi-value">
          {formatCurrency(result.baseline_monthly_cost - result.target_monthly_cost)}/mo
        </span>
      </div>
      <div className="kpi-card">
        <span className="kpi-label">Annual Impact</span>
        <span className="kpi-value">
          {formatCurrency((result.baseline_monthly_cost - result.target_monthly_cost) * 12)}/yr
        </span>
      </div>
    </div>
  );
}

function LoadingState() {
  return (
    <div className="nexus-loading">
      <div className="loading-spinner" />
      <div className="loading-text">
        <h3>Analyzing your cloud economics...</h3>
        <p>Gathering cost data, identifying opportunities, building your plan</p>
      </div>
    </div>
  );
}

function NexusChart({ chart }: { chart: ChartSpec }) {
  const datasets = chart.datasets.map((ds, idx) => ({
    label: ds.label,
    data: ds.data,
    backgroundColor: ds.background_color || CHART_COLORS[idx % CHART_COLORS.length] + "33",
    borderColor: ds.border_color || CHART_COLORS[idx % CHART_COLORS.length],
    borderWidth: 2,
    tension: 0.3,
    fill: chart.type === "area" || chart.type === "line",
    pointRadius: chart.type === "line" ? 4 : undefined,
    pointHoverRadius: chart.type === "line" ? 6 : undefined,
    spanGaps: true,
  }));

  const chartData = { labels: chart.labels, datasets };

  const commonOpts = {
    responsive: true,
    maintainAspectRatio: false,
    plugins: {
      legend: {
        position: "top" as const,
        labels: {
          font: { family: "'Inter', sans-serif", size: 12 },
          color: "#94a3b8",
          padding: 16,
        },
      },
      tooltip: {
        backgroundColor: "#1e293b",
        titleFont: { family: "'Inter', sans-serif", size: 13 },
        bodyFont: { family: "'Inter', sans-serif", size: 12 },
        padding: 12,
        borderColor: "#6366f1",
        borderWidth: 1,
        callbacks: {
          label: (ctx: { dataset: { label?: string }; parsed: { y: number } }) => {
            const val = ctx.parsed.y;
            if (val == null) return "";
            return `${ctx.dataset.label}: ${formatCurrencyFull(val)}`;
          },
        },
      },
    },
    scales: chart.type !== "doughnut" && chart.type !== "pie" ? {
      x: {
        title: { display: !!chart.x_axis_label, text: chart.x_axis_label || "", color: "#94a3b8" },
        grid: { color: "rgba(148, 163, 184, 0.1)" },
        ticks: { color: "#94a3b8" },
      },
      y: {
        title: { display: !!chart.y_axis_label, text: chart.y_axis_label || "", color: "#94a3b8" },
        grid: { color: "rgba(148, 163, 184, 0.1)" },
        ticks: {
          color: "#94a3b8",
          callback: (value: number | string) => formatCurrency(Number(value)),
        },
      },
    } : undefined,
  };

  if (chart.type === "doughnut" || chart.type === "pie") {
    const doughnutData = {
      labels: chart.labels,
      datasets: [{
        data: chart.datasets[0]?.data || [],
        backgroundColor: CHART_COLORS.slice(0, chart.labels.length),
        borderColor: "#0f172a",
        borderWidth: 2,
      }],
    };
    return (
      <div style={{ height: 320 }}>
        <Doughnut data={doughnutData} options={{
          responsive: true,
          maintainAspectRatio: false,
          plugins: {
            legend: { position: "right", labels: { color: "#94a3b8", padding: 12, font: { size: 11 } } },
            tooltip: {
              backgroundColor: "#1e293b",
              callbacks: {
                label: (ctx: { label?: string; parsed: number }) =>
                  `${ctx.label}: ${formatCurrencyFull(ctx.parsed)}`,
              },
            },
          },
        }} />
      </div>
    );
  }

  if (chart.type === "bar" || chart.type === "stacked_bar") {
    return (
      <div style={{ height: 320 }}>
        <Bar data={chartData} options={commonOpts as never} />
      </div>
    );
  }

  return (
    <div style={{ height: 320 }}>
      <Line data={chartData} options={commonOpts as never} />
    </div>
  );
}

function NexusTable({ table }: { table: TableSpec }) {
  const formatCell = (value: unknown, type: string): string => {
    if (value == null || value === "") return "—";
    if (type === "currency") return formatCurrencyFull(Number(value));
    if (type === "percent") return `${Number(value).toFixed(1)}%`;
    return String(value);
  };

  return (
    <div className="table-wrapper">
      <table className="nexus-table">
        <thead>
          <tr>
            {table.columns.map((col) => (
              <th key={col.key}>{col.label}</th>
            ))}
          </tr>
        </thead>
        <tbody>
          {table.rows.map((row, i) => (
            <tr key={i}>
              {table.columns.map((col) => (
                <td key={col.key} className={col.type === "currency" || col.type === "number" ? "num" : ""}>
                  {formatCell(row[col.key], col.type)}
                </td>
              ))}
            </tr>
          ))}
        </tbody>
        {table.summary_row && (
          <tfoot>
            <tr>
              {table.columns.map((col) => (
                <td key={col.key} className={col.type === "currency" ? "num" : ""}>
                  {formatCell(table.summary_row![col.key], col.type)}
                </td>
              ))}
            </tr>
          </tfoot>
        )}
      </table>
    </div>
  );
}

function ActionCard({ action }: { action: ActionRecommendation }) {
  const [expanded, setExpanded] = useState(false);
  return (
    <div className={`action-card risk-${action.risk_level}`} onClick={() => setExpanded(!expanded)}>
      <div className="action-header">
        <span className="action-priority">#{action.priority}</span>
        <div className="action-meta">
          <span className="risk-badge" style={{ backgroundColor: RISK_COLORS[action.risk_level] + "22", color: RISK_COLORS[action.risk_level] }}>
            {action.risk_level.toUpperCase()} RISK
          </span>
          {action.reversible && <span className="tag">↩ Reversible</span>}
          {!action.requires_code_changes && <span className="tag">🚫 No code changes</span>}
        </div>
      </div>
      <h4 className="action-title">{action.title}</h4>
      <div className="action-savings">
        <span className="savings-amount">{formatCurrency(action.estimated_monthly_savings)}/mo</span>
        <span className="savings-annual">{formatCurrency(action.estimated_annual_savings)}/yr</span>
      </div>
      {expanded && (
        <div className="action-details">
          <p>{action.description}</p>
          <div className="detail-row">
            <span>👤 Owner: <strong>{action.owner_suggestion}</strong></span>
            <span>⏱️ Timeline: <strong>{action.implementation_time}</strong></span>
          </div>
        </div>
      )}
    </div>
  );
}

function AssumptionsPanel({
  assumptions,
  risks,
  evidence,
}: {
  assumptions: AssumptionItem[];
  risks: string[];
  evidence: EvidenceItem[];
}) {
  const [tab, setTab] = useState<"assumptions" | "risks" | "evidence">("assumptions");
  return (
    <div className="assumptions-panel">
      <div className="panel-tabs">
        <button className={tab === "assumptions" ? "active" : ""} onClick={() => setTab("assumptions")}>
          Assumptions ({assumptions.length})
        </button>
        <button className={tab === "risks" ? "active" : ""} onClick={() => setTab("risks")}>
          Risks ({risks.length})
        </button>
        <button className={tab === "evidence" ? "active" : ""} onClick={() => setTab("evidence")}>
          Evidence ({evidence.length})
        </button>
      </div>
      <div className="panel-content">
        {tab === "assumptions" && assumptions.map((a, i) => (
          <div key={i} className="panel-item">
            <span className={`impact-dot ${a.impact}`} />
            <span>{a.text}</span>
          </div>
        ))}
        {tab === "risks" && risks.map((r, i) => (
          <div key={i} className="panel-item risk-item">
            <span>⚠️</span>
            <span>{r}</span>
          </div>
        ))}
        {tab === "evidence" && evidence.map((e, i) => (
          <div key={i} className="panel-item evidence-item">
            <strong>{e.source}</strong>
            <span>{e.description}</span>
            {e.data_point && <code>{e.data_point}</code>}
          </div>
        ))}
      </div>
    </div>
  );
}
