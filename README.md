# Havenkeep 🛡️

**Interactive, Economical, and Governed Multi-Agent System**

Havenkeep is a multi-agent orchestration framework designed for safe, cost-bounded, and policy-governed agent workflows. It dynamically routes user requests into either a lightweight **Fast-Lane** or a self-correcting **Governed-Lane** based on real-time risk classification.

---

## 📚 Documentation Index

- [🧠 **Concept & Core Philosophy**](docs/CONCEPT.md) — What is an AI harness? Layman explanation of Havenkeep's goals and architecture.
- [🛠️ **Setup & Installation Guide**](docs/SETUP.md) — Detailed environment setup, Docker/Podman compose, local dev, and testing instructions.
- [🧪 **Manual & Regression Testing Guide**](docs/TESTING.md) — Step-by-step cURL scenarios, CLI harness, and automated regression test matrix.
- [📐 **Technical Architecture Specification**](ARCHITECTURE.md) — System design, risk scoring math, LangGraph state machine, policy engine, and SSE protocols.
- [📋 **Phased Implementation Plan**](multi_agent_harness_implementation_plan.md) — Multi-phase build roadmap and governance invariants.
- [📜 **Changelog & Version History**](CHANGELOG.md) — Detailed release logs and version notes (Current version: `v0.3.0`).

---

## 💡 What is Havenkeep in Plain English?

> **Think of Havenkeep as an AI Security Guard, Traffic Controller, and Budget Enforcer.**
> 
> Raw AI models (like GPT-4o or Claude) are like powerful sports car engines. A **harness** is the vehicle framework built around the engine—providing **steering, brakes, seatbelts, fuel gauges, and black-box flight recorders**.
> 
> Havenkeep gives AI agents real power to complete work, while guaranteeing they can **never overspend your budget, bypass safety policies, or modify critical production systems without your explicit permission.**



---

## 🌟 Key Architecture & Highlights

```
User <-> Interactive UI (Next.js @ Port 3000)
              │
        FastAPI Gateway & SSE Stream (Port 8000)
              │
        Supervisor Router (Risk Rubric Scoring)
              │
      ┌───────┴────────┐
      │                │
 Fast-Lane        Governed-Lane
 (Low Risk)       (High Risk / Complex)
      │                │
   Worker         Planner → Executor → Critic
      │                │
 Guardrail Pass   Durable Approval Gate (LangGraph interrupt)
      │                │
      └───────┬────────┘
              │
     Shared Governance Engine
  (Policy Allowlist + Audit Log + Cost Tracker)
              │
           Response
```

### 1. Shift-Left Governance (Phase 1 Complete)
Audit logging, 3-tier policy allowlist enforcement, token usage tracking, and model provider abstractions are established as core primitives called by every agent node from day one.

### 2. Dual-Lane Dynamic Routing & Fast-Lane Orchestration (Phase 2 Complete)
- **Fast-Lane:** Low-stakes tasks (`RESEARCH`, `CODE_GENERATION`, `DATA_ANALYSIS`, `GENERAL_QA`) execute via specialized worker agents (`FastLaneWorkerNode`) with minimal token overhead and low latency, verified by a checklist guardrail pass (`FastLaneGuardrailNode`).

### 3. Governed-Lane Multi-Agent Flow & Dynamic Cost Pricing (Phase 3 Complete)
- **Governed-Lane:** High-stakes or multi-step tasks run through a **Planner → Executor → Critic** self-correction loop with durable human-in-the-loop approval gates.
- **Dynamic Model Cost Pricing Lookup:** `ModelProviderAdapter.get_model_name(role)` resolves exact configured model strings from `.env` overrides (`SUPERVISOR_MODEL`, `PLANNER_MODEL`, `WORKER_MODEL`, `CRITIC_MODEL`, `EXECUTOR_MODEL`) or provider defaults for accurate cost tracking.

