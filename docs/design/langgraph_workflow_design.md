# LangGraph Workflow Design

## 1. Design Goal

The workflow models telecom fault diagnosis as an explicit state machine.

Instead of using a single prompt such as:

```text
User Question → LLM → Final Answer
```

the system uses:

```text
User Question → Intent → Entity Extraction → Planning → Tool Routing
→ Evidence Collection → Diagnosis → Reflection → Report
```

This makes the Agent easier to debug, evaluate, and extend.

---

## 2. Agent State

```python
from typing import Annotated, Any, Dict, List, Literal, Optional, TypedDict
from pydantic import BaseModel, Field


class TimeRange(BaseModel):
    start: Optional[str] = None
    end: Optional[str] = None


class ToolCallRecord(BaseModel):
    tool_name: str
    input: Dict[str, Any]
    output: Optional[Any] = None
    error: Optional[str] = None
    latency_ms: Optional[float] = None


class EvidenceItem(BaseModel):
    source: Literal["rag", "sql", "graph", "case", "oss"]
    title: str
    content: str
    score: Optional[float] = None
    metadata: Dict[str, Any] = Field(default_factory=dict)


class DiagnosisResult(BaseModel):
    symptoms: List[str] = Field(default_factory=list)
    possible_causes: List[str] = Field(default_factory=list)
    recommended_actions: List[str] = Field(default_factory=list)
    confidence: Literal["low", "medium", "high"] = "medium"
    missing_evidence: List[str] = Field(default_factory=list)


class AgentState(TypedDict, total=False):
    # Raw user input
    query: str
    session_id: str
    user_id: Optional[str]

    # Parsed context
    intent: str
    entities: Dict[str, Any]
    site_id: Optional[str]
    cell_id: Optional[str]
    time_range: Optional[TimeRange]

    # Planning and routing
    plan: List[str]
    next_tools: List[str]
    current_step: str

    # Tool execution traces
    tool_calls: List[ToolCallRecord]
    tool_errors: List[str]
    retry_count: int

    # Evidence
    rag_evidence: List[EvidenceItem]
    sql_evidence: List[EvidenceItem]
    graph_evidence: List[EvidenceItem]
    case_evidence: List[EvidenceItem]
    fused_evidence: List[EvidenceItem]

    # Reasoning output
    diagnosis: Optional[DiagnosisResult]
    report_markdown: Optional[str]

    # Control flags
    enough_evidence: bool
    needs_human_review: bool
    final_answer: Optional[str]
```

---

## 3. Nodes

### 3.1 `input_guard`

Purpose:

- reject unsafe or irrelevant queries
- normalize language
- remove sensitive fields if needed
- initialize retry count and trace list

Input:

```python
AgentState(query=...)
```

Output:

```python
{
  "query": normalized_query,
  "retry_count": 0,
  "tool_calls": [],
  "tool_errors": []
}
```

---

### 3.2 `intent_classifier`

Classifies query type.

Possible intents:

```text
kpi_query
alarm_query
fault_diagnosis
parameter_check
handover_analysis
coverage_analysis
report_generation
general_qa
```

Example:

```text
"RSRP suddenly dropped and call drop rate increased"
→ fault_diagnosis
```

---

### 3.3 `entity_extractor`

Extracts telecom entities:

```python
{
  "site_id": "SZ-NS-023",
  "cell_id": "SZ-NS-023-2",
  "kpi_names": ["rsrp", "call_drop_rate"],
  "alarm_names": ["VSWR_HIGH"],
  "time_range": {
    "start": "2026-05-01T10:00:00",
    "end": "2026-05-01T12:00:00"
  }
}
```

---

### 3.4 `planner`

Generates a high-level plan.

Example plan:

```python
[
  "Check KPI trend for the specified cell and time range.",
  "Search related alarms around the incident time.",
  "Query knowledge graph for root causes linked to RSRP drop and call drop rate.",
  "Retrieve similar historical cases.",
  "Fuse evidence and generate troubleshooting report."
]
```

---

### 3.5 `tool_router`

Chooses which tools to call.

Routing rule examples:

| Condition | Tool |
|---|---|
| Query asks KPI trend | PostgreSQL KPI Tool |
| Query mentions alarm | SQL Tool + Graph Tool |
| Query asks root cause | Neo4j Graph Tool |
| Query asks SOP or explanation | RAG Tool |
| Query asks similar incident | Case Search Tool |

Output example:

```python
{
  "next_tools": ["sql_kpi_tool", "graph_fault_tool", "case_search_tool"]
}
```

---

### 3.6 `sql_query_node`

Queries PostgreSQL for KPI, alarm, parameter, ticket, and change records.

Typical SQL tasks:

- KPI trend before and after incident
- alarm records around incident
- parameter changes before incident
- historical trouble tickets

---

### 3.7 `graph_query_node`

Queries Neo4j for multi-hop reasoning.

Typical Cypher tasks:

```cypher
MATCH path = (:KPI {name: "RSRP"})
  -[:INDICATES]->(:FaultMode)
  -[:CAUSED_BY]->(:RootCause)
  -[:RESOLVED_BY]->(:Action)
RETURN path
LIMIT 5;
```

---

### 3.8 `rag_retriever_node`

Retrieves SOPs, troubleshooting manuals, and network optimization documents.

Typical retrieval queries:

```text
"RSRP drop VSWR high troubleshooting"
"call drop rate increase root cause wireless network"
"antenna feeder fault diagnosis SOP"
```

---

### 3.9 `case_search_node`

