# Milestone 1 — 项目骨架搭建 完成总结

**完成日期**: 2026-06-03
**分支**: main

---

## 1. 本阶段目标

搭建 TelecomOps-Agent 项目的标准 Python 工程骨架，包括：

- 标准 Python 包结构（`src/telecomops_agent/`）
- 子包目录预留（api、agent、tools、db、retrievers、evaluation、utils）
- 项目配置文件（pyproject.toml、requirements.txt、.env.example、.gitignore）
- 最小可运行的 FastAPI 入口（仅 health check）
- 最小 pytest 测试（health check + 包导入验证）

明确不做的内容：LangGraph 业务流程、SQL/Neo4j/RAG 工具实现、数据库连接、大模型调用。

---

## 2. 创建/修改的文件

### 新增文件

| 文件 | 说明 |
|---|---|
| `pyproject.toml` | 项目元数据、构建系统配置（setuptools），pytest/ruff 工具配置 |
| `requirements.txt` | 当前阶段最小依赖：fastapi, uvicorn, pydantic, pydantic-settings, pytest, pytest-asyncio, httpx, ruff |
| `.env.example` | 环境变量模板（API、PostgreSQL、Neo4j、LLM、Embedding、日志） |
| `configs/app.yaml` | 应用配置模板（所有工具开关默认 false） |
| `data/mock/.gitkeep` | mock 数据目录占位 |
| `src/telecomops_agent/__init__.py` | 主包，定义 `__version__ = "0.1.0"` |
| `src/telecomops_agent/api/__init__.py` | API 子包 |
| `src/telecomops_agent/api/main.py` | FastAPI app 工厂（CORS + router），创建 `app` 实例 |
| `src/telecomops_agent/api/routes.py` | `GET /health` → `{"status": "ok", "version": "0.1.0"}` |
| `src/telecomops_agent/api/schemas.py` | `HealthResponse`、`ErrorResponse` Pydantic 模型 |
| `src/telecomops_agent/api/dependencies.py` | 依赖注入占位（为后续准备） |
| `src/telecomops_agent/api/errors.py` | `TelecomOpsError`、`InvalidRequestError`、`ToolExecutionError`、`InsufficientEvidenceError` |
| `src/telecomops_agent/agent/__init__.py` | Agent 子包占位（LangGraph 后续添加） |
| `src/telecomops_agent/tools/__init__.py` | 工具子包占位（RAG/SQL/Graph 后续添加） |
| `src/telecomops_agent/db/__init__.py` | 数据库子包占位（PostgreSQL/Neo4j 后续添加） |
| `src/telecomops_agent/retrievers/__init__.py` | 检索子包占位（向量搜索后续添加） |
| `src/telecomops_agent/evaluation/__init__.py` | 评估子包占位（指标/数据集后续添加） |
| `src/telecomops_agent/utils/__init__.py` | 工具子包占位（日志/配置后续添加） |
| `tests/__init__.py` | 测试包 |
| `tests/conftest.py` | FastAPI TestClient fixture |
| `tests/test_api.py` | 10 个测试：health check × 2 + 包导入 × 8 |
| `docs/progress/milestone1_summary.md` | 本文件 |

### 修改文件

| 文件 | 说明 |
|---|---|
| `.gitignore` | 修复原有异常格式，补充 Python/IDE/OS/构建/密钥忽略规则 |

---

## 3. 项目目录结构

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
│       └── milestone1_summary.md
├── scripts/                    ← 空（后续添加脚本）
├── src/
│   └── telecomops_agent/
│       ├── __init__.py          ← __version__ = "0.1.0"
│       ├── api/                 ← FastAPI（仅 health check）
│       │   ├── __init__.py
│       │   ├── main.py          ← app 工厂 + CORS
│       │   ├── routes.py        ← GET /health
│       │   ├── schemas.py       ← HealthResponse, ErrorResponse
│       │   ├── dependencies.py  ← 占位
│       │   └── errors.py        ← 异常类
│       ├── agent/               ← 空包（LangGraph 后续）
│       ├── db/                  ← 空包（数据库后续）
│       ├── evaluation/          ← 空包（评估后续）
│       ├── retrievers/          ← 空包（检索后续）
│       ├── tools/               ← 空包（工具后续）
│       └── utils/               ← 空包
└── tests/
    ├── __init__.py
    ├── conftest.py              ← TestClient fixture
    └── test_api.py              ← 10 tests
