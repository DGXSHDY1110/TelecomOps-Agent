"""LangGraph workflow nodes for telecom fault diagnosis.

Every node is **deterministic** (rule-based, no LLM calls).
Mock tool nodes return hardcoded evidence that simulates real tool outputs
for an RSRP-drop / call-drop-rate-increase scenario.

Node list (matching the design document):
  input_guard, intent_classifier, entity_extractor, planner, tool_router,
  sql_query_node, graph_query_node, rag_retriever_node, case_search_node,
  evidence_fusion, diagnosis_reasoner, reflection_node, report_generator
"""

import re
import uuid
from datetime import datetime, timedelta, timezone

from src.telecomops_agent.agent.state import (
    AgentState,
    DiagnosisResult,
    EvidenceItem,
    TimeRange,
    ToolCallRecord,
)


# ---------------------------------------------------------------------------
# Supported intents (used by intent_classifier and referenced throughout)
# ---------------------------------------------------------------------------

INTENTS = [
    "kpi_query",
    "alarm_query",
    "fault_diagnosis",
    "parameter_check",
    "handover_analysis",
    "coverage_analysis",
    "report_generation",
    "general_qa",
]

# ---------------------------------------------------------------------------
# 3.1  input_guard
# ---------------------------------------------------------------------------

# Keywords that indicate unsafe / irrelevant queries (deterministic guard)
_UNSAFE_PATTERNS = [
    r"(?i)\bDROP\s+TABLE\b",
    r"(?i)\bDELETE\s+FROM\b",
    r"(?i)\bEXEC\s*\(",
    r"(?i)\bUNION\s+SELECT\b",
    r"(?i)<script",
]


def input_guard(state: AgentState) -> dict:
    """Normalize query, reject unsafe input, initialize control fields.

    Returns a partial state dict with only the keys this node is responsible for.
    """
    raw = (state.get("query") or "").strip()

    # ---- Reject unsafe / irrelevant queries ----
    for pat in _UNSAFE_PATTERNS:
        if re.search(pat, raw):
            return {
                "query": raw,
                "final_answer": "⚠️ 抱歉，您的查询包含不安全的语句或被识别为非运维场景问题，请重新描述故障现象。",
                "needs_human_review": True,
                "diagnosis": DiagnosisResult(
                    symptoms=[],
                    possible_causes=[],
                    recommended_actions=[],
                    confidence="low",
                    missing_evidence=["Unsafe/irrelevant query rejected by input guard."],
                ),
            }

    # ---- Normalize: strip extra whitespace, collapse newlines ----
    normalized = " ".join(raw.split())

    return {
        "query": normalized,
        "retry_count": 0,
        "tool_calls": [],
        "tool_errors": [],
        "rag_evidence": [],
        "sql_evidence": [],
        "graph_evidence": [],
        "case_evidence": [],
        "fused_evidence": [],
        "plan": [],
        "next_tools": [],
        "current_step": "input_guard",
    }


# ---------------------------------------------------------------------------
# 3.2  intent_classifier
# ---------------------------------------------------------------------------

# Ordered keyword → intent rules (first match wins)
_INTENT_RULES: list[tuple[str, str]] = [
    # (keyword/substring, intent)
    ("故障", "fault_diagnosis"),
    ("诊断", "fault_diagnosis"),
    ("分析原因", "fault_diagnosis"),
    ("排查", "fault_diagnosis"),
    ("解决", "fault_diagnosis"),
    ("diagnos", "fault_diagnosis"),  # covers "diagnose", "diagnosis"
    ("troubleshoot", "fault_diagnosis"),
    ("root cause", "fault_diagnosis"),
    ("告警", "alarm_query"),
    ("alarm", "alarm_query"),
    ("KPI", "kpi_query"),
    ("kpi", "kpi_query"),
    ("指标", "kpi_query"),
    ("参数", "parameter_check"),
    ("parameter", "parameter_check"),
    ("切换", "handover_analysis"),
    ("handover", "handover_analysis"),
    ("覆盖", "coverage_analysis"),
    ("coverage", "coverage_analysis"),
    ("信号", "coverage_analysis"),
    ("报告", "report_generation"),
    ("总结", "report_generation"),
]


def intent_classifier(state: AgentState) -> dict:
    """Classify the user query into one of the predefined telecom intents.

    Uses keyword matching (deterministic).  The first matching keyword wins.
    Falls back to ``general_qa`` when no keywords match.
    """
    query = state.get("query", "")
    query_lower = query.lower()

    for keyword, intent in _INTENT_RULES:
        if keyword.lower() in query_lower:
            return {"intent": intent, "current_step": "intent_classifier"}

    return {"intent": "general_qa", "current_step": "intent_classifier"}


