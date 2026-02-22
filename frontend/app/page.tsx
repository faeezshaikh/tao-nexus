"use client";

import { useState, useRef, useEffect, Suspense } from "react";
import { useSearchParams } from "next/navigation";
import { FinopsResponse, HistoryEntry } from "../types/finops";
import { useAuth } from "../contexts/AuthContext";
import { isAdmin } from "../lib/auth";
import { saveHistoryEntry } from "../lib/history";
import LoginPage from "../components/LoginPage";
import Link from "next/link";
import ReactMarkdown from "react-markdown";
import {
  Chart as ChartJS,
  CategoryScale,
  LinearScale,
  PointElement,
  LineElement,
  BarElement,
  Tooltip,
  Legend,
} from "chart.js";
import { Line, Bar } from "react-chartjs-2";

ChartJS.register(
  CategoryScale,
  LinearScale,
  PointElement,
  LineElement,
  BarElement,
  Tooltip,
  Legend
);

// Pre-canned prompts catalog
const PROMPT_CATALOG = [
  {
    category: "Cost Analysis",
    prompts: [
      "What were my total AWS costs last month?",
      "Show EC2 costs by region for the last full month",
      "Break down S3 costs for the last 6 months",
    ],
  },
  {
    category: "Forecasting",
    prompts: [
      "Forecast total AWS costs for next month",
      "What will my S3 costs be next month?",
      "Predict EC2 spending for the next quarter",
    ],
  },
  {
    category: "Resource Utilization",
    prompts: [
      "Show RDS costs grouped by instance type",
      "Show Lambda costs for last 7 days",
      "Compare data transfer costs across regions",
    ],
  },
  {
    category: "Trends & Insights",
    prompts: [
      "Show me cost trends over the last 6 months",
      "Show daily cost breakdown for the current month",
      "Compare costs between last month and the month before",
    ],
  },
  {
    category: "Anomaly Detection",
    prompts: [
      "Were there any cost anomalies in the last 30 days?",
      "What caused the unusual spending spike?",
      "Why did my AWS bill increase last month?",
    ],
  },
  {
    category: "Budget Monitoring",
    prompts: [
      "Am I on track with my AWS budgets?",
      "Show my budget status and alerts",
      "Which budgets are close to their limit?",
    ],
  },
  {
    category: "Free Tier",
    prompts: [
      "Am I about to exceed any free tier limits?",
      "Show free tier usage across all services",
      "Which services are closest to free tier caps?",
    ],
  },
  {
    category: "Savings Plans & RIs",
    prompts: [
      "What Savings Plans should I purchase?",
      "Show my Reserved Instance coverage",
      "What's my Savings Plans coverage percentage?",
    ],
  },
  {
    category: "Optimization",
    prompts: [
      "Which EC2 instances should I right-size?",
      "Get Lambda optimization recommendations",
      "Show idle resources I'm paying for",
    ],
  },
];

export default function Home() {
  return (
    <Suspense fallback={
      <div className="min-h-screen bg-[#FAFAFA] flex items-center justify-center">
        <div className="text-2xl font-bold">Loading...</div>
      </div>
    }>
      <HomeInner />
    </Suspense>
  );
}

