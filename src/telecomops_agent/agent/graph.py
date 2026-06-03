"""LangGraph workflow graph — compiles the telecom fault diagnosis state machine.

Nodes: input_guard → intent_classifier → entity_extractor → planner → tool_router
       tool_router → [sql_query | graph_query | rag_retriever | case_search] → evidence_fusion
       evidence_fusion → diagnosis_reasoner → reflection
       reflection → [retry → tool_router | report → report_generator | human_review → report_generator]
"""

from langgraph.graph import END, StateGraph

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
from src.telecomops_agent.agent.state import AgentState


# ---------------------------------------------------------------------------
# Conditional routing functions
# ---------------------------------------------------------------------------


def route_tools(state: AgentState) -> str:
    """Route from tool_router to the next uncalled tool or to evidence_fusion.

    Reads ``next_tools`` (the queue of tools yet to be called) and maps
    the first entry to the corresponding LangGraph node name.  When the
    queue is empty we proceed directly to evidence fusion.
    """
    next_tools: list[str] = state.get("next_tools", [])

    if not next_tools:
        return "evidence_fusion"

    next_tool = next_tools[0]

    # Map tool name → node name
    if next_tool in ("sql_kpi_tool", "sql_alarm_tool", "sql_param_tool"):
        return "sql_query"
    if next_tool == "graph_fault_tool":
        return "graph_query"
    if next_tool == "rag_tool":
        return "rag_retriever"
    if next_tool == "case_search_tool":
        return "case_search"

    return "evidence_fusion"


def should_continue(state: AgentState) -> str:
    """Decide whether to retry (call more tools), generate a report, or
    flag for human review based on evidence sufficiency and retry budget.
    """
    if state.get("needs_human_review"):
        return "human_review"

    if state.get("enough_evidence"):
        return "report"

    if state.get("retry_count", 0) >= 2:
        return "human_review"

    return "retry"


# ---------------------------------------------------------------------------
# Graph assembly
# ---------------------------------------------------------------------------


def build_workflow() -> StateGraph:
    """Build the LangGraph StateGraph for telecom fault diagnosis."""

    workflow = StateGraph(AgentState)

    # ---- Add all nodes ----
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

    # ---- Entry point ----
    workflow.set_entry_point("input_guard")

    # ---- Linear chain: input → intent → entities → plan → tools ----
    workflow.add_edge("input_guard", "intent_classifier")
    workflow.add_edge("intent_classifier", "entity_extractor")
    workflow.add_edge("entity_extractor", "planner")
    workflow.add_edge("planner", "tool_router")

    # ---- Conditional branching from tool_router ----
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

    # ---- All tool nodes converge to evidence_fusion ----
    workflow.add_edge("sql_query", "evidence_fusion")
    workflow.add_edge("graph_query", "evidence_fusion")
    workflow.add_edge("rag_retriever", "evidence_fusion")
    workflow.add_edge("case_search", "evidence_fusion")

    # ---- Reasoning chain ----
    workflow.add_edge("evidence_fusion", "diagnosis_reasoner")
    workflow.add_edge("diagnosis_reasoner", "reflection")

    # ---- Conditional exit from reflection ----
    workflow.add_conditional_edges(
        "reflection",
        should_continue,
        {
            "retry": "tool_router",
            "report": "report_generator",
            "human_review": "report_generator",
        },
    )

    # ---- Terminal ----
    workflow.add_edge("report_generator", END)

    return workflow


# ---- Compiled application (imported by routes.py) ----
_workflow = build_workflow()
agent_app = _workflow.compile()
