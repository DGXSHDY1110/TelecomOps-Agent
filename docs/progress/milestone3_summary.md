# Milestone 3 — LangGraph 工作流骨架 完成总结

**完成日期**: 2026-06-03
**分支**: main
**依赖 milestone**: [Milestone 1](milestone1_summary.md) → [Milestone 2](milestone2_summary.md)

---

## 1. 本阶段目标

在 Milestone 2 的 FastAPI API 骨架基础上，实现 LangGraph 工作流骨架：

- 定义 `AgentState` TypedDict（对齐设计文档 `langgraph_workflow_design.md`）
- 实现所有 13 个节点的 deterministic / rule-based 逻辑（不接入 LLM）
- 搭建 LangGraph 图骨架（节点注册 + 条件路由边 + entry/exit）
- 将 `/api/v1/diagnose` 从直接返回固定 mock 切换到调用 LangGraph workflow
- 编写测试验证 RSRP 下降问题的完整诊断路径

**本阶段不做的事情**：真实 SQL / Neo4j / RAG 工具、真实 mock 数据文件、工具调试端点、LLM 调用。

---

## 2. 创建/修改的文件

### 新增文件

| 文件 | 行数 | 说明 |
|---|---|---|
| `src/telecomops_agent/agent/state.py` | ~90 | `AgentState` TypedDict + 4 个 Pydantic 辅助模型（`TimeRange`, `ToolCallRecord`, `EvidenceItem`, `DiagnosisResult`） |
| `src/telecomops_agent/agent/nodes.py` | ~550 | 13 个节点函数，全部 deterministic / rule-based / mock |
| `src/telecomops_agent/agent/graph.py` | ~125 | LangGraph `StateGraph` 定义：节点注册 + 条件路由函数 `route_tools` / `should_continue` + `agent_app` 编译导出 |
| `tests/test_agent_graph.py` | ~450 | 38 个测试：节点级单元测试 + 图结构验证 + 端到端集成测试 |

### 修改文件

| 文件 | 操作 | 说明 |
|---|---|---|
| `requirements.txt` | +2 行 | 新增 `langgraph>=0.2.0`, `langchain-core>=0.3.0` |
| `src/telecomops_agent/agent/__init__.py` | 重写 | 导出 `agent_app`, `AgentState`, `DiagnosisResult`, `EvidenceItem`, `TimeRange`, `ToolCallRecord` |
| `src/telecomops_agent/api/routes.py` | 重写 diagnose 端点 | 从 `_build_mock_diagnosis()` 直接返回改为 `agent_app.ainvoke(initial_state)` 调用 LangGraph；保留 mock 反馈端点 |

### 未修改文件

| 文件 | 原因 |
|---|---|
| `src/telecomops_agent/api/main.py` | 已满足要求，无需修改 |
| `src/telecomops_agent/api/schemas.py` | 现有 schema 已覆盖 workflow 输出映射 |
| `src/telecomops_agent/api/errors.py` | 异常类已就绪 |
| `src/telecomops_agent/api/dependencies.py` | 无需额外的依赖注入 |
| `tests/conftest.py` | 现有 TestClient fixture 已满足要求 |
| `pyproject.toml` | 配置正确 |
| `.env.example` | 无需变更 |

---

## 3. 项目目录结构（Milestone 3 完成后）

