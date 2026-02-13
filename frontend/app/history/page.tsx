"use client";

import { useState, useEffect } from "react";
import { useAuth } from "../../contexts/AuthContext";
import { useRouter } from "next/navigation";
import { getHistory, clearHistory } from "../../lib/history";
import { HistoryEntry, FinopsResponse } from "../../types/finops";
import LoginPage from "../../components/LoginPage";
import Link from "next/link";
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

export default function HistoryPage() {
    const { user, isLoading: authLoading } = useAuth();
    const router = useRouter();
    const [entries, setEntries] = useState<HistoryEntry[]>([]);
    const [expandedId, setExpandedId] = useState<string | null>(null);
    const [confirmClear, setConfirmClear] = useState(false);

    useEffect(() => {
        if (!authLoading && user) {
            setEntries(getHistory());
        }
    }, [authLoading, user]);

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

    const handleClear = () => {
        if (!confirmClear) {
            setConfirmClear(true);
            return;
        }
        clearHistory();
        setEntries([]);
        setConfirmClear(false);
    };

    const handleRunAgain = (query: string) => {
        router.push(`/?q=${encodeURIComponent(query)}`);
    };

    const toggleExpand = (id: string) => {
        setExpandedId((prev) => (prev === id ? null : id));
    };

    const formatDuration = (ms: number) => {
        const totalSeconds = Math.max(0, Math.round(ms / 1000));
        const minutes = Math.floor(totalSeconds / 60);
        const seconds = totalSeconds % 60;
        if (minutes > 0) return `${minutes}m ${seconds.toString().padStart(2, "0")}s`;
        return `${seconds}s`;
    };

    const formatTimestamp = (ts: string) => {
        const d = new Date(ts);
        return d.toLocaleDateString("en-US", {
            month: "short",
            day: "numeric",
            year: "numeric",
        }) + " at " + d.toLocaleTimeString("en-US", {
            hour: "numeric",
            minute: "2-digit",
            hour12: true,
        });
    };

    const relativeTime = (ts: string) => {
        const diffMs = Date.now() - new Date(ts).getTime();
        const mins = Math.floor(diffMs / 60000);
        if (mins < 1) return "Just now";
        if (mins < 60) return `${mins}m ago`;
        const hrs = Math.floor(mins / 60);
        if (hrs < 24) return `${hrs}h ago`;
        const days = Math.floor(hrs / 24);
        return `${days}d ago`;
    };

    /* ─── Chart builder (mirrors main page) ─── */
    const renderChart = (data: FinopsResponse) => {
        if (!data.chart) return null;
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
            animation: { duration: 750 },
            transitions: { active: { animation: { duration: 0 } } },
            plugins: {
                legend: {
                    position: "top" as const,
                    labels: {
                        font: { family: "'Space Grotesk', sans-serif", size: 12, weight: 600 as const },
                        color: "#0A0A0A",
                        padding: 12,
                    },
                },
                tooltip: {
                    enabled: true,
                    mode: "index" as const,
                    intersect: false,
                    backgroundColor: "#0A0A0A",
                    titleFont: { family: "'Space Grotesk', sans-serif", size: 13, weight: 600 as const },
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
                        font: { family: "'Space Grotesk', sans-serif", size: 13, weight: 600 as const },
                        color: "#0A0A0A",
                    },
                    grid: { color: "rgba(10, 10, 10, 0.1)" },
                    ticks: { font: { family: "'Space Grotesk', sans-serif", size: 11 }, color: "#0A0A0A" },
                },
                y: {
                    title: {
                        display: true,
                        text: "Cost (USD)",
                        font: { family: "'Space Grotesk', sans-serif", size: 13, weight: 600 as const },
                        color: "#0A0A0A",
                    },
                    grid: { color: "rgba(10, 10, 10, 0.1)" },
                    ticks: { font: { family: "'Space Grotesk', sans-serif", size: 11 }, color: "#0A0A0A" },
                },
            },
        };

        return type === "bar" ? (
            <Bar data={chartData} options={commonOptions} />
        ) : (
            <Line data={chartData} options={commonOptions} />
        );
    };

    /* ─── Render ─── */
    return (
        <main className="min-h-screen bg-[#FAFAFA] text-[#0A0A0A] p-4 md:p-8 relative overflow-hidden">
            {/* Decorative background elements */}
            <div className="fixed top-10 right-10 w-32 h-32 bg-[#FFE500] rounded-full opacity-20 blur-3xl pointer-events-none" />
            <div className="fixed bottom-20 left-10 w-40 h-40 bg-[#FF6B9D] rounded-full opacity-20 blur-3xl pointer-events-none" />
            <div className="fixed top-1/2 left-1/3 w-36 h-36 bg-[#00D4FF] rounded-full opacity-15 blur-3xl pointer-events-none" />

            <div className="max-w-6xl mx-auto relative z-10">
                {/* Header */}
                <div className="mb-8 flex flex-col md:flex-row items-start md:items-center justify-between gap-4">
                    <div>
                        <h1 className="text-4xl md:text-5xl font-bold mb-2">
                            <span className="inline-block bg-[#B794F6] px-4 py-2 border-4 border-[#0A0A0A] shadow-[6px_6px_0px_#0A0A0A] transform -rotate-1">
                                🕘 HISTORY
                            </span>
                        </h1>
                        <p className="text-sm md:text-base text-[#0A0A0A]/70 mt-4">
                            Your recent queries and results
                        </p>
                    </div>
                    <div className="flex gap-3">
                        {entries.length > 0 && (
                            <button
                                onClick={handleClear}
                                className={`border-4 border-[#0A0A0A] shadow-[6px_6px_0px_#0A0A0A] px-4 py-2 font-bold text-sm hover:shadow-[8px_8px_0px_#0A0A0A] hover:-translate-y-0.5 transition-all active:shadow-[4px_4px_0px_#0A0A0A] active:translate-y-0 ${confirmClear
                                        ? "bg-[#FF6B9D] animate-pulse"
                                        : "bg-white"
                                    }`}
                            >
                                {confirmClear ? "⚠️ CONFIRM CLEAR?" : "🗑️ CLEAR HISTORY"}
                            </button>
                        )}
                        <Link href="/">
                            <button className="bg-[#00D4FF] border-4 border-[#0A0A0A] shadow-[6px_6px_0px_#0A0A0A] px-4 py-2 font-bold text-sm hover:shadow-[8px_8px_0px_#0A0A0A] hover:-translate-y-0.5 transition-all active:shadow-[4px_4px_0px_#0A0A0A] active:translate-y-0">
                                ← BACK TO APP
                            </button>
                        </Link>
                    </div>
                </div>

                {/* Empty state */}
                {entries.length === 0 && (
                    <div className="bg-white border-4 border-[#0A0A0A] shadow-[12px_12px_0px_#0A0A0A] p-12 text-center">
                        <div className="text-6xl mb-4">📭</div>
                        <h2 className="text-2xl font-bold mb-2">No queries yet</h2>
                        <p className="text-[#0A0A0A]/60 font-medium mb-6">
                            Run a query on the home page and it will appear here automatically.
                        </p>
                        <Link href="/">
                            <button className="bg-[#00FF94] border-4 border-[#0A0A0A] shadow-[6px_6px_0px_#0A0A0A] px-6 py-3 font-bold text-base hover:shadow-[8px_8px_0px_#0A0A0A] hover:-translate-y-0.5 transition-all active:shadow-[4px_4px_0px_#0A0A0A] active:translate-y-0">
                                🚀 RUN YOUR FIRST QUERY
                            </button>
                        </Link>
                    </div>
                )}

                {/* History cards */}
                <div className="space-y-4">
                    {entries.map((entry, idx) => {
                        const isExpanded = expandedId === entry.id;
                        return (
                            <div
                                key={entry.id}
                                className="bg-white border-4 border-[#0A0A0A] shadow-[8px_8px_0px_#0A0A0A] transition-all duration-200"
                            >
                                {/* Card header — clickable */}
                                <button
                                    onClick={() => toggleExpand(entry.id)}
                                    className="w-full text-left px-5 py-4 flex flex-col md:flex-row md:items-center gap-3 hover:bg-[#FAFAFA] transition-colors"
                                >
                                    <div className="flex-1 min-w-0">
                                        <p className="font-bold text-base truncate">{entry.query}</p>
                                        <div className="flex flex-wrap items-center gap-2 mt-2">
                                            <span className="inline-flex items-center gap-1 bg-[#FAFAFA] border-2 border-[#0A0A0A] px-2 py-0.5 text-xs font-bold">
                                                👤 {entry.username}
                                            </span>
                                            <span className="inline-flex items-center gap-1 bg-[#FAFAFA] border-2 border-[#0A0A0A] px-2 py-0.5 text-xs font-bold">
                                                📅 {formatTimestamp(entry.timestamp)}
                                            </span>
                                            <span className="inline-flex items-center gap-1 bg-[#00FF94] border-2 border-[#0A0A0A] px-2 py-0.5 text-xs font-bold">
                                                ⏱️ {formatDuration(entry.durationMs)}
                                            </span>
                                            <span className="text-xs font-medium text-[#0A0A0A]/50">
                                                {relativeTime(entry.timestamp)}
                                            </span>
                                        </div>
                                    </div>
                                    <div className="flex items-center gap-3 shrink-0">
                                        <span
                                            className={`text-xl transition-transform duration-300 ${isExpanded ? "rotate-90" : "rotate-0"
                                                }`}
                                        >
                                            ▶
                                        </span>
                                    </div>
                                </button>

                                {/* Expanded results */}
                                {isExpanded && (
                                    <div className="border-t-4 border-[#0A0A0A] px-5 py-5 space-y-5 bg-[#FAFAFA]">
                                        {/* Action bar */}
                                        <div className="flex justify-end">
                                            <button
                                                onClick={() => handleRunAgain(entry.query)}
                                                className="bg-[#FFE500] border-4 border-[#0A0A0A] shadow-[6px_6px_0px_#0A0A0A] px-5 py-2 font-bold text-sm hover:shadow-[8px_8px_0px_#0A0A0A] hover:-translate-y-0.5 transition-all active:shadow-[4px_4px_0px_#0A0A0A] active:translate-y-0"
                                            >
                                                🔄 RUN AGAIN
                                            </button>
                                        </div>

                                        {/* Summary */}
                                        {entry.response.summary && (
                                            <div className="bg-[#FFE500] border-4 border-[#0A0A0A] shadow-[6px_6px_0px_#0A0A0A] px-5 py-4">
                                                <div className="flex items-center flex-wrap gap-3 mb-2">
                                                    <h2 className="font-bold text-lg uppercase tracking-wide">
                                                        📊 Summary
                                                    </h2>
                                                    <span className="inline-flex items-center gap-2 bg-white border-2 border-[#0A0A0A] shadow-[3px_3px_0px_#0A0A0A] px-3 py-1 text-sm font-bold uppercase tracking-wide">
                                                        🧠 Thought for {formatDuration(entry.durationMs)}
                                                    </span>
                                                </div>
                                                <p className="text-base leading-relaxed font-medium">
                                                    {entry.response.summary}
                                                </p>
                                            </div>
                                        )}

                                        {/* Chart */}
                                        {entry.response.chart && (
                                            <div className="bg-white border-4 border-[#0A0A0A] shadow-[6px_6px_0px_#0A0A0A] p-5">
                                                <h2 className="font-bold text-lg mb-4 uppercase tracking-wide bg-[#00D4FF] inline-block px-3 py-1 border-2 border-[#0A0A0A]">
                                                    📈 Cost Chart
                                                </h2>
                                                <div className="h-80 mt-4">
                                                    {renderChart(entry.response)}
                                                </div>
                                            </div>
                                        )}

                                        {/* Table */}
                                        {entry.response.table &&
                                            entry.response.table.rows?.length > 0 && (
                                                <div className="bg-white border-4 border-[#0A0A0A] shadow-[6px_6px_0px_#0A0A0A] p-5 overflow-x-auto">
                                                    <h2 className="font-bold text-lg mb-4 uppercase tracking-wide bg-[#B794F6] inline-block px-3 py-1 border-2 border-[#0A0A0A]">
                                                        📋 Details
                                                    </h2>
                                                    <div className="overflow-x-auto">
                                                        <table className="min-w-full text-sm border-collapse mt-4">
                                                            <thead>
                                                                <tr className="bg-[#0A0A0A] text-white">
                                                                    {entry.response.table.columns.map((col) => (
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
                                                                {entry.response.table.rows.map((row, i) => (
                                                                    <tr
                                                                        key={i}
                                                                        className={
                                                                            i % 2 === 0 ? "bg-[#FAFAFA]" : "bg-white"
                                                                        }
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
                                )}
                            </div>
                        );
                    })}
                </div>

                {/* Footer */}
                <div className="text-center mt-8">
                    <p className="text-sm font-medium text-[#0A0A0A]/60">
                        Showing {entries.length} recent {entries.length === 1 ? "query" : "queries"} • Max 25 stored
                    </p>
                </div>
            </div>
        </main>
    );
}