function HomeInner() {
  const { user, logout, isLoading: authLoading } = useAuth();
  const [question, setQuestion] = useState("");
  const [data, setData] = useState<FinopsResponse | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [catalogOpen, setCatalogOpen] = useState(false);
  const [lastExecutedQuery, setLastExecutedQuery] = useState<string>("");
  const [thoughtMs, setThoughtMs] = useState<number | null>(null);
  const [progressStatus, setProgressStatus] = useState<{
    step: number;
    total: number;
    message: string;
    emoji: string;
  } | null>(null);
  const [completedSteps, setCompletedSteps] = useState<
    { step: number; message: string; emoji: string }[]
  >([]);
  const [elapsedSeconds, setElapsedSeconds] = useState(0);
  const timerRef = useRef<NodeJS.Timeout | null>(null);
  const searchParams = useSearchParams();

  // Pre-fill from URL param (used by History "Run Again")
  useEffect(() => {
    const q = searchParams.get("q");
    if (q) setQuestion(q);
  }, [searchParams]);

  // Show login page if not authenticated
  if (authLoading) {
    return (
      <div className="min-h-screen bg-[#FAFAFA] flex items-center justify-center">
        <div className="text-2xl font-bold">Loading...</div>
      </div>
    );
  }

  if (!user) {
    return <LoginPage />;
  }

  const formatDuration = (ms: number) => {
    const totalSeconds = Math.max(0, Math.round(ms / 1000));
    const minutes = Math.floor(totalSeconds / 60);
    const seconds = totalSeconds % 60;

    if (minutes > 0) {
      return `${minutes}m ${seconds.toString().padStart(2, "0")}s`;
    }
    return `${seconds}s`;
  };

  async function runQuery() {
    if (!question.trim()) return;

    // Safe username extraction
    const currentUsername = user?.username || "anonymous";

    const queryToExecute = question.trim();
    setLastExecutedQuery(queryToExecute);
    setLoading(true);
    setError(null);
    setData(null);
    setThoughtMs(null);
    setProgressStatus(null);
    setCompletedSteps([]);
    setElapsedSeconds(0);
    const startedAt = performance.now();

    // Start elapsed timer
    timerRef.current = setInterval(() => {
      setElapsedSeconds(Math.floor((performance.now() - startedAt) / 1000));
    }, 1000);

    const API_URL = process.env.NEXT_PUBLIC_API_URL || "http://10.103.30.81:8000";

    try {
      const res = await fetch(`${API_URL}/query/stream`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          question: queryToExecute,
          username: currentUsername,
        }),
      });

      if (!res.ok) {
        const body = await res.json().catch(() => null);
        throw new Error(body?.detail || `HTTP ${res.status}`);
      }

      const reader = res.body?.getReader();
      if (!reader) throw new Error("No response stream available");

      const decoder = new TextDecoder();
      let buffer = "";
      let currentEvent = "";

      while (true) {
        const { done, value } = await reader.read();
        if (done) break;

        buffer += decoder.decode(value, { stream: true });
        const lines = buffer.split("\n");
        buffer = lines.pop() || "";

        for (const line of lines) {
          if (line.startsWith("event: ")) {
            currentEvent = line.slice(7).trim();
          } else if (line.startsWith("data: ")) {
            const jsonStr = line.slice(6);
            try {
              const payload = JSON.parse(jsonStr);

              // Detect result: explicit "result" event OR payload that looks like a FinopsResponse
              const isResult =
                currentEvent === "result" ||
                (!currentEvent && payload && ("summary" in payload || "table" in payload || "chart" in payload));

              if (currentEvent === "progress") {
                setProgressStatus(payload);
                setCompletedSteps((prev) => {
                  if (prev.some((s) => s.step === payload.step)) return prev;
                  return [...prev, { step: payload.step, message: payload.message, emoji: payload.emoji }];
                });
              } else if (isResult) {
                const resultData = payload as FinopsResponse;
                setData(resultData);
                const elapsed = performance.now() - startedAt;
                setThoughtMs(elapsed);
                // Persist to history
                try {
                  saveHistoryEntry({
                    id: Math.random().toString(36).slice(2) + Date.now().toString(36),
                    query: queryToExecute,
                    username: currentUsername,
                    timestamp: new Date().toISOString(),
                    durationMs: Math.round(elapsed),
                    response: resultData,
                  });
                } catch (historyErr) {
                  console.error("[History] Failed to save entry:", historyErr);
                }
              }
              currentEvent = "";
            } catch {
              // ignore malformed JSON
            }
          }
        }
      }
    } catch (err: any) {
      setError(err.message || "Something went wrong");
      setThoughtMs(null);
    } finally {
      setLoading(false);
      setProgressStatus(null);
      setCompletedSteps([]);
      if (timerRef.current) clearInterval(timerRef.current);
    }
  }

  const selectPrompt = (prompt: string) => {
    setQuestion(prompt);
    setCatalogOpen(false);
  };

  const chartElement = (() => {
    if (!data?.chart || !data.chart.series || data.chart.series.length === 0) return null;

    const { x, series, type } = data.chart;

    const chartData = {
      labels: x,
      datasets: series.map((s, idx) => ({
        label: s.name,
        data: s.values,
        borderWidth: 3,
        backgroundColor: [
          "rgba(255, 229, 0, 0.3)",
          "rgba(255, 107, 157, 0.3)",
          "rgba(0, 212, 255, 0.3)",
          "rgba(0, 255, 148, 0.3)",
        ][idx % 4],
        borderColor: [
          "rgba(255, 229, 0, 1)",
          "rgba(255, 107, 157, 1)",
          "rgba(0, 212, 255, 1)",
          "rgba(0, 255, 148, 1)",
        ][idx % 4],
      })),
    };

    const commonOptions = {
      responsive: true,
      maintainAspectRatio: false,
      animation: {
        duration: 750, // Keep chart rendering animation (bars growing, etc.)
      },
      transitions: {
        active: {
          animation: {
            duration: 0, // Instant tooltip response when hovering
          },
        },
      },
      plugins: {
        legend: {
          position: "top" as const,
          labels: {
            font: { family: "'Space Grotesk', sans-serif", size: 12, weight: 600 },
            color: "#0A0A0A",
            padding: 12,
          }
        },
        tooltip: {
          enabled: true,
          mode: "index" as const,
          intersect: false,
          backgroundColor: "#0A0A0A",
          titleFont: { family: "'Space Grotesk', sans-serif", size: 13, weight: 600 },
          bodyFont: { family: "'Space Grotesk', sans-serif", size: 12 },
          padding: 12,
          borderColor: "#FFE500",
          borderWidth: 2,
        },
      },
      scales: {
        x: {
          title: {
            display: true,
            text: "Time / Dimension",
            font: { family: "'Space Grotesk', sans-serif", size: 13, weight: 600 },
            color: "#0A0A0A",
          },
          grid: { color: "rgba(10, 10, 10, 0.1)" },
          ticks: {
            font: { family: "'Space Grotesk', sans-serif", size: 11 },
            color: "#0A0A0A",
          },
        },
        y: {
          title: {
            display: true,
            text: "Cost (USD)",
            font: { family: "'Space Grotesk', sans-serif", size: 13, weight: 600 },
            color: "#0A0A0A",
          },
          grid: { color: "rgba(10, 10, 10, 0.1)" },
          ticks: {
            font: { family: "'Space Grotesk', sans-serif", size: 11 },
            color: "#0A0A0A",
          },
        },
      },
    };

    return type === "bar" ? (
      <Bar data={chartData} options={commonOptions} />
    ) : (
      <Line data={chartData} options={commonOptions} />
    );
  })();

  return (
    <main className="min-h-screen bg-[#FAFAFA] text-[#0A0A0A] p-4 md:p-8 relative overflow-hidden">
      {/* Decorative background elements */}
      <div className="fixed top-10 right-10 w-32 h-32 bg-[#FFE500] rounded-full opacity-20 blur-3xl pointer-events-none" />
      <div className="fixed bottom-20 left-10 w-40 h-40 bg-[#FF6B9D] rounded-full opacity-20 blur-3xl pointer-events-none" />
      <div className="fixed top-1/2 left-1/3 w-36 h-36 bg-[#00D4FF] rounded-full opacity-15 blur-3xl pointer-events-none" />

      <div className="max-w-6xl mx-auto relative z-10">
        {/* User Info & Logout */}
        <div className="flex justify-end mb-4 gap-3">
          <Link href="/history">
            <button className="bg-[#B794F6] border-4 border-[#0A0A0A] shadow-[6px_6px_0px_#0A0A0A] px-4 py-2 font-bold text-sm hover:shadow-[8px_8px_0px_#0A0A0A] hover:-translate-y-0.5 transition-all active:shadow-[4px_4px_0px_#0A0A0A] active:translate-y-0">
              🕘 HISTORY
            </button>
          </Link>
          {isAdmin(user) && (
            <Link href="/analytics">
              <button className="bg-[#00FF94] border-4 border-[#0A0A0A] shadow-[6px_6px_0px_#0A0A0A] px-4 py-2 font-bold text-sm hover:shadow-[8px_8px_0px_#0A0A0A] hover:-translate-y-0.5 transition-all active:shadow-[4px_4px_0px_#0A0A0A] active:translate-y-0">
                📊 ANALYTICS
              </button>
            </Link>
          )}
          <div className="bg-white border-4 border-[#0A0A0A] shadow-[6px_6px_0px_#0A0A0A] px-4 py-2 flex items-center gap-3">
            <span className="font-bold text-sm">👤 {user.displayName}</span>
            <button
              onClick={logout}
              className="bg-[#FF6B9D] border-2 border-[#0A0A0A] px-3 py-1 font-bold text-xs hover:shadow-[4px_4px_0px_#0A0A0A] hover:-translate-y-0.5 transition-all active:shadow-[2px_2px_0px_#0A0A0A] active:translate-y-0"
            >
              LOGOUT
            </button>
          </div>
        </div>

        {/* Header */}
        <div className="mb-8 text-center">
          <div className="flex items-center justify-center gap-4 mb-4">
            <img
              src="/lens-icon.png"
              alt="TAO Lens"
              className="w-16 h-16 md:w-20 md:h-20 border-4 border-[#0A0A0A] shadow-[4px_4px_0px_#0A0A0A] bg-white p-2 transform -rotate-6"
            />
            <h1 className="text-4xl md:text-6xl font-bold tracking-tight">
              <span className="inline-block bg-[#FFE500] px-4 py-2 border-4 border-[#0A0A0A] shadow-[6px_6px_0px_#0A0A0A] transform -rotate-1">
                TAO
              </span>
              <span className="inline-block ml-3 bg-[#00D4FF] px-4 py-2 border-4 border-[#0A0A0A] shadow-[6px_6px_0px_#0A0A0A] transform rotate-1">
                LENS
              </span>
            </h1>
          </div>
          <p className="text-lg md:text-xl font-medium mt-6 max-w-2xl mx-auto">
            Ask natural-language questions about your AWS costs
          </p>
          <p className="text-sm md:text-base text-[#0A0A0A]/70 mt-2">
            Powered by AWS MCP Server & AI-Driven Analytics
          </p>
        </div>

        {/* Main Card */}
        <div className="bg-white border-4 border-[#0A0A0A] shadow-[12px_12px_0px_#0A0A0A] p-6 md:p-8 mb-8 relative">
          {/* Prompt Catalog Toggle Button */}
          <button
            onClick={() => setCatalogOpen(!catalogOpen)}
            className="absolute -top-5 -right-5 bg-[#FF6B9D] border-4 border-[#0A0A0A] shadow-[6px_6px_0px_#0A0A0A] px-6 py-3 font-bold text-sm md:text-base hover:shadow-[8px_8px_0px_#0A0A0A] hover:-translate-y-0.5 hover:translate-x-0.5 transition-all duration-200 active:shadow-[4px_4px_0px_#0A0A0A] active:translate-y-0.5 active:-translate-x-0.5 z-20"
            aria-label="Toggle prompt catalog"
          >
            {catalogOpen ? "✕ CLOSE" : "✨ PROMPTS"}
          </button>

          {/* Sliding Prompt Catalog */}
          <div
            className={`fixed top-0 right-0 h-full w-full md:w-[480px] bg-white border-l-4 border-[#0A0A0A] shadow-[-12px_0px_0px_#0A0A0A] transition-transform duration-500 ease-in-out z-50 overflow-y-auto ${catalogOpen ? "translate-x-0" : "translate-x-full"
              }`}
          >
            <div className="p-6 md:p-8">
              <div className="flex items-center justify-between mb-6">
                <h2 className="text-2xl md:text-3xl font-bold">Prompt Catalog</h2>
                <button
                  onClick={() => setCatalogOpen(false)}
                  className="bg-[#0A0A0A] text-white border-3 border-[#0A0A0A] px-4 py-2 font-bold hover:bg-[#FFE500] hover:text-[#0A0A0A] transition-colors"
                  aria-label="Close catalog"
                >
                  ✕
                </button>
              </div>

              <div className="space-y-6">
                {PROMPT_CATALOG.map((category, catIdx) => (
                  <div key={catIdx} className="border-4 border-[#0A0A0A] bg-[#FAFAFA] p-4">
                    <h3 className="text-lg font-bold mb-3 bg-[#00FF94] inline-block px-3 py-1 border-2 border-[#0A0A0A]">
                      {category.category}
                    </h3>
                    <div className="space-y-2">
                      {category.prompts.map((prompt, pIdx) => (
                        <button
                          key={pIdx}
                          onClick={() => selectPrompt(prompt)}
                          className="w-full text-left bg-white border-3 border-[#0A0A0A] px-4 py-3 font-medium text-sm hover:bg-[#FFE500] hover:shadow-[4px_4px_0px_#0A0A0A] hover:-translate-y-0.5 transition-all duration-150 active:shadow-[2px_2px_0px_#0A0A0A] active:translate-y-0"
                        >
                          {prompt}
                        </button>
                      ))}
                    </div>
                  </div>
                ))}
              </div>
            </div>
          </div>

          {/* Overlay when catalog is open */}
          {catalogOpen && (
            <div
              className="fixed inset-0 bg-[#0A0A0A]/30 backdrop-blur-sm z-40"
              onClick={() => setCatalogOpen(false)}
            />
          )}

          {/* Input Section */}
          <div className="mb-6">
            <label className="block text-sm font-bold mb-3 uppercase tracking-wide">
              Your Question
            </label>
            <div className="flex flex-col md:flex-row gap-4">
              <textarea
                className="flex-1 border-4 border-[#0A0A0A] px-4 py-3 text-base font-medium focus:outline-none focus:shadow-[6px_6px_0px_#0A0A0A] focus:-translate-y-1 transition-all resize-none min-h-[100px] bg-[#FAFAFA]"
                placeholder="e.g. Show EC2 cost by region for the last full month"
                value={question}
                onChange={(e) => setQuestion(e.target.value)}
                onKeyDown={(e) => {
                  if (e.key === "Enter" && e.metaKey) {
                    runQuery();
                  }
                }}
              />
              <button
                onClick={runQuery}
                disabled={loading || !question.trim()}
                className="md:w-44 h-auto md:h-[100px] bg-[#00FF94] border-4 border-[#0A0A0A] shadow-[6px_6px_0px_#0A0A0A] px-6 py-4 font-bold text-lg hover:shadow-[8px_8px_0px_#0A0A0A] hover:-translate-y-1 hover:translate-x-1 transition-all duration-200 disabled:bg-[#E0E0E0] disabled:cursor-not-allowed disabled:shadow-[4px_4px_0px_#0A0A0A] active:shadow-[4px_4px_0px_#0A0A0A] active:translate-y-0.5 active:-translate-x-0.5"
              >
                {loading ? "⏳ ANALYZING..." : "🚀 RUN QUERY"}
              </button>
            </div>
            {!loading && !data && !error && (
              <p className="text-xs mt-3 text-[#0A0A0A]/60 font-medium">
                💡 Tip: Click the <span className="font-bold text-[#FF6B9D]">✨ PROMPTS</span> button to browse pre-made queries!
              </p>
            )}
          </div>

          {/* Error */}
          {error && (
            <div className="mb-6 bg-[#FF6B9D] border-4 border-[#0A0A0A] shadow-[6px_6px_0px_#0A0A0A] px-5 py-4">
              <p className="font-bold text-sm">⚠️ ERROR</p>
              <p className="text-sm mt-1">{error}</p>
            </div>
          )}

          {/* Live Progress Indicator */}
          {loading && progressStatus && (
            <div className="mb-6 bg-white border-4 border-[#0A0A0A] shadow-[8px_8px_0px_#0A0A0A] px-5 py-5 overflow-hidden">
              {/* Header Row */}
              <div className="flex items-center justify-between mb-4">
                <h2 className="font-bold text-sm uppercase tracking-wide bg-[#00D4FF] inline-block px-3 py-1 border-2 border-[#0A0A0A]">
                  ⚙️ Processing Pipeline
                </h2>
                <div className="flex items-center gap-3">
                  <span className="font-mono font-bold text-sm bg-[#FAFAFA] border-2 border-[#0A0A0A] px-3 py-1">
                    ⏱️ {elapsedSeconds}s
                  </span>
                  <span className="font-bold text-sm bg-[#FFE500] border-2 border-[#0A0A0A] px-3 py-1">
                    Step {progressStatus.step} / {progressStatus.total}
                  </span>
                </div>
              </div>

              {/* Progress Bar */}
              <div className="w-full h-6 bg-[#FAFAFA] border-3 border-[#0A0A0A] mb-4 overflow-hidden relative">
                <div
                  className="h-full transition-all duration-500 ease-out relative"
                  style={{
                    width: `${(progressStatus.step / progressStatus.total) * 100}%`,
                    background: "repeating-linear-gradient(45deg, #00FF94, #00FF94 10px, #00D4FF 10px, #00D4FF 20px)",
                    backgroundSize: "28.28px 28.28px",
                    animation: "barberpole 0.8s linear infinite",
                  }}
                />
              </div>

              {/* Current Step - Big & Bold */}
              <div className="bg-[#FFE500] border-3 border-[#0A0A0A] shadow-[4px_4px_0px_#0A0A0A] px-4 py-3 mb-4 flex items-center gap-3">
                <span
                  className="text-2xl"
                  style={{ animation: "bounce 1s ease-in-out infinite" }}
                >
                  {progressStatus.emoji}
                </span>
                <span className="font-bold text-base">{progressStatus.message}</span>
              </div>

              {/* Step Timeline */}
              <div className="space-y-1">
                {completedSteps.map((s, i) => {
                  const isCurrent = s.step === progressStatus.step;
                  const isDone = s.step < progressStatus.step;
                  return (
                    <div
                      key={s.step}
                      className={`flex items-center gap-2 px-3 py-1.5 text-sm font-medium transition-all duration-300 border-2 ${isCurrent
                        ? "border-[#0A0A0A] bg-[#00FF94] shadow-[3px_3px_0px_#0A0A0A] -translate-y-0.5"
                        : isDone
                          ? "border-[#0A0A0A]/30 bg-[#FAFAFA] text-[#0A0A0A]/50"
                          : "border-transparent bg-transparent text-[#0A0A0A]/30"
                        }`}
                      style={{
                        animationName: isCurrent ? "none" : undefined,
                        animationDuration: isCurrent ? "0s" : undefined,
                        animationDelay: isCurrent ? undefined : `${i * 100}ms`,
                      }}
                    >
                      <span className="text-base">
                        {isDone ? "✅" : isCurrent ? s.emoji : "⬜"}
                      </span>
                      <span>{s.message}</span>
                    </div>
                  );
                })}
              </div>
            </div>
          )}

          {/* Inline CSS for barber-pole animation */}
          <style jsx>{`
            @keyframes barberpole {
              0% { background-position: 0 0; }
              100% { background-position: 28.28px 0; }
            }
            @keyframes bounce {
              0%, 100% { transform: translateY(0); }
              50% { transform: translateY(-6px); }
            }
          `}</style>

          {/* Query Display - Shows what the results are for */}
          {lastExecutedQuery && data && (
            <div className="mb-6 bg-[#00FF94] border-4 border-[#0A0A0A] shadow-[6px_6px_0px_#0A0A0A] px-5 py-4">
              <h2 className="font-bold text-sm mb-2 uppercase tracking-wide text-[#0A0A0A]/70">
                🔍 Query Results For:
              </h2>
              <p className="text-base leading-relaxed font-bold italic">"{lastExecutedQuery}"</p>
            </div>
          )}

          {/* Summary */}
          {data?.summary && (
            <div className="mb-6 bg-[#FFE500] border-4 border-[#0A0A0A] shadow-[6px_6px_0px_#0A0A0A] px-5 py-4">
              <div className="flex items-center flex-wrap gap-3 mb-2">
                <h2 className="font-bold text-lg uppercase tracking-wide">
                  📊 Summary
                </h2>
                {thoughtMs !== null && (
                  <span className="inline-flex items-center gap-2 bg-white border-2 border-[#0A0A0A] shadow-[3px_3px_0px_#0A0A0A] px-3 py-1 text-sm font-bold uppercase tracking-wide">
                    🧠 Thought for {formatDuration(thoughtMs)}
                  </span>
                )}
              </div>
              <div className="prose-summary text-base leading-relaxed font-medium">
                <ReactMarkdown>{data.summary}</ReactMarkdown>
              </div>
            </div>
          )}

          {/* Chart */}
          {chartElement && (
            <div className="mb-6 bg-white border-4 border-[#0A0A0A] shadow-[6px_6px_0px_#0A0A0A] p-5">
              <h2 className="font-bold text-lg mb-4 uppercase tracking-wide bg-[#00D4FF] inline-block px-3 py-1 border-2 border-[#0A0A0A]">
                📈 Cost Chart
              </h2>
              <div className="h-80 mt-4">
                {chartElement}
              </div>
            </div>
          )}

          {/* Table */}
          {data?.table && data.table.columns && data.table.rows && data.table.rows.length > 0 && (
            <div className="bg-white border-4 border-[#0A0A0A] shadow-[6px_6px_0px_#0A0A0A] p-5 overflow-x-auto">
              <h2 className="font-bold text-lg mb-4 uppercase tracking-wide bg-[#B794F6] inline-block px-3 py-1 border-2 border-[#0A0A0A]">
                📋 Details
              </h2>
              <div className="overflow-x-auto">
                <table className="min-w-full text-sm border-collapse mt-4">
                  <thead>
                    <tr className="bg-[#0A0A0A] text-white">
                      {data.table.columns.map((col) => (
                        <th
                          key={col}
                          className="px-4 py-3 text-left font-bold border-2 border-[#0A0A0A] uppercase text-xs tracking-wide"
                        >
                          {col}
                        </th>
                      ))}
                    </tr>
                  </thead>
                  <tbody>
                    {data.table.rows.map((row, i) => (
                      <tr
                        key={i}
                        className={i % 2 === 0 ? "bg-[#FAFAFA]" : "bg-white"}
                      >
                        {row.map((cell, j) => (
                          <td
                            key={j}
                            className="px-4 py-3 border-2 border-[#0A0A0A] font-medium"
                          >
                            {cell as any}
                          </td>
                        ))}
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            </div>
          )}
        </div>

        {/* Footer */}
        <div className="text-center">
          <p className="text-sm font-medium text-[#0A0A0A]/60">
            Built with ❤️ by the Tuning and Optimization (TAO) Team at Discount Tire
          </p>
        </div>
      </div>
    </main>
  );
}
