# FastAPI API Design

## 1. Design Goal

The API exposes the TelecomOps-Agent as a service.

Main capabilities:

- run one-shot fault diagnosis
- run multi-turn chat diagnosis
- query raw tools for debugging
- retrieve generated reports
- collect user feedback
- run evaluation cases

---

## 2. Suggested File Layout

```text
src/telecomops_agent/api/
├── main.py
├── routes.py
├── schemas.py
├── dependencies.py
└── errors.py
```

---

## 3. Pydantic Models

```python
from datetime import datetime
from enum import Enum
from typing import Any, Dict, List, Optional
from pydantic import BaseModel, Field


class ConfidenceLevel(str, Enum):
    low = "low"
    medium = "medium"
    high = "high"


class TimeRange(BaseModel):
    start: Optional[datetime] = None
    end: Optional[datetime] = None


class DiagnosisRequest(BaseModel):
    query: str = Field(..., description="Natural language operation question")
    session_id: Optional[str] = None
    user_id: Optional[str] = None
    site_id: Optional[str] = None
    cell_id: Optional[str] = None
    time_range: Optional[TimeRange] = None
    language: str = "zh"
    debug: bool = False


class EvidenceItem(BaseModel):
    source: str
    title: str
    content: str
    score: Optional[float] = None
    metadata: Dict[str, Any] = Field(default_factory=dict)


class ToolTrace(BaseModel):
    tool_name: str
    input: Dict[str, Any]
    output_summary: Optional[str] = None
    error: Optional[str] = None
    latency_ms: Optional[float] = None


class DiagnosisResult(BaseModel):
    symptoms: List[str] = Field(default_factory=list)
    possible_causes: List[str] = Field(default_factory=list)
    recommended_actions: List[str] = Field(default_factory=list)
    confidence: ConfidenceLevel = ConfidenceLevel.medium
    risk_notes: List[str] = Field(default_factory=list)


class DiagnosisResponse(BaseModel):
    query_id: str
    session_id: Optional[str] = None
    answer: str
    result: DiagnosisResult
    evidence: List[EvidenceItem] = Field(default_factory=list)
    tool_traces: List[ToolTrace] = Field(default_factory=list)
    latency_ms: Optional[float] = None
    needs_human_review: bool = False


class ChatMessage(BaseModel):
    role: str
    content: str


class ChatRequest(BaseModel):
    session_id: str
    messages: List[ChatMessage]
    site_id: Optional[str] = None
    cell_id: Optional[str] = None
    time_range: Optional[TimeRange] = None
    debug: bool = False


class ToolQueryRequest(BaseModel):
    query: str
    site_id: Optional[str] = None
    cell_id: Optional[str] = None
    time_range: Optional[TimeRange] = None
    limit: int = 10


class SQLToolRequest(BaseModel):
    task: str
    site_id: Optional[str] = None
    cell_id: Optional[str] = None
    time_range: Optional[TimeRange] = None
    safe_mode: bool = True


class GraphToolRequest(BaseModel):
    task: str
    entities: Dict[str, Any] = Field(default_factory=dict)
    limit: int = 10


class FeedbackRequest(BaseModel):
    query_id: str
    rating: int = Field(..., ge=1, le=5)
    is_correct: Optional[bool] = None
    comment: Optional[str] = None
```

---

## 4. Routes

### 4.1 Health check

```python
@router.get("/health")
async def health_check():
    return {"status": "ok"}
```

---

### 4.2 One-shot diagnosis

```python
@router.post("/api/v1/diagnose", response_model=DiagnosisResponse)
async def diagnose(request: DiagnosisRequest):
    """
    Run the full LangGraph workflow:
    query → intent → plan → tools → evidence → diagnosis → report.
    """
    result = await agent_app.ainvoke({
        "query": request.query,
        "session_id": request.session_id,
        "user_id": request.user_id,
        "site_id": request.site_id,
        "cell_id": request.cell_id,
        "time_range": request.time_range,
        "debug": request.debug,
    })

    return DiagnosisResponse(
        query_id=result["query_id"],
        session_id=request.session_id,
        answer=result["final_answer"],
        result=result["diagnosis"],
        evidence=result.get("fused_evidence", []),
        tool_traces=result.get("tool_calls", []) if request.debug else [],
        latency_ms=result.get("latency_ms"),
        needs_human_review=result.get("needs_human_review", False),
    )
```

Example request:

