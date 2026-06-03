"""Tests for the LangGraph agent workflow: nodes, graph structure, and end-to-end.

Tests verify that an RSRP-drop fault diagnosis query produces:
  - ``final_answer`` (non-empty markdown report)
  - ``diagnosis`` (structured DiagnosisResult with symptoms, causes, actions, confidence)
  - ``confidence`` (one of low / medium / high)
  - ``fused_evidence`` (non-empty after evidence fusion)
"""

import re

import pytest

from src.telecomops_agent.agent.graph import agent_app
from src.telecomops_agent.agent.nodes import (
    case_search_node,
    diagnosis_reasoner,
    entity_extractor,
    evidence_fusion,
    graph_query_node,
    input_guard,
    intent_classifier,
    planner,
    rag_retriever_node,
    reflection_node,
    report_generator,
    sql_query_node,
    tool_router,
)
from src.telecomops_agent.agent.state import AgentState, DiagnosisResult

# ---------------------------------------------------------------------------
# Shared test fixtures
# ---------------------------------------------------------------------------


@pytest.fixture
def rsrp_query() -> str:
    """The canonical test query for an RSRP drop diagnosis scenario."""
    return (
        "SZ-NS-023-2 最近2小时RSRP突然下降，从-88降到-106，"
        "掉话率从0.6%升高到3.8%，请分析原因并给出排查步骤。"
    )


@pytest.fixture
def initial_state(rsrp_query: str) -> AgentState:
    """Minimal initial agent state with only the user query populated."""
    return AgentState(
        query=rsrp_query,
        session_id="test-session-001",
        user_id=None,
    )


def _invoke_sync(state: dict) -> dict:
    """Synchronous helper to invoke the compiled graph."""
    import asyncio

    return asyncio.run(agent_app.ainvoke(state))


# ---------------------------------------------------------------------------
# Node-level unit tests
# ---------------------------------------------------------------------------


class TestInputGuard:
    """Tests for the input_guard node."""

    def test_initializes_control_fields(self, initial_state: AgentState):
        result = input_guard(initial_state)
        assert result["retry_count"] == 0
        assert result["tool_calls"] == []
        assert result["tool_errors"] == []
        assert result["current_step"] == "input_guard"

    def test_normalizes_whitespace(self):
        state: AgentState = {"query": "   SZ-NS-023-2   RSRP  下降  \n\n请分析  "}
        result = input_guard(state)
        assert "\n" not in result["query"]
        assert "  " not in result["query"]
        assert result["query"] == "SZ-NS-023-2 RSRP 下降 请分析"

    def test_rejects_sql_injection(self):
        state: AgentState = {"query": "DROP TABLE alarm_records; SELECT * FROM users"}
        result = input_guard(state)
        assert result.get("needs_human_review") is True
        assert result.get("final_answer") is not None
        diag = result.get("diagnosis")
        assert diag is not None
        assert diag.confidence == "low"

    def test_rejects_delete_from(self):
        state: AgentState = {"query": "DELETE FROM config WHERE 1=1"}
        result = input_guard(state)
        assert result.get("needs_human_review") is True

    def test_rejects_script_tag(self):
        state: AgentState = {"query": "<script>alert('XSS')</script>"}
        result = input_guard(state)
        assert result.get("needs_human_review") is True