# ---------------------------------------------------------------------------
# 3.3  entity_extractor
# ---------------------------------------------------------------------------

# Regex for telecom site / cell IDs
_SITE_RE = re.compile(r"([A-Z]{2,4}-[A-Z]{2,3}-\d{3})")
_CELL_RE = re.compile(r"([A-Z]{2,4}-[A-Z]{2,3}-\d{3}-\d+)")

# KPI name keywords
_KPI_NAMES = {
    "rsrp": "rsrp",
    "sinr": "sinr",
    "掉话率": "call_drop_rate",
    "call drop": "call_drop_rate",
    "通话掉线": "call_drop_rate",
    "接通率": "call_setup_success_rate",
    "prb利用率": "prb_utilization",
    "prb": "prb_utilization",
    "吞吐率": "throughput",
    "throughput": "throughput",
    "rrc连接": "rrc_connection",
    "rrc": "rrc_connection",
    "erab": "erab_drop_rate",
    "切换成功率": "handover_success_rate",
}

# Alarm name keywords
_ALARM_NAMES = {
    "vswr": "VSWR_HIGH",
    "驻波": "VSWR_HIGH",
    "rru": "RRU_FAULT",
    "温度": "TEMPERATURE_HIGH",
    "光模块": "OPTICAL_MODULE_FAULT",
    "power": "POWER_ABNORMAL",
    "功率": "POWER_ABNORMAL",
    "cell outage": "CELL_OUTAGE",
    "断站": "CELL_OUTAGE",
}

# Time-range patterns  e.g. "最近2小时", "过去30分钟", "今天上午"
_TIME_PATTERNS = [
    (re.compile(r"最近\s*(\d+)\s*小时"), lambda m: timedelta(hours=int(m.group(1)))),
    (re.compile(r"最近\s*(\d+)\s*分钟"), lambda m: timedelta(minutes=int(m.group(1)))),
    (re.compile(r"最近\s*(\d+)\s*天"), lambda m: timedelta(days=int(m.group(1)))),
    (re.compile(r"过去\s*(\d+)\s*小时"), lambda m: timedelta(hours=int(m.group(1)))),
    (re.compile(r"最近\s*(\d+)\s*周"), lambda m: timedelta(weeks=int(m.group(1)))),
]


def _parse_time_range(query: str) -> TimeRange | None:
    """Try to extract a time range from natural-language phrases."""
    for pat, delta_fn in _TIME_PATTERNS:
        m = pat.search(query)
        if m:
            delta = delta_fn(m)
            now = datetime.now(timezone.utc)
            start = now - delta
            return TimeRange(
                start=start.strftime("%Y-%m-%dT%H:%M:%S"),
                end=now.strftime("%Y-%m-%dT%H:%M:%S"),
            )
    return None


def entity_extractor(state: AgentState) -> dict:
    """Extract telecom entities (site, cell, KPIs, alarms, time range) from query."""
    query = state.get("query", "")

    # ---- site_id: first SITE_RE match that is not already a CELL_RE match ----
    cells = _CELL_RE.findall(query)
    cell_id = cells[0] if cells else None

    # Derive site_id from cell_id if present, else look for standalone site pattern
    if cell_id:
        # e.g. "SZ-NS-023-2" → "SZ-NS-023"
        site_id = "-".join(cell_id.split("-")[:3])
    else:
        sites = _SITE_RE.findall(query)
        # Exclude any that are actually cell prefixes
        site_id = sites[0] if sites else None

    # ---- kpi_names ----
    kpi_names: list[str] = []
    query_lower = query.lower()
    for kw, kpi_name in _KPI_NAMES.items():
        if kw.lower() in query_lower:
            kpi_names.append(kpi_name)
    kpi_names = list(dict.fromkeys(kpi_names))  # dedup, keep order

    # ---- alarm_names ----
    alarm_names: list[str] = []
    for kw, alarm_name in _ALARM_NAMES.items():
        if kw.lower() in query_lower:
            alarm_names.append(alarm_name)
    alarm_names = list(dict.fromkeys(alarm_names))

    # ---- time_range ----
    time_range = state.get("time_range") or _parse_time_range(query)

    entities: dict = {
        "kpi_names": kpi_names,
        "alarm_names": alarm_names,
    }

    return {
        "site_id": site_id or state.get("site_id"),
        "cell_id": cell_id or state.get("cell_id"),
        "entities": entities,
        "time_range": time_range,
        "current_step": "entity_extractor",
    }


# ---------------------------------------------------------------------------
# 3.4  planner
# ---------------------------------------------------------------------------

