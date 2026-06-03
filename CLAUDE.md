# TelecomOps-Agent Development Rules

You are helping build TelecomOps-Agent, a production-style telecom fault diagnosis agent based on LangGraph, GraphRAG, PostgreSQL, Neo4j, RAG, and FastAPI.

## 1. Project Path

The project root is:

/root/autodl-tmp/TelecomOps-Agent

Before running any command, always make sure you are inside this directory:

cd /root/autodl-tmp/TelecomOps-Agent

## 2. Python Environment Rules

A dedicated conda environment already exists:

conda activate telecomops-agent

You must not pollute the base environment.

Strict rules:

1. Never install packages into base.
2. Never use global pip.
3. Never run pip install without confirming the active conda environment.
4. Prefer:
   python -m pip install ...
5. Before installing or running anything, check:
   which python
   python -V
   python -m pip -V
6. The Python interpreter should come from the telecomops-agent conda environment.
7. If the environment is not active, stop and tell the user to activate it.
8. Do not run conda install unless the user explicitly asks.
9. Do not use sudo apt install unless the user explicitly asks.
10. Add project dependencies to requirements.txt or pyproject.toml instead of installing random packages silently.

## 3. Development Scope Rules

1. Do not implement the whole project at once.
2. Only complete the specific milestone requested by the user.
3. Before coding, read the relevant design files under docs/design/.
4. Keep the repository structure clean and standard.
5. Do not create unrelated directories such as day1/, day2/, tmp_project/, demo_old/.
6. Do not put secrets, API keys, tokens, or private data into the repository.
7. Prefer mock data and deterministic logic first. LLM calls can be added later.
8. Every milestone must include a clear verification method.
9. Add or update tests whenever possible.
10. After finishing each milestone, summarize:
   - files created or modified
   - how to run
   - how to test
   - what remains unfinished

## 4. Current Design Documents

Read these files when needed:

- README.md
- docs/design/README.md
- docs/design/architecture.mmd
- docs/design/langgraph_workflow_design.md
- docs/design/postgres_schema.sql
- docs/design/neo4j_schema.md
- docs/design/api_design.md
- docs/design/resume_project_description.md

## 5. Standard Verification Commands

After each milestone, use:

conda activate telecomops-agent
cd /root/autodl-tmp/TelecomOps-Agent

which python
python -V
python -m pip -V

python -m compileall src tests
pytest -q
git status
git diff --stat

If tests fail, fix only the current milestone's related files.
