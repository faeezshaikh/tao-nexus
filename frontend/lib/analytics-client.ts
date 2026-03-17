// Frontend analytics tracking utilities

const API_URL = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000";

export interface AnalyticsEvent {
    event_type: "query";
    timestamp: string;
    username: string;
    ip_address: string;
    query: string;
    duration_ms: number;
    success: boolean;
    error?: string;
}

export interface AnalyticsSummary {
    total_queries: number;
    successful_queries: number;
    failed_queries: number;
    avg_query_duration_ms: number;
    unique_users: number;
}

export interface AnalyticsData {
    events: AnalyticsEvent[];
    summary: AnalyticsSummary;
}

export async function fetchAnalytics(
    usernameFilter?: string,
    limit: number = 100
): Promise<AnalyticsData> {
    const params = new URLSearchParams();
    if (usernameFilter) params.append("username", usernameFilter);
    params.append("limit", limit.toString());

    const response = await fetch(`${API_URL}/analytics?${params}`);
    if (!response.ok) {
        throw new Error("Failed to fetch analytics");
    }
    return response.json();
}
