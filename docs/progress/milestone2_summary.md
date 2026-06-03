# Milestone 2 — FastAPI API 骨架补全 完成总结

**完成日期**: 2026-06-03
**分支**: main
**依赖 milestone**: [Milestone 1](milestone1_summary.md)

---

## 1. 本阶段目标

在 Milestone 1 的项目骨架基础上，对照 `docs/design/api_design.md` 审查现有实现并补齐缺失的 API 层内容：

- 补全 Pydantic schemas（诊断请求/响应、反馈、证据等 11 个模型）
- 补全 API routes（diagnose、feedback 端点）
- 实现 deterministic mock 诊断响应（不调 LLM、不连数据库、不走 LangGraph）
- 补齐测试覆盖（从 10 个扩展到 29 个）

---

## 2. 创建/修改的文件

### 修改文件

| 文件 | 新增行 | 操作说明 |
|---|---|---|
| `src/telecomops_agent/api/schemas.py` | +119 | 从 2 个模型（HealthResponse, ErrorResponse）扩展到 11 个模型 |
| `src/telecomops_agent/api/routes.py` | +186 | 从 1 个端点（GET /health）扩展到 3 个端点 |
| `tests/test_api.py` | +191 | 从 10 个测试扩展到 29 个测试 |

### 未修改文件（保持 Milestone 1 原样）

| 文件 | 原因 |
|---|---|
| `src/telecomops_agent/api/main.py` | 已满足要求（app 工厂 + CORS + router） |
| `src/telecomops_agent/api/__init__.py` | 无需变更 |
| `src/telecomops_agent/api/dependencies.py` | 占位，后续使用 |
| `src/telecomops_agent/api/errors.py` | 自定义异常类已就绪 |
| `tests/conftest.py` | TestClient fixture 已满足需要 |
| `requirements.txt` | fastapi/uvicorn/pydantic/pytest/httpx 均已包含 |
| `pyproject.toml` | src layout + pytest 配置已正确 |

---

## 3. 项目目录结构（当前状态）

```text
TelecomOps-Agent/
├── .env.example
├── .gitignore
├── CLAUDE.md
├── README.md
├── pyproject.toml
├── requirements.txt
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
│       └── milestone2_summary.md
├── scripts/                    ← 空
├── src/
│   └── telecomops_agent/
│       ├── __init__.py
│       ├── api/
│       │   ├── __init__.py
│       │   ├── main.py          ← FastAPI app 工厂
│       │   ├── routes.py        ← GET /health, POST /api/v1/diagnose, POST /api/v1/feedback
│       │   ├── schemas.py       ← 11 个 Pydantic 模型
│       │   ├── dependencies.py  ← 占位
│       │   └── errors.py        ← 4 个异常类
│       ├── agent/               ← 空包
│       ├── db/                  ← 空包
│       ├── evaluation/          ← 空包
│       ├── retrievers/          ← 空包
│       ├── tools/               ← 空包
│       └── utils/               ← 空包
└── tests/
    ├── __init__.py
    ├── conftest.py
    └── test_api.py              ← 29 tests
```

---

## 4. 已完成的功能

### 4.1 Pydantic Schemas（11 个模型）

| 模型 | 类型 | 说明 |
|---|---|---|
| `ConfidenceLevel` | `str, Enum` | low / medium / high |
| `TimeRange` | `BaseModel` | start: datetime\|None, end: datetime\|None |
| `DiagnosisRequest` | `BaseModel` | query, session_id, user_id, site_id, cell_id, time_range, language="zh", debug |
| `EvidenceItem` | `BaseModel` | source, title, content, score, metadata |
| `ToolTrace` | `BaseModel` | tool_name, input, output_summary, error, latency_ms |
| `DiagnosisResult` | `BaseModel` | symptoms, possible_causes, recommended_actions, confidence, risk_notes |
| `DiagnosisResponse` | `BaseModel` | query_id, session_id, answer, result, evidence, tool_traces, latency_ms, needs_human_review |
| `FeedbackRequest` | `BaseModel` | query_id, rating (ge=1, le=5), is_correct, comment |
| `FeedbackResponse` | `BaseModel` | status, query_id |
| `HealthResponse` | `BaseModel` | status, service |
| `ErrorResponse` | `BaseModel` | error_code, message, details, suggestion |

全部使用 Pydantic v2 风格（`| None` 替代 `Optional`，`list[...]` / `dict[...]` 替代 `List[...]` / `Dict[...]`）。

### 4.2 API 端点（3 个）

| 方法 | 路径 | 说明 |
|---|---|---|
| GET | `/health` | 返回 `{"status": "ok", "service": "telecomops-agent"}` |
| POST | `/api/v1/diagnose` | 接收 DiagnosisRequest，返回 mock DiagnosisResponse（含 2 条 evidence、debug 控制 tool_traces） |
| POST | `/api/v1/feedback` | 接收 FeedbackRequest（rating 1-5 自动校验），返回 FeedbackResponse |