Retrieves similar historical cases.

Similarity dimensions:

- same KPI anomaly
- same alarm pattern
- same vendor
- same site type
- similar time sequence

---

### 3.10 `evidence_fusion`

Combines evidence from different sources.

Fusion priority:

```text
1. Direct KPI/Alarm evidence from SQL
2. Multi-hop graph evidence from Neo4j
3. Historical cases
4. SOP/RAG documents
5. LLM prior knowledge
```

The final report must cite concrete evidence and avoid unsupported claims.

---

### 3.11 `diagnosis_reasoner`

Generates structured diagnosis:

```python
{
  "symptoms": [
    "RSRP dropped from -88 dBm to -106 dBm.",
    "Call drop rate increased from 0.6% to 3.8%.",
    "VSWR_HIGH alarm appeared 20 minutes before KPI degradation."
  ],
  "possible_causes": [
    "Antenna feeder issue",
    "Power amplifier abnormality",
    "Recent radio parameter change"
  ],
  "recommended_actions": [
    "Check feeder and antenna connection.",
    "Verify VSWR and power alarm.",
    "Compare parameter change history and consider rollback."
  ],
  "confidence": "high"
}
```

---

### 3.12 `reflection_node`

Checks whether the evidence is sufficient.

Reflection questions:

```text
1. Do we have KPI evidence?
2. Do we have alarm evidence?
3. Do we have graph reasoning path?
4. Do we have similar historical cases?
5. Are there conflicting signals?
6. Does the final conclusion cite evidence?
```

Conditional output:

```python
{
  "enough_evidence": True,
  "missing_evidence": []
}
```

or:

```python
{
  "enough_evidence": False,
  "missing_evidence": ["No alarm record found. Need to query parameter change history."]
}
```

---

### 3.13 `report_generator`

Generates final report in Markdown or JSON.

Report sections:

```text
1. Query Summary
2. Observed Symptoms
3. Evidence Table
4. Root Cause Analysis
5. Recommended Actions
6. Confidence and Risk
7. Next Steps
```

---

## 4. Edges

```python
from langgraph.graph import StateGraph, END

workflow = StateGraph(AgentState)

workflow.add_node("input_guard", input_guard)
workflow.add_node("intent_classifier", intent_classifier)
workflow.add_node("entity_extractor", entity_extractor)
workflow.add_node("planner", planner)
workflow.add_node("tool_router", tool_router)
workflow.add_node("sql_query", sql_query_node)
workflow.add_node("graph_query", graph_query_node)
workflow.add_node("rag_retriever", rag_retriever_node)
workflow.add_node("case_search", case_search_node)
workflow.add_node("evidence_fusion", evidence_fusion)
workflow.add_node("diagnosis_reasoner", diagnosis_reasoner)
workflow.add_node("reflection", reflection_node)
workflow.add_node("report_generator", report_generator)

workflow.set_entry_point("input_guard")

workflow.add_edge("input_guard", "intent_classifier")
workflow.add_edge("intent_classifier", "entity_extractor")
workflow.add_edge("entity_extractor", "planner")
workflow.add_edge("planner", "tool_router")

workflow.add_conditional_edges(
    "tool_router",
    route_tools,
    {
        "sql_query": "sql_query",
        "graph_query": "graph_query",
        "rag_retriever": "rag_retriever",
        "case_search": "case_search",
        "evidence_fusion": "evidence_fusion",
    },
)

workflow.add_edge("sql_query", "evidence_fusion")
workflow.add_edge("graph_query", "evidence_fusion")
workflow.add_edge("rag_retriever", "evidence_fusion")
workflow.add_edge("case_search", "evidence_fusion")

workflow.add_edge("evidence_fusion", "diagnosis_reasoner")
workflow.add_edge("diagnosis_reasoner", "reflection")

workflow.add_conditional_edges(
    "reflection",
    should_continue,
    {
        "retry": "tool_router",
        "report": "report_generator",
        "human_review": "report_generator",
    },
)

workflow.add_edge("report_generator", END)

app = workflow.compile()
```

---

## 5. Conditional Routing Functions

```python
def route_tools(state: AgentState) -> str:
    next_tools = state.get("next_tools", [])

    if "sql_kpi_tool" in next_tools or "sql_alarm_tool" in next_tools:
        return "sql_query"

    if "graph_fault_tool" in next_tools:
        return "graph_query"

    if "rag_tool" in next_tools:
        return "rag_retriever"

    if "case_search_tool" in next_tools:
        return "case_search"

    return "evidence_fusion"


def should_continue(state: AgentState) -> str:
    if state.get("needs_human_review"):
        return "human_review"

    if state.get("enough_evidence"):
        return "report"

    if state.get("retry_count", 0) >= 2:
        return "human_review"

    return "retry"
```

---

## 6. Failure Handling

| Failure | Strategy |
|---|---|
| SQL generation error | Use SQL template or ask LLM to repair SQL |
| Empty SQL result | Expand time range or query related cell/site |
| Neo4j no path found | Fall back to RAG and case retrieval |
| RAG low score | Rewrite query and retrieve again |
| Conflicting evidence | Mark confidence as medium/low and request human review |
| Too many retries | Generate partial report with missing evidence |

---

## 7. MVP Implementation Order

1. Define `AgentState`.
2. Implement deterministic mock tools first.
3. Build LangGraph nodes with simple rule-based logic.
4. Replace rule-based parts with LLM calls.
5. Add tracing and evaluation.
6. Add frontend demo.
