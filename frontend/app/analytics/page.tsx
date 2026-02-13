"use client";

import { useState, useEffect } from "react";
import { useAuth } from "../../contexts/AuthContext";
import { isAdmin } from "../../lib/auth";
import { useRouter } from "next/navigation";
import { fetchAnalytics, AnalyticsData, AnalyticsEvent } from "../../lib/analytics-client";
import Link from "next/link";

export default function AnalyticsPage() {
    const { user, isLoading: authLoading } = useAuth();
    const router = useRouter();
    const [analytics, setAnalytics] = useState<AnalyticsData | null>(null);
    const [loading, setLoading] = useState(true);
    const [error, setError] = useState<string | null>(null);
    const [userFilter, setUserFilter] = useState<string>("");

    useEffect(() => {
        // Redirect if not admin
        if (!authLoading && (!user || !isAdmin(user))) {
            router.push("/");
            return;
        }

        if (user && isAdmin(user)) {
            loadAnalytics();
        }
    }, [user, authLoading, router]); // Removed userFilter from dependencies

    async function loadAnalytics() {
        setLoading(true);
        setError(null);
        try {
            // Fetch all data, we'll filter client-side
            const data = await fetchAnalytics(undefined, 100);
            setAnalytics(data);
        } catch (err: any) {
            setError(err.message || "Failed to load analytics");
        } finally {
            setLoading(false);
        }
    }

    if (authLoading || loading) {
        return (
            <div className="min-h-screen bg-[#FAFAFA] flex items-center justify-center">
                <div className="text-2xl font-bold">Loading...</div>
            </div>
        );
    }

    if (!user || !isAdmin(user)) {
        return null;
    }

    const formatDuration = (ms: number) => {
        if (ms < 1000) return `${ms}ms`;
        return `${(ms / 1000).toFixed(2)}s`;
    };

    const formatTimestamp = (timestamp: string) => {
        return new Date(timestamp).toLocaleString();
    };

    const getEventIcon = (eventType: string) => {
        return eventType === "query" ? "🔍" : "📝";
    };

    // Filter events client-side for partial matching
    const filteredEvents = analytics?.events.filter(event => {
        if (!userFilter) return true;
        return event.username.toLowerCase().includes(userFilter.toLowerCase());
    }) || [];

    return (
        <main className="min-h-screen bg-[#FAFAFA] text-[#0A0A0A] p-4 md:p-8 relative overflow-hidden">
            {/* Decorative background elements */}
            <div className="fixed top-10 right-10 w-32 h-32 bg-[#FFE500] rounded-full opacity-20 blur-3xl pointer-events-none" />
            <div className="fixed bottom-20 left-10 w-40 h-40 bg-[#FF6B9D] rounded-full opacity-20 blur-3xl pointer-events-none" />
            <div className="fixed top-1/2 left-1/3 w-36 h-36 bg-[#00D4FF] rounded-full opacity-15 blur-3xl pointer-events-none" />

            <div className="max-w-7xl mx-auto relative z-10">
                {/* Header */}
                <div className="mb-8 flex items-center justify-between">
                    <div>
                        <h1 className="text-4xl md:text-5xl font-bold mb-2">
                            <span className="inline-block bg-[#FFE500] px-4 py-2 border-4 border-[#0A0A0A] shadow-[6px_6px_0px_#0A0A0A] transform -rotate-1">
                                ANALYTICS
                            </span>
                        </h1>
                        <p className="text-sm md:text-base text-[#0A0A0A]/70 mt-4">
                            Usage statistics and activity monitoring
                        </p>
                    </div>
                    <Link href="/">
                        <button className="bg-[#00D4FF] border-4 border-[#0A0A0A] shadow-[6px_6px_0px_#0A0A0A] px-4 py-2 font-bold text-sm hover:shadow-[8px_8px_0px_#0A0A0A] hover:-translate-y-0.5 transition-all active:shadow-[4px_4px_0px_#0A0A0A] active:translate-y-0">
                            ← BACK TO APP
                        </button>
                    </Link>
                </div>

                {error && (
                    <div className="mb-6 bg-[#FF6B9D] border-4 border-[#0A0A0A] shadow-[6px_6px_0px_#0A0A0A] px-5 py-4">
                        <p className="font-bold text-sm">⚠️ ERROR</p>
                        <p className="text-sm mt-1">{error}</p>
                    </div>
                )}

                {analytics && (
                    <>
                        {/* Summary Cards */}
                        <div className="grid grid-cols-2 md:grid-cols-3 lg:grid-cols-5 gap-4 mb-8">
                            <div className="bg-[#FFE500] border-4 border-[#0A0A0A] shadow-[6px_6px_0px_#0A0A0A] p-4">
                                <div className="text-2xl font-bold">{analytics.summary.total_queries}</div>
                                <div className="text-xs font-bold uppercase mt-1">Total Queries</div>
                            </div>
                            <div className="bg-[#00FF94] border-4 border-[#0A0A0A] shadow-[6px_6px_0px_#0A0A0A] p-4">
                                <div className="text-2xl font-bold">{analytics.summary.successful_queries}</div>
                                <div className="text-xs font-bold uppercase mt-1">Successful</div>
                            </div>
                            <div className="bg-[#FF6B9D] border-4 border-[#0A0A0A] shadow-[6px_6px_0px_#0A0A0A] p-4">
                                <div className="text-2xl font-bold">{analytics.summary.failed_queries}</div>
                                <div className="text-xs font-bold uppercase mt-1">Failed</div>
                            </div>
                            <div className="bg-[#00D4FF] border-4 border-[#0A0A0A] shadow-[6px_6px_0px_#0A0A0A] p-4">
                                <div className="text-2xl font-bold">{formatDuration(analytics.summary.avg_query_duration_ms)}</div>
                                <div className="text-xs font-bold uppercase mt-1">Avg Duration</div>
                            </div>
                            <div className="bg-white border-4 border-[#0A0A0A] shadow-[6px_6px_0px_#0A0A0A] p-4">
                                <div className="text-2xl font-bold">{analytics.summary.unique_users}</div>
                                <div className="text-xs font-bold uppercase mt-1">Unique Users</div>
                            </div>
                        </div>

                        {/* Filter */}
                        <div className="mb-6 bg-white border-4 border-[#0A0A0A] shadow-[6px_6px_0px_#0A0A0A] p-5">
                            <label className="block text-sm font-bold mb-2 uppercase tracking-wide">
                                Filter by User
                            </label>
                            <div className="flex gap-3">
                                <input
                                    type="text"
                                    value={userFilter}
                                    onChange={(e) => setUserFilter(e.target.value)}
                                    className="flex-1 border-4 border-[#0A0A0A] px-4 py-2 text-base font-medium focus:outline-none focus:shadow-[6px_6px_0px_#0A0A0A] focus:-translate-y-1 transition-all bg-[#FAFAFA]"
                                    placeholder="Enter username (leave empty for all)"
                                />
                                {userFilter && (
                                    <button
                                        onClick={() => setUserFilter("")}
                                        className="bg-[#FF6B9D] border-4 border-[#0A0A0A] shadow-[4px_4px_0px_#0A0A0A] px-4 py-2 font-bold text-sm hover:shadow-[6px_6px_0px_#0A0A0A] hover:-translate-y-0.5 transition-all"
                                    >
                                        CLEAR
                                    </button>
                                )}
                            </div>
                        </div>

                        {/* Activity Table */}
                        <div className="bg-white border-4 border-[#0A0A0A] shadow-[6px_6px_0px_#0A0A0A] p-5 overflow-x-auto">
                            <h2 className="font-bold text-lg mb-4 uppercase tracking-wide bg-[#00FF94] inline-block px-3 py-1 border-2 border-[#0A0A0A]">
                                📋 Recent Activity
                            </h2>
                            <div className="overflow-x-auto">
                                <table className="min-w-full text-sm border-collapse mt-4">
                                    <thead>
                                        <tr className="bg-[#0A0A0A] text-white">
                                            <th className="px-4 py-3 text-left font-bold border-2 border-[#0A0A0A] uppercase text-xs tracking-wide">Type</th>
                                            <th className="px-4 py-3 text-left font-bold border-2 border-[#0A0A0A] uppercase text-xs tracking-wide">User</th>
                                            <th className="px-4 py-3 text-left font-bold border-2 border-[#0A0A0A] uppercase text-xs tracking-wide">Timestamp</th>
                                            <th className="px-4 py-3 text-left font-bold border-2 border-[#0A0A0A] uppercase text-xs tracking-wide">IP Address</th>
                                            <th className="px-4 py-3 text-left font-bold border-2 border-[#0A0A0A] uppercase text-xs tracking-wide">Details</th>
                                            <th className="px-4 py-3 text-left font-bold border-2 border-[#0A0A0A] uppercase text-xs tracking-wide">Status</th>
                                        </tr>
                                    </thead>
                                    <tbody>
                                        {filteredEvents.map((event, i) => (
                                            <tr
                                                key={i}
                                                className={i % 2 === 0 ? "bg-[#FAFAFA]" : "bg-white"}
                                            >
                                                <td className="px-4 py-3 border-2 border-[#0A0A0A] font-bold">
                                                    {getEventIcon(event.event_type)} {event.event_type.toUpperCase()}
                                                </td>
                                                <td className="px-4 py-3 border-2 border-[#0A0A0A] font-medium">
                                                    {event.username}
                                                </td>
                                                <td className="px-4 py-3 border-2 border-[#0A0A0A] font-medium text-xs">
                                                    {formatTimestamp(event.timestamp)}
                                                </td>
                                                <td className="px-4 py-3 border-2 border-[#0A0A0A] font-mono text-xs">
                                                    {event.ip_address}
                                                </td>
                                                <td className="px-4 py-3 border-2 border-[#0A0A0A] font-medium text-xs max-w-md truncate">
                                                    <span title={event.query}>{event.query}</span>
                                                </td>
                                                <td className="px-4 py-3 border-2 border-[#0A0A0A]">
                                                    <div className="flex items-center gap-2">
                                                        {event.success ? (
                                                            <span className="bg-[#00FF94] px-2 py-1 border-2 border-[#0A0A0A] text-xs font-bold">
                                                                ✓ {formatDuration(event.duration_ms || 0)}
                                                            </span>
                                                        ) : (
                                                            <span className="bg-[#FF6B9D] px-2 py-1 border-2 border-[#0A0A0A] text-xs font-bold" title={event.error || ""}>
                                                                ✗ ERROR
                                                            </span>
                                                        )}
                                                        {!event.success && event.error && (
                                                            <span className="text-xs text-[#0A0A0A]/70 truncate max-w-[200px]" title={event.error}>
                                                                {event.error}
                                                            </span>
                                                        )}
                                                    </div>
                                                </td>
                                            </tr>
                                        ))}
                                    </tbody>
                                </table>
                            </div>
                        </div>
                    </>
                )}

                {/* Footer */}
                <div className="text-center mt-8">
                    <p className="text-sm font-medium text-[#0A0A0A]/60">
                        Analytics Dashboard • Admin Only
                    </p>
                </div>
            </div>
        </main>
    );
}