_INTENT_PLANS: dict[str, list[str]] = {
    "fault_diagnosis": [
        "Check KPI trend for the specified cell and time range.",
        "Search related alarms around the incident time.",
        "Query knowledge graph for root causes linked to KPI degradation.",
        "Retrieve similar historical cases.",
        "Fuse evidence and generate troubleshooting report.",
    ],
    "kpi_query": [
        "Query KPI data for the specified cell and time range.",
        "Compare with baseline values.",
        "Summarize KPI trend.",
    ],
    "alarm_query": [
        "Query alarm records for the specified cell/site and time range.",
        "Correlate alarms with KPI changes.",
        "Summarize alarm timeline.",
    ],
    "parameter_check": [
        "Query parameter change history for the specified cell.",
        "Check whether changes align with KPI degradation onset.",
        "Report parameter anomalies.",
    ],
    "handover_analysis": [
        "Query handover success rate for the cell.",
        "Check neighbor cell relations and handover attempts.",
        "Identify abnormal handover patterns.",
    ],
    "coverage_analysis": [
        "Query RSRP/RSRQ distribution for the area.",
        "Check for coverage holes or overshooting cells.",
        "Suggest coverage optimization actions.",
    ],
    "report_generation": [
        "Collect KPI summary.",
        "Collect alarm summary.",
        "Generate comprehensive report.",
    ],
    "general_qa": [
        "Retrieve relevant SOPs and documentation.",
        "Answer based on available telecom knowledge.",
    ],
}


def planner(state: AgentState) -> dict:
    """Generate a high-level investigation plan based on the classified intent."""
    intent = state.get("intent", "general_qa")
    plan = _INTENT_PLANS.get(intent, _INTENT_PLANS["general_qa"])
    return {"plan": plan, "current_step": "planner"}


# ---------------------------------------------------------------------------
# 3.5  tool_router
# ---------------------------------------------------------------------------

# Mapping from intent → recommended tool names in priority order
_INTENT_TOOLS: dict[str, list[str]] = {
    "fault_diagnosis": ["sql_kpi_tool", "sql_alarm_tool", "graph_fault_tool", "case_search_tool", "rag_tool"],
    "kpi_query": ["sql_kpi_tool"],
    "alarm_query": ["sql_alarm_tool", "graph_fault_tool"],
    "parameter_check": ["sql_param_tool"],
    "handover_analysis": ["sql_kpi_tool", "graph_fault_tool"],
    "coverage_analysis": ["sql_kpi_tool", "rag_tool"],
    "report_generation": ["sql_kpi_tool", "case_search_tool"],
    "general_qa": ["rag_tool"],
}

# Tools that have already been called (tracked via tool_calls list)
_TOOL_TO_NODE = {
    "sql_kpi_tool": "sql_query",
    "sql_alarm_tool": "sql_query",
    "sql_param_tool": "sql_query",
    "graph_fault_tool": "graph_query",
    "rag_tool": "rag_retriever",
    "case_search_tool": "case_search",
}


def tool_router(state: AgentState) -> dict:
    """Choose which tool to call next based on intent and previous tool results.

    On first entry: selects all tools relevant to the intent, queues them in
    ``next_tools``, and the conditional edge routes to the first one.

    On retry (from reflection): picks the next uncalled tool from the queue,
    skipping tools whose *target node* has already been visited (e.g.
    ``sql_kpi_tool`` and ``sql_alarm_tool`` both go to ``sql_query``, so
    only the first one in the queue is actually called).
    """
    intent = state.get("intent", "general_qa")
    retry_count = state.get("retry_count", 0)

    # Nodes that have already been executed
    previously_called_nodes = {
        _TOOL_TO_NODE.get(tc.tool_name)
        for tc in state.get("tool_calls", [])
    }

    # Detect re-entry: if we already have tool calls, we are retrying
    if previously_called_nodes:
        retry_count += 1

    # If we already have next_tools (from previous planning), filter out
    # tools whose target node has already been visited
    existing_queue = state.get("next_tools", [])
    if existing_queue:
        remaining = [
            t for t in existing_queue
            if _TOOL_TO_NODE.get(t) not in previously_called_nodes
        ]
    else:
        # First time — build the full queue
        candidate_tools = _INTENT_TOOLS.get(intent, ["rag_tool"])
        remaining = [
            t for t in candidate_tools
            if _TOOL_TO_NODE.get(t) not in previously_called_nodes
        ]

    return {
        "next_tools": remaining,
        "current_step": "tool_router",
        "retry_count": retry_count,
    }


# ---------------------------------------------------------------------------
# 3.6  sql_query_node  (mock — no real database)
# ---------------------------------------------------------------------------


