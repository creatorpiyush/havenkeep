# Havenkeep: Implementation Plan

**Product name:** Havenkeep — Multi-agent orchestration with built-in governance. "Haven" signals a safe, protected space where agents operate; "keep" carries the dual meaning of a fortified stronghold and the act of watching over, maintaining, and holding in check — reflecting the audit trail, approval gates, and cost controls at the core of the design.

**Design goal:** Interactive, economical, governed multi-agent system combining a Supervisor+Workers pattern for low-stakes tasks with a Planner→Executor→Critic pattern for high-stakes tasks, routed dynamically by risk classification.

---

## 1. Architecture Overview

```
User <-> Interactive UI (approve / monitor / adjust)
              |
        Supervisor (router + risk classifier)
              |
              |-- Policy engine (permission check before dispatch)
              |
      ┌───────┴────────┐
      |                |
 Fast-lane         Governed-lane
      |                |
   Worker         Planner → Executor → Critic
      |                |
 Guardrail check   Approval gate (human, if external action)
      |                |
      └───────┬────────┘
              |
     Audit log + Cost tracker (shared, every step)
              |
           Response to user
```

**Core principle:** the Supervisor doesn't just pick a worker — it also scores task risk and decides which lane the task travels through. This is what keeps the system economical: only tasks that need governance overhead pay for it.

---

## 2. Phased Build Plan

**Sequencing principle (shift-left governance):** audit logging, policy allowlists, and token/cost tracking are not features bolted on after the worker and lane logic exists — they are primitives every agent node calls into from its first line of code. Building nodes first and retrofitting governance later means rewriting every node. Phase 1 now establishes these primitives alongside the Supervisor, before any worker or lane is built, so nothing downstream needs to be rewritten.

### Phase 1 — Supervisor + Risk Rubric + Shared Governance Primitives
**Goal:** A router that classifies task type *and* risk level before any execution happens, wired directly into the shared infrastructure every later node will depend on.

**Supervisor & risk rubric:**
- [x] Define task taxonomy (e.g., research, code, writing, data lookup, external action)
- [x] Define risk rubric with explicit criteria:
  - Reversibility (read-only vs. sends/spends/deletes/deploys)
  - Ambiguity (single interpretation vs. multiple plausible ones)
  - Domain risk (general Q&A vs. financial/legal/customer-facing/shipped code)
  - Supervisor confidence score (threshold-based)
  - Task complexity (single-step vs. multi-step/dependent)
- [x] Supervisor outputs structured JSON: `{ task_type, risk_score, lane, confidence }`
- [x] Build a labeled test set of example tasks (20–30) to validate routing accuracy before moving on
- [x] Use a cheap/fast model for this step where possible — supervisor should be lightweight unless task complexity demands otherwise

**Shared governance primitives (pulled forward from the original Phase 4/5, built here so nothing downstream needs rewriting):**
- [x] **Audit log schema** — defined and wired to Postgres from the first node onward (session ID, agent, route/lane, tool calls, tokens/cost, outcome). The dashboard to *view* this comes later (Phase 6); the schema and write path exist now.
- [x] **Policy/permission engine skeleton** — allowlist structure for tools/actions per agent role, checked at dispatch time. Rules can start minimal (deny-by-default with a small allowlist) and expand as workers are added in Phase 2/3.
- [x] **Escalation path contract** — the defined interface (what an agent calls when uncertain, blocked, or over budget), even before the human-facing UI to handle it exists.
- [x] **Token/cost tracking middleware** — a wrapper around every LLM call that records usage (see Section 6.4). Tracking is wired in now; hard budget *enforcement* (halting execution) is also implemented here, since it must live inside the same wrapper — this is cheaper to build once than to retrofit.
- [x] **Model provider abstraction** — LangChain's standard chat model interface, configured per agent role rather than hardcoded, so provider/model choice is a config change, not a code change (see Section 6.5).

**Exit criteria:** Supervisor correctly routes ≥90% of labeled test tasks to the intended lane; every routed task produces an audit log entry and passes through the policy engine and cost-tracking wrapper, even though no worker logic exists yet.