```json
{
  "query": "SZ-NS-023-2 最近2小时RSRP下降且掉话率升高，请分析原因并给出排查步骤。",
  "site_id": "SZ-NS-023",
  "cell_id": "SZ-NS-023-2",
  "time_range": {
    "start": "2026-05-01T10:00:00",
    "end": "2026-05-01T12:00:00"
  },
  "debug": true
}
```

---

### 4.3 Multi-turn chat diagnosis

```python
@router.post("/api/v1/chat", response_model=DiagnosisResponse)
async def chat(request: ChatRequest):
    latest_query = request.messages[-1].content

    result = await agent_app.ainvoke({
        "query": latest_query,
        "session_id": request.session_id,
        "messages": [m.model_dump() for m in request.messages],
        "site_id": request.site_id,
        "cell_id": request.cell_id,
        "time_range": request.time_range,
        "debug": request.debug,
    })

    return DiagnosisResponse(
        query_id=result["query_id"],
        session_id=request.session_id,
        answer=result["final_answer"],
        result=result["diagnosis"],
        evidence=result.get("fused_evidence", []),
        tool_traces=result.get("tool_calls", []) if request.debug else [],
        latency_ms=result.get("latency_ms"),
        needs_human_review=result.get("needs_human_review", False),
    )
```

---

### 4.4 RAG search debug endpoint

```python
@router.post("/api/v1/tools/rag/search")
async def rag_search(request: ToolQueryRequest):
    """
    Debug endpoint for document retrieval.
    Not recommended to expose directly in production.
    """
    return await rag_tool.asearch(
        query=request.query,
        limit=request.limit,
    )
```

---

### 4.5 SQL tool debug endpoint

```python
@router.post("/api/v1/tools/sql/query")
async def sql_tool_query(request: SQLToolRequest):
    """
    Generate and execute safe SQL templates for KPI/alarm/parameter queries.
    Production systems should never expose arbitrary SQL execution.
    """
    return await sql_tool.arun(
        task=request.task,
        site_id=request.site_id,
        cell_id=request.cell_id,
        time_range=request.time_range,
        safe_mode=request.safe_mode,
    )
```

---

### 4.6 Graph tool debug endpoint

```python
@router.post("/api/v1/tools/graph/query")
async def graph_tool_query(request: GraphToolRequest):
    """
    Execute graph reasoning query over Neo4j.
    """
    return await graph_tool.arun(
        task=request.task,
        entities=request.entities,
        limit=request.limit,
    )
```

---

### 4.7 Report retrieval

```python
@router.get("/api/v1/reports/{query_id}")
async def get_report(query_id: str):
    report = await report_store.get(query_id)
    if report is None:
        raise HTTPException(status_code=404, detail="Report not found")
    return report
```

---

### 4.8 Feedback

```python
@router.post("/api/v1/feedback")
async def submit_feedback(request: FeedbackRequest):
    await feedback_store.save(
        query_id=request.query_id,
        rating=request.rating,
        is_correct=request.is_correct,
        comment=request.comment,
    )
    return {"status": "saved"}
```

---

## 5. `main.py`

```python
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from src.telecomops_agent.api.routes import router


def create_app() -> FastAPI:
    app = FastAPI(
        title="TelecomOps-Agent API",
        description="LangGraph + GraphRAG telecom operation diagnosis agent",
        version="0.1.0",
    )

    app.add_middleware(
        CORSMiddleware,
        allow_origins=["*"],
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    app.include_router(router)

    return app


app = create_app()
```

---

## 6. Error Handling

Recommended error response:

```json
{
  "error_code": "TOOL_EXECUTION_FAILED",
  "message": "SQL KPI query failed.",
  "details": {
    "tool": "sql_kpi_tool",
    "reason": "No KPI rows found for the requested time range."
  },
  "suggestion": "Try expanding the time range or checking the cell_id."
}
```

Common error codes:

| Error Code | Meaning |
|---|---|
| INVALID_REQUEST | Missing required fields |
| UNSUPPORTED_INTENT | Query is outside supported telecom operation scenarios |
| TOOL_EXECUTION_FAILED | Tool call failed |
| INSUFFICIENT_EVIDENCE | Evidence is not enough for reliable diagnosis |
| HUMAN_REVIEW_REQUIRED | The agent cannot safely give a final conclusion |

---

## 7. API Design Notes for Interview

When explaining this API in an interview, emphasize:

1. The external API is simple, but the internal workflow is stateful.
2. Debug endpoints are useful for development and evaluation, but should be protected in production.
3. The final response includes both answer and evidence, which helps reduce hallucination.
4. Feedback is stored for future evaluation and prompt/tool improvement.
5. The API design separates diagnosis, tool debugging, report retrieval, and feedback collection.