def sql_query_node(state: AgentState) -> dict:
    """Mock SQL query node — returns deterministic KPI & alarm evidence.

    In production this will query PostgreSQL for cell_kpi_15min and
    alarm_records tables.
    """
    cell_id = state.get("cell_id", "SZ-NS-023-2")
    site_id = state.get("site_id", "SZ-NS-023")
    time_range = state.get("time_range")

    now = datetime.now(timezone.utc)
    start_str = time_range.start if time_range else (now - timedelta(hours=2)).strftime("%Y-%m-%dT%H:%M:%S")
    end_str = time_range.end if time_range else now.strftime("%Y-%m-%dT%H:%M:%S")

    # Build mock SQL evidence items
    evidence_items: list[EvidenceItem] = []

    # KPI trend evidence
    evidence_items.append(
        EvidenceItem(
            source="sql",
            title=f"KPI Trend for cell {cell_id}",
            content=(
                f"Cell {cell_id} (site {site_id}): "
                f"RSRP dropped from -88 dBm to -106 dBm between {start_str} and {end_str}. "
                "Call drop rate increased from 0.6% to 3.8% in the same window. "
                "PRB utilization remained stable at 62%. "
                "SINR degraded from 18 dB to 7 dB."
            ),
            score=0.95,
            metadata={
                "table": "cell_kpi_15min",
                "rows": 16,
                "kpi_names": ["rsrp", "call_drop_rate", "prb_utilization", "sinr"],
                "time_range": {"start": start_str, "end": end_str},
            },
        )
    )

    # Alarm evidence
    evidence_items.append(
        EvidenceItem(
            source="sql",
            title=f"Alarm Records for cell {cell_id}",
            content=(
                f"Found 3 alarms for cell {cell_id}: "
                "1) VSWR_HIGH (major) at " + start_str + " — lasted 95 minutes; "
                "2) RRU_POWER_LOW (minor) at " + start_str + " — lasted 40 minutes; "
                "3) CELL_OUTAGE warning 5 minutes after VSWR_HIGH onset."
            ),
            score=0.90,
            metadata={
                "table": "alarm_records",
                "rows": 3,
                "alarm_names": ["VSWR_HIGH", "RRU_POWER_LOW", "CELL_OUTAGE"],
            },
        )
    )

    # Tool trace
    tool_call = ToolCallRecord(
        tool_name="sql_kpi_tool",
        input={"cell_id": cell_id, "time_range": {"start": start_str, "end": end_str}},
        output={
            "kpi_rows": 16,
            "alarm_rows": 3,
        },
        latency_ms=42.3,
    )

    existing_sql = list(state.get("sql_evidence", []))
    existing_calls = list(state.get("tool_calls", []))
    existing_errors = list(state.get("tool_errors", []))

    return {
        "sql_evidence": existing_sql + evidence_items,
        "tool_calls": existing_calls + [tool_call],
        "tool_errors": existing_errors,
        "current_step": "sql_query",
    }


# ---------------------------------------------------------------------------
# 3.7  graph_query_node  (mock — no real Neo4j)
# ---------------------------------------------------------------------------


def graph_query_node(state: AgentState) -> dict:
    """Mock graph query node — returns deterministic knowledge-graph reasoning path.

    In production this will query Neo4j for multi-hop fault diagnosis paths.
    """
    cell_id = state.get("cell_id", "SZ-NS-023-2")
    kpi_names = state.get("entities", {}).get("kpi_names", ["rsrp", "call_drop_rate"])
    alarm_names = state.get("entities", {}).get("alarm_names", ["VSWR_HIGH"])

    evidence_items: list[EvidenceItem] = []

    evidence_items.append(
        EvidenceItem(
            source="graph",
            title="Knowledge Graph: RSRP Drop → VSWR_HIGH → Feeder Fault",
            content=(
                "Multi-hop path found in telecom knowledge graph:\n"
                "(KPI:RSRP_DROP) -[:INDICATES]-> (FaultMode:VSWR_HIGH) "
                "-[:CAUSED_BY]-> (RootCause:AntennaFeederIssue) "
                "-[:RESOLVED_BY]-> (Action:CheckFeederConnection).\n"
                "Additional path:\n"
                "(KPI:CALL_DROP_RATE_INCREASE) -[:INDICATES]-> (FaultMode:VSWR_HIGH) "
                "-[:CAUSED_BY]-> (RootCause:PowerAmplifierAbnormality).\n"
                "Also matches historical case #HC-2024-0815 with 0.87 similarity."
            ),
            score=0.88,
            metadata={
                "graph_path_length": 4,
                "matched_case_id": "HC-2024-0815",
                "similarity": 0.87,
                "fault_modes": ["VSWR_HIGH"],
                "root_causes": ["AntennaFeederIssue", "PowerAmplifierAbnormality"],
            },
        )
    )

    tool_call = ToolCallRecord(
        tool_name="graph_fault_tool",
        input={
            "kpi_names": kpi_names,
            "alarm_names": alarm_names,
            "cell_id": cell_id,
        },
        output={"paths_found": 2, "matched_cases": 1},
        latency_ms=87.1,
    )

    existing_graph = list(state.get("graph_evidence", []))
    existing_calls = list(state.get("tool_calls", []))
    existing_errors = list(state.get("tool_errors", []))

    return {
        "graph_evidence": existing_graph + evidence_items,
        "tool_calls": existing_calls + [tool_call],
        "tool_errors": existing_errors,
        "current_step": "graph_query",
    }