```text
TelecomOps-Agent/
├── .env.example
├── .gitignore
├── CLAUDE.md
├── README.md
├── pyproject.toml
├── requirements.txt                    ← +langgraph, langchain-core
├── configs/
│   └── app.yaml
├── data/
│   └── mock/
│       └── .gitkeep
├── docs/
│   ├── design/
│   │   ├── README.md
│   │   ├── api_design.md
│   │   ├── architecture.mmd
│   │   ├── langgraph_workflow_design.md
│   │   ├── neo4j_schema.md
│   │   ├── postgres_schema.sql
│   │   └── resume_project_description.md
│   └── progress/
│       ├── milestone1_summary.md
│       ├── milestone2_summary.md
│       └── milestone3_summary.md       ← 本文件
├── src/
│   └── telecomops_agent/
│       ├── __init__.py                 ← __version__ = "0.1.0"
│       ├── agent/                      ← Milestone 3 核心新增
│       │   ├── __init__.py             ← 导出 agent_app + 状态模型
│       │   ├── state.py                ← AgentState TypedDict + Pydantic 模型
│       │   ├── nodes.py                ← 13 个 deterministic 节点
│       │   └── graph.py                ← LangGraph StateGraph + agent_app
│       ├── api/
│       │   ├── __init__.py
│       │   ├── main.py                 ← FastAPI app 工厂
│       │   ├── routes.py               ← /diagnose 调用 agent_app.ainvoke()
│       │   ├── schemas.py              ← API 请求/响应 Pydantic 模型
│       │   ├── dependencies.py
│       │   └── errors.py
│       ├── db/                         ← 空包（后续 milestone）
│       │   └── __init__.py
│       ├── evaluation/                 ← 空包
│       │   └── __init__.py
│       ├── retrievers/                 ← 空包
│       │   └── __init__.py
│       ├── tools/                      ← 空包
│       │   └── __init__.py
│       └── utils/
│           └── __init__.py
└── tests/
    ├── __init__.py
    ├── conftest.py                     ← TestClient fixture
    ├── test_api.py                     ← API 端点测试 (现有, 26 tests)
    └── test_agent_graph.py             ← 新增, 38 tests
```

---

## 4. 已完成的功能

### 4.1 AgentState（`agent/state.py`）

```python
class AgentState(TypedDict, total=False):
    # Raw user input
    query: str
    session_id: str
    user_id: Optional[str]

    # Parsed context / intent
    intent: str                         # 8 intents: kpi_query, alarm_query, fault_diagnosis, ...
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

    # Evidence buckets
    rag_evidence: List[EvidenceItem]
    sql_evidence: List[EvidenceItem]
    graph_evidence: List[EvidenceItem]
    case_evidence: List[EvidenceItem]
    fused_evidence: List[EvidenceItem]

    # Reasoning output
    diagnosis: Optional[DiagnosisResult]  # symptoms, possible_causes, recommended_actions, confidence
    report_markdown: Optional[str]

    # Control flags
    enough_evidence: bool
    needs_human_review: bool
    final_answer: Optional[str]
```

辅助 Pydantic 模型：
- `TimeRange(start, end)` — ISO 8601 时间范围
- `ToolCallRecord(tool_name, input, output, error, latency_ms)` — 工具调用记录
- `EvidenceItem(source, title, content, score, metadata)` — 证据项（sources: rag / sql / graph / case / oss）
- `DiagnosisResult(symptoms, possible_causes, recommended_actions, confidence, missing_evidence)` — 结构化诊断

### 4.2 节点实现（`agent/nodes.py`）

| # | 节点 | 实现方式 | 核心逻辑 |
|---|---|---|---|
| 1 | `input_guard` | Regex 规则 | 拒绝 SQL injection / XSS；归一化空白符；初始化 `retry_count=0`, `tool_calls=[]`, 各 evidence 为空 |
| 2 | `intent_classifier` | 关键词匹配 | 中英文关键词 → 8 种 intent（`fault_diagnosis`, `kpi_query`, `alarm_query`, `parameter_check`, `handover_analysis`, `coverage_analysis`, `report_generation`, `general_qa`） |
| 3 | `entity_extractor` | Regex + 字典 | 正则提取 `cell_id`（如 `SZ-NS-023-2`）、`site_id`；字典匹配 `kpi_names`（RSRP, SINR, 掉话率...）、`alarm_names`（VSWR, RRU...）；正则解析 `time_range`（最近N小时/分钟/天） |
| 4 | `planner` | 模板映射 | 根据 intent 返回预设的计划步骤列表（fault_diagnosis → 5 步，kpi_query → 3 步，etc.） |
| 5 | `tool_router` | 规则队列 | 根据 intent 构建工具调用队列；按目标节点类型去重；重新进入时 `retry_count += 1` |
| 6 | `sql_query_node` | Mock | 返回确定性 KPI 趋势（RSRP -88→-106 dBm）+ 告警记录（VSWR_HIGH, RRU_POWER_LOW） |
| 7 | `graph_query_node` | Mock | 返回确定性多跳推理路径（RSRP_DROP → VSWR_HIGH → AntennaFeederIssue → CheckFeederConnection） |
| 8 | `rag_retriever_node` | Mock | 返回确定性 SOP 文档片段（VSWR 排查 SOP + RSRP 下降分析方法） |
| 9 | `case_search_node` | Mock | 返回确定性历史案例（HC-2024-0815 相似度 0.87 + HC-2025-0302 相似度 0.63） |
| 10 | `evidence_fusion` | 规则排序 | 合并 4 类 evidence，按标题去重，按来源优先级排序（sql > graph > case > rag） |
| 11 | `diagnosis_reasoner` | 模板提取 | 从 `fused_evidence` 提取 symptoms/causes/actions；根据证据来源多样性计算 confidence（≥3 sources + ≥4 items → high） |
| 12 | `reflection_node` | 规则判断 | 检查 evidence 是否覆盖 sql + graph；缺失超过 2 项 → 不足；`retry_count >= 2` → human_review |
| 13 | `report_generator` | 模板组装 | 生成 7 节中文 Markdown 报告：查询概要 → 症状 → 证据表 → 根因分析 → 排查步骤 → 置信度与风险 → 后续建议 |

