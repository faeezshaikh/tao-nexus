/**
 * TAO Nexus API client.
 * Handles communication with the FastAPI backend at /api/v1/nexus/*.
 */
import { NexusAnalyzeRequest, NexusAnalyzeResponse } from "../types/nexus";

const API_URL = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000";

export async function analyzeQuery(
  request: NexusAnalyzeRequest
): Promise<NexusAnalyzeResponse> {
  const res = await fetch(`${API_URL}/api/v1/nexus/analyze`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(request),
  });

  if (!res.ok) {
    const body = await res.json().catch(() => null);
    throw new Error(body?.detail || `HTTP ${res.status}`);
  }

  return res.json();
}

export async function checkNexusHealth(): Promise<Record<string, unknown>> {
  const res = await fetch(`${API_URL}/api/v1/nexus/health`);
  return res.json();
}