# ---------------------------------------------------------------------------
# 3.8  rag_retriever_node  (mock — no real RAG pipeline)
# ---------------------------------------------------------------------------


def rag_retriever_node(state: AgentState) -> dict:
    """Mock RAG retriever node — returns deterministic SOP / document excerpts.

    In production this will retrieve relevant documents from a vector store.
    """
    intent = state.get("intent", "fault_diagnosis")

    evidence_items: list[EvidenceItem] = []

    evidence_items.append(
        EvidenceItem(
            source="rag",
            title="SOP: VSWR High Troubleshooting",
            content=(
                "**VSWR_HIGH 告警处理 SOP (R4-2024)**\n"
                "1. 检查基站侧 VSWR 实时值，若 >2.0 则存在明显失配。\n"
                "2. 通过网管查询该小区历史 VSWR 趋势，判断是否为突发上升。\n"
                "3. 检查 RRU 输出功率是否异常。\n"
                "4. 若 VSWR 持续恶化，安排现场工程师检查天馈接头和馈线。\n"
                "5. 现场检查项目：接头防水、馈线弯曲度、天线面板物理损伤。\n"
                "6. 常见根因：馈线进水（占比 42%）、接头松动（28%）、天线老化（18%）。"
            ),
            score=0.91,
            metadata={
                "doc_id": "SOP-VSWR-2024-R4",
                "source_type": "troubleshooting_manual",
                "chunk_index": 3,
            },
        )
    )

    evidence_items.append(
        EvidenceItem(
            source="rag",
            title="Network Optimization Guide: RSRP Degradation Analysis",
            content=(
                "**RSRP 下降分析方法**\n"
                "RSRP 突然下降通常由以下原因引起：\n"
                "- 天馈系统故障（VSWR 升高是最常见伴随现象）\n"
                "- RRU 功率放大器性能劣化\n"
                "- 射频参数被错误修改（功率、倾角等）\n"
                "- 外部干扰源（如私装放大器）\n"
                "建议排查顺序：先看告警 → 再看参数变更记录 → 最后排查干扰。"
            ),
            score=0.85,
            metadata={
                "doc_id": "NW-OPT-GUIDE-2025",
                "source_type": "optimization_manual",
                "chunk_index": 7,
            },
        )
    )

    tool_call = ToolCallRecord(
        tool_name="rag_tool",
        input={
            "queries": [
                "RSRP drop VSWR high troubleshooting",
                "call drop rate increase root cause wireless network",
            ],
        },
        output={"retrieved_docs": 2, "top_scores": [0.91, 0.85]},
        latency_ms=56.2,
    )

    existing_rag = list(state.get("rag_evidence", []))
    existing_calls = list(state.get("tool_calls", []))
    existing_errors = list(state.get("tool_errors", []))

    return {
        "rag_evidence": existing_rag + evidence_items,
        "tool_calls": existing_calls + [tool_call],
        "tool_errors": existing_errors,
        "current_step": "rag_retriever",
    }


# ---------------------------------------------------------------------------
# 3.9  case_search_node  (mock — no real case database)
# ---------------------------------------------------------------------------


