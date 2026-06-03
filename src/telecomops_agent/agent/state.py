"""AgentState TypedDict and supporting models for the LangGraph workflow.

Defines the full state schema used by the telecom fault diagnosis workflow,
including structured evidence, diagnosis results, and tool traces.
"""

from typing import Annotated, Any, Dict, List, Literal, Optional, TypedDict

from pydantic import BaseModel, Field


# ---------------------------------------------------------------------------
# Structured helper models
# ---------------------------------------------------------------------------


class TimeRange(BaseModel):
    """A time window with optional start/end timestamps (ISO 8601 strings)."""

    start: Optional[str] = None
    end: Optional[str] = None


class ToolCallRecord(BaseModel):
    """Execution record for a single tool call during the workflow."""

    tool_name: str
    input: Dict[str, Any] = Field(default_factory=dict)
    output: Optional[Any] = None
    error: Optional[str] = None
    latency_ms: Optional[float] = None


class EvidenceItem(BaseModel):
    """A single piece of evidence from a tool or knowledge source."""

    source: Literal["rag", "sql", "graph", "case", "oss"]
    title: str
    content: str
    score: Optional[float] = None
    metadata: Dict[str, Any] = Field(default_factory=dict)


class DiagnosisResult(BaseModel):
    """Structured diagnosis produced by the reasoner node."""

    symptoms: List[str] = Field(default_factory=list)
    possible_causes: List[str] = Field(default_factory=list)
    recommended_actions: List[str] = Field(default_factory=list)
    confidence: Literal["low", "medium", "high"] = "medium"
    missing_evidence: List[str] = Field(default_factory=list)


# ---------------------------------------------------------------------------
# AgentState — the full TypedDict schema shared across all LangGraph nodes
# ---------------------------------------------------------------------------


class AgentState(TypedDict, total=False):
    """LangGraph agent state for telecom fault diagnosis.

    Fields are optional by default (total=False) so each node only
    needs to return the subset of keys it modifies.
    """

    # ---- Raw user input ----
    query: str
    session_id: str
    user_id: Optional[str]

    # ---- Parsed context / intent ----
    intent: str
    entities: Dict[str, Any]
    site_id: Optional[str]
    cell_id: Optional[str]
    time_range: Optional[TimeRange]

    # ---- Planning and routing ----
    plan: List[str]
    next_tools: List[str]
    current_step: str

    # ---- Tool execution traces ----
    tool_calls: List[ToolCallRecord]
    tool_errors: List[str]
    retry_count: int

    # ---- Evidence buckets ----
    rag_evidence: List[EvidenceItem]
    sql_evidence: List[EvidenceItem]
    graph_evidence: List[EvidenceItem]
    case_evidence: List[EvidenceItem]
    fused_evidence: List[EvidenceItem]

    # ---- Reasoning output ----
    diagnosis: Optional[DiagnosisResult]
    report_markdown: Optional[str]

    # ---- Control flags ----
    enough_evidence: bool
    needs_human_review: bool
    final_answer: Optional[str]
