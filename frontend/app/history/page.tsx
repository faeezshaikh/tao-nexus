"use client";

import { useState, useEffect } from "react";
import { useAuth } from "../../contexts/AuthContext";
import { useRouter } from "next/navigation";
import { getHistory, clearHistory, deleteHistoryEntry } from "../../lib/history";
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
    const [selectedId, setSelectedId] = useState<string | null>(null);
    const [confirmClear, setConfirmClear] = useState(false);
    const [confirmDeleteId, setConfirmDeleteId] = useState<string | null>(null);

    useEffect(() => {
        if (!authLoading && user) {
            const h = getHistory();
            setEntries(h);
            if (h.length > 0) setSelectedId(h[0].id);
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

    const selectedEntry = entries.find((e) => e.id === selectedId) ?? null;

    const handleClear = () => {
        if (!confirmClear) {
            setConfirmClear(true);
            return;
        }
        clearHistory();
        setEntries([]);
        setSelectedId(null);
        setConfirmClear(false);
    };

    const handleRunAgain = (query: string) => {
        router.push(`/?q=${encodeURIComponent(query)}`);
    };

    const handleDelete = (id: string) => {
        if (confirmDeleteId !== id) {
            setConfirmDeleteId(id);
            return;
        }
        deleteHistoryEntry(id);
        const updated = entries.filter((e) => e.id !== id);
        setEntries(updated);
        setConfirmDeleteId(null);
        if (selectedId === id) {
            setSelectedId(updated.length > 0 ? updated[0].id : null);
        }
    };

    const handleSelect = (id: string) => {
        setSelectedId(id);
        setConfirmDeleteId(null);
    };

    const formatDuration = (ms: number) => {
        const totalSeconds = Math.max(0, Math.round(ms / 1000));
        const minutes = Math.floor(totalSeconds / 60);
        const seconds = totalSeconds % 60;
        if (minutes > 0)
            return `${minutes}m ${seconds.toString().padStart(2, "0")}s`;
        return `${seconds}s`;
    };

    const formatTimestamp = (ts: string) => {
        const d = new Date(ts);
        return (
            d.toLocaleDateString("en-US", {
                month: "short",
                day: "numeric",
                year: "numeric",
            }) +
            " at " +
            d.toLocaleTimeString("en-US", {
                hour: "numeric",
                minute: "2-digit",
                hour12: true,
            })
        );
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
                        font: {
                            family: "'Space Grotesk', sans-serif",
                            size: 12,
                            weight: 600 as const,
                        },
                        color: "#0A0A0A",
                        padding: 12,
                    },
                },
                tooltip: {
                    enabled: true,
                    mode: "index" as const,
                    intersect: false,
                    backgroundColor: "#0A0A0A",
                    titleFont: {
                        family: "'Space Grotesk', sans-serif",
                        size: 13,
                        weight: 600 as const,
                    },
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
                        font: {
                            family: "'Space Grotesk', sans-serif",
                            size: 13,
                            weight: 600 as const,
                        },
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
                        font: {
                            family: "'Space Grotesk', sans-serif",
                            size: 13,
                            weight: 600 as const,
                        },
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
    };

    /* ─── Render ─── */
    return (
        <main className="min-h-screen bg-[#FAFAFA] text-[#0A0A0A] p-4 md:p-6 relative overflow-hidden">
            {/* Decorative background elements */}
            <div className="fixed top-10 right-10 w-32 h-32 bg-[#FFE500] rounded-full opacity-20 blur-3xl pointer-events-none" />
            <div className="fixed bottom-20 left-10 w-40 h-40 bg-[#FF6B9D] rounded-full opacity-20 blur-3xl pointer-events-none" />
            <div className="fixed top-1/2 left-1/3 w-36 h-36 bg-[#00D4FF] rounded-full opacity-15 blur-3xl pointer-events-none" />

            <div className="max-w-[1400px] mx-auto relative z-10 flex flex-col h-[calc(100vh-3rem)]">
                {/* Header */}
                <div className="mb-4 flex flex-col md:flex-row items-start md:items-center justify-between gap-3 shrink-0">
                    <div className="flex items-center gap-4">
                        <h1 className="text-3xl md:text-4xl font-bold">
                            <span className="inline-block bg-[#B794F6] px-4 py-2 border-4 border-[#0A0A0A] shadow-[6px_6px_0px_#0A0A0A] transform -rotate-1">
                                🕘 HISTORY
                            </span>
                        </h1>
                        <span className="text-sm text-[#0A0A0A]/50 font-bold mt-1">
                            {entries.length} {entries.length === 1 ? "query" : "queries"}
                        </span>
                    </div>
                    <div className="flex gap-3">
                        {entries.length > 0 && (
                            <button
                                onClick={handleClear}
                                className={`border-4 border-[#0A0A0A] shadow-[6px_6px_0px_#0A0A0A] px-4 py-2 font-bold text-sm hover:shadow-[8px_8px_0px_#0A0A0A] hover:-translate-y-0.5 transition-all active:shadow-[4px_4px_0px_#0A0A0A] active:translate-y-0 ${confirmClear ? "bg-[#FF6B9D] animate-pulse" : "bg-white"
                                    }`}
                            >
                                {confirmClear ? "⚠️ CONFIRM CLEAR ALL?" : "🗑️ CLEAR ALL"}
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
                {entries.length === 0 ? (
                    <div className="flex-1 flex items-center justify-center">
                        <div className="bg-white border-4 border-[#0A0A0A] shadow-[12px_12px_0px_#0A0A0A] p-12 text-center max-w-lg">
                            <div className="text-6xl mb-4">📭</div>
                            <h2 className="text-2xl font-bold mb-2">No queries yet</h2>
                            <p className="text-[#0A0A0A]/60 font-medium mb-6">
                                Run a query on the home page and it will appear here
                                automatically.
                            </p>
                            <Link href="/">
                                <button className="bg-[#00FF94] border-4 border-[#0A0A0A] shadow-[6px_6px_0px_#0A0A0A] px-6 py-3 font-bold text-base hover:shadow-[8px_8px_0px_#0A0A0A] hover:-translate-y-0.5 transition-all active:shadow-[4px_4px_0px_#0A0A0A] active:translate-y-0">
                                    🚀 RUN YOUR FIRST QUERY
                                </button>
                            </Link>
                        </div>
                    </div>
                ) : (
                    /* ─── Two-panel layout ─── */
                    <div className="flex-1 flex gap-4 min-h-0">
                        {/* Left panel — query list */}
                        <div className="w-80 shrink-0 flex flex-col border-4 border-[#0A0A0A] shadow-[8px_8px_0px_#0A0A0A] bg-white">
                            <div className="px-4 py-3 bg-[#0A0A0A] text-white shrink-0">
                                <h2 className="font-bold text-sm uppercase tracking-wide">
                                    📋 Recent Queries
                                </h2>
                            </div>
                            <div className="flex-1 overflow-y-auto">
                                {entries.map((entry) => {
                                    const isActive = selectedId === entry.id;
                                    const isConfirmingDelete = confirmDeleteId === entry.id;
                                    return (
                                        <button
                                            key={entry.id}
                                            onClick={() => handleSelect(entry.id)}
                                            className={`w-full text-left px-4 py-3 border-b-2 border-[#0A0A0A]/10 transition-all duration-150 hover:bg-[#FFE500]/20 group relative ${isActive
                                                ? "bg-[#FFE500]/30 border-l-[6px] border-l-[#FFE500]"
                                                : "border-l-[6px] border-l-transparent"
                                                }`}
                                        >
                                            {/* Delete button */}
                                            <span
                                                role="button"
                                                tabIndex={0}
                                                onClick={(e) => {
                                                    e.stopPropagation();
                                                    handleDelete(entry.id);
                                                }}
                                                onKeyDown={(e) => {
                                                    if (e.key === "Enter") {
                                                        e.stopPropagation();
                                                        handleDelete(entry.id);
                                                    }
                                                }}
                                                className={`absolute top-2 right-2 flex items-center gap-1 px-1.5 py-0.5 text-xs font-bold transition-all cursor-pointer border-2 ${isConfirmingDelete
                                                        ? "bg-[#FF6B9D] text-[#0A0A0A] border-[#0A0A0A] opacity-100 shadow-[2px_2px_0px_#0A0A0A]"
                                                        : "text-[#0A0A0A]/40 border-transparent hover:text-[#0A0A0A] hover:bg-[#FF6B9D]/30 hover:border-[#0A0A0A]/30 opacity-0 group-hover:opacity-100"
                                                    }`}
                                                title={isConfirmingDelete ? "Click again to confirm" : "Delete this entry"}
                                            >
                                                🗑️ {isConfirmingDelete && <span>Sure?</span>}
                                            </span>
                                            <p
                                                className={`text-sm leading-snug mb-1.5 line-clamp-2 ${isActive ? "font-bold" : "font-medium"
                                                    }`}
                                            >
                                                {entry.query}
                                            </p>
                                            <div className="flex items-center gap-2 flex-wrap">
                                                <span className="text-[10px] font-bold text-[#0A0A0A]/40 uppercase">
                                                    {relativeTime(entry.timestamp)}
                                                </span>
                                                <span className="text-[10px] font-bold bg-[#00FF94]/50 px-1.5 py-0.5 border border-[#0A0A0A]/20">
                                                    ⏱ {formatDuration(entry.durationMs)}
                                                </span>
                                                <span className="text-[10px] font-bold text-[#0A0A0A]/40">
                                                    👤 {entry.username}
                                                </span>
                                            </div>
                                        </button>
                                    );
                                })}
                            </div>
                        </div>

                        {/* Right panel — detail view */}
                        <div className="flex-1 flex flex-col border-4 border-[#0A0A0A] shadow-[8px_8px_0px_#0A0A0A] bg-white min-w-0">
                            {selectedEntry ? (
                                <>
                                    {/* Detail header */}
                                    <div className="px-5 py-4 bg-[#FAFAFA] border-b-4 border-[#0A0A0A] shrink-0">
                                        <div className="flex items-start justify-between gap-4">
                                            <div className="min-w-0 flex-1">
                                                <p className="font-bold text-lg leading-snug mb-2">
                                                    &ldquo;{selectedEntry.query}&rdquo;
                                                </p>
                                                <div className="flex flex-wrap items-center gap-2">
                                                    <span className="inline-flex items-center gap-1 bg-white border-2 border-[#0A0A0A] px-2 py-0.5 text-xs font-bold">
                                                        👤 {selectedEntry.username}
                                                    </span>
                                                    <span className="inline-flex items-center gap-1 bg-white border-2 border-[#0A0A0A] px-2 py-0.5 text-xs font-bold">
                                                        📅 {formatTimestamp(selectedEntry.timestamp)}
                                                    </span>
                                                    <span className="inline-flex items-center gap-1 bg-[#00FF94] border-2 border-[#0A0A0A] px-2 py-0.5 text-xs font-bold">
                                                        ⏱️ {formatDuration(selectedEntry.durationMs)}
                                                    </span>
                                                </div>
                                            </div>
                                            <button
                                                onClick={() => handleRunAgain(selectedEntry.query)}
                                                className="bg-[#FFE500] border-4 border-[#0A0A0A] shadow-[6px_6px_0px_#0A0A0A] px-5 py-2 font-bold text-sm hover:shadow-[8px_8px_0px_#0A0A0A] hover:-translate-y-0.5 transition-all active:shadow-[4px_4px_0px_#0A0A0A] active:translate-y-0 shrink-0"
                                            >
                                                🔄 RUN AGAIN
                                            </button>
                                        </div>
                                    </div>

                                    {/* Scrollable results */}
                                    <div className="flex-1 overflow-y-auto p-5 space-y-5">
                                        {/* Summary */}
                                        {selectedEntry.response.summary && (
                                            <div className="bg-[#FFE500] border-4 border-[#0A0A0A] shadow-[6px_6px_0px_#0A0A0A] px-5 py-4">
                                                <div className="flex items-center flex-wrap gap-3 mb-2">
                                                    <h2 className="font-bold text-lg uppercase tracking-wide">
                                                        📊 Summary
                                                    </h2>
                                                    <span className="inline-flex items-center gap-2 bg-white border-2 border-[#0A0A0A] shadow-[3px_3px_0px_#0A0A0A] px-3 py-1 text-sm font-bold uppercase tracking-wide">
                                                        🧠 Thought for{" "}
                                                        {formatDuration(selectedEntry.durationMs)}
                                                    </span>
                                                </div>
                                                <p className="text-base leading-relaxed font-medium">
                                                    {selectedEntry.response.summary}
                                                </p>
                                            </div>
                                        )}

                                        {/* Chart */}
                                        {selectedEntry.response.chart && (
                                            <div className="bg-white border-4 border-[#0A0A0A] shadow-[6px_6px_0px_#0A0A0A] p-5">
                                                <h2 className="font-bold text-lg mb-4 uppercase tracking-wide bg-[#00D4FF] inline-block px-3 py-1 border-2 border-[#0A0A0A]">
                                                    📈 Cost Chart
                                                </h2>
                                                <div className="h-80 mt-4">
                                                    {renderChart(selectedEntry.response)}
                                                </div>
                                            </div>
                                        )}

                                        {/* Table */}
                                        {selectedEntry.response.table &&
                                            selectedEntry.response.table.rows?.length > 0 && (
                                                <div className="bg-white border-4 border-[#0A0A0A] shadow-[6px_6px_0px_#0A0A0A] p-5 overflow-x-auto">
                                                    <h2 className="font-bold text-lg mb-4 uppercase tracking-wide bg-[#B794F6] inline-block px-3 py-1 border-2 border-[#0A0A0A]">
                                                        📋 Details
                                                    </h2>
                                                    <div className="overflow-x-auto">
                                                        <table className="min-w-full text-sm border-collapse mt-4">
                                                            <thead>
                                                                <tr className="bg-[#0A0A0A] text-white">
                                                                    {selectedEntry.response.table.columns.map(
                                                                        (col) => (
                                                                            <th
                                                                                key={col}
                                                                                className="px-4 py-3 text-left font-bold border-2 border-[#0A0A0A] uppercase text-xs tracking-wide"
                                                                            >
                                                                                {col}
                                                                            </th>
                                                                        )
                                                                    )}
                                                                </tr>
                                                            </thead>
                                                            <tbody>
                                                                {selectedEntry.response.table.rows.map(
                                                                    (row, i) => (
                                                                        <tr
                                                                            key={i}
                                                                            className={
                                                                                i % 2 === 0
                                                                                    ? "bg-[#FAFAFA]"
                                                                                    : "bg-white"
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
                                                                    )
                                                                )}
                                                            </tbody>
                                                        </table>
                                                    </div>
                                                </div>
                                            )}
                                    </div>
                                </>
                            ) : (
                                <div className="flex-1 flex items-center justify-center text-[#0A0A0A]/40">
                                    <div className="text-center">
                                        <div className="text-5xl mb-3">👈</div>
                                        <p className="font-bold text-lg">Select a query</p>
                                        <p className="text-sm mt-1">
                                            Choose a query from the left panel to view its results.
                                        </p>
                                    </div>
                                </div>
                            )}
                        </div>
                    </div>
                )}
            </div>
        </main>
    );
}
