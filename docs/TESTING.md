# Havenkeep Manual & Regression Testing Guide 🧪

This guide contains step-by-step manual test scenarios, cURL regression commands, and automated test instructions for validating **Phase 1 (Governance Primitives & Supervisor Risk Router)**, **Phase 2 (Fast-Lane Worker & Guardrail Orchestration)**, and **Phase 3 (Governed-Lane Planner $\rightarrow$ Executor $\rightarrow$ Critic Orchestration & Dynamic Cost Pricing)**.

---

## 📋 Quick Test Matrix

| Test Suite / Scenario | Purpose | Command / Endpoint | Expected Outcome |
| :--- | :--- | :--- | :--- |
| **1. Automated Pytest Suite** | Unit & integration tests | `TESTING=1 PYTHONPATH=backend pytest tests/ -v` | 16/16 Passed (0.5s) |
| **2. Interactive CLI Harness** | Terminal manual test | `PYTHONPATH=backend python scripts/interactive_test.py` | Interactive prompt execution |
| **3. Supervisor Classification** | Risk Scoring & Policy Check | `POST /api/supervisor/classify` | `lane`, `risk_score`, `simulated_policy_check` |
| **4. Low-Risk Research Query** | Fast-Lane execution | `POST /api/workflow/execute` | `lane: "fast_lane"`, `critic: "PASS"` |
| **5. High-Risk Governed Query** | Governed-Lane execution | `POST /api/workflow/execute` | `lane: "governed_lane"`, `critic_verdict` |
| **6. Code Generation Query** | Specialized Code Worker | `POST /api/workflow/execute` | `task_type: "CODE_GENERATION"`, formatted code |
| **7. Model Config Inspection** | Governance models lookup | `GET /api/governance/models` | Active role bindings & pricing table |
| **8. Budget Cap Limit Check** | Budget halt enforcement | `POST /api/workflow/execute` | `is_budget_exceeded: true` |

---

## 🛠️ Section 1: Automated Regression Testing

Run the full automated Pytest suite covering all 16 test modules:

```bash
TESTING=1 PYTHONPATH=backend ./venv/bin/pytest tests/ -v
```

### Verified Test Modules:
- `test_cost_tracker.py`: Token calculation, soft warning threshold, hard halt threshold.
- `test_policy_engine.py`: Tier 1 action approval requirement, Tier 3 allowlist, scratch sandbox paths, plan drift evaluation.
- `test_supervisor.py`: 30-prompt supervisor risk routing benchmark suite (100% accuracy target).
- `test_fast_lane.py`: End-to-end Fast-Lane state machine execution and policy evaluation.
- `test_governed_lane.py`: End-to-end Governed-Lane (Planner $\rightarrow$ Executor $\rightarrow$ Critic) state machine execution, Tier 1 action approval flags, dynamic model pricing lookup, and critic iteration cap.

---

## 💻 Section 2: Interactive Terminal Testing

Run the interactive CLI harness to test prompts interactively:

```bash
PYTHONPATH=backend ./venv/bin/python3 scripts/interactive_test.py
```

---

## 🚀 How to Test via Swagger UI (Recommended)

1. **Start the FastAPI development server:**
   ```bash
   PYTHONPATH=backend ./venv/bin/uvicorn app.main:app --reload --port 8000
   ```