---

### Phase 2 — Fast-Lane (Supervisor + Workers)
**Goal:** End-to-end path for low-stakes tasks, optimized for cost and latency, built directly against the Phase 1 primitives.

- [x] Build specialized worker agents (research, code, writer, etc.), each with a narrow, well-scoped system prompt
- [x] Assign cheap/fast models to workers by default via the Phase 1 provider config; escalate model tier only for tasks where the supervisor flags moderate complexity
- [x] Add a lightweight guardrail/critic pass (cheap model, checklist-based) before returning output to the user
- [x] Every worker calls into the Phase 1 policy engine before tool use, and the Phase 1 cost-tracking wrapper for every LLM call — no separate implementation, no retrofitting
- [x] Every worker run logs to the Phase 1 audit schema

**Exit criteria:** A full low-stakes task (e.g., simple research query) runs end-to-end with logged cost and latency, using only the Phase 1 primitives — no governance logic is written from scratch in this phase.

---

### Phase 3 — Governed-Lane (Planner → Executor → Critic)
**Goal:** Self-correcting path for high-stakes or complex tasks, also built directly against the Phase 1 primitives.

- [x] Build Planner agent — decomposes task into steps; mid-tier model is usually sufficient
- [x] Reuse Phase 2 workers as Executors where possible (avoid duplicating logic)
- [x] Build Critic agent — rubric-driven checklist review, not open-ended "is this good?" prompting; cheap model
- [x] Critic returns a verdict enum, not a binary pass/fail: `{ pass, minor_revision, major_revision, escalate }`. A `major_revision` verdict can short-circuit straight to human review rather than spending a full iteration on a fundamentally broken approach.
- [x] Implement iteration cap — **default: 2 revision cycles** before escalating to human review or flagging a warning. Consider making this configurable per risk-tier (e.g., 1 for lower-risk governed tasks, 3 for higher-stakes ones) rather than a single global constant.
- [x] Track cap-hits as a signal: if a task type or worker consistently hits the cap, feed this into the Phase 6 feedback loop for rubric tuning — it likely signals a misrouted task, not just a hard problem.
- [x] Implement the human-approval gate using **LangGraph's native `interrupt()` / `Command(resume=...)` pattern** for tasks that reach an external or irreversible action — see Section 6.6 for the full design and caveats.
- [x] Define clear pass/fail/revise output schema for Critic, including which specific tool actions trigger the approval gate by default — see Section 6.7 (Human Approval Thresholds).

**Exit criteria:** A complex or multi-step task runs through the full loop, self-corrects at least once in testing, respects the iteration cap, and correctly pauses/resumes at an approval gate via `interrupt()` without losing state across a simulated server restart.

---

### Phase 4 — Governance Layer (Enforcement & UI Backend)
**Goal:** With the Phase 1 primitives already in place, this phase is scoped to what's actually left: human-facing controls and hard enforcement, not plumbing.

- [x] **Approval gate backend & resumption API:** human-in-the-loop confirmation engine, wired to the `interrupt()`/`Command(resume=...)` flow from Phase 3, triggered only for governed-lane tasks hitting an external/irreversible action per the Section 6.7 threshold table (`POST /api/workflow/resume`)
- [x] **Hard budget-cap enforcement:** the soft/hard threshold behavior from Section 6.4 — soft threshold warns and optionally downgrades to cheaper models; hard threshold halts and flags `BUDGET_EXCEEDED`
- [x] **Policy editor API:** REST endpoints (`GET /api/governance/policies` & `PUT /api/governance/policies`) over the Phase 1 policy engine's allowlists, so rules can change dynamically without a redeploy
- [x] **TTL/abandonment sweep:** background service & API (`POST /api/governance/sweep`) scanning for interrupted threads not resumed within a threshold (e.g., 24 hours) and marking them abandoned

