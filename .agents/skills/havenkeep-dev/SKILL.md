---
name: havenkeep-dev
description: >-
  Development runbook and guide for maintaining, building, testing, and debugging the Havenkeep multi-agent orchestration project.
---

# Havenkeep Development & Maintenance Skill

Use this skill when developing, testing, refactoring, or extending the **Havenkeep** multi-agent harness.

---

## 🚀 Quick Command Reference

### Docker Commands
- **Start All Services:** `docker-compose up --build -d`
- **Check Service Logs:** `docker-compose logs -f backend` or `docker-compose logs -f frontend`
- **Stop All Services:** `docker-compose down`

### Backend Development (FastAPI + LangGraph)
- **Install Dependencies:** `pip install -r backend/requirements.txt`
- **Run Backend Locally:** `cd backend && uvicorn app.main:app --reload --port 8000`
- **Run Unit & Integration Tests:**
  - Supervisor benchmark (30 routing test cases): `pytest tests/test_supervisor.py`
  - Policy Engine & 3-Tier enforcement: `pytest tests/test_policy_engine.py`
  - Cost tracker & budget cap checks: `pytest tests/test_cost_tracker.py`
  - Governed-Lane state machine & interrupts: `pytest tests/test_governed_lane.py`

### Frontend Development (Next.js @ Port 3000)
- **Install Dependencies:** `cd frontend && npm install`
- **Run Frontend Dev Server:** `cd frontend && npm run dev` (starts on `http://localhost:3000`)
- **Build Production Bundle:** `cd frontend && npm run build`

---

## 🛠️ Architecture & Adding New Features

### 1. How to Add a New Worker Agent
1. Create worker definition in `backend/app/graph/nodes/workers.py`.
2. Wrap system prompt with target capabilities and policy bounds.
3. Register the new worker in `SupervisorNode` taxonomy (`backend/app/graph/nodes/supervisor.py`).
4. Ensure LLM calls use `CostTracker` and tool calls check `PolicyEngine`.

### 2. How to Add a New Tool / Action Tier
1. Define tool function in `backend/app/graph/nodes/workers.py` or `executor.py`.
2. Register the tool action name in `PolicyEngine` (`backend/app/governance/policy_engine.py`) under Tier 1, Tier 2, or Tier 3.
3. Update `ARCHITECTURE.md` Section 4.1.

### 3. Debugging LangGraph `interrupt()` Resumption Issues
- Check PostgreSQL checkpoint logs in `checkpoints` table.
- Verify `interrupt()` call is at the top of the target node before any side-effect function calls.
- Ensure client resumes with exact thread ID via `app.stream(Command(resume=...))`.

---

## 🧪 Testing Checklist Before Submitting Code

- [ ] All `pytest` suites pass cleanly with no unhandled exceptions.
- [ ] Docker Compose environment compiles and runs without port conflicts.
- [ ] Next.js UI on port 3000 receives SSE events cleanly from FastAPI backend on port 8000.
- [ ] Every task execution creates an audit entry in the database.