def case_search_node(state: AgentState) -> dict:
    """Mock case search node — returns deterministic historical case matches.

    In production this will search a vector database of historical
    trouble tickets and resolved cases.
    """
    evidence_items: list[EvidenceItem] = []

    evidence_items.append(
        EvidenceItem(
            source="case",
            title="Historical Case #HC-2024-0815: VSWR High → RSRP Drop",
            content=(
                "**Case #HC-2024-0815** (2024-08-15, resolved in 4.2 h)\n"
                "Site: SZ-NS-023, Cell: SZ-NS-023-2\n"
                "Symptoms: RSRP dropped from -90 to -108 dBm, VSWR_HIGH alarm, "
                "call drop rate increased to 4.1%.\n"
                "Root cause: Feeder connector water ingress after heavy rain.\n"
                "Actions taken: Replaced damaged feeder connector, re-sealed waterproofing.\n"
                "Resolution time: 4.2 hours.\n"
                "Similarity to current issue: 0.87."
            ),
            score=0.87,
            metadata={
                "case_id": "HC-2024-0815",
                "similarity": 0.87,
                "site_id": "SZ-NS-023",
                "cell_id": "SZ-NS-023-2",
                "resolution_time_hours": 4.2,
            },
        )
    )

    evidence_items.append(
        EvidenceItem(
            source="case",
            title="Historical Case #HC-2025-0302: Power Amplifier Degradation",
            content=(
                "**Case #HC-2025-0302** (2025-03-02, resolved in 8.0 h)\n"
                "Site: SZ-NS-045, Cell: SZ-NS-045-1\n"
                "Symptoms: Gradual RSRP decline over 6 hours, call drop rate from 0.5% to 2.9%.\n"
                "Root cause: RRU power amplifier aging, output power dropped by 6 dB.\n"
                "Actions taken: Replaced RRU module.\n"
                "Resolution time: 8.0 hours.\n"
                "Similarity to current issue: 0.63."
            ),
            score=0.63,
            metadata={
                "case_id": "HC-2025-0302",
                "similarity": 0.63,
                "site_id": "SZ-NS-045",
                "resolution_time_hours": 8.0,
            },
        )
    )

    tool_call = ToolCallRecord(
        tool_name="case_search_tool",
        input={
            "symptoms": ["RSRP drop", "call drop rate increase", "VSWR_HIGH"],
            "cell_id": state.get("cell_id"),
            "top_k": 5,
        },
        output={"matched_cases": 2, "top_similarity": 0.87},
        latency_ms=125.6,
    )

    existing_case = list(state.get("case_evidence", []))
    existing_calls = list(state.get("tool_calls", []))
    existing_errors = list(state.get("tool_errors", []))

    return {
        "case_evidence": existing_case + evidence_items,
        "tool_calls": existing_calls + [tool_call],
        "tool_errors": existing_errors,
        "current_step": "case_search",
    }


# ---------------------------------------------------------------------------
# 3.10  evidence_fusion
# ---------------------------------------------------------------------------

# Source priority for ranking (lower number = higher priority)
_SOURCE_PRIORITY = {
    "sql": 0,
    "graph": 1,
    "case": 2,
    "rag": 3,
    "oss": 4,
}


def evidence_fusion(state: AgentState) -> dict:
    """Combine evidence from all sources into a single ranked list.

    Evidence is deduplicated by title and sorted by source priority and score.
    """
    all_evidence: list[EvidenceItem] = []
    seen_titles: set[str] = set()

    # Collect from all buckets, dedup by title
    for bucket_name in ("sql_evidence", "graph_evidence", "case_evidence", "rag_evidence"):
        for item in state.get(bucket_name, []):  # type: ignore[attr-defined]
            if item.title not in seen_titles:
                seen_titles.add(item.title)
                all_evidence.append(item)

    # Sort: source priority first, then descending score
    all_evidence.sort(
        key=lambda e: (
            _SOURCE_PRIORITY.get(e.source, 99),  # source priority
            -(e.score or 0),  # higher score first
        )
    )

    return {
        "fused_evidence": all_evidence,
        "current_step": "evidence_fusion",
    }


# ---------------------------------------------------------------------------
# 3.11  diagnosis_reasoner
# ---------------------------------------------------------------------------