### 4.3 API 端点集成

`POST /api/v1/diagnose` 现在调用完整的 LangGraph workflow：

```python
result = await agent_app.ainvoke(initial_state)
# → 映射回 DiagnosisResponse(
#     answer=result["final_answer"],
#     result=result["diagnosis"],
#     evidence=result["fused_evidence"],
#     tool_traces=result["tool_calls"] (debug=True 时),
#     needs_human_review=result["needs_human_review"],
# )
```

### 4.4 关键设计决策

**工具路由的去重机制**：多个逻辑工具（`sql_kpi_tool`, `sql_alarm_tool`, `sql_param_tool`）映射到同一个节点（`sql_query`）。`tool_router` 使用 `_TOOL_TO_NODE` 映射表，按**目标节点**而非工具名去重，避免同一节点被重复调用。当 `sql_kpi_tool` 被执行后，`sql_alarm_tool` 和 `sql_param_tool` 会从队列中被跳过。

**重试计数**：`tool_router` 在检测到已有 tool calls 时自动递增 `retry_count`。`reflection_node` + `should_continue` 检查 `retry_count >= 2` → `human_review`，保证循环不会无限进行。

**确定性优先**：所有节点不使用 LLM 调用，输出完全可预测、可重复、可测试。后续可逐节点替换为 LLM 调用。

---

## 5. 测试结果

```text
74 passed in ~9s
```

### 测试用例明细

| 测试类 | 测试数 | 覆盖内容 |
|---|---|---|
| `TestHealthCheck` | 4 | 200、status、service、content-type |
| `TestDiagnose` | 13 | LangGraph-backed diagnose 响应结构 + 置信度 + debug toggle + evidence 来源 + 缺少字段 422 |
| `TestFeedback` | 5 | rating 1-5 校验 + comment 支持 + 越界 422 |
| `TestPackageImports` | 8 | 主包 + 7 个子包可导入 |
| **新增 →** `TestInputGuard` | 5 | 初始化控制字段 + 空白符归一化 + SQL injection / DELETE / XSS 拒绝 |
| **新增 →** `TestIntentClassifier` | 8 | 8 种 intent 分类正确性 + fallback 到 general_qa |
| **新增 →** `TestEntityExtractor` | 5 | cell_id/site_id 提取 + KPI 名称识别 + time_range 解析 + 无 cell 返回 None |
| **新增 →** `TestPlanner` | 1 | fault_diagnosis 计划包含 KPI 和 alarm 步骤 |
| **新增 →** `TestToolRouter` | 3 | fault_diagnosis 路由包含 sql/graph/case + 重入递增 retry_count + 全部完成后队列为空 |
| **新增 →** `TestMockToolNodes` | 4 | SQL/Graph/RAG/Case 各返回正确 source 的 evidence + tool_call 记录 |
| **新增 →** `TestEvidenceFusion` | 1 | 合并后 fused_evidence >= 3 条 |
| **新增 →** `TestDiagnosisReasoner` | 1 | 生成 symptoms/causes/actions 非空 + confidence 合法值 |
| **新增 →** `TestReflectionNode` | 3 | sql+graph → enough=True；仅 sql → 不足；retry_count>=2 → human_review |
| **新增 →** `TestReportGenerator` | 1 | 生成 >100 字符的中文 Markdown 报告 |
| **新增 →** `TestGraphStructure` | 3 | 编译为 CompiledStateGraph；13 个必需节点全部存在；entry point 为 input_guard；report_generator → END |
| **新增 →** `TestEndToEndWorkflow` | 9 | RSRP query 生成 final_answer + diagnosis + confidence + fused_evidence + tool_calls；无 cell 也可完成；needs_human_review 为 bool；报告含 7 章节；8 种 intent 全部 smoke test |

