# Resume Project Description: TelecomOps-Agent

## 1. Resume Version - Chinese

### 基于 LangGraph + GraphRAG 的电信运维诊断 Agent 系统

基于真实无线网络运维流程抽象并实现电信故障诊断智能体，将复杂故障处理流程拆解为“问题理解 → 实体抽取 → 工具路由 → 多源证据检索 → 图谱推理 → 反思校验 → 报告生成”的状态机工作流。系统集成 PostgreSQL KPI 查询、Neo4j 知识图谱推理、RAG 文档检索与历史案例检索，支持从故障现象到可能原因、排查步骤和解决方案的自动化闭环。

推荐简历 bullet：

- 基于 LangGraph 设计电信运维 Agent 状态机，将故障诊断拆分为 Intent Classification、Entity Extraction、Planning、Tool Routing、Evidence Fusion、Reflection、Report Generation 等节点，提升复杂任务可观测性与可维护性。
- 构建脱敏电信知识图谱，建模基站、扇区、小区、KPI、告警、故障模式、根因、排查动作等实体关系，支持从 KPI 异常和告警到根因与处理动作的多跳推理。
- 封装 PostgreSQL KPI 查询、Neo4j Cypher 查询、RAG 检索、相似案例召回和运维报告生成等工具，通过 Function Calling / Tool Calling 实现自动工具选择与参数生成。
- 设计 Reflection 与 fallback 机制，在工具调用失败、证据不足、SQL 查询为空或图谱路径缺失时自动改写查询、补充检索或转人工复核，降低 Agent 幻觉风险。
- 构建 Agent 评估集，覆盖 KPI 查询、告警解释、多跳根因诊断、相似案例复用等场景，使用 Tool Accuracy、Evidence Recall、Faithfulness、Task Success Rate、Latency 等指标衡量系统效果。
- 输出可运行 GitHub Demo，包含 FastAPI 服务、LangGraph 工作流、PostgreSQL/Neo4j schema、模拟电信数据、诊断报告样例与评估脚本，作为企业级 Agent 工程能力证明。

---

## 2. Resume Version - English

### TelecomOps Diagnosis Agent with LangGraph and GraphRAG

Designed and implemented a telecom operations diagnosis agent based on LangGraph and GraphRAG. The system decomposes wireless network troubleshooting into a stateful workflow: query understanding, entity extraction, tool routing, multi-source evidence retrieval, graph reasoning, reflection, and report generation. It integrates PostgreSQL KPI queries, Neo4j knowledge graph reasoning, RAG-based document retrieval, and historical case search to automate the loop from symptoms to root causes and recommended actions.

Suggested resume bullets:

- Built a LangGraph-based state machine for telecom fault diagnosis, including intent classification, entity extraction, planning, tool routing, evidence fusion, reflection, and report generation.
- Modeled a desensitized telecom knowledge graph in Neo4j with entities such as sites, cells, KPIs, alarms, fault modes, root causes, and troubleshooting actions, enabling multi-hop reasoning from KPI anomalies and alarms to root causes.
- Implemented tool calling for PostgreSQL KPI queries, Neo4j Cypher queries, RAG retrieval, historical case search, and operation report generation.
- Designed reflection and fallback mechanisms to handle tool failures, empty SQL results, missing graph paths, and insufficient evidence, reducing hallucination risk in complex diagnosis tasks.
- Built an evaluation set covering KPI lookup, alarm explanation, multi-hop root cause analysis, and similar-case retrieval, measuring Tool Accuracy, Evidence Recall, Faithfulness, Task Success Rate, and Latency.
- Delivered a runnable GitHub demo with FastAPI, LangGraph workflow, PostgreSQL/Neo4j schemas, mock telecom data, diagnosis report examples, and evaluation scripts.

---

## 3. GitHub Project Tagline

```text
TelecomOps-Agent: A production-style telecom fault diagnosis agent powered by LangGraph, GraphRAG, PostgreSQL, Neo4j, and RAG.
```

Chinese tagline:

```text
TelecomOps-Agent：基于 LangGraph + GraphRAG + 多工具调用的电信运维故障诊断智能体。
```

---

## 4. 30-second Interview Pitch

中文：

> 这个项目是我把电信运维场景抽象成可开源展示的 Agent 工程项目。它不是简单的 RAG 问答，而是把故障诊断拆成 LangGraph 状态机：先识别问题类型和基站小区实体，再根据任务选择 SQL、Neo4j、RAG、案例库等工具，最后融合证据生成诊断报告。项目重点体现三个能力：第一是 Agent 工作流设计，第二是结构化数据、知识图谱和非结构化文档的联合检索，第三是通过 Reflection 和评估指标控制幻觉和工具误用。