**Exit criteria:** Every task, regardless of lane, produces a complete audit trail entry; external actions cannot execute without passing the approval gate; a simulated runaway task is halted by the budget wrapper before exceeding the hard threshold; an abandoned approval is correctly flagged after its TTL expires.

---

### Phase 5 — Cost Optimization
**Goal:** With tracking and enforcement already live from Phase 1/4, this phase is genuinely about optimization, not building the budget system itself.

- [x] Prompt caching for system prompts, tool definitions, and few-shot examples (`CostTracker` cache read/creation token pricing math)
- [x] Context trimming / scratchpad summarization for long-running agent loops (`ContextCompressor`)
- [x] Tool-call result caching within and across sessions (`ToolResultCache` TTL service)
- [x] Batch processing for non-interactive work (`BatchProcessor` concurrency pool)
- [x] Cost dashboard backend / metrics aggregation (`GET /api/governance/metrics`)

**Exit criteria:** Cost-per-task is visible and broken down by lane; prompt caching demonstrably reduces token spend on repeated-context runs in testing.

---

### Phase 6 — Interactive Layer & Polish
**Goal:** User-facing UI for monitoring, approving, and adjusting agent behavior.

- [ ] Live task/session view (what's running, which lane, current step)
- [ ] Approval gate UI polish (accept/reject/edit before external action executes) — functional version already exists from Phase 4; this phase covers UX refinement
- [ ] Audit log viewer (searchable by session, agent, cost, outcome)
- [ ] Manual override: user can force a task into governed-lane even if supervisor scored it fast-lane
- [ ] Feedback loop: flagged misroutes, bad critic verdicts, and repeated iteration-cap hits feed back into rubric tuning

**Exit criteria:** A user can submit a task, watch it route and execute, intervene at an approval gate, and review the audit trail — all without touching code.

---

## 3. Shared Infrastructure Checklist

These are built once in Phase 1, used by both lanes from that point forward:

- [x] Unified audit log schema
- [x] Unified budget tracker (with soft/hard threshold enforcement)
- [x] Unified policy/permission engine
- [x] Unified session/state management (so context isn't duplicated between lanes)
- [x] Unified model provider abstraction (config-driven, not hardcoded)

---

## 4. Open Decisions

**Resolved:**
- ~~Orchestration framework~~ → LangGraph (Section 6.1)
- ~~Model provider strategy~~ → Modular multi-provider via LangChain's standard chat model interface, config-driven per agent role (Section 6.5)
- ~~Approval gate scope~~ → Default tool-action tiers defined in Section 6.7; refine per-domain as needed
- ~~Iteration cap value~~ → Default 2 revision cycles, with verdict-severity short-circuiting and optional per-risk-tier configurability (Phase 3)
- ~~Budget enforcement mechanism~~ → Mid-flight wrapper with soft/hard thresholds, checked after every node (Section 6.4)
- ~~Human-approval durability mechanism~~ → LangGraph `interrupt()` / `Command(resume=...)` with Postgres checkpointing (Section 6.6)

**Still open:**
- [ ] Model tiering specifics: which exact models (and which provider) map to "cheap," "mid," "strong" tiers for your budget — verify current model names/pricing before launch, as these change frequently
- [ ] Risk rubric thresholds: what confidence score numerically triggers governed-lane by default?
- [ ] Approval gate scope, domain-specific refinement: which additional actions beyond the Section 6.7 defaults are "external/irreversible" for your specific use case?
- [ ] Approve-and-continue on budget cap: should hitting `BUDGET_EXCEEDED` be a hard dead-end, or should it route to a human with an "approve additional budget" option via the same interrupt mechanism? (Recommended: the latter for governed-lane tasks — see Section 6.4.)
- [ ] Per-action vs. per-plan approval: does every governed-lane tool call pause individually, or is the full plan approved once upfront? Per-action is safer but less "interactive"; per-plan is faster but needs a drift-detection trigger if the executor deviates from what was approved.
- [ ] Multi-tenancy: is this single-team or multi-org from day one? Affects audit log and budget tracker schema design.

---

## 5. Success Metrics

| Metric | Target |
|---|---|
| Routing accuracy (supervisor) | ≥90% on labeled test set |
| Cost per fast-lane task | Baseline, tracked from Phase 2 |
| Cost per governed-lane task | Tracked separately, compared against fast-lane |
| Governed-lane self-correction rate | % of tasks where critic catches and fixes an issue |
| Budget cap reliability | 100% — no task exceeds hard threshold in testing |
| Audit log completeness | 100% of tasks logged, no gaps |
| Interrupt durability | 100% — approval-gated tasks survive a simulated server restart with no state loss |
| Abandoned approval detection | 100% — TTL sweep correctly flags threads not resumed within threshold |

---

## 6. Tech Stack

### 6.1 Orchestration

**Primary choice: LangGraph**

- Models workflows as an explicit graph (nodes + edges) — maps directly onto the fast-lane/governed-lane split: the supervisor's routing decision becomes a conditional edge, each lane becomes a subgraph, and both share state through LangGraph's built-in state object.
- Best token efficiency and cost predictability of the major frameworks — each LLM call is a discrete, known quantity rather than an open-ended conversation loop.
- Native Postgres checkpointing for durable execution — critical for the governed-lane's human-approval step (a server restart mid-approval shouldn't lose the pending task).
- Most mature production readiness and largest ecosystem of the current frameworks.
- Steeper learning curve and more verbose than CrewAI — accepted tradeoff for the control this architecture needs.

**Alternatives considered and why they were not chosen as primary:**

| Framework | Strength | Why not primary here |
|---|---|---|
| CrewAI | Fastest to prototype, intuitive role-based teams | Error handling is adequate only when failed tasks can simply be re-run; governed-lane needs graceful partial-failure recovery, which CrewAI doesn't do as well |
| AutoGen / AG2 | Good for debate-style, multi-perspective tasks | Microsoft has shifted active development to the Microsoft Agent Framework; AutoGen itself is now in maintenance mode — riskier foundation for a new build |

**Optional:** CrewAI can be used short-term to prototype fast-lane worker prompts quickly, then migrated into the LangGraph subgraph once validated. Not recommended as a permanent split — adds a second framework to maintain.

### 6.2 Backend

| Layer | Choice | Why |
|---|---|---|
| Orchestration | LangGraph (Python) | Graph-based control flow, matches lane design |
| API server | FastAPI | Async-native, streams naturally to the UI (SSE/WebSocket), pairs well with LangGraph |
| LLM access | Anthropic API (direct or via LangGraph model bindings) | Native prompt caching support — key lever for cost goals |
| Task queue | Redis + Celery (or async background tasks in FastAPI if scale is modest) | Long-running governed-lane tasks shouldn't block the request thread |
| State / session store | Postgres | Session state and task history; LangGraph checkpointing writes here for durability |
| Audit log | Postgres (dedicated schema/table) | Structured, queryable, satisfies Phase 4 governance requirements |
| Vector store (if research agents need retrieval) | pgvector (inside same Postgres) or Qdrant | pgvector avoids running an extra service if scale allows |
| Budget / cost tracking | Custom middleware around every LLM call, writes to Postgres | Not provided out-of-the-box by LangGraph — build a thin wrapper |

### 6.3 Deployment notes

- Keep the governed-lane's approval step and audit log **synchronous and durable**, not in-memory — a restart mid-approval must not lose the pending task. This is a governance requirement as much as an infra one.
- Containerize the FastAPI + LangGraph service separately from the queue workers so governed-lane tasks can scale independently of fast-lane traffic.

### 6.4 Mid-Flight Budget Cap Enforcement

Rather than relying on post-execution cost analysis, budget enforcement is built as a **custom LLM invocation wrapper** that inspects cumulative token usage after every node — not just at the end of a task.

**How it works:**
- The wrapper sits around every LLM call (already required for provider normalization — see 6.5) and, after each node completes, checks cumulative cost against two independent counters: **session-level** and **task-level**. A task can blow its own budget without threatening the session, and vice versa; both are checked on every call.
- **Halt granularity:** an in-flight LLM call can't be un-spent once it's running, so enforcement happens at the *node transition*, not mid-stream — after a node completes, the wrapper checks cumulative cost and refuses to transition to the next node if over threshold, rather than literally interrupting a call in progress.
- **Two thresholds, not one:**
  - **Soft threshold** — triggers a warning and audit-log entry, and optionally downgrades remaining steps to cheaper models. Gives graceful degradation instead of an abrupt cliff.
  - **Hard threshold** — halts execution immediately (at the next node boundary) with a `BUDGET_EXCEEDED` state flag and audit entry.
- **Provider-normalized cost:** since different providers report token usage differently, the wrapper converts raw usage into a normalized dollar-cost figure before comparing against either threshold, regardless of which model/provider handled the call.
- **On hitting the hard threshold:** decide whether this is a dead-end (task fails, full stop) or routes to a human with an "approve additional budget and continue" option — the latter can reuse the same `interrupt()`/`Command(resume=...)` mechanism from Section 6.6, since the plumbing already exists. Recommended for governed-lane tasks, where silently killing a task on a token limit is poor UX.

### 6.5 Model Provider & API Access

The backend uses **modular multi-provider support**, not a hardcoded single vendor.

**Why:**
- Different agent roles benefit from different providers, not just different cost tiers — the fast-lane worker wants the cheapest capable model regardless of vendor, the critic wants a model good at structured rubric-following, the planner wants strong reasoning. Locking to one provider prevents picking the actual best-cost-per-task model per role.
- Pricing, rate limits, and model availability shift often enough that hardcoding one vendor is an operational risk for a system whose core goal is being economical.
- Self-hosted OSS users will expect to plug in their own provider of choice, including local models.

**Implementation:**
- Use **LangChain's standard chat model interface** (`init_chat_model`, or provider-specific `ChatAnthropic` / `ChatOpenAI` classes) as the abstraction layer — this pairs directly with the already-chosen LangGraph orchestrator.
- Model selection is **config, not code** — each agent role (supervisor, planner, worker, critic) gets a config entry specifying provider and model, e.g.:
  ```yaml
  supervisor:
    provider: anthropic
    model: claude-haiku-4-5
  planner:
    provider: anthropic
    model: claude-sonnet-5
  critic:
    provider: openai
    model: gpt-4o-mini  # verify current model name/availability before launch
  ```
- **Note on model names:** model lineups change frequently — verify current model names and pricing at build time rather than trusting any name written into this document. The config-driven pattern above exists specifically so a model swap is a one-line config change, not a code change.
- API keys are provisioned and managed by the deploying team (Anthropic Console, OpenAI platform, etc.) via `.env`/secrets manager — not something hardcoded or checked into the repo.
- The provider adapter layer normalizes cost/token reporting for the Section 6.4 budget wrapper, so tracking is consistent regardless of which provider handled a given call.

### 6.6 Human Approval via LangGraph Durable Interrupts

For governed-lane tasks requiring external or irreversible actions (database mutations, sending emails, external API triggers), the approval gate uses **LangGraph's native `interrupt()` function**, paired with Postgres checkpointing.

**Mechanism:**
- `interrupt()` pauses graph execution at the approval node and persists state via the checkpointer (Postgres, per Section 6.2) rather than in memory.
- The client (FastAPI, driven by the Next.js UI) resumes the paused thread with `Command(resume=...)` once the user approves, rejects, or edits — execution continues from that point without losing state or context, and survives a server restart in between.

**Two implementation caveats to build in from the start:**
1. **Node re-execution on resume, not mid-line resumption.** When a node containing `interrupt()` is resumed, LangGraph re-executes the node from its start, re-running all logic up to the interrupt point — it does not resume from the exact interrupted line. Practical rule: **call `interrupt()` at the very start of the approval node**, before any side effects, so re-execution on resume doesn't double-run anything (e.g., don't call an external API and then interrupt — you'd re-trigger the call on resume).
2. **TTL/abandonment sweep required.** If a thread hits `interrupt()` and nobody ever resumes it, the checkpointer holds the frozen state indefinitely. A background job must scan for threads not resumed within a defined threshold (e.g., 24 hours) and mark them abandoned — otherwise a forgotten approval silently holds a checkpoint open forever with no visible failure state. Built as part of Phase 4.

### 6.7 Human Approval Thresholds (Default Tool-Action Tiers)

Default rubric for which tool actions trigger the approval gate, organized by confidence level. Ships as hardcoded defaults, refined per-domain as an Open Decision (Section 4).

**Tier 1 — Always require approval (irreversible or external-facing):**
- `external_http_post` (non-read-only outbound calls)
- `send_email`, `send_message` (any external communication channel)
- `database_write` (inserts/updates/deletes against production data)
- `file_delete` (regardless of location)
- `deploy_command` (staging/production pushes)
- `payment` / `financial_transaction`
- `execute_shell_command` / `run_arbitrary_code` (unless in a fully sandboxed, disposable environment)
- `send_invite` / `grant_access` / `modify_permissions` (identity/access control)
- `external_api_write` to third-party production systems (CRM updates, ticket creation, calendar invites to real people)

**Tier 2 — Approval by default, reasonable to auto-approve with explicit opt-in:**
- `file_write` (workspace/scratch paths can auto-approve; paths outside the sandbox require approval)
- `database_read` with broad/unscoped queries (e.g., unfiltered `SELECT *` — read isn't inherently safe if it's exfiltrating a lot of data)
- `git_commit` / `git_push` to a branch (pushing to `main` stays Tier 1)
- `create_calendar_event` (internal only, not sent to external parties)
- `web_fetch` from an unvetted URL — flag as a prompt-injection risk vector feeding into an agent's context, not just an approval question

**Tier 3 — Never require approval by default (read-only, reversible, internal):**
- `file_read`
- `database_read` (scoped, small)
- Internal computation, summarization, classification
- `web_search` for research (no data leaves the system)

**Rubric for scoring actions not on this list** (score against these signals to decide the tier):

| Signal | Escalate to approval if... |
|---|---|
| Reversibility | Action can't be undone (delete, send, deploy, pay) |
| Blast radius | Affects data/systems outside the agent's sandbox |
| Destination | Leaves your infrastructure (external API, email, message) |
| Data sensitivity | Touches PII, credentials, financial data |
| Scope | Bulk/wildcard operations vs. single-record operations |

---

## 7. GUI

Two distinct surfaces — build and reason about them separately.

### 7.1 End-user interactive UI

**Stack:** Next.js + React, Tailwind + shadcn/ui, streaming via SSE or WebSocket from FastAPI (Vercel AI SDK optional, for streaming/tool-call UI primitives).

Key components:
- Chat / task input
- Live status indicator — which lane the task is in, which agent is currently running
- Inline approval prompt — surfaces when a governed-lane task hits an external/irreversible action; accept / reject / edit before it executes
- Running cost indicator for the current session

### 7.2 Governance / ops dashboard

Separate app or admin route, same design system as the end-user UI for component reuse.

| Component | Purpose | Suggested tooling |
|---|---|---|
| Audit log viewer | Filterable/searchable table — session, agent, cost, outcome, lane | TanStack Table over Postgres audit log |
| Approval queue | Pending governed-lane actions awaiting human sign-off | Simple list/queue UI, accept/reject/edit actions |
| Cost dashboard | Per-lane, per-agent, per-session cost breakdown | Tremor or Recharts over aggregated Postgres queries |
| Policy editor | Form-based editor for the policy engine's tool/action allowlists | Avoids requiring a redeploy to change permissions |

### 7.3 Recommended combination

Next.js + Tailwind + shadcn/ui for both surfaces, Tremor or Recharts for the cost dashboard, TanStack Table for the audit log. This keeps one design system and one frontend codebase covering both the interactive task UI and the governance dashboard.