```

---

## 4. 已完成的功能

- **FastAPI 应用工厂** (`src/telecomops_agent/api/main.py`)：支持 CORS、可扩展的 app 创建模式
- **Health check 端点** (`GET /health`)：返回 `{"status": "ok", "version": "0.1.0"}`
- **错误处理框架**：4 个自定义异常类，覆盖请求验证、工具执行、证据不足等场景
- **Pydantic Schema**：`HealthResponse` 和 `ErrorResponse`
- **可编辑安装兼容**：`pyproject.toml` 配置 `[tool.setuptools.packages.find] where = ["src"]`
- **10 个 pytest 测试**全部通过
- **环境隔离**：所有操作在 `telecomops-agent` conda 环境中完成，未污染 base 环境

---

## 5. 测试结果

```text
10 passed in 0.50s
```

| 测试类 | 测试用例 | 验证内容 |
|---|---|---|
| `TestHealthCheck` | `test_health_check_returns_ok` | `/health` 返回 200，含 `status` 和 `version` |
| `TestHealthCheck` | `test_health_check_content_type` | 响应 Content-Type 为 `application/json` |
| `TestPackageImports` | `test_import_telecomops_agent` | 主包可导入，`__version__` 正确 |
| `TestPackageImports` | `test_import_api` | api 子包（main, routes, schemas, errors）可导入 |
| `TestPackageImports` | `test_import_agent` | agent 子包可导入 |
| `TestPackageImports` | `test_import_tools` | tools 子包可导入 |
| `TestPackageImports` | `test_import_db` | db 子包可导入 |
| `TestPackageImports` | `test_import_retrievers` | retrievers 子包可导入 |
| `TestPackageImports` | `test_import_evaluation` | evaluation 子包可导入 |
| `TestPackageImports` | `test_import_utils` | utils 子包可导入 |

---

## 6. 当前没有做的事情

以下内容属于后续 milestone，本阶段明确不实现：

| 未实现 | 归属阶段 |
|---|---|
| LangGraph 工作流定义（`agent/state.py`、`graph.py`、`nodes.py`） | Milestone 2+ |
| Intent Classifier / Entity Extractor / Planner / Tool Router 节点 | Milestone 2+ |
| PostgreSQL KPI/SQL Tool | Milestone 3+（需数据库） |
| Neo4j Graph Tool | Milestone 3+（需 Neo4j） |
| RAG Retrieval Tool | Milestone 3+（需向量数据库） |
| Case Search Tool | Milestone 3+ |
| Report Generator | Milestone 3+ |
| `/api/v1/diagnose` 业务路由 | Milestone 2+ |
| `/api/v1/chat` 多轮对话路由 | Milestone 2+ |
| 工具调试端点（`/api/v1/tools/*`） | Milestone 3+ |
| Feedback 端点 | Milestone 3+ |
| `docker-compose.yml` | 基础设施就绪后 |
| `scripts/` 下的数据初始化脚本 | 有 mock 数据后 |
| mock KPI / alarm / case 数据生成 | Milestone 2+ |
| LLM / Embedding 调用 | 后续阶段 |

---

## 7. 下一阶段建议

### Milestone 2 — LangGraph 工作流骨架

建议优先级：

1. **定义 AgentState** — 根据 `docs/design/langgraph_workflow_design.md` 第 2 节实现完整的 `TypedDict` state
2. **搭建 LangGraph 图骨架** — 创建 `agent/graph.py`，添加所有节点（用 mock/rule-based 逻辑）
3. **创建 mock 数据生成脚本** — `scripts/generate_mock_data.py`，生成 KPI、告警、案例的 mock 数据
4. **创建 `agent/prompts.py`** — 集中管理 LLM prompt 模板（先用占位文本）
5. **添加测试** — 验证 LangGraph 图可以编译和运行基本路径
6. **API 路由扩展** — 添加 `/api/v1/diagnose` 端点（返回 mock 结果）

新增依赖预估：`langgraph`, `langchain-core`, `pyyaml`（已在 uvicorn 依赖中）

### 验证命令（当前阶段）

```bash
source /root/miniconda3/etc/profile.d/conda.sh
conda activate telecomops-agent
cd /root/autodl-tmp/TelecomOps-Agent

python -m compileall src tests    # 语法检查
python -m pytest -q               # 运行测试 → 10 passed

# 手动启动验证
uvicorn src.telecomops_agent.api.main:app --host 0.0.0.0 --port 8000 --reload
# 另一个终端:
curl http://localhost:8000/health  # → {"status":"ok","version":"0.1.0"}
# 浏览器: http://localhost:8000/docs
```
