# Havenkeep Workspace Guidelines for AI Pair Programming

Welcome to the **Havenkeep** repository! This document contains project-specific coding standards, architecture constraints, and governance invariants that all AI agents must follow when maintaining or expanding this codebase.

---

## 1. Architectural Invariants

1. **Shift-Left Governance First:** Never build or modify an agent worker or node without ensuring it routes tool calls through `PolicyEngine`, tracks LLMs through `CostTracker`, and logs transitions to `AuditLogger`.
2. **Dynamic Lane Split:** Low-risk tasks MUST route through Fast-Lane (`FastLaneWorker` + `GuardrailNode`); high-risk or multi-step tasks MUST route through Governed-Lane (`PlannerNode` -> `ExecutorNode` -> `CriticNode`).
3. **LangGraph Interrupt Discipline:** `interrupt()` calls MUST be invoked at the start of approval nodes before any tool side-effects or external network calls to guarantee re-execution safety upon `Command(resume=...)`.
4. **Model Provider Abstraction:** Never hardcode LLM vendor classes (e.g. `ChatAnthropic` or `ChatOpenAI`) directly in node files. Always instantiate chat models via `ModelProviderAdapter.get_model(role="...")` or LangChain's `init_chat_model`.
5. **Port 3000 UI:** The Next.js frontend application must always be configured to run on **port 3000** to align with Docker Compose service mapping.

---

## 2. Codebase Standards

- **Python (Backend):**
  - Python 3.11+, fully type-annotated (`mypy` compliant).
  - Use `async/await` for FastAPI routes and database queries (`SQLAlchemy` async session).
  - Use Pydantic v2 for API request/response schemas.
  - Follow `pytest` testing conventions in `tests/`.

- **TypeScript / React (Frontend):**
  - Next.js 14 App Router (`frontend/src/app`).
  - Tailwind CSS + Lucide icons (`lucide-react`) for styling.
  - Strict TypeScript typing; avoid `any`.
  - Real-time data updates via Server-Sent Events (`EventSource` SSE API).

---

## 3. Maintenance & Testing Checklist

Before completing any feature, fix, or node implementation:
- **Run Automated Test Suite:** Execute `TESTING=1 PYTHONPATH=backend ./venv/bin/pytest tests/ -v` to verify all governance, router, fast-lane, and state machine tests pass (12/12 passing baseline).
- **Run Interactive Test Harness / API Execution:** Verify task prompt execution through `/api/workflow/execute` and `/api/supervisor/classify` per [docs/TESTING.md](docs/TESTING.md).
- **Verify Docker Compose:** Ensure Docker Compose builds cleanly (`docker-compose build`).
- **Audit Logging Verification:** Ensure every node logs transitions to `AuditLogger.log_event` and fields match the database schema in `backend/app/db/models.py`.