### 运行命令

```bash
source /root/miniconda3/etc/profile.d/conda.sh
conda activate telecomops-agent
cd /root/autodl-tmp/TelecomOps-Agent

# 编译检查
python -m compileall src tests

# 全部测试
python -m pytest -q

# 仅 agent graph 测试
python -m pytest tests/test_agent_graph.py -v

# 启动 API 测试
uvicorn src.telecomops_agent.api.main:app --host 0.0.0.0 --port 8000

curl -X POST "http://localhost:8000/api/v1/diagnose" \
  -H "Content-Type: application/json" \
  -d '{
    "query": "SZ-NS-023-2 最近2小时RSRP下降掉话率升高，请分析原因并给出排查步骤。",
    "cell_id": "SZ-NS-023-2",
    "debug": true
  }' | python -m json.tool
```

---

## 6. LangGraph 图结构：所有节点和边

### 节点（13 个）

```
[input_guard] → [intent_classifier] → [entity_extractor] → [planner] → [tool_router]
                                                                              │
                                                    ┌─────────────────────────┤
                                                    │  route_tools(state)     │
                                                    │  → sql_query            │
                                                    │  → graph_query          │
                                                    │  → rag_retriever        │
                                                    │  → case_search          │
                                                    │  → evidence_fusion      │
                                                    └─────────────────────────┘
                                                                              │
                                              ┌───────────────────────────────┤
                                              │  sql_query ─────────────────┐ │
                                              │  graph_query ───────────────┤ │
                                              │  rag_retriever ─────────────┤ │
                                              │  case_search ───────────────┤ │
                                              │  evidence_fusion ←──────────┘ │
                                              └───────────────────────────────┘
                                                     │
                                              [diagnosis_reasoner]
                                                     │
                                              [reflection_node]
                                               ╱    │     ╲
                                   should_continue(state)
                                   → retry ──────────────────────→ tool_router (循环)
                                   → report ─────────────────────→ report_generator
                                   → human_review ───────────────→ report_generator
                                                                       │
                                                                      END
```

### 条件路由函数

```python
def route_tools(state: AgentState) -> str:
    """从 next_tools 队列取第一个未调用的工具，映射到目标节点。
       队列为空 → 'evidence_fusion'"""
    # sql_kpi_tool / sql_alarm_tool / sql_param_tool → 'sql_query'
    # graph_fault_tool → 'graph_query'
    # rag_tool → 'rag_retriever'
    # case_search_tool → 'case_search'

def should_continue(state: AgentState) -> str:
    """enough_evidence=True → 'report'
       needs_human_review=True → 'human_review'
       retry_count >= 2 → 'human_review'
       否则 → 'retry'"""
```

### 边汇总

| 类型 | 边 |
|---|---|
| 直线边 | input_guard → intent_classifier → entity_extractor → planner → tool_router |
| 直线边 | sql_query → evidence_fusion |
| 直线边 | graph_query → evidence_fusion |
| 直线边 | rag_retriever → evidence_fusion |
| 直线边 | case_search → evidence_fusion |
| 直线边 | evidence_fusion → diagnosis_reasoner → reflection |
| 直线边 | report_generator → END |
| 条件边 | tool_router → {sql_query, graph_query, rag_retriever, case_search, evidence_fusion} |
| 条件边 | reflection → {tool_router (retry), report_generator (report), report_generator (human_review)} |

---

## 7. 当前没有做的事情

