# Havenkeep: Technical Architecture Specification

This document details the software architecture, state machine models, governance engine design, and data flows of **Havenkeep**.

---

## 1. System Overview

Havenkeep is designed around three core pillars:
1. **Dynamic Risk-Based Orchestration:** Routing tasks to either a Fast-Lane or a Governed-Lane to optimize cost, latency, and security.
2. **Shift-Left Governance:** Enforcing policy allowlists, token budget caps, and audit logging directly in the core LLM execution wrappers rather than as external post-processors.
3. **Durable Human-in-the-Loop Interruption:** Pausing workflow execution state safely into PostgreSQL when high-risk actions or plan drift are detected, allowing human intervention via an interactive Next.js web application.

---

## 2. Dynamic Risk Classification Matrix

The **Supervisor Router Node** receives incoming user prompts and scores them using a structured LLM output schema against five risk factors:

```json
{
  "task_type": "CODE_GENERATION | RESEARCH | DATA_ANALYSIS | EXTERNAL_ACTION | GENERAL_QA",
  "risk_score": 0.85,
  "lane": "governed_lane | fast_lane",
  "confidence": 0.94,
  "risk_factors": {
    "reversibility": "IRREVERSIBLE",
    "ambiguity": "HIGH",
    "domain_risk": "PRODUCTION_SYSTEMS",
    "complexity": "MULTI_STEP",
    "supervisor_confidence": "HIGH"
  },
  "rationale": "Task involves file updates and shell execution against production repository."
}
```

### Risk Scoring Formula & Decision Rule
$$\text{Risk Score} = w_1 \cdot \text{Reversibility} + w_2 \cdot \text{Ambiguity} + w_3 \cdot \text{DomainRisk} + w_4 \cdot \text{Complexity}$$

- **Fast-Lane Threshold:** $\text{Risk Score} \le 0.40$ AND $\text{Confidence} \ge 0.80$.
- **Governed-Lane Threshold:** $\text{Risk Score} > 0.40$ OR $\text{Confidence} < 0.80$.

---

## 3. LangGraph State Machine Architecture

### 3.1 State Schema (`HavenkeepState`)

```python
from typing import TypedDict, List, Dict, Any, Optional
from langchain_core.messages import BaseMessage

class HavenkeepState(TypedDict):
    messages: List[BaseMessage]
    session_id: str
    task_prompt: str
    task_type: str
    risk_score: float
    lane: str
    
    # Governed-Lane state fields
    plan_steps: List[Dict[str, Any]]
    current_step_index: int
    approved_plan: Optional[List[Dict[str, Any]]]
    
    # Critic evaluation fields
    critic_verdict: Optional[str] # "PASS" | "MINOR_REVISION" | "MAJOR_REVISION" | "ESCALATE"
    critic_feedback: Optional[str]
    revision_count: int
    
    # Governance & Interrupt fields
    pending_tool_call: Optional[Dict[str, Any]]
    approval_required: bool
    approval_reason: Optional[str]
    is_budget_exceeded: bool
    
    # Cost metrics
    cumulative_prompt_tokens: int
    cumulative_completion_tokens: int
    cumulative_cost_usd: float
    
    # Final Output Response
    final_output: Optional[str]
```

### 3.2 Fast-Lane Subgraph Execution Flow (Phase 2)

```
                       ┌─────────────────────────┐
                       │          START          │
                       └────────────┬────────────┘
                                    │
                       ┌────────────▼────────────┐
                       │     SupervisorNode      │
                       └────────────┬────────────┘
                                    │
                         Is Risk Score <= 0.40?
                        ┌───────────┴───────────┐
                        │                       │
                       YES                      NO
                        │                       │
           ┌────────────▼────────────┐ ┌────────▼───────────┐
           │   FastLaneWorkerNode    │ │ GovernedLaneStub   │
           └────────────┬────────────┘ └────────┬───────────┘
                        │                       │
           ┌────────────▼────────────┐          │
           │ FastLaneGuardrailNode   │          │
           └────────────┬────────────┘          │
                        │                       │
                        └───────────┬───────────┘
                                    │
                       ┌────────────▼────────────┐
                       │           END           │
                       └─────────────────────────┘
```

1. **FastLaneWorkerNode ([worker.py](backend/app/graph/nodes/worker.py)):**
   - Applies specialized prompt strategies according to `task_type` (`RESEARCH`, `CODE_GENERATION`, `DATA_ANALYSIS`, `GENERAL_QA`).
   - Calls `PolicyEngine.evaluate_tool_call` before initiating tool invocations.
   - Calculates token cost via `CostTracker` and updates `cumulative_cost_usd`.
   - Records transition event `WORKER_EXECUTED` to `AuditLogger`.

