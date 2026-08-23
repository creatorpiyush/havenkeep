# Changelog

All notable changes to **Havenkeep** will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

---

## [0.2.0] - 2026-08-23

### Added
- **Fast-Lane Worker Node (`FastLaneWorkerNode`):** Specialized prompt handlers for `RESEARCH`, `CODE_GENERATION`, `DATA_ANALYSIS`, and `GENERAL_QA` integrated directly with Shift-Left governance (`PolicyEngine`, `CostTracker`, `AuditLogger`).
- **Fast-Lane Guardrail Node (`FastLaneGuardrailNode`):** Checklist-based safety and quality pass evaluating worker outputs prior to user delivery.
- **LangGraph State Machine Engine (`workflow.py`):** Compiled LangGraph workflow routing tasks: `START` -> `SupervisorNode` -> (`FastLaneWorkerNode` -> `FastLaneGuardrailNode` | `GovernedLaneStub`) -> `END`.
- **FastAPI End-to-End Execution API (`/api/workflow/execute`):** REST API endpoint invoking the full LangGraph state machine with token/cost tracking and audit responses.
- **Fast-Lane Automated Test Suite (`test_fast_lane.py`):** Integration tests covering end-to-end execution, policy allowlists, budget tracking, and governed-lane routing stubs.

## [0.1.0] - 2026-08-23

### Added
- **Supervisor Risk Classifier Node (`SupervisorNode`):** Structured LLM prompt scoring tasks across Reversibility, Ambiguity, Domain Risk, Task Complexity, and Supervisor Confidence, dynamically routing queries to `fast_lane` or `governed_lane`.
- **Shift-Left Governance Engine:**
  - **`PolicyEngine`:** 3-tier action classification matrix (Tier 1 Irreversible, Tier 2 Sandbox Restricted, Tier 3 Read-only) and Plan Drift evaluation.
  - **`CostTracker`:** Multi-model token usage normalization, soft budget warnings, and hard execution budget halts.
  - **`AuditLogger`:** Durable JSON audit logging to PostgreSQL database and real-time console stdout.
- **Multi-Supplier Provider Adapter (`ModelProviderAdapter`):** Supports Anthropic, OpenAI, Ollama (local free models), Google Gemini, Groq, and OpenRouter with custom Base URLs and provider-driven model defaults.
- **FastAPI REST API Gateway & Swagger Docs:** `/health`, `/api/config`, and `/api/supervisor/classify` manual test endpoints.
- **Containerized Development Environment:** Multi-platform `docker-compose.yml` supporting PostgreSQL 16 (`pgvector`), Redis 7, FastAPI backend (port 8000), and Next.js frontend (port 3000).
- **Automated Test Suite & Interactive Test Harness:** Pytest benchmark test suite (30 routing test cases with 100% accuracy) and CLI testing script (`scripts/interactive_test.py`).
- **Project Documentation:** `README.md`, `ARCHITECTURE.md`, `docs/SETUP.md`, `.agents/AGENTS.md`, and `.agents/skills/havenkeep-dev/SKILL.md`.