2. **Open Swagger UI in your browser:**
   👉 **[http://localhost:8000/docs](http://localhost:8000/docs)**
3. **Select Endpoint:**
   - For Risk Classification & Policy Checks: expand **`POST /api/supervisor/classify`**
   - For Full Workflow Execution: expand **`POST /api/workflow/execute`**
   - For Model Pricing & Role Bindings: expand **`GET /api/governance/models`**
4. Click **Try it out**, paste any payload box below into the request body, and click **Execute**!

---

## 🔍 Section 3: Supervisor Risk Classification API (`POST /api/supervisor/classify`)

This endpoint tests **Phase 1 Supervisor Risk Routing** and **Policy Engine checks** directly without executing downstream worker nodes.

### Case 3.1: Low-Risk Task Classification 🟢

**Goal:** Verify a read-only research prompt scores low risk ($\le 0.40$), routes to `fast_lane`, and passes policy checks (`TIER_3`, `ALLOWED`).

**Swagger UI Endpoint:** `POST /api/supervisor/classify`

**Swagger UI Payload (Copy & Paste):**
```json
{
  "prompt": "Explain the difference between synchronous and asynchronous code in Python.",
  "session_id": "test-classify-lowrisk"
}
```

**cURL Command:**
```bash
curl -X POST "http://localhost:8000/api/supervisor/classify" \
     -H "Content-Type: application/json" \
     -d '{
       "prompt": "Explain the difference between synchronous and asynchronous code in Python.",
       "session_id": "test-classify-lowrisk"
     }'
```

**Expected Response JSON:**
```json
{
  "session_id": "test-classify-lowrisk",
  "task_prompt": "Explain the difference between synchronous and asynchronous code in Python.",
  "task_type": "RESEARCH",
  "risk_score": 0.20,
  "lane": "fast_lane",
  "confidence": 0.95,
  "simulated_policy_check": {
    "tool_name": "file_read",
    "tier": "TIER_3",
    "verdict": "ALLOWED",
    "requires_human_interrupt": false,
    "reason": "Read-only workspace file access is allowed by default."
  }
}
```

---

### Case 3.2: High-Risk Task Classification 🔴

**Goal:** Verify a destructive database query scores high risk ($> 0.40$), routes to `governed_lane`, and flags `APPROVAL_REQUIRED` (`TIER_1`).

**Swagger UI Endpoint:** `POST /api/supervisor/classify`

**Swagger UI Payload (Copy & Paste):**
```json
{
  "prompt": "Delete all outdated user records from production database.",
  "session_id": "test-classify-highrisk"
}
```

**cURL Command:**
```bash
curl -X POST "http://localhost:8000/api/supervisor/classify" \
     -H "Content-Type: application/json" \
     -d '{
       "prompt": "Delete all outdated user records from production database.",
       "session_id": "test-classify-highrisk"
     }'
```

**Expected Response JSON:**
```json
{
  "session_id": "test-classify-highrisk",
  "task_prompt": "Delete all outdated user records from production database.",
  "task_type": "EXTERNAL_ACTION",
  "risk_score": 0.80,
  "lane": "governed_lane",
  "confidence": 0.85,
  "simulated_policy_check": {
    "tool_name": "database_write",
    "tier": "TIER_1",
    "verdict": "APPROVAL_REQUIRED",
    "requires_human_interrupt": true,
    "reason": "Production database mutation requires explicit human approval."
  }
}
```

---

### Case 3.3: Production Deployment Classification 🚀

**Goal:** Verify infrastructure deployment requests route to `governed_lane` under `EXTERNAL_ACTION`.

**Swagger UI Endpoint:** `POST /api/supervisor/classify`

**Swagger UI Payload (Copy & Paste):**
```json
{
  "prompt": "Deploy hotfix container to Kubernetes production cluster.",
  "session_id": "test-classify-deploy"
}
```

---

## 🌐 Section 4: Workflow Execution API (`POST /api/workflow/execute`)

### Scenario 4.1: Low-Risk Task $\rightarrow$ Fast-Lane Execution 🟢

**Goal:** Verify read-only informational prompts route to `fast_lane`, execute through `FastLaneWorkerNode`, pass `FastLaneGuardrailNode`, and log cost metrics.

**Swagger UI Endpoint:** `POST /api/workflow/execute`

**Swagger UI Payload (Copy & Paste):**
```json
{
  "prompt": "Summarize the top 3 benefits of microservices architecture.",
  "session_id": "test-fastlane-01",
  "soft_budget_usd": 0.5,
  "hard_budget_usd": 2.0
}
```

**cURL Command:**
```bash
curl -X POST "http://localhost:8000/api/workflow/execute" \
     -H "Content-Type: application/json" \
     -d '{
       "prompt": "Summarize the top 3 benefits of microservices architecture.",
       "session_id": "test-fastlane-01"
     }'
```

**Expected Response JSON:**
```json
{
  "lane": "fast_lane",
  "task_type": "RESEARCH",
  "critic_verdict": "PASS",
  "is_budget_exceeded": false
}
```

---

### Scenario 4.2: High-Risk Task $\rightarrow$ Governed-Lane Multi-Agent Flow 🔴

**Goal:** Verify high-risk tasks score high risk ($>0.40$), route to Governed-Lane (`Planner` $\rightarrow$ `Executor` $\rightarrow$ `Critic`), decompose into plan steps, and trigger approval/critic safety checks.

**Swagger UI Endpoint:** `POST /api/workflow/execute`

**Swagger UI Payload (Copy & Paste):**
```json
{
  "prompt": "DELETE FROM users WHERE active = false; DROP TABLE logs;",
  "session_id": "test-governed-01",
  "soft_budget_usd": 0.5,
  "hard_budget_usd": 2.0
}
```

**cURL Command:**
```bash
curl -X POST "http://localhost:8000/api/workflow/execute" \
     -H "Content-Type: application/json" \
     -d '{
       "prompt": "DELETE FROM users WHERE active = false; DROP TABLE logs;",
       "session_id": "test-governed-01"
     }'
```

**Expected Response JSON:**
```json
{
  "task_type": "EXTERNAL_ACTION",
  "lane": "governed_lane",
  "critic_verdict": "ESCALATE",
  "is_budget_exceeded": false
}
```

---

### Scenario 4.3: Code Generation $\rightarrow$ Specialized Code Worker 💻

**Goal:** Verify software code prompts classify under `CODE_GENERATION` taxonomy and output formatted code blocks via the Fast-Lane Code Worker.

**Swagger UI Endpoint:** `POST /api/workflow/execute`

**Swagger UI Payload (Copy & Paste):**
```json
{
  "prompt": "Write a Python function to validate email addresses using regex.",
  "session_id": "test-code-01"
}
```

**cURL Command:**
```bash
curl -X 'POST' \
  'http://localhost:8000/api/workflow/execute' \
  -H 'accept: application/json' \
  -H 'Content-Type: application/json' \
  -d '{
  "prompt": "Write a Python function to validate email addresses using regex.",
  "session_id": "test-code-01"
}'
```

**Expected Response JSON:**
```json
{
  "session_id": "test-code-01",
  "task_prompt": "Write a Python function to validate email addresses using regex.",
  "task_type": "CODE_GENERATION",
  "risk_score": 0.35,
  "lane": "fast_lane",
  "confidence": 0.98,
  "final_output": "Task processed successfully under Fast-Lane worker execution.",
  "critic_verdict": "PASS",
  "critic_feedback": "Passed quality and safety guardrail check.",
  "is_budget_exceeded": false
}
```

---

### Scenario 4.4: Governance Model Configuration & Pricing Lookup 🔍

**Swagger UI Endpoint:** `GET /api/governance/models`

**cURL Command:**
```bash
curl -X GET "http://localhost:8000/api/governance/models"
```

**Expected Response JSON:**
```json
{
  "active_roles": {
    "supervisor": {
      "provider": "ollama",
      "resolved_model": "gemma3:latest"
    },
    "planner": {
      "provider": "anthropic",
      "resolved_model": "claude-3-5-sonnet-20240620"
    },
    "worker": {
      "provider": "openai",
      "resolved_model": "gpt-4o-mini"
    },
    "critic": {
      "provider": "ollama",
      "resolved_model": "gemma3:latest"
    },
    "executor": {
      "provider": "openai",
      "resolved_model": "gpt-4o-mini"
    }
  },
  "pricing_table_usd_per_1m": {
    "claude-3-haiku-20240307": { "input": 0.25, "output": 1.25 },
    "claude-3-5-sonnet-20240620": { "input": 3.0, "output": 15.0 },
    "claude-3-opus-20240229": { "input": 15.0, "output": 75.0 },
    "gpt-4o-mini": { "input": 0.15, "output": 0.6 },
    "gpt-4o": { "input": 5.0, "output": 15.0 },
    "default": { "input": 1.0, "output": 3.0 }
  },
  "default_budgets": {
    "session_soft_budget_usd": 0.5,
    "session_hard_budget_usd": 2.0,
    "task_hard_budget_usd": 1.0
  }
}
```

---

### Scenario 4.5: Low Budget Cap $\rightarrow$ Hard Limit Enforcement 💰

**Swagger UI Endpoint:** `POST /api/workflow/execute`

**Swagger UI Payload (Copy & Paste):**
```json
{
  "prompt": "Explain synchronous vs asynchronous programming in Python.",
  "session_id": "test-budget-01",
  "soft_budget_usd": 0.00001,
  "hard_budget_usd": 0.0001
}
```

---

## 🔍 Section 5: Regression Pre-Release Checklist

Before committing new agent nodes or routing rules, verify:
1. `TESTING=1 PYTHONPATH=backend pytest tests/` passes 100% of tests (16/16).
2. Every node logs `AuditLogger.log_event` with session ID, cost, and payload.
3. Model calls pass through `ModelProviderAdapter` without hardcoded vendor classes.
4. Dynamic model pricing lookup uses `ModelProviderAdapter.get_model_name(role)` instead of hardcoded model pricing strings.
