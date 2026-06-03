"""API routes — health check, diagnosis, and feedback endpoints."""

import uuid
from datetime import datetime, timedelta, timezone

from fastapi import APIRouter

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
# One-shot diagnosis (mock implementation — no real tools / LLM / DB)
# ---------------------------------------------------------------------------


def _build_mock_diagnosis(request: DiagnosisRequest) -> DiagnosisResponse:
    """Build a deterministic mock diagnosis response for development / testing."""

    query_id = uuid.uuid4().hex
    now = datetime.now(timezone.utc)

    # --- Mock evidence (at least one SQL/KPI and one Graph/KG item) ---

    evidence_sql = EvidenceItem(
        source="sql",
        title="KPI Trend: RSRP & Call Drop Rate",
        content=(
            f"Cell {request.cell_id or 'SZ-NS-023-2'}: "
            "RSRP dropped from -88 dBm to -106 dBm between "
            f"{(now - timedelta(hours=2)).isoformat(timespec='minutes')} and {now.isoformat(timespec='minutes')}. "
            "Call drop rate increased from 0.6% to 3.8% in the same window. "
            "PRB utilization remained stable at 62%."
        ),
        score=0.95,
        metadata={
            "table": "cell_kpi_15min",
            "rows": 8,
            "kpi_names": ["rsrp", "call_drop_rate", "prb_utilization"],
        },
    )

    evidence_graph = EvidenceItem(
        source="graph",
        title="Knowledge Graph: RSRP Drop → VSWR_HIGH → Feeder Fault",
        content=(
            "Multi-hop path found in telecom knowledge graph: "
            "(KPI:RSRP_DROP) -[:INDICATES]-> (FaultMode:VSWR_HIGH) "
            "-[:CAUSED_BY]-> (RootCause:AntennaFeederIssue) "
            "-[:RESOLVED_BY]-> (Action:CheckFeederConnection). "
            "Also matches historical case #HC-2024-0815 with 0.87 similarity."
        ),
        score=0.88,
        metadata={
            "graph_path_length": 4,
            "matched_case_id": "HC-2024-0815",
            "similarity": 0.87,
        },
    )

    # --- Diagnosis result ---

    result = DiagnosisResult(
        symptoms=[
            f"RSRP decreased from -88 dBm to -106 dBm on cell {request.cell_id or 'SZ-NS-023-2'}.",
            "Call drop rate increased from 0.6% to 3.8%.",
            "VSWR_HIGH alarm detected 20 minutes before KPI degradation.",
        ],
        possible_causes=[
            "Antenna feeder issue (VSWR anomaly).",
            "Power amplifier abnormality.",
            "Recent radio parameter change causing coverage degradation.",
        ],
        recommended_actions=[
            "Check current alarms and VSWR values on site.",
            "Compare KPI trends before and after recent parameter changes.",
            "Verify neighboring cell handover success rate.",
            "Dispatch field engineer if VSWR_HIGH persists after remote checks.",
        ],
        confidence=ConfidenceLevel.high,
        risk_notes=[
            "If VSWR continues rising, risk of cell outage within 4 hours.",
            "Neighbor cells may experience temporary load increase due to handover retries.",
        ],
    )

    # --- Tool traces (only populated when debug=True) ---

    tool_traces: list[ToolTrace] = []
    if request.debug:
        tool_traces = [
            ToolTrace(
                tool_name="sql_kpi_tool",
                input={
                    "cell_id": request.cell_id,
                    "time_range": request.time_range.model_dump() if request.time_range else None,
                    "kpi_names": ["rsrp", "call_drop_rate"],
                },
                output_summary="Retrieved 8 rows of 15-min KPI data.",
                latency_ms=42.3,
            ),
            ToolTrace(
                tool_name="graph_fault_tool",
                input={"kpi_name": "RSRP_DROP", "alarm_name": "VSWR_HIGH"},
                output_summary="Found 1 multi-hop reasoning path (length 4).",
                latency_ms=87.1,
            ),
            ToolTrace(
                tool_name="case_search_tool",
                input={"symptoms": ["RSRP drop", "call drop rate increase", "VSWR_HIGH"]},
                output_summary="Matched 3 historical cases, top similarity 0.87.",
                latency_ms=125.6,
            ),
        ]

    # --- Build final response ---

    answer = (
        "## 故障诊断报告\n\n"
        "### 1. 观察到的症状\n"
        f"- 小区 **{request.cell_id or 'SZ-NS-023-2'}** 在最近 2 小时内 RSRP 从 -88 dBm 下降至 -106 dBm。\n"
        "- 掉话率从 0.6% 上升至 3.8%。\n"
        "- 检测到 VSWR_HIGH 告警，出现在 KPI 劣化前约 20 分钟。\n\n"
        "### 2. 可能的根因\n"
        "- **天馈系统故障**（VSWR 异常指向馈线/天线连接问题）。\n"
        "- **功放异常**（功率放大器性能下降）。\n"
        "- **最近射频参数变更**（可能引起覆盖收缩）。\n\n"
        "### 3. 建议排查步骤\n"
        "1. 检查当前告警和 VSWR 值。\n"
        "2. 对比参数变更前后的 KPI 趋势。\n"
        "3. 验证邻区切换成功率。\n"
        "4. 如硬件告警持续，安排现场工程师上站检查。\n\n"
        "### 4. 置信度\n"
        "- **高** — KPI 趋势、告警记录和历史案例证据一致。\n\n"
        "### 5. 风险提示\n"
        "- 若 VSWR 继续恶化，4 小时内存在断站风险。\n"
        "- 邻区可能因切换重试出现瞬时负载升高。\n"
    )

    return DiagnosisResponse(
        query_id=query_id,
        session_id=request.session_id,
        answer=answer,
        result=result,
        evidence=[evidence_sql, evidence_graph],
        tool_traces=tool_traces,
        latency_ms=312.5,
        needs_human_review=False,
    )


@router.post("/api/v1/diagnose", response_model=DiagnosisResponse)
async def diagnose(request: DiagnosisRequest):
    """Run diagnosis (mock implementation — returns deterministic fake result).

    In later milestones this will invoke the real LangGraph workflow with
    SQL / Neo4j / RAG tools.
    """
    return _build_mock_diagnosis(request)


# ---------------------------------------------------------------------------
# Feedback (mock implementation — no database)
# ---------------------------------------------------------------------------


@router.post("/api/v1/feedback", response_model=FeedbackResponse)
async def submit_feedback(request: FeedbackRequest):
    """Submit user feedback for a diagnosis (mock — no persistence yet).

    Pydantic validates rating is between 1 and 5 automatically via Field(ge=1, le=5).
    """
    return FeedbackResponse(status="saved", query_id=request.query_id)