2. **FastLaneGuardrailNode ([guardrail.py](backend/app/graph/nodes/guardrail.py)):**
   - Conducts a lightweight checklist review of the generated worker output verifying safety, relevance, and coherent structure.
   - Updates `HavenkeepState` with `final_output` and verdict (`PASS` / `REVISED`).
   - Logs `GUARDRAIL_PASSED` / `GUARDRAIL_REVISED` to `AuditLogger`.

---

## 4. Shared Governance Primitives

```
                    ┌─────────────────────────┐
                    │      LLM Call / Node    │
                    └────────────┬────────────┘
                                 │
                    ┌────────────▼────────────┐
                    │  ModelProviderAdapter   │ (Translates raw LLM outputs across vendors)
                    └────────────┬────────────┘
                                 │
                    ┌────────────▼────────────┐
                    │       CostTracker       │ (Inspects tokens, calculates USD, checks soft/hard caps)
                    └────────────┬────────────┘
                                 │
                    ┌────────────▼────────────┐
                    │      PolicyEngine       │ (Validates tool action against 3-tier allowlist & plan drift)
                    └────────────┬────────────┘
                                 │
                    ┌────────────▼────────────┐
                    │       AuditLogger       │ (Persists JSON log event to PostgreSQL audit_logs table)
                    └─────────────────────────┘
```

### 4.1 PolicyEngine & 3-Tier Tool Matrix

Before executing any tool, the `PolicyEngine` evaluates the requested function and arguments against pre-defined rules:

- **Tier 1 (Always Require Approval):** `external_http_post`, `send_email`, `send_message`, `database_write`, `file_delete`, `deploy_command`, `payment`, `execute_shell_command`, `modify_permissions`.
- **Tier 2 (Opt-in Auto-Approve / Sandbox Restricted):** `file_write` (outside scratch path), `database_read` (unscoped wildcard `SELECT *`), `git_commit`/`git_push` to feature branch, `web_fetch` from external unvetted URL.
- **Tier 3 (Never Require Approval):** `file_read`, scoped `database_read`, internal computation, `web_search`.

### 4.2 Plan Drift Detection
In the Governed-Lane, when the `ExecutorNode` attempts a tool call, `PolicyEngine` compares the tool call against the `approved_plan`. If the tool action or target resource diverges from the approved step description, the execution is flagged with `PLAN_DRIFT` and sent to the approval gate.

### 4.3 CostTracker & Soft/Hard Budget Enforcer
- **Soft Threshold (e.g., $0.50):** Emits `BUDGET_WARNING` SSE event and logs warning to audit trail.
- **Hard Threshold (e.g., $2.00):** Halts node transition, sets `is_budget_exceeded = True`, and invokes `interrupt()` presenting a human budget-escalation prompt.

---

## 5. LangGraph `interrupt()` & Durable State Resumption

```
   Executor / Approval Node
             │
   Check Action & Policy
             │
   Action is Tier 1 / Drift?
       ├── NO ──► Execute Tool & Continue
       │
      YES
       │
  interrupt({ "action": tool_name, "params": args })
       │
  [Graph Execution Paused] ──► State saved to PostgreSQL via PostgresSaver
       │
  Client Receives SSE Event ("INTERRUPT_REQUIRED")
       │
  User Clicks Approve / Reject in Next.js UI (@ Port 3000)
       │
  FastAPI receives POST /api/tasks/{task_id}/approve
       │
  app.stream(Command(resume={"status": "APPROVED"}), config=thread_config)
       │
  [Graph Resumes from Node Start]
```

> [!CAUTION]
> **Node Re-Execution Safety:** When LangGraph resumes from a `Command(resume=...)`, it restarts the node from the beginning. All `interrupt()` calls are placed at the top of the node before side effects to ensure functions are not executed twice.

---

## 6. Real-Time Streaming Protocol (SSE)

FastAPI streams graph state updates to the Next.js client using Server-Sent Events (SSE) over `/api/tasks/{task_id}/stream`:

```json
event: node_start
data: {"node": "supervisor", "timestamp": "2026-08-23T01:15:00Z"}

event: router_classified
data: {"lane": "governed_lane", "risk_score": 0.85, "task_type": "CODE_GENERATION"}

event: node_start
data: {"node": "planner", "timestamp": "2026-08-23T01:15:02Z"}

event: plan_created
data: {"steps": [{"id": 1, "title": "Inspect repository structure"}, {"id": 2, "title": "Refactor component"}]}

event: interrupt_required
data: {"thread_id": "session-123", "action": "file_write", "path": "/app/main.py", "tier": "Tier 2"}

event: node_complete
data: {"node": "executor", "cost_usd": 0.042, "tokens": 1250}
```
