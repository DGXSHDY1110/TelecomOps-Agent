"""API routes — health check, diagnosis, and feedback endpoints."""

import time
import uuid
from datetime import datetime, timezone

from fastapi import APIRouter

from src.telecomops_agent.agent.graph import agent_app
from src.telecomops_agent.api.schemas import (
    ConfidenceLevel,
    DiagnosisRequest,
    DiagnosisResponse,
    DiagnosisResult,
    EvidenceItem,
    FeedbackRequest,
    FeedbackResponse,
    ToolTrace,
)

router = APIRouter()

# ---------------------------------------------------------------------------
# Health check
# ---------------------------------------------------------------------------


@router.get("/health")
async def health_check():
    """Health check endpoint — verifies the API service is running."""
    return {"status": "ok", "service": "telecomops-agent"}


# ---------------------------------------------------------------------------
# One-shot diagnosis — delegates to the LangGraph workflow
# ---------------------------------------------------------------------------


def _convert_confidence(value: str) -> ConfidenceLevel:
    """Normalize a confidence label into the API ConfidenceLevel enum."""
    try:
        return ConfidenceLevel(value)
    except ValueError:
        return ConfidenceLevel.medium


@router.post("/api/v1/diagnose", response_model=DiagnosisResponse)
async def diagnose(request: DiagnosisRequest):
    """Run the full LangGraph workflow and return a structured diagnosis.

    Internally executes: input_guard → intent_classifier →
    entity_extractor → planner → tool_router → tool nodes →
    evidence_fusion → diagnosis_reasoner → reflection →
    report_generator.
    """
    t0 = time.monotonic()
    query_id = uuid.uuid4().hex

    # Build the initial agent state from the API request
    initial_state = {
        "query": request.query,
        "session_id": request.session_id or query_id[:12],
        "user_id": request.user_id,
        "site_id": request.site_id,
        "cell_id": request.cell_id,
        "time_range": (
            {
                "start": request.time_range.start.isoformat() if request.time_range and request.time_range.start else None,
                "end": request.time_range.end.isoformat() if request.time_range and request.time_range.end else None,
            }
            if request.time_range
            else None
        ),
    }

    # Run the workflow
    result = await agent_app.ainvoke(initial_state)

    # ---- Map agent state back to API response models ----

    # Evidence mapping: agent EvidenceItem → API EvidenceItem
    fused = result.get("fused_evidence", [])
    evidence = [
        EvidenceItem(
            source=ei.source,
            title=ei.title,
            content=ei.content,
            score=ei.score,
            metadata=ei.metadata,
        )
        for ei in fused
    ]

    # Tool traces mapping (only when debug=True)
    tool_traces: list[ToolTrace] = []
    if request.debug:
        for tc in result.get("tool_calls", []):
            tool_traces.append(
                ToolTrace(
                    tool_name=tc.tool_name,
                    input=tc.input,
                    output_summary=str(tc.output)[:200] if tc.output else None,
                    error=tc.error,
                    latency_ms=tc.latency_ms,
                )
            )

    # Diagnosis result mapping
    agent_diag = result.get("diagnosis")
    if agent_diag is not None:
        api_diag = DiagnosisResult(
            symptoms=agent_diag.symptoms,
            possible_causes=agent_diag.possible_causes,
            recommended_actions=agent_diag.recommended_actions,
            confidence=_convert_confidence(agent_diag.confidence),
            risk_notes=[],
        )
    else:
        api_diag = DiagnosisResult(
            symptoms=[],
            possible_causes=[],
            recommended_actions=[],
            confidence=ConfidenceLevel.low,
        )

    latency_ms = round((time.monotonic() - t0) * 1000, 1)

    return DiagnosisResponse(
        query_id=query_id,
        session_id=request.session_id,
        answer=result.get("final_answer", ""),
        result=api_diag,
        evidence=evidence,
        tool_traces=tool_traces,
        latency_ms=latency_ms,
        needs_human_review=result.get("needs_human_review", False),
    )


# ---------------------------------------------------------------------------
# Feedback (mock implementation — no database)
# ---------------------------------------------------------------------------


@router.post("/api/v1/feedback", response_model=FeedbackResponse)
async def submit_feedback(request: FeedbackRequest):
    """Submit user feedback for a diagnosis (mock — no persistence yet).

    Pydantic validates rating is between 1 and 5 automatically via Field(ge=1, le=5).
    """
    return FeedbackResponse(status="saved", query_id=request.query_id)
