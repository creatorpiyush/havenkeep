# Havenkeep Manual & Regression Testing Guide 🧪

This guide contains step-by-step manual test scenarios, cURL regression commands, and automated test instructions for validating **Phase 1 (Governance Primitives)**, **Phase 2 (Fast-Lane Worker)**, **Phase 3 (Governed-Lane & Dynamic Pricing)**, **Phase 4 (Governance Layer: Approval Gate, Policy APIs & Thread Sweeps)**, and **Phase 5 (Cost Optimization & Governance Telemetry)**.

---

## 📋 Quick Test Matrix

| Test Suite / Scenario | Purpose | Command / Endpoint | Expected Outcome |
| :--- | :--- | :--- | :--- |
| **1. Automated Pytest Suite** | Unit & integration tests | `TESTING=1 PYTHONPATH=backend pytest tests/ -v` | 23/23 Passed (0.5s) |
| **2. Pre-Commit Verification** | Full 4-step test runner | `./scripts/precommit.sh` | 100% Passed (Pytest + 12 API Scenarios) |
| **3. Interactive CLI Harness** | Terminal manual test | `PYTHONPATH=backend python scripts/interactive_test.py` | Interactive prompt execution |
| **4. Governance Telemetry API** | Telemetry metrics lookup | `GET /api/governance/metrics` | Total cost, cache savings, critic verdicts |
| **5. Human Approval Resumption** | Resume interrupted task | `POST /api/workflow/resume` | Resumes paused thread with `APPROVED` |
| **6. Dynamic Policy Rules** | Runtime policy allowlist edit | `GET/PUT /api/governance/policies` | Updates Tier 1/2/3 tool rules |
| **7. Thread TTL Abandon Sweep** | Idle checkpoint cleanup | `POST /api/governance/sweep` | Sweeps abandoned threads |
| **8. Supervisor Classification** | Risk Scoring & Policy Check | `POST /api/supervisor/classify` | `lane`, `risk_score`, `simulated_policy_check` |
| **9. Low-Risk Research Query** | Fast-Lane execution | `POST /api/workflow/execute` | `lane: "fast_lane"`, `critic: "PASS"` |
| **10. High-Risk Governed Query** | Governed-Lane execution | `POST /api/workflow/execute` | `lane: "governed_lane"`, `critic_verdict` |
| **11. Model Config Inspection** | Governance models lookup | `GET /api/governance/models` | Active role bindings & pricing table |

---

## 🛠️ Section 1: Automated Regression Testing

Run the full automated Pytest suite covering all 19 test modules:

```bash
TESTING=1 PYTHONPATH=backend ./venv/bin/pytest tests/ -v
```

### Verified Test Modules:
- `test_cost_tracker.py`: Token calculation, soft warning threshold, hard halt threshold.
- `test_policy_engine.py`: Tier 1 action approval requirement, Tier 3 allowlist, scratch sandbox paths, plan drift evaluation.
- `test_supervisor.py`: 30-prompt supervisor risk routing benchmark suite (100% accuracy target).
- `test_fast_lane.py`: End-to-end Fast-Lane state machine execution and policy evaluation.
- `test_governed_lane.py`: End-to-end Governed-Lane (Planner $\rightarrow$ Executor $\rightarrow$ Critic) state machine execution, Tier 1 action approval flags, dynamic model pricing lookup, and critic iteration cap.
- `test_governance_layer.py`: Phase 4 Human approval gate interrupts, thread resumption API, dynamic policy editing, and TTL abandonment sweep.
- `test_cost_optimization.py`: Phase 5 Prompt caching discounts, ToolResultCache TTL caching, ContextCompressor history trimming, BatchProcessor concurrency pool, and `/api/governance/metrics`.

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

---

## 🛑 Section 5: Phase 4 Governance Layer APIs (Approval Gate & Policies)

### Scenario 5.1: Human Approval Interruption Resumption ✋

**Goal:** Resume an interrupted task thread paused at `ApprovalGateNode` using `POST /api/workflow/resume`.

**Swagger UI Endpoint:** `POST /api/workflow/resume`

**Swagger UI Payload (Copy & Paste):**
```json
{
  "session_id": "test-governed-01",
  "decision": "APPROVED"
}
```

**cURL Command:**
```bash
curl -X POST "http://localhost:8000/api/workflow/resume" \
     -H "Content-Type: application/json" \
     -d '{
       "session_id": "test-governed-01",
       "decision": "APPROVED"
     }'
```

