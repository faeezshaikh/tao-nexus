"""
TAO Nexus — FastAPI router.

Exposes the Nexus analysis API at /api/v1/nexus/*.
"""
import logging
from fastapi import APIRouter, HTTPException

from .schemas import NexusAnalyzeRequest, NexusAnalyzeResponse
from .service import NexusService

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/v1/nexus", tags=["TAO Nexus"])

# Singleton service instance
_service = NexusService()


@router.get("/health")
async def nexus_health():
    """TAO Nexus health check."""
    return {
        "status": "healthy",
        "service": "TAO Nexus",
        "mock_mode": _service.use_mock,
    }


@router.post("/analyze", response_model=NexusAnalyzeResponse)
async def analyze(request: NexusAnalyzeRequest) -> NexusAnalyzeResponse:
    """
    Run a TAO Nexus analysis.

    Accepts a natural-language query about cloud cost optimization,
    along with audience, constraints, and session context.
    Returns a structured response with executive summary, action cards,
    charts, tables, and supporting evidence.
    """
    try:
        logger.info(
            f"Nexus analyze: query='{request.query[:80]}...' "
            f"audience={request.audience.value}"
        )
        response = await _service.analyze(request)
        logger.info(
            f"Nexus analyze complete: {response.processing_time_ms:.0f}ms, "
            f"{len(response.action_cards)} actions, "
            f"${response.scenario.total_monthly_savings:,.0f}/mo savings"
        )
        return response

    except Exception as e:
        logger.error(f"Nexus analyze error: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))