class TestIntentClassifier:
    """Tests for the intent_classifier node."""

    def test_classifies_fault_diagnosis(self, initial_state: AgentState):
        result = intent_classifier(initial_state)
        assert result["intent"] == "fault_diagnosis"

    def test_classifies_kpi_query(self):
        state: AgentState = {"query": "查询SZ-NS-023-2的KPI指标趋势"}
        result = intent_classifier(state)
        assert result["intent"] == "kpi_query"

    def test_classifies_alarm_query(self):
        state: AgentState = {"query": "查看最近告警记录"}
        result = intent_classifier(state)
        assert result["intent"] == "alarm_query"

    def test_classifies_parameter_check(self):
        state: AgentState = {"query": "检查参数变更记录"}
        result = intent_classifier(state)
        assert result["intent"] == "parameter_check"

    def test_classifies_handover_analysis(self):
        state: AgentState = {"query": "分析切换成功率"}
        result = intent_classifier(state)
        assert result["intent"] == "handover_analysis"

    def test_classifies_coverage_analysis(self):
        state: AgentState = {"query": "覆盖分析报告"}
        result = intent_classifier(state)
        assert result["intent"] == "coverage_analysis"

    def test_classifies_report_generation(self):
        state: AgentState = {"query": "生成本周网络质量报告"}
        result = intent_classifier(state)
        assert result["intent"] == "report_generation"

    def test_falls_back_to_general_qa(self):
        state: AgentState = {"query": "今天天气怎么样"}
        result = intent_classifier(state)
        assert result["intent"] == "general_qa"


class TestEntityExtractor:
    """Tests for the entity_extractor node."""

    def test_extracts_cell_id(self, initial_state: AgentState):
        result = entity_extractor(initial_state)
        assert result["cell_id"] == "SZ-NS-023-2"

    def test_derives_site_id_from_cell(self, initial_state: AgentState):
        result = entity_extractor(initial_state)
        assert result["site_id"] == "SZ-NS-023"

    def test_extracts_kpi_names(self, initial_state: AgentState):
        result = entity_extractor(initial_state)
        kpis = result["entities"]["kpi_names"]
        assert "rsrp" in kpis
        assert "call_drop_rate" in kpis

    def test_extracts_time_range(self, initial_state: AgentState):
        result = entity_extractor(initial_state)
        tr = result["time_range"]
        assert tr is not None
        assert tr.start is not None
        assert tr.end is not None

    def test_no_cell_id_returns_none(self):
        state: AgentState = {"query": "KPI指标查询"}
        result = entity_extractor(state)
        assert result["cell_id"] is None


class TestPlanner:
    """Tests for the planner node."""

    def test_generates_plan_for_fault_diagnosis(self, initial_state: AgentState):
        # Intent must be set before planner runs
        state: dict = dict(initial_state)
        state["intent"] = "fault_diagnosis"
        result = planner(state)
        plan = result["plan"]
        assert isinstance(plan, list)
        assert len(plan) >= 3
        assert any("KPI" in step for step in plan)
        assert any("alarm" in step.lower() or "告警" in step for step in plan)


class TestToolRouter:
    """Tests for the tool_router node."""

    def test_routes_fault_diagnosis_to_sql_graph_case(self, initial_state: AgentState):
        state: dict = dict(initial_state)
        state["intent"] = "fault_diagnosis"
        result = tool_router(state)
        assert "sql_kpi_tool" in result["next_tools"]
        assert "graph_fault_tool" in result["next_tools"]
        assert "case_search_tool" in result["next_tools"]

    def test_increments_retry_on_reentry(self, initial_state: AgentState):
        # Simulate first pass: tool_router already called, one tool executed
        state_with_calls: dict = dict(initial_state)
        state_with_calls["intent"] = "fault_diagnosis"
        state_with_calls["next_tools"] = ["sql_kpi_tool", "graph_fault_tool", "case_search_tool"]
        state_with_calls["tool_calls"] = [
            type("tc", (), {"tool_name": "sql_kpi_tool"})()  # minimal mock
        ]
        state_with_calls["retry_count"] = 0

        result = tool_router(state_with_calls)
        assert result["retry_count"] == 1  # incremented on re-entry

    def test_empties_queue_when_all_called(self, initial_state: AgentState):
        state_all_called: dict = dict(initial_state)
        state_all_called["intent"] = "fault_diagnosis"
        state_all_called["next_tools"] = ["sql_kpi_tool", "graph_fault_tool"]
        state_all_called["tool_calls"] = [
            type("tc", (), {"tool_name": "sql_kpi_tool"})(),
            type("tc", (), {"tool_name": "graph_fault_tool"})(),
        ]
        result = tool_router(state_all_called)
        assert result["next_tools"] == []