def diagnosis_reasoner(state: AgentState) -> dict:
    """Build a structured diagnosis from fused evidence.

    In production this will use an LLM to reason over the evidence.
    For now it uses deterministic rule-based extraction.
    """
    fused = list(state.get("fused_evidence", []))
    cell_id = state.get("cell_id", "SZ-NS-023-2")

    # ---- Derive symptoms from SQL evidence ----
    symptoms: list[str] = []
    for item in fused:
        if item.source == "sql":
            if "RSRP" in item.content:
                symptoms.append(f"Cell {cell_id} RSRP severely degraded (approx -88 → -106 dBm).")
            if "call drop" in item.content.lower():
                symptoms.append(f"Call drop rate increased significantly (0.6% → 3.8%) on cell {cell_id}.")
            if "SINR" in item.content:
                symptoms.append("SINR degraded from 18 dB to 7 dB.")
            if "VSWR" in item.content.upper():
                symptoms.append("VSWR_HIGH alarm detected, onset precedes KPI degradation by ~20 min.")

    if not symptoms:
        symptoms = [
            f"Symptoms detected on cell {cell_id}.",
            "KPI metrics show abnormal degradation pattern.",
            "Related alarms may be present.",
        ]

    # ---- Derive possible causes from graph + case evidence ----
    possible_causes: list[str] = []
    for item in fused:
        if item.source == "graph":
            if "AntennaFeeder" in item.content:
                possible_causes.append("Antenna feeder issue (VSWR anomaly, possible water ingress or loose connector).")
            if "PowerAmplifier" in item.content:
                possible_causes.append("RRU power amplifier abnormality or aging.")
        if item.source == "case" and "parameter" in item.content.lower():
            possible_causes.append("Recent radio parameter change causing coverage degradation.")

    if not possible_causes:
        possible_causes = [
            "Antenna feeder system fault.",
            "RF hardware degradation.",
            "External interference or parameter misconfiguration.",
        ]

    # ---- Derive recommended actions from RAG + graph evidence ----
    recommended_actions: list[str] = []
    for item in fused:
        if item.source == "rag" and "SOP" in item.title:
            recommended_actions.append("Follow VSWR troubleshooting SOP: check VSWR value, RRU output power, feeder connections.")
        if item.source == "rag" and "RSRP" in item.title:
            recommended_actions.append("Check alarm timeline first, then review parameter change history, finally check for external interference.")

    if not recommended_actions:
        recommended_actions = [
            "Check current active alarms and real-time VSWR values.",
            "Compare KPI trends before and after recent parameter changes.",
            "Verify neighboring cell handover success rate.",
            "If VSWR persists, dispatch field engineer for on-site inspection.",
        ]

    # ---- Determine confidence based on evidence diversity ----
    sources_present = {e.source for e in fused}
    evidence_count = len(fused)
    if len(sources_present) >= 3 and evidence_count >= 4:
        confidence = "high"
    elif len(sources_present) >= 2 and evidence_count >= 2:
        confidence = "medium"
    else:
        confidence = "low"

    diagnosis = DiagnosisResult(
        symptoms=symptoms,
        possible_causes=possible_causes,
        recommended_actions=recommended_actions,
        confidence=confidence,
        missing_evidence=[],
    )

    return {
        "diagnosis": diagnosis,
        "current_step": "diagnosis_reasoner",
    }


# ---------------------------------------------------------------------------
# 3.12  reflection_node
# ---------------------------------------------------------------------------


def reflection_node(state: AgentState) -> dict:
    """Evaluate whether the collected evidence is sufficient for a reliable diagnosis.

    Checks:
    1. Do we have KPI (SQL) evidence?
    2. Do we have alarm evidence?
    3. Do we have a graph reasoning path?
    4. Do we have similar historical cases?
    5. Have we exceeded the retry budget?
    """
    fused = list(state.get("fused_evidence", []))
    sources = {e.source for e in fused}
    retry_count = state.get("retry_count", 0)

    missing: list[str] = []
    if "sql" not in sources:
        missing.append("No KPI or alarm records retrieved from SQL.")
    if "graph" not in sources:
        missing.append("No knowledge graph reasoning path found.")
    if "case" not in sources:
        missing.append("No similar historical cases retrieved.")
    if "rag" not in sources:
        missing.append("No SOP or documentation retrieved.")

    # Check conflicting signals
    has_vswr = any("VSWR" in e.content.upper() for e in fused)
    has_power = any("power" in e.content.lower() or "Power" in e.content for e in fused)
    conflicting = has_vswr and not has_power  # VSWR without power check is not conflicting per se

    # Signal markers
    has_sql_evidence = "sql" in sources
    has_graph_evidence = "graph" in sources

    enough = bool(has_sql_evidence and has_graph_evidence and len(missing) <= 2)

    needs_human: bool
    if retry_count >= 2:
        needs_human = True
        enough = False
    elif not enough and retry_count < 2:
        needs_human = False
    else:
        needs_human = False

    return {
        "enough_evidence": enough,
        "needs_human_review": needs_human,
        "current_step": "reflection",
        # If diagnosis exists, add missing evidence note
        "diagnosis": _patch_missing(
            state.get("diagnosis"),
            missing if not enough else [],
        ),
    }


def _patch_missing(diagnosis: DiagnosisResult | None, missing: list[str]) -> DiagnosisResult | None:
    """Attach missing-evidence list to diagnosis (non-destructive)."""
    if diagnosis is None:
        return None
    return DiagnosisResult(
        symptoms=list(diagnosis.symptoms),
        possible_causes=list(diagnosis.possible_causes),
        recommended_actions=list(diagnosis.recommended_actions),
        confidence="low" if missing else diagnosis.confidence,
        missing_evidence=list(missing),
    )


