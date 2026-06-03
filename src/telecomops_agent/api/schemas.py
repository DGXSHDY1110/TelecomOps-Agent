"""Pydantic schemas for API request and response models."""

from datetime import datetime
from enum import Enum
from typing import Any

from pydantic import BaseModel, Field


# ---------------------------------------------------------------------------
# Enums
# ---------------------------------------------------------------------------

class ConfidenceLevel(str, Enum):
    """Diagnosis confidence level."""

    low = "low"
    medium = "medium"
    high = "high"


# ---------------------------------------------------------------------------
# Shared / utility models
# ---------------------------------------------------------------------------

class TimeRange(BaseModel):
    """A time window with optional start and end."""

    start: datetime | None = None
    end: datetime | None = None


class EvidenceItem(BaseModel):
    """A single piece of evidence from a tool or knowledge source."""

    source: str
    title: str
    content: str
    score: float | None = None
    metadata: dict[str, Any] = Field(default_factory=dict)


class ToolTrace(BaseModel):
    """Execution trace for a single tool call (returned when debug=True)."""

    tool_name: str
    input: dict[str, Any]
    output_summary: str | None = None
    error: str | None = None
    latency_ms: float | None = None


# ---------------------------------------------------------------------------
# Diagnosis request / response
# ---------------------------------------------------------------------------

class DiagnosisRequest(BaseModel):
    """Request body for the one-shot diagnosis endpoint."""

    query: str = Field(..., description="Natural language operation question")
    session_id: str | None = None
    user_id: str | None = None
    site_id: str | None = None
    cell_id: str | None = None
    time_range: TimeRange | None = None
    language: str = "zh"
    debug: bool = False


class DiagnosisResult(BaseModel):
    """Structured diagnosis result produced by the agent."""

    symptoms: list[str] = Field(default_factory=list)
    possible_causes: list[str] = Field(default_factory=list)
    recommended_actions: list[str] = Field(default_factory=list)
    confidence: ConfidenceLevel = ConfidenceLevel.medium
    risk_notes: list[str] = Field(default_factory=list)


class DiagnosisResponse(BaseModel):
    """Full response from the diagnosis endpoint."""

    query_id: str
    session_id: str | None = None
    answer: str
    result: DiagnosisResult
    evidence: list[EvidenceItem] = Field(default_factory=list)
    tool_traces: list[ToolTrace] = Field(default_factory=list)
    latency_ms: float | None = None
    needs_human_review: bool = False


# ---------------------------------------------------------------------------
# Feedback request / response
# ---------------------------------------------------------------------------

class FeedbackRequest(BaseModel):
    """User feedback for a specific diagnosis query."""

    query_id: str
    rating: int = Field(..., ge=1, le=5)
    is_correct: bool | None = None
    comment: str | None = None


class FeedbackResponse(BaseModel):
    """Acknowledgement of received feedback."""

    status: str
    query_id: str


# ---------------------------------------------------------------------------
# Generic response models
# ---------------------------------------------------------------------------

class HealthResponse(BaseModel):
    """Response model for the health check endpoint."""

    status: str
    service: str


class ErrorResponse(BaseModel):
    """Standard error response model."""

    error_code: str
    message: str
    details: dict | None = None
    suggestion: str | None = None