| 未实现 | 归属阶段 |
|---|---|
| **真实 LLM 调用** — 所有节点为 deterministic / rule-based | Milestone 5+ |
| **真实 SQL 工具** — `sql_query_node` 返回硬编码 mock 数据 | Milestone 4 |
| **真实 Neo4j 工具** — `graph_query_node` 返回硬编码 mock 路径 | Milestone 4 |
| **真实 RAG 检索** — `rag_retriever_node` 返回硬编码 SOP 片段 | Milestone 4 |
| **真实 Case Search** — `case_search_node` 返回硬编码历史案例 | Milestone 4 |
| **工具层抽象** — 无 `tools/base.py`, `tools/sql_tool.py` 等独立工具类 | Milestone 4 |
| **Mock 数据文件** — 无 `data/mock/kpi_15min.csv` 等数据文件 | Milestone 4 |
| **Mock 数据生成脚本** — 无 `scripts/generate_mock_data.py` | Milestone 4 |
| **API 工具调试端点** — 无 `/api/v1/tools/sql/query` 等端点 | Milestone 4 |
| **Multi-turn Chat** — `/api/v1/chat` 端点未实现 | 后续 |
| **向量检索器** — `retrievers/` 为空包 | Milestone 4 |
| **数据库连接层** — `db/` 为空包 | Milestone 4 |
| **LLM Prompt 模板** — 无 `agent/prompts.py` | Milestone 5+ |
| **配置加载工具** — 无 `utils/config.py` | Milestone 4 |
| **Docker Compose** — 无 PostgreSQL/Neo4j 容器编排 | Milestone 4 |
| **Streaming / SSE** | Milestone 5+ |
| **LangSmith / Tracing** | Milestone 5+ |
| **RAGAS 评估** | Milestone 5+ |
| **Feedback 持久化** — `POST /api/v1/feedback` 仍为 mock | Milestone 4 |

---

## 8. 下一阶段建议

### Milestone 4 — 真实数据库 + 真实工具

建议按以下顺序推进：

1. **编写 `docker-compose.yml`** — 启动 PostgreSQL + Neo4j（一键本地开发环境）
2. **实现 `db/postgres.py`** — asyncpg / SQLAlchemy async 连接管理 + 连接池
3. **实现 `db/neo4j.py`** — neo4j async driver 连接管理
4. **创建工具层抽象** — `tools/base.py` `ToolBase` 基类
5. **重写 `tools/sql_tool.py`** — 从 mock 切换到真实 PostgreSQL 查询（模板化 SQL）
6. **重写 `tools/graph_tool.py`** — 从 mock 切换到真实 Neo4j Cypher 查询
7. **编写 mock 数据 + 导入脚本** — `scripts/generate_mock_data.py` + `scripts/init_postgres.py` + `scripts/init_neo4j.py`
8. **实现 `retrievers/` 向量检索** — FAISS + sentence-transformers embedding
9. **更新 LangGraph 节点** — `sql_query_node` / `graph_query_node` / `rag_retriever_node` 调用真实工具
10. **添加工具调试端点** — `/api/v1/tools/sql/query`, `/api/v1/tools/graph/query`, `/api/v1/tools/rag/search`
11. **Feedback 持久化** — 将反馈存储到 PostgreSQL

### Milestone 4 预期新增依赖

```
docker-compose          ← 基础设施编排
asyncpg                 ← PostgreSQL async driver
neo4j                   ← Neo4j async driver
sqlalchemy[asyncio]     ← ORM (可选)
sentence-transformers   ← embedding 模型
faiss-cpu               ← 向量检索
```

---

## 9. 架构决策记录

### 9.1 为什么先用 deterministic / rule-based 节点？

1. **可测试性** — 输出确定、可重复、可断言，74 个测试全部通过
2. **快速迭代** — 毫秒级响应，无需等待 LLM API
3. **成本控制** — 零 API 调用费用
4. **渐进替换** — 每个节点可独立替换为 LLM 调用，不影响其他节点

### 9.2 为什么 AgentState 使用 TypedDict(total=False)？

- LangGraph 原生支持 TypedDict 作为 state schema
- `total=False` 使每个节点只需返回它修改的 key 子集，LangGraph 自动合并
- 与 LangGraph 的 `add_node` / `add_conditional_edges` API 完全兼容

### 9.3 为什么工具路由按目标节点去重？

多个逻辑工具（`sql_kpi_tool`, `sql_alarm_tool`, `sql_param_tool`）映射到同一个 LangGraph 节点（`sql_query`）。只按工具名去重会导致同一节点被重复调用（因为 `ToolCallRecord` 记录的 tool_name 总是第一个工具的）。按目标节点去重解决了这个问题，同时保留了工具队列的语义清晰性。