# ---------------------------------------------------------------------------
# 3.13  report_generator
# ---------------------------------------------------------------------------


def report_generator(state: AgentState) -> dict:
    """Generate the final markdown diagnosis report.

    Produces a structured report covering: query summary, symptoms,
    evidence table, root cause analysis, recommended actions, confidence,
    and next steps.
    """
    diagnosis = state.get("diagnosis")
    fused = list(state.get("fused_evidence", []))
    query = state.get("query", "")
    cell_id = state.get("cell_id", "")
    intent = state.get("intent", "fault_diagnosis")
    needs_human = state.get("needs_human_review", False)

    # Generate query summary based on intent
    if "RSRP" in query.upper() or "rsrp" in query.lower():
        query_summary = f"用户反馈小区 **{cell_id}** RSRP（参考信号接收功率）突然下降，伴随掉话率升高，请求故障诊断。"
    elif "告警" in query or "alarm" in query.lower():
        query_summary = f"用户查询小区 **{cell_id}** 的告警记录和分析。"
    else:
        query_summary = f"用户查询: {query[:120]}"

    # ---- Build evidence table rows ----
    evidence_rows: list[str] = []
    for i, ev in enumerate(fused, 1):
        evidence_rows.append(
            f"| {i} | {ev.source.upper()} | {ev.title} | {ev.score or '—':.2f} |"
        )

    evidence_table = "\n".join(evidence_rows) if evidence_rows else "| — | — | 无证据 | — |"

    # ---- Build report ----
    lines: list[str] = []

    lines.append("# 电信运维故障诊断报告\n")
    lines.append("## 1. 查询概要\n")
    lines.append(query_summary + "\n")

    lines.append("## 2. 观察到的症状\n")
    if diagnosis and diagnosis.symptoms:
        for s in diagnosis.symptoms:
            lines.append(f"- {s}")
    else:
        lines.append("- （未能自动提取，请参考证据表。）")
    lines.append("")

    lines.append("## 3. 证据汇总\n")
    lines.append("| # | 来源 | 标题 | 得分 |")
    lines.append("|---|---|---|---|")
    lines.append(evidence_table)
    lines.append("")

    lines.append("## 4. 根因分析\n")
    if diagnosis and diagnosis.possible_causes:
        for i, cause in enumerate(diagnosis.possible_causes, 1):
            lines.append(f"{i}. {cause}")
    else:
        lines.append("- 无法确定根因，建议人工介入分析。")
    lines.append("")

    lines.append("## 5. 建议排查步骤\n")
    if diagnosis and diagnosis.recommended_actions:
        for i, action in enumerate(diagnosis.recommended_actions, 1):
            lines.append(f"{i}. {action}")
    else:
        lines.append("- 请参考 SOP 和专家经验进行排查。")
    lines.append("")

    lines.append("## 6. 置信度与风险\n")
    confidence_label = diagnosis.confidence if diagnosis else "low"
    confidence_zh = {"high": "🟢 高", "medium": "🟡 中", "low": "🔴 低"}
    lines.append(f"- **置信度**: {confidence_zh.get(confidence_label, confidence_label)}\n")

    if needs_human:
        lines.append("- ⚠️ **需要人工审查**: 自动诊断证据不足或超出重试次数，建议人工介入。\n")

    if diagnosis and diagnosis.missing_evidence:
        lines.append("- **缺失证据**:\n")
        for me in diagnosis.missing_evidence:
            lines.append(f"  - {me}")
        lines.append("")

    if "VSWR" in " ".join(e.content for e in fused).upper():
        lines.append("- ⚡ 若 VSWR 持续恶化，4 小时内存在断站风险。\n")
        lines.append("- 📡 邻区可能因切换重试出现瞬时负载升高。\n")

    lines.append("## 7. 后续建议\n")
    lines.append("- 如现场检查确认硬件故障，请及时提交维修工单。")
    lines.append("- 建议将本次诊断结果归档为历史案例，用于后续相似问题参考。")
    lines.append("- 可在 `POST /api/v1/feedback` 提交对本次诊断的评价。\n")
    lines.append("---\n")
    lines.append(f"*诊断 ID: {uuid.uuid4().hex}*  \n")
    lines.append(f"*生成时间: {datetime.now(timezone.utc).strftime('%Y-%m-%d %H:%M:%S UTC')}*")

    final_answer = "\n".join(lines)

    return {
        "final_answer": final_answer,
        "report_markdown": final_answer,
        "current_step": "report_generator",
    }
