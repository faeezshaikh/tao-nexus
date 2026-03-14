"""
LLM synthesis layer for TAO Nexus.

Wraps the existing OllamaClient with Nexus-specific methods:
 - generate_executive_summary
 - generate_narrative
 - propose_actions

Includes a mock fallback for development without a running LLM.
"""
import json
import logging
import os
from typing import Any, Dict, List, Optional

logger = logging.getLogger(__name__)


class NexusLLM:
    """LLM abstraction for TAO Nexus analysis synthesis."""

    def __init__(self, *, use_mock: bool = True):
        self.use_mock = use_mock
        self._ollama = None

        if not use_mock:
            try:
                # Import from parent package (agent/)
                import sys, pathlib
                sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent.parent))
                from ollama_client import OllamaClient
                self._ollama = OllamaClient()
                logger.info("NexusLLM: Using real Ollama client")
            except Exception as e:
                logger.warning(f"NexusLLM: Failed to init Ollama, falling back to mock: {e}")
                self.use_mock = True

    async def generate_executive_summary(
        self,
        *,
        query: str,
        audience: str,
        baseline_cost: float,
        target_savings_pct: float,
        total_identified_savings: float,
        top_actions: List[Dict[str, Any]],
        constraints: List[str],
    ) -> str:
        """Generate an executive summary for the analysis."""
        if self.use_mock:
            return self._mock_executive_summary(
                query=query,
                audience=audience,
                baseline_cost=baseline_cost,
                target_savings_pct=target_savings_pct,
                total_identified_savings=total_identified_savings,
                top_actions=top_actions,
                constraints=constraints,
            )

        prompt = f"""You are TAO Nexus, an AI Cloud Economics advisor for Discount Tire.
Generate a concise executive summary for the {audience} audience.

Query: {query}
Current monthly spend: ${baseline_cost:,.0f}
Target savings: {target_savings_pct}%
Identified savings: ${total_identified_savings:,.0f}/month
Top actions: {json.dumps(top_actions[:3], default=str)}
Constraints: {', '.join(constraints) if constraints else 'None'}

Write 2-3 paragraphs in markdown. Be specific with numbers. Start with the key finding."""

        return await self._ollama.generate(
            prompt,
            system_prompt="You are a strategic FinOps advisor writing for enterprise leadership.",
            temperature=0.4,
        )

    async def generate_narrative_sections(
        self,
        *,
        query: str,
        audience: str,
        analysis_data: Dict[str, Any],
    ) -> List[Dict[str, str]]:
        """Generate audience-appropriate narrative sections."""
        if self.use_mock:
            return self._mock_narrative_sections(audience, analysis_data)

        prompt = f"""Generate 3-4 narrative sections for a {audience} audience analyzing cloud costs.
Analysis data: {json.dumps(analysis_data, default=str)[:2000]}
Return a JSON array of objects with: title, content (markdown), icon (emoji), order (int)."""

        response = await self._ollama.generate(prompt, temperature=0.4)
        try:
            return json.loads(response)
        except json.JSONDecodeError:
            return self._mock_narrative_sections(audience, analysis_data)

    # ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
    #  Mock Implementations
    # ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

    def _mock_executive_summary(self, **kw) -> str:
        baseline = kw["baseline_cost"]
        savings = kw["total_identified_savings"]
        pct = (savings / baseline * 100) if baseline else 0
        target_pct = kw.get("target_savings_pct", 12)
        constraints = kw.get("constraints", [])
        audience = kw.get("audience", "leadership")

        constraint_text = ""
        if constraints:
            constraint_text = f" The analysis respects your constraints: **{', '.join(constraints)}**."

        if audience == "leadership":
            return (
                f"## Savings Plan: ${savings:,.0f}/month achievable ({pct:.1f}% reduction)\n\n"
                f"Based on analysis of your current **${baseline:,.0f}/month** AWS footprint, "
                f"we have identified **${savings:,.0f}/month** in optimization opportunities "
                f"(**${savings * 12:,.0f}/year**). "
                f"This {'exceeds' if pct >= target_pct else 'approaches'} your "
                f"**{target_pct}%** reduction target.{constraint_text}\n\n"
                f"The recommended plan focuses on **low-risk, high-impact** actions including "
                f"right-sizing non-production compute, expanding Savings Plan coverage, "
                f"implementing S3 storage optimization, and removing idle resources. "
                f"**83% of identified savings** come from actions that require no application code changes "
                f"and can be implemented within 1-2 weeks.\n\n"
                f"Key risk mitigation: all recommended first-phase actions target "
                f"non-production environments or are fully reversible, ensuring "
                f"**zero impact to customer-facing systems**."
            )
        elif audience == "finance":
            return (
                f"## Financial Impact: ${savings * 12:,.0f} annualized savings opportunity\n\n"
                f"Current run-rate: **${baseline:,.0f}/month** (${baseline * 12:,.0f}/year). "
                f"Identified optimization potential: **${savings:,.0f}/month** ({pct:.1f}% reduction). "
                f"Projected Q2 savings if actions are implemented by April 1: **${savings * 3:,.0f}**.{constraint_text}\n\n"
                f"Savings breakdown by category:\n"
                f"- **Commitment optimization** (Savings Plans): ~$31,200/month\n"
                f"- **Right-sizing non-prod compute**: ~$22,700/month\n"
                f"- **Idle resource removal**: ~$14,760/month\n"
                f"- **Storage optimization**: ~$12,480/month\n"
                f"- **Scheduling automation**: ~$16,950/month\n"
                f"- **Other optimizations**: ~$13,310/month\n\n"
                f"No CapEx required. All actions are OpEx optimization. "
                f"Savings Plan commitment requires finance approval for 1-year term."
            )
        else:  # engineering
            return (
                f"## Technical Optimization Plan: {pct:.1f}% cost reduction identified\n\n"
                f"Analysis of **${baseline:,.0f}/month** across 50+ AWS services identified "
                f"**8 actionable optimizations** totaling **${savings:,.0f}/month** in savings.{constraint_text}\n\n"
                f"**Immediate wins (no code changes):**\n"
                f"- Right-size 47 over-provisioned EC2 instances in dev/test (m5.2xlarge → m5.large)\n"
                f"- Delete 23 idle RDS instances (zero connections in 30 days)\n"
                f"- Enable S3 Intelligent-Tiering on 8 cold data buckets (62TB)\n\n"
                f"**Scheduled actions:**\n"
                f"- Implement EKS cluster scheduling for non-prod (stop outside 8am-8pm CT)\n"
                f"- Lambda memory right-sizing across 120+ functions\n\n"
                f"All first-phase actions are reversible and target non-production workloads."
            )

    def _mock_narrative_sections(
        self, audience: str, data: Dict[str, Any]
    ) -> List[Dict[str, str]]:
        sections = [
            {
                "title": "Current Cost Baseline",
                "content": (
                    "Your AWS environment is running at **$847,320/month** "
                    "($10.2M annualized) across 50+ services. "
                    "**EC2 accounts for 40%** of total spend, followed by RDS (15%), "
                    "S3 (10%), and EKS (8%). Month-over-month growth is **1.8%**, "
                    "driven primarily by EKS adoption and increased Lambda usage.\n\n"
                    "**60% of spend is production**, 20% development, 12% staging, "
                    "with the remaining 8% split between test and sandbox environments."
                ),
                "icon": "💰",
                "order": 1,
            },
            {
                "title": "Cost Growth Trajectory",
                "content": (
                    "At the current **1.8% monthly growth rate**, your projected spend will reach "
                    "**$877K/month by Q3 2026** without intervention. Key growth drivers:\n\n"
                    "- **EKS adoption** (+12% QoQ as teams migrate from EC2)\n"
                    "- **Lambda execution volume** (+8% QoQ from new microservices)\n"
                    "- **Data transfer costs** (+6% QoQ from cross-region replication)\n\n"
                    "Implementing the recommended savings plan would **flatten the growth curve** "
                    "and bring monthly spend to approximately **$736K** — a net reduction "
                    "despite ongoing organic growth."
                ),
                "icon": "📈",
                "order": 2,
            },
            {
                "title": "Risk Assessment",
                "content": (
                    "The recommended plan has been designed for **minimal operational risk**:\n\n"
                    "| Risk Factor | Assessment |\n"
                    "|---|---|\n"
                    "| Production impact | ✅ None — all phase-1 actions target non-prod or are reversible |\n"
                    "| Implementation complexity | ✅ Low — 83% of savings require no code changes |\n"
                    "| Rollback capability | ✅ High — 6 of 8 actions are fully reversible |\n"
                    "| Timeline risk | ⚠️ Medium — Lambda tuning requires staged rollout |\n"
                    "| Commitment risk | ⚠️ Medium — Savings Plan requires 1-year term |\n\n"
                    "Recommended approach: implement non-commitment actions first (weeks 1-3), "
                    "validate savings trajectory, then approve Savings Plan purchase (week 4)."
                ),
                "icon": "🛡️",
                "order": 3,
            },
        ]

        if audience == "finance":
            sections.append({
                "title": "Budget Impact Analysis",
                "content": (
                    "**Q2 2026 projected impact** (assuming April 1 implementation):\n\n"
                    "| Metric | Current | After Optimization |\n"
                    "|---|---|---|\n"
                    "| Monthly AWS spend | $847,320 | $736,020 |\n"
                    "| Quarterly AWS spend | $2,541,960 | $2,208,060 |\n"
                    "| Annual run-rate | $10,167,840 | $8,832,240 |\n"
                    "| Savings vs. budget | — | $333,900/quarter |\n\n"
                    "The Savings Plan commitment ($120K/year additional) "
                    "delivers a **2.6x ROI** based on projected savings of $374,400/year."
                ),
                "icon": "📊",
                "order": 4,
            })

        return sections
