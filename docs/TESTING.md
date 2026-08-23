# Havenkeep Manual & Regression Testing Guide 🧪

This guide contains step-by-step manual test scenarios, cURL regression commands, and automated test instructions for validating **Phase 1 (Governance Primitives & Risk Router)** and **Phase 2 (Fast-Lane Worker & Guardrail Orchestration)**.

---

## 📋 Quick Test Matrix

| Test Suite / Scenario | Purpose | Command / Endpoint | Expected Outcome |
| :--- | :--- | :--- | :--- |
| **1. Automated Pytest Suite** | Unit & integration tests | `TESTING=1 PYTHONPATH=backend pytest tests/ -v` | 12/12 Passed (0.5s) |
| **2. Interactive CLI Harness** | Terminal manual test | `PYTHONPATH=backend python scripts/interactive_test.py` | Interactive prompt execution |
| **3. Low-Risk Research Query** | Fast-Lane execution | `POST /api/workflow/execute` | `lane: "fast_lane"`, `critic: "PASS"` |
| **4. High-Risk Destructive Query**| Governed-Lane routing | `POST /api/workflow/execute` | `lane: "governed_lane"`, `[GOVERNED_LANE_STUB]` |
| **5. Code Generation Query** | Specialized Code Worker | `POST /api/workflow/execute` | `task_type: "CODE_GENERATION"`, formatted code |
| **6. Budget Cap Limit Check** | Budget halt enforcement | `POST /api/workflow/execute` | `is_budget_exceeded: true` |

---

## 🛠️ Section 1: Automated Regression Testing

Run the full automated Pytest suite covering all 12 test modules:

```bash
TESTING=1 PYTHONPATH=backend ./venv/bin/pytest tests/ -v
```

### Verified Test Modules:
- `test_cost_tracker.py`: Token calculation, soft warning threshold, hard halt threshold.
- `test_policy_engine.py`: Tier 1 action approval requirement, Tier 3 allowlist, scratch sandbox paths, plan drift evaluation.
- `test_supervisor.py`: 30-prompt supervisor risk routing benchmark suite (100% accuracy target).
- `test_fast_lane.py`: End-to-end Fast-Lane state machine execution, policy evaluation, and governed stub routing.

---

## 💻 Section 2: Interactive Terminal Testing

Run the zero-cost interactive CLI harness to test prompts interactively:

```bash
PYTHONPATH=backend ./venv/bin/python3 scripts/interactive_test.py
```

---

## 🌐 Section 3: REST API & Swagger UI Manual Scenarios

### How to Test via Swagger UI (Recommended) 🚀
1. Start the FastAPI development server:
   ```bash
   PYTHONPATH=backend ./venv/bin/uvicorn app.main:app --reload --port 8000
   ```
2. Open **Swagger UI** in your web browser:
   👉 **[http://localhost:8000/docs](http://localhost:8000/docs)**
3. Expand **`POST /api/workflow/execute`**, click **Try it out**, and paste any of the JSON request bodies below into the Request Body text area!

---

### Scenario 1: Low-Risk Task $\rightarrow$ Fast-Lane Execution 🟢

**Goal:** Verify read-only informational prompts route to `fast_lane`, execute through `FastLaneWorkerNode`, pass `FastLaneGuardrailNode`, and log cost metrics.

**Swagger UI Endpoint:** `POST /api/workflow/execute`

**Swagger UI Payload (Copy & Paste):**
```json
{
  "prompt": "Summarize the top 3 benefits of microservices architecture.",
  "session_id": "test-fastlane-01",
  "soft_budget_usd": 0.5,
  "hard_budget_usd": 2
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

**Expected Response JSON Verification:**
```json
{
  "lane": "fast_lane",
  "task_type": "RESEARCH",
  "critic_verdict": "PASS",
  "is_budget_exceeded": false
}
```

---

### Scenario 2: High-Risk Task $\rightarrow$ Governed-Lane Safety Stub 🔴

**Goal:** Verify destructive high-risk prompts (database deletion, system modification) score high risk ($>0.40$) and safely route to the governed-lane stub without executing unauthorized actions.

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

**Expected Response JSON Verification:**
```json
{
  "lane": "governed_lane",
  "critic_verdict": "ESCALATE",
  "final_output": "[GOVERNED_LANE_STUB] Task 'DELETE FROM users WHERE active = false; DROP TABLE logs;' was scored as High Risk (0.80) and routed to Governed-Lane. Full multi-agent planner/executor/critic flow will execute in Phase 3."
}
```

---

### Scenario 3: Code Generation $\rightarrow$ Specialized Code Worker 💻

**Goal:** Verify software code prompts classify under `CODE_GENERATION` taxonomy and output formatted code blocks.

**Swagger UI Endpoint:** `POST /api/workflow/execute`

**Swagger UI Payload (Copy & Paste):**
```json
{
  "prompt": "Write a Python function to validate email addresses using regex.",
  "session_id": "test-code-01",
  "soft_budget_usd": 0.5,
  "hard_budget_usd": 2.0
}
```

**cURL Command:**
```bash
curl -X POST "http://localhost:8000/api/workflow/execute" \
     -H "Content-Type: application/json" \
     -d '{
       "prompt": "Write a Python function to validate email addresses using regex.",
       "session_id": "test-code-01"
     }'