### 3. Human-in-the-Loop (`interrupt`) & Per-Plan Approval
- Native LangGraph `interrupt()` pauses execution at critical decision points and persists graph state directly to PostgreSQL.
- **3-Tier Approval Rubric:**
  - **Tier 1 (Always Require Approval):** `external_http_post`, `send_email`, `database_write`, `file_delete`, `deploy_command`, `payment`, `execute_shell_command`, `modify_permissions`.
  - **Tier 2 (Opt-in Auto-Approve):** `file_write` (outside scratch dir), `database_read` (unscoped), `git_push`, `web_fetch` from unvetted URLs.
  - **Tier 3 (Never Require Approval):** `file_read`, scoped `database_read`, internal computation, `web_search`.

### 4. Mid-Flight Token & Budget Control
- Tracks cumulative session and task costs after every node transition.
- **Soft Threshold:** Issues audit warning and optionally degrades model tier.
- **Hard Threshold:** Halts execution with `BUDGET_EXCEEDED` and presents a human budget-escalation prompt.

### 5. Multi-Supplier Model Engine with Custom Base URLs
Config-driven model bindings supporting Anthropic (Claude), OpenAI (GPT-4o), Google Gemini, Groq, OpenRouter, and Ollama (free local models) with custom base URLs for enterprise proxies or vLLM / LM Studio / LocalAI servers. Model names are provider-driven and optional!

---

## 🛠️ Tech Stack

- **Orchestration:** LangGraph (Python) with PostgreSQL State Checkpointing
- **Backend API:** FastAPI (Async Python) + Server-Sent Events (SSE)
- **Database & Queue:** PostgreSQL 16 (`pgvector`) + Redis
- **Frontend Dashboard:** Next.js 14 App Router, TypeScript, Tailwind CSS (**Port 3000**)
- **Deployment:** Docker / Podman Compose (Multi-platform: macOS Apple Silicon, Linux, Windows)

---

## 🚀 Quickstart

### 1. Configure Environment
```bash
cp backend/.env.example backend/.env
```

### 2. Start Services with Docker / Podman
```bash
docker-compose up --build -d
```

### 3. Access Services
- **Frontend GUI:** `http://localhost:3000`
- **FastAPI API & Swagger Docs:** `http://localhost:8000/docs`

For detailed manual setup, local python virtualenv execution, and interactive testing CLI options, see the [Setup Guide](docs/SETUP.md).

---

## 📂 Repository Structure

```
havenkeep/
├── docker-compose.yml           # Cross-platform multi-container setup
├── ARCHITECTURE.md              # Technical design & state machine documentation
├── README.md                    # Project overview & quickstart index
├── docs/                        # Project documentation
│   └── SETUP.md                 # Setup, configuration & local dev guide
├── .agents/                     # Workspace rules & skills for AI pair programming
│   ├── AGENTS.md
│   └── skills/
│       └── havenkeep-dev/
│           └── SKILL.md
├── scripts/                     # Developer tools & test scripts
│   └── interactive_test.py      # Free interactive CLI test harness
├── backend/
│   ├── Dockerfile
│   ├── requirements.txt
│   └── app/
│       ├── main.py              # FastAPI application entry point
│       ├── config.py            # Global settings & provider mapping
│       ├── db/                  # Database models & Async SQLAlchemy session
│       ├── governance/          # Policy engine, cost tracker, audit logger, model adapter
│       ├── graph/               # LangGraph state machine & supervisor node
│       └── api/                 # REST & SSE streaming endpoints
├── frontend/
│   ├── Dockerfile
│   ├── package.json
│   └── src/                     # Next.js App Router UI components
└── tests/                       # Automated Pytest benchmark test suite
```

---

## 🧪 Testing

Run automated tests:

```bash
TESTING=1 PYTHONPATH=backend ./venv/bin/python3 -m pytest tests/
```

Run free interactive terminal testing:

```bash
PYTHONPATH=backend ./venv/bin/python3 scripts/interactive_test.py
```

---

## 📜 License

MIT License. See [LICENSE](LICENSE) for details.