English:

> This project is a production-style demo of a telecom operations diagnosis agent. It is not a simple RAG chatbot. I model the troubleshooting process as a LangGraph state machine: intent detection, entity extraction, planning, tool routing, evidence retrieval, graph reasoning, reflection, and report generation. The key value is that it combines structured KPI data, a Neo4j knowledge graph, RAG documents, and historical cases to produce evidence-grounded diagnosis reports.

---

## 5. 2-minute Interview Explanation

中文：

> 在电信运维里，一个故障现象通常不是单点问题，比如 RSRP 下降可能来自天馈问题、功率参数变化、邻区关系异常、干扰或者站点硬件故障。如果只是普通 RAG，很难同时处理 KPI 时序数据、告警记录、参数变更和知识图谱推理。所以我把这个项目设计成多工具 Agent。
>
> 工作流上，我用 LangGraph 显式定义 Agent 状态，包括用户问题、识别出的站点和小区、时间范围、计划、工具调用记录、检索证据、诊断结论和置信度。节点包括意图识别、实体抽取、规划、工具路由、SQL 查询、图谱查询、RAG 检索、案例检索、证据融合、诊断推理、反思和报告生成。
>
> 数据层面，PostgreSQL 存储 KPI、告警、参数变更和工单；Neo4j 存储基站、小区、KPI 异常、故障模式、根因和处理动作之间的关系；向量库用于 SOP 和历史案例检索。最终 Agent 会把这些证据融合起来，生成一份带依据的运维诊断报告。
>
> 我认为这个项目的重点不是“会调用大模型”，而是展示企业级 Agent 需要考虑的工程问题：工具怎么选、状态怎么传、证据不足怎么办、SQL 查不到怎么办、图谱路径缺失怎么办、最终答案如何评估。这些也是我想通过 GitHub 项目证明的能力。

---

## 6. Interview Deep-dive Questions and Strong Answers

### Q1: 这个项目为什么需要 Agent，而不是普通 RAG？

答：

> 普通 RAG 更适合从文档中回答知识型问题，但电信运维诊断需要同时访问多种数据源，包括 KPI 时序数据、告警、参数变更、知识图谱和历史工单。Agent 的价值在于可以根据问题动态选择工具，并根据中间结果继续规划下一步。例如 RSRP 下降时，系统可能先查 KPI 趋势，再查同时间段告警，再查最近参数变更，最后结合知识图谱判断可能根因。所以这里需要 Agent 的状态管理和工具调用能力，而不是一次性文档检索。

### Q2: GraphRAG 在这个项目里解决了什么问题？

答：

> GraphRAG 主要解决多跳推理和领域关系显式建模的问题。比如“RSRP 下降”只是一个 KPI 异常，它可能指向“覆盖退化”这个故障模式，而覆盖退化又可能由天馈问题、功率参数错误、站点硬件异常等根因引起，每个根因对应不同排查动作。用 Neo4j 可以把 KPI、告警、故障模式、根因和处理动作建成路径，Agent 查询图谱后能拿到可解释的推理链，而不是只依赖 LLM 自己猜。

### Q3: 如何降低 Agent 幻觉？

答：

> 我主要从三个层面控制：第一，答案必须基于 SQL、图谱或 RAG 返回的证据，报告里保留 evidence；第二，引入 Reflection 节点检查证据是否足够，比如有没有 KPI 证据、告警证据、图谱路径和相似案例，如果不足就继续检索或降置信度；第三，对高风险结论设置 human review，比如证据冲突、工具失败超过重试次数、或者只能给出低置信度判断时，不直接给确定结论。

### Q4: LangGraph 的状态怎么设计？

答：

> 我会把状态分成几类：输入上下文，如 query、site_id、cell_id、time_range；任务理解结果，如 intent、entities、plan；工具调用轨迹，如 tool_calls、tool_errors、retry_count；证据结果，如 rag_evidence、sql_evidence、graph_evidence、case_evidence、fused_evidence；最后是 diagnosis、confidence、report 和 needs_human_review。这样每个节点只读写自己负责的字段，方便调试和追踪。

### Q5: 如何评估这个 Agent？

答：

> 我不会只看大模型回答是否流畅，而是拆成几个指标：Tool Accuracy 看工具是否选对，Evidence Recall 看关键证据是否被找回，Faithfulness 看答案是否忠于证据，Task Success Rate 看最终诊断是否解决问题，Latency 看端到端响应时间。对于复杂诊断任务，还可以人工标注标准答案，统计根因命中率和推荐动作命中率。