**Expected Response JSON:**
```json
{
  "session_id": "test-governed-01",
  "task_prompt": "DELETE FROM users WHERE active = false; DROP TABLE logs;",
  "task_type": "EXTERNAL_ACTION",
  "risk_score": 0.95,
  "lane": "governed_lane",
  "confidence": 0.98,
  "final_output": "Governed plan execution completed safely under policy allowlist supervision.",
  "critic_verdict": "PASS",
  "is_budget_exceeded": false
}
```

---

### Scenario 5.2: Dynamic Policy Rules Inspection & Update 🛡️

**Goal:** View and update 3-tier action allowlists (`PolicyEngine`) dynamically at runtime.

#### GET /api/governance/policies (Inspect Active Rules)
**Swagger UI Endpoint:** `GET /api/governance/policies`

**cURL Command:**
```bash
curl -X GET "http://localhost:8000/api/governance/policies"
```

**Expected Response JSON:**
```json
{
  "tier_1_actions": ["database_write", "deploy_command", "external_http_post", "file_delete"],
  "tier_2_actions": ["file_write", "git_commit", "git_push"],
  "tier_3_actions": ["database_read_scoped", "file_read", "internal_compute", "web_search"]
}
```

#### PUT /api/governance/policies (Update Allowlist Rules)
**Swagger UI Endpoint:** `PUT /api/governance/policies`

**Swagger UI Payload (Copy & Paste):**
```json
{
  "tier": "TIER_1",
  "actions": ["database_write", "file_delete", "deploy_command", "custom_highrisk_tool"]
}
```

**cURL Command:**
```bash
curl -X PUT "http://localhost:8000/api/governance/policies" \
     -H "Content-Type: application/json" \
     -d '{
       "tier": "TIER_1",
       "actions": ["database_write", "file_delete", "deploy_command", "custom_highrisk_tool"]
     }'
```

**Expected Response JSON:**
```json
{
  "tier_1_actions": ["custom_highrisk_tool", "database_write", "deploy_command", "file_delete"],
  "tier_2_actions": ["file_write", "git_commit", "git_push"],
  "tier_3_actions": ["database_read_scoped", "file_read", "internal_compute", "web_search"]
}
```

---

### Scenario 5.3: Thread TTL Abandonment Sweep 🧹

**Goal:** Trigger background sweep service marking unresumed interrupted thread checkpoints as `ABANDONED`.

**Swagger UI Endpoint:** `POST /api/governance/sweep`

**cURL Command:**
```bash
curl -X POST "http://localhost:8000/api/governance/sweep?max_idle_hours=24.0"
```

**Expected Response JSON:**
```json
{
  "status": "completed",
  "max_idle_hours": 24.0,
  "abandoned_threads_count": 0
}
```

---

## 📈 Section 6: Phase 5 Governance Telemetry API (`GET /api/governance/metrics`)

### Scenario 6.1: Governance Metrics & Cache Savings Lookup 📊

**Goal:** Retrieve aggregated telemetry metrics across PostgreSQL audit logs, including total audit events, lane distribution (`fast_lane` vs `governed_lane`), cumulative cost USD, total cache read tokens, estimated dollar savings from prompt caching, and critic verdict breakdowns.

**Swagger UI Endpoint:** `GET /api/governance/metrics`

**Swagger UI Payload (Copy & Paste):**
*(None — GET request with no request body)*

**cURL Command:**
```bash
curl -X GET "http://localhost:8000/api/governance/metrics" \
     -H "accept: application/json"
```

**Expected Response JSON:**
```json
{
  "total_audit_events": 14,
  "lane_distribution": {
    "fast_lane": 4,
    "governed_lane": 6
  },
  "cumulative_cost_usd": 0.005145,
  "total_cache_read_tokens": 15000,
  "estimated_cache_savings_usd": 0.0405,
  "critic_verdicts": {
    "PASS": 4,
    "MINOR_REVISION": 1
  }
}
```

---

## 🔍 Section 7: Regression Pre-Release Checklist

Before committing new agent nodes or routing rules, verify:
1. `TESTING=1 PYTHONPATH=backend pytest tests/` passes 100% of tests (23/23).
2. `./scripts/precommit.sh` executes all 4 validation steps with 100% success.
3. Every node logs `AuditLogger.log_event` with session ID, cost, and payload.
4. Model calls pass through `ModelProviderAdapter` without hardcoded vendor classes.
5. Dynamic model pricing lookup uses `ModelProviderAdapter.get_model_name(role)` instead of hardcoded model pricing strings.
6. Approval gates invoke `interrupt()` at node start before side-effects and handle `Command(resume=...)`.
