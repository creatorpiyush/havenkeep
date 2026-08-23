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

### 3.2 State Machine Routing Flow (Phase 2 & Phase 3)

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
           │   FastLaneWorkerNode    │ │    PlannerNode     │
           └────────────┬────────────┘ └────────┬───────────┘
                        │                       │
           ┌────────────▼────────────┐ ┌────────▼───────────┐
           │  FastLaneGuardrailNode  │ │    ExecutorNode    │
           └────────────┬────────────┘ └────────┬───────────┘
                        │                       │
                        │              ┌────────▼───────────┐
                        │              │     CriticNode     │
                        │              └────────┬───────────┘
                        │                       │
                        │         Is MINOR_REVISION & count < 2?
                        │            ┌──────────┴──────────┐
                        │           YES                    NO
                        │            │                      │
                        │      Route back to                │
                        │      ExecutorNode                 │
                        │                       │           │
                        └───────────────────────┴─────┬─────┘
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

3. **PlannerNode ([planner.py](backend/app/graph/nodes/planner.py)):**
   - Decomposes high-risk tasks into a sequential execution plan (JSON steps).
   - Emits `PLAN_GENERATED` event to `AuditLogger` and tracks token spend.

4. **ExecutorNode ([executor.py](backend/app/graph/nodes/executor.py)):**
   - Executes plan steps, checking every tool action against `PolicyEngine`.
   - If a Tier 1 or unapproved tool action is proposed, flags `approval_required: true`.

5. **CriticNode ([critic.py](backend/app/graph/nodes/critic.py)):**
   - Evaluates execution output against rubric.
   - Returns structured verdict (`PASS`, `MINOR_REVISION`, `MAJOR_REVISION`, `ESCALATE`) and enforces a 2-cycle iteration cap.

---

## 4. Shared Governance Primitives & Dynamic Model Cost Pricing

```
                    ┌─────────────────────────┐
                    │      LLM Call / Node    │
                    └────────────┬────────────┘
                                 │
                    ┌────────────▼────────────┐
                    │  ModelProviderAdapter   │ (Translates raw LLM outputs & resolves active model names)
                    └────────────┬────────────┘
                                 │
                    ┌────────────▼────────────┐
                    │       CostTracker       │ (Calculates USD using dynamic ModelProviderAdapter.get_model_name)
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

### 4.1 Dynamic Model Cost Pricing Lookup
Instead of hardcoding pricing strings inside individual agent nodes, `ModelProviderAdapter.get_model_name(role)` dynamically resolves the configured model string from `.env` overrides (`SUPERVISOR_MODEL`, `PLANNER_MODEL`, `WORKER_MODEL`, `CRITIC_MODEL`, `EXECUTOR_MODEL`) or provider defaults, ensuring accurate cost tracking across Anthropic, OpenAI, Ollama, Google Gemini, Groq, and OpenRouter.

### 4.2 PolicyEngine & 3-Tier Tool Matrix

Before executing any tool, the `PolicyEngine` evaluates the requested function and arguments against pre-defined rules:

- **Tier 1 (Always Require Approval):** `external_http_post`, `send_email`, `send_message`, `database_write`, `file_delete`, `deploy_command`, `payment`, `execute_shell_command`, `modify_permissions`.
- **Tier 2 (Opt-in Auto-Approve / Sandbox Restricted):** `file_write` (outside scratch path), `database_read` (unscoped wildcard `SELECT *`), `git_commit`/`git_push` to feature branch, `web_fetch` from external unvetted URL.
- **Tier 3 (Never Require Approval):** `file_read`, scoped `database_read`, internal computation, `web_search`.