class TestMockToolNodes:
    """Tests for the mock tool nodes (sql, graph, rag, case)."""

    def test_sql_query_returns_evidence(self, initial_state: AgentState):
        result = sql_query_node(initial_state)
        assert len(result["sql_evidence"]) >= 1
        assert result["sql_evidence"][0].source == "sql"
        assert len(result["tool_calls"]) == 1
        assert result["tool_calls"][0].tool_name == "sql_kpi_tool"

    def test_graph_query_returns_evidence(self, initial_state: AgentState):
        result = graph_query_node(initial_state)
        assert len(result["graph_evidence"]) >= 1
        assert result["graph_evidence"][0].source == "graph"

    def test_rag_retriever_returns_evidence(self, initial_state: AgentState):
        result = rag_retriever_node(initial_state)
        assert len(result["rag_evidence"]) >= 1
        assert result["rag_evidence"][0].source == "rag"

    def test_case_search_returns_evidence(self, initial_state: AgentState):
        result = case_search_node(initial_state)
        assert len(result["case_evidence"]) >= 1
        assert result["case_evidence"][0].source == "case"


class TestEvidenceFusion:
    """Tests for the evidence_fusion node."""

    def test_fuses_multiple_sources(self, initial_state: AgentState):
        # Simulate state after all tools have run
        import asyncio

        results_sql = sql_query_node(initial_state)
        results_graph = graph_query_node(initial_state)
        results_case = case_search_node(initial_state)

        mock_ev = type("EvidenceItem", (), {
            "source": "sql",
            "title": "Test KPI Trend",
            "content": "RSRP dropped.",
            "score": 0.95,
            "metadata": {},
        })

        state: dict = dict(initial_state)
        state["sql_evidence"] = results_sql.get("sql_evidence", [])
        state["graph_evidence"] = results_graph.get("graph_evidence", [])
        state["case_evidence"] = results_case.get("case_evidence", [])
        state["rag_evidence"] = []

        result = evidence_fusion(state)
        assert "fused_evidence" in result
        fused = result["fused_evidence"]
        assert len(fused) >= 3  # should have at least sql, graph, case


class TestDiagnosisReasoner:
    """Tests for the diagnosis_reasoner node."""

    def test_produces_structured_diagnosis(self, initial_state: AgentState):
        results_sql = sql_query_node(initial_state)
        results_graph = graph_query_node(initial_state)
        results_case = case_search_node(initial_state)

        state: dict = dict(initial_state)
        state["sql_evidence"] = results_sql.get("sql_evidence", [])
        state["graph_evidence"] = results_graph.get("graph_evidence", [])
        state["case_evidence"] = results_case.get("case_evidence", [])
        state["rag_evidence"] = []
        state["fused_evidence"] = (
            results_sql.get("sql_evidence", [])
            + results_graph.get("graph_evidence", [])
            + results_case.get("case_evidence", [])
        )

        result = diagnosis_reasoner(state)
        diag = result["diagnosis"]
        assert diag is not None
        assert isinstance(diag, DiagnosisResult)
        assert len(diag.symptoms) > 0
        assert len(diag.possible_causes) > 0
        assert len(diag.recommended_actions) > 0
        assert diag.confidence in ("low", "medium", "high")