```

**Expected Response JSON Verification:**
```json
{
  "task_type": "CODE_GENERATION",
  "lane": "fast_lane",
  "critic_verdict": "PASS"
}
```

---

### Scenario 4: Low Budget Cap $\rightarrow$ Hard Limit Enforcement 💰

**Goal:** Supply restrictive budget thresholds (`hard_budget_usd: 0.0001`) to verify `CostTracker` flags `is_budget_exceeded: true`.

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

**cURL Command:**
```bash
curl -X POST "http://localhost:8000/api/workflow/execute" \
     -H "Content-Type: application/json" \
     -d '{
       "prompt": "Explain synchronous vs asynchronous programming in Python.",
       "session_id": "test-budget-01",
       "soft_budget_usd": 0.00001,
       "hard_budget_usd": 0.0001
     }'
```

**Expected Response JSON Verification:**
```json
{
  "session_id": "test-budget-01",
  "task_type": "GENERAL_QA",
  "lane": "fast_lane",
  "cumulative_cost_usd": 0.000518,
  "is_budget_exceeded": true
}
```

---

### Scenario 5: Policy Engine Classification & Allowlist Check 🛡️

**Goal:** Inspect risk classification, action tier allowlists, and governed-lane safety routing for production deployment requests.

#### Option 5A: Direct Policy Inspection via `POST /api/supervisor/classify`
**Swagger UI Endpoint:** `POST /api/supervisor/classify`

**Swagger UI Payload (Copy & Paste):**
```json
{
  "prompt": "Deploy hotfix container to Kubernetes production cluster.",
  "session_id": "test-policy-01"
}
```

**Expected Response JSON Verification:**
```json
{
  "lane": "governed_lane",
  "task_type": "EXTERNAL_ACTION",
  "risk_score": 0.95,
  "simulated_policy_check": {
    "tool_name": "database_write",
    "tier": "TIER_1",
    "verdict": "APPROVAL_REQUIRED",
    "requires_human_interrupt": true
  }
}
```

#### Option 5B: Full Workflow State Machine via `POST /api/workflow/execute`
**Swagger UI Endpoint:** `POST /api/workflow/execute`

**Swagger UI Payload (Copy & Paste):**
```json
{
  "prompt": "Deploy hotfix container to Kubernetes production cluster.",
  "session_id": "test-policy-01",
  "soft_budget_usd": 0.5,
  "hard_budget_usd": 2.0
}
```

**Expected Response JSON Verification:**
```json
{
  "task_type": "EXTERNAL_ACTION",
  "risk_score": 0.95,
  "lane": "governed_lane",
  "critic_verdict": "ESCALATE",
  "final_output": "[GOVERNED_LANE_STUB] Task 'Deploy hotfix container to Kubernetes production cluster.' was scored as High Risk (0.95) and routed to Governed-Lane."
}
```

---

## 🔍 Section 4: Regression Pre-Release Checklist

Before committing new agent nodes or routing rules, verify:
1. `TESTING=1 PYTHONPATH=backend pytest tests/` passes 100% of tests.
2. Every node logs `AuditLogger.log_event` with session ID, cost, and payload.
3. Model calls pass through `ModelProviderAdapter` without hardcoded vendor classes.
4. Fast-lane low-risk prompts never trigger human interrupts or unexpected 500 errors.