### 4.3 Mock 诊断响应特性

- `query_id`：uuid4 hex 生成
- `answer`：面向电信运维诊断场景的 Markdown 报告（症状 → 根因 → 建议 → 置信度 → 风险）
- `result`：包含 symptoms（3 条）、possible_causes（3 条）、recommended_actions（4 条）、confidence="high"
- `evidence`：2 条（sql + graph），每条含 source/title/content/score/metadata
- `tool_traces`：debug=true 时返回 3 条 trace（sql_kpi_tool, graph_fault_tool, case_search_tool），debug=false 时为空列表
- `needs_human_review`：false

---

## 5. 测试结果

```text
29 passed, 1 warning in 2.99s
```

### 测试用例明细

| 测试类 | 测试数 | 覆盖内容 |
|---|---|---|
| `TestHealthCheck` | 4 | 200、status="ok"、service 值、content-type |
| `TestDiagnose` | 12 | 200、query_id、answer、result、evidence、tool_traces、needs_human_review、confidence 校验、debug=true 时 tool_traces 非空、debug=false 时 tool_traces 为空列表、evidence 含 sql+graph、缺 query 返回 422 |
| `TestFeedback` | 5 | rating=5 → 200、rating=6 → 422、rating=0 → 422、rating=1 → 200、含 comment 正常 |
| `TestPackageImports` | 8 | 主包及 7 个子包均可导入 |

### 运行命令

```bash
source /root/miniconda3/etc/profile.d/conda.sh
conda activate telecomops-agent
cd /root/autodl-tmp/TelecomOps-Agent

python -m compileall src tests  # 语法检查
python -m pytest -q -v          # 运行测试
```

---

## 6. 当前没有做的事情

| 未实现 | 归属阶段 |
|---|---|
| LangGraph workflow（agent/state.py, graph.py, nodes.py） | Milestone 3+ |
| AgentState 定义 | Milestone 3+ |
| Intent Classifier / Entity Extractor / Planner 节点 | Milestone 3+ |
| SQL/PostgreSQL Tool | Milestone 3+（需数据库） |
| Neo4j Graph Tool | Milestone 3+（需 Neo4j） |
| RAG Retrieval Tool | Milestone 3+（需向量数据库） |
| Case Search Tool | Milestone 3+ |
| Report Generator | Milestone 3+ |
| `/api/v1/chat` 多轮对话路由 | 后续 milestone |
| 工具调试端点（`/api/v1/tools/*`） | Milestone 3+ |
| 真实 LLM 调用 | diagnose 返回 deterministic mock |
| 数据库连接（PostgreSQL / Neo4j / Vector Store） | 后续 milestone |
| `docker-compose.yml` | 基础设施就绪后 |
| `scripts/` 下的脚本 | 有 mock 数据/数据库时 |
| Streamlit 前端 | 后续 milestone |

---

## 7. 下一阶段建议

### Milestone 3 — LangGraph 工作流骨架 + Mock 数据

建议按以下顺序推进：

1. **定义 AgentState** — 根据 `docs/design/langgraph_workflow_design.md` 第 2 节实现 TypedDict state，将所有字段加入 `agent/state.py`
2. **搭建 LangGraph 图骨架** — 创建 `agent/graph.py`，注册全部节点（input_guard → intent_classifier → ... → report_generator），先用 rule-based / mock 逻辑填充每个节点
3. **创建 `agent/prompts.py`** — 集中管理各节点的 LLM prompt 模板（先用占位文本）
4. **创建 mock 数据生成脚本** — `scripts/generate_mock_data.py`，生成 KPI、告警、案例的 CSV/JSON 数据放入 `data/mock/`
5. **将 mock 路由替换为 LangGraph 调用** — 修改 `/api/v1/diagnose` 调用 `agent_app.ainvoke()`，但 agent 内部仍用 mock logic
6. **添加测试** — 验证 LangGraph 图可以编译、基本 path 可以走通

### 预估新增依赖（Milestone 3）

```
langgraph
langchain-core
pyyaml
```

### API 启动验证

```bash
source /root/miniconda3/etc/profile.d/conda.sh
conda activate telecomops-agent
cd /root/autodl-tmp/TelecomOps-Agent

# 启动
uvicorn src.telecomops_agent.api.main:app --host 0.0.0.0 --port 8000 --reload

# 另一个终端验证
curl http://localhost:8000/health
# → {"status":"ok","service":"telecomops-agent"}

curl -X POST "http://localhost:8000/api/v1/diagnose" \
  -H "Content-Type: application/json" \
  -d '{"query": "Cell SZ-NS-023-2 RSRP drop, please diagnose.", "debug": true}'

curl -X POST "http://localhost:8000/api/v1/feedback" \
  -H "Content-Type: application/json" \
  -d '{"query_id": "abc123", "rating": 5}'
# → {"status":"saved","query_id":"abc123"}

# API 文档: http://localhost:8000/docs
```