class TestReflectionNode:
    """Tests for the reflection_node."""

    def test_enough_evidence_with_sql_and_graph(self, initial_state: AgentState):
        state: dict = dict(initial_state)
        state["fused_evidence"] = [
            type("e", (), {"source": "sql", "title": "KPI", "content": "RSRP drop", "score": 0.95})(),
            type("e", (), {"source": "graph", "title": "KG path", "content": "VSWR_HIGH", "score": 0.88})(),
        ]
        result = reflection_node(state)
        assert result["enough_evidence"] is True
        assert result["needs_human_review"] is False

    def test_insufficient_evidence_no_graph(self, initial_state: AgentState):
        state: dict = dict(initial_state)
        state["fused_evidence"] = [
            type("e", (), {"source": "sql", "title": "KPI", "content": "data", "score": 0.95})(),
        ]
        result = reflection_node(state)
        assert result["enough_evidence"] is False

    def test_retry_budget_exceeded(self, initial_state: AgentState):
        state: dict = dict(initial_state)
        state["fused_evidence"] = [
            type("e", (), {"source": "sql", "title": "X", "content": "Y", "score": 0.5})(),
        ]
        state["retry_count"] = 2
        result = reflection_node(state)
        assert result["needs_human_review"] is True


class TestReportGenerator:
    """Tests for the report_generator node."""

    def test_generates_markdown_report(self, initial_state: AgentState):
        state: dict = dict(initial_state)
        state["intent"] = "fault_diagnosis"
        state["cell_id"] = "SZ-NS-023-2"
        state["diagnosis"] = DiagnosisResult(
            symptoms=["RSRP dropped."],
            possible_causes=["Antenna feeder issue."],
            recommended_actions=["Check VSWR."],
            confidence="medium",
        )
        state["fused_evidence"] = [
            type("e", (), {"source": "sql", "title": "KPI", "content": "VSWR_HIGH alarm", "score": 0.95})(),
        ]

        result = report_generator(state)
        answer = result["final_answer"]
        assert answer is not None
        assert len(answer) > 100
        assert "诊断报告" in answer
        assert "RSRP" in answer
        assert "VSWR" in answer


# ---------------------------------------------------------------------------
# Graph structure tests
# ---------------------------------------------------------------------------


class TestGraphStructure:
    """Tests that verify the compiled graph's node set and edges."""

    def test_graph_is_compiled(self):
        """The workflow must compile to a CompiledStateGraph."""
        from langgraph.graph.state import CompiledStateGraph

        assert isinstance(agent_app, CompiledStateGraph)

    def test_all_required_nodes_present(self):
        """Every node from the design document must be registered."""
        nodes = list(agent_app.get_graph().nodes.keys())
        required = {
            "input_guard",
            "intent_classifier",
            "entity_extractor",
            "planner",
            "tool_router",
            "sql_query",
            "graph_query",
            "rag_retriever",
            "case_search",
            "evidence_fusion",
            "diagnosis_reasoner",
            "reflection",
            "report_generator",
        }
        missing = required - set(nodes)
        assert not missing, f"Missing graph nodes: {missing}"

    def test_entry_point_is_input_guard(self):
        """The workflow must start at input_guard."""
        # ─ access via compiled graph internals ─
        # The entry point is stored on the builder; after compilation we
        # check the graph channels for the __start__ edge.
        import json

        graph_spec = agent_app.get_graph()
        # The entry point is visible in the graph's nodes; __start__ has
        # an edge to input_guard
        edges = list(graph_spec.edges)
        start_edges = [e for e in edges if e[0] == "__start__"]
        assert len(start_edges) == 1, f"Expected 1 __start__ edge, got {len(start_edges)}"
        assert start_edges[0][1] == "input_guard"

    def test_report_generator_has_edge_to_end(self):
        """report_generator should have an edge to __end__ (END)."""
        edges = list(agent_app.get_graph().edges)
        end_edges = [e for e in edges if e[0] == "report_generator" and e[1] == "__end__"]
        assert len(end_edges) == 1


# ---------------------------------------------------------------------------
# End-to-end integration tests
# ---------------------------------------------------------------------------


class TestEndToEndWorkflow:
    """Full integration tests: run the entire LangGraph workflow end-to-end."""

    def test_rsrp_query_produces_final_answer(self, rsrp_query: str):
        """A complete RSRP diagnosis query must return a non-empty final_answer."""
        state = {"query": rsrp_query, "session_id": "e2e-test-001"}
        result = _invoke_sync(state)

        assert "final_answer" in result
        answer = result["final_answer"]
        assert answer is not None
        assert len(answer) > 100
        # Should contain diagnostic sections
        assert "诊断报告" in answer

    def test_rsrp_query_produces_diagnosis(self, rsrp_query: str):
        """The result must include a structured DiagnosisResult."""
        result = _invoke_sync({"query": rsrp_query, "session_id": "e2e-test-002"})

        assert "diagnosis" in result
        diag = result["diagnosis"]
        assert diag is not None
        assert len(diag.symptoms) > 0
        assert len(diag.possible_causes) > 0
        assert len(diag.recommended_actions) > 0

    def test_rsrp_query_has_confidence(self, rsrp_query: str):
        """The diagnosis confidence must be one of low/medium/high."""
        result = _invoke_sync({"query": rsrp_query, "session_id": "e2e-test-003"})

        diag = result["diagnosis"]
        assert diag.confidence in ("low", "medium", "high")

    def test_rsrp_query_has_fused_evidence(self, rsrp_query: str):
        """After evidence fusion, fused_evidence must be non-empty."""
        result = _invoke_sync({"query": rsrp_query, "session_id": "e2e-test-004"})

        fused = result.get("fused_evidence", [])
        assert len(fused) > 0
        sources = {e.source for e in fused}
        assert "sql" in sources
        assert "graph" in sources

    def test_rsrp_query_has_tool_calls(self, rsrp_query: str):
        """The workflow must record tool call traces."""
        result = _invoke_sync({"query": rsrp_query, "session_id": "e2e-test-005"})

        calls = result.get("tool_calls", [])
        assert len(calls) > 0

    def test_query_without_cell_still_completes(self):
        """A generic fault query without cell info should still complete."""
        result = _invoke_sync({
            "query": "某小区掉话率突然升高，请协助排查。",
            "session_id": "e2e-test-006",
        })

        assert result.get("final_answer") is not None
        assert len(result["final_answer"]) > 50
        assert result.get("diagnosis") is not None

    def test_needs_human_review_is_boolean(self, rsrp_query: str):
        """needs_human_review must always be a boolean."""
        result = _invoke_sync({"query": rsrp_query, "session_id": "e2e-test-007"})
        assert isinstance(result.get("needs_human_review"), bool)

    def test_report_contains_expected_sections(self, rsrp_query: str):
        """The generated report should contain standard sections."""
        result = _invoke_sync({"query": rsrp_query, "session_id": "e2e-test-008"})
        answer = result["final_answer"]

        # Check for the 7 standard report sections
        assert "查询概要" in answer or "查询" in answer
        assert "症状" in answer
        assert "证据" in answer
        assert "根因" in answer
        assert "排查" in answer
        assert "置信度" in answer
        assert "建议" in answer or "后续" in answer

    def test_all_intents_complete_without_error(self):
        """A quick smoke test across all supported intents."""
        queries = {
            "kpi_query": "查询SZ-NS-023-2的KPI指标",
            "alarm_query": "查看SZ-NS-023最近告警",
            "fault_diagnosis": "SZ-NS-023-2 RSRP下降，请诊断",
            "parameter_check": "检查SZ-NS-023参数变更",
            "handover_analysis": "分析SZ-NS-023切换成功率",
            "coverage_analysis": "SZ-NS-023覆盖分析",
            "report_generation": "生成SZ-NS-023周报",
            "general_qa": "什么是RSRP",
        }

        for intent, query in queries.items():
            result = _invoke_sync({"query": query, "session_id": f"smoke-{intent}"})
            assert result.get("final_answer") is not None, f"Intent {intent} failed"
            assert isinstance(result["final_answer"], str)
            assert len(result["final_answer"]) > 0
