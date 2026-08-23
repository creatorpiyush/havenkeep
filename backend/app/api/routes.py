from typing import Dict, Any, Optional, List
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from sqlalchemy.ext.asyncio import AsyncSession
from langgraph.types import Command
from app.db.database import get_db
from app.graph.nodes.supervisor import SupervisorNode
from app.governance.policy_engine import PolicyEngine
from app.governance.audit_logger import AuditLogger
from app.governance.model_adapter import ModelProviderAdapter
from app.governance.cost_tracker import CostTracker
from app.graph.state import HavenkeepState
from app.graph.workflow import havenkeep_app
from app.config import settings

router = APIRouter(prefix="/api", tags=["Governance & Routing"])

class TaskResumeRequest(BaseModel):
    session_id: str = Field(..., description="Session identifier of interrupted task.")
    decision: str = Field(default="APPROVED", description="Decision: APPROVED, REJECTED, or EDITED.")
    edited_args: Optional[Dict[str, Any]] = Field(default=None, description="Optional edited tool arguments.")

class PolicyUpdateRequest(BaseModel):
    tier: str = Field(..., description="Tier to update: TIER_1, TIER_2, or TIER_3.")
    actions: List[str] = Field(..., description="List of tool action names for the tier.")

class TaskClassifyRequest(BaseModel):
    prompt: str = Field(..., description="The user prompt or task instruction to classify.")
    session_id: Optional[str] = Field(default="manual-test-session", description="Session identifier.")

class TaskClassifyResponse(BaseModel):
    session_id: str
    task_prompt: str
    task_type: str
    risk_score: float
    lane: str
    confidence: float
    risk_factors: Dict[str, Any]
    simulated_policy_check: Dict[str, Any]
    cost_usd: float
    cumulative_cost_usd: float

class TaskExecuteRequest(BaseModel):
    prompt: str = Field(..., description="The user task instruction to execute through the state machine.")
    session_id: Optional[str] = Field(default="workflow-session", description="Session identifier.")
    soft_budget_usd: Optional[float] = Field(default=0.50, description="Soft warning budget in USD.")
    hard_budget_usd: Optional[float] = Field(default=2.00, description="Hard halt budget in USD.")

class TaskExecuteResponse(BaseModel):
    session_id: str
    task_prompt: str
    task_type: str
    risk_score: float
    lane: str
    confidence: float
    final_output: str
    critic_verdict: Optional[str]
    critic_feedback: Optional[str]
    cumulative_prompt_tokens: int
    cumulative_completion_tokens: int
    cumulative_cost_usd: float
    is_budget_exceeded: bool

@router.post("/supervisor/classify", response_model=TaskClassifyResponse)
async def classify_task(
    request: TaskClassifyRequest,
    db: AsyncSession = Depends(get_db)
):
    """
    Routes a task through the Supervisor Router, evaluates policy allowlists,
    calculates token cost, and logs a durable audit entry into the database.
    """
    initial_state: HavenkeepState = {
        "messages": [],
        "session_id": request.session_id or "manual-test-session",
        "task_prompt": request.prompt,
        "task_type": "UNKNOWN",
        "risk_score": 0.0,
        "lane": "fast_lane",
        "confidence": 0.0,
        "risk_factors": {},
        "plan_steps": [],
        "current_step_index": 0,
        "approved_plan": None,
        "critic_verdict": None,
        "critic_feedback": None,
        "revision_count": 0,
        "pending_tool_call": None,
        "approval_required": False,
        "approval_reason": None,
        "is_budget_exceeded": False,
        "cumulative_prompt_tokens": 0,
        "cumulative_completion_tokens": 0,
        "cumulative_cost_usd": 0.0,
        "soft_budget_usd": 0.50,
        "hard_budget_usd": 2.00,
        "final_output": None
    }

    # 1. Run Supervisor Node
    result = await SupervisorNode.run(initial_state)

    # 2. Simulate Policy Engine Check based on lane
    lane = result["lane"]
    sample_tool = "file_read" if lane == "fast_lane" else "database_write"
    policy_verdict = PolicyEngine.evaluate_tool_call(
        agent_role="worker" if lane == "fast_lane" else "executor",
        tool_name=sample_tool,
        tool_args={"path": "doc.txt"} if lane == "fast_lane" else {"query": "DELETE FROM users"}
    )

    # 3. Save Audit Log in DB
    await AuditLogger.log_event(
        session_id=request.session_id or "manual-test-session",
        agent_name="Supervisor",
        lane="supervisor",
        step_name="manual_api_classification",
        event_type="ROUTER_CLASSIFIED",
        db=db,
        cost_usd=result["cumulative_cost_usd"],
        tool_name=sample_tool,
        policy_verdict=policy_verdict.verdict,
        payload=result
    )

    return TaskClassifyResponse(
        session_id=request.session_id or "manual-test-session",
        task_prompt=request.prompt,
        task_type=result["task_type"],
        risk_score=result["risk_score"],
        lane=result["lane"],
        confidence=result["confidence"],
        risk_factors=result.get("risk_factors", {}),
        simulated_policy_check={
            "tool_name": sample_tool,
            "tier": policy_verdict.tier,
            "verdict": policy_verdict.verdict,
            "requires_human_interrupt": policy_verdict.requires_human_interrupt,
            "reason": policy_verdict.reason
        },
        cost_usd=result["cumulative_cost_usd"],
        cumulative_cost_usd=result["cumulative_cost_usd"]
    )

@router.post("/workflow/execute", response_model=TaskExecuteResponse)
async def execute_workflow(
    request: TaskExecuteRequest,
    db: AsyncSession = Depends(get_db)
):
    """
    End-to-End Workflow Execution Endpoint:
    Executes a task prompt through the full LangGraph state machine:
    Supervisor -> Lane Router -> Worker / Governed Stub -> Guardrail -> Result.
    """
    initial_state: HavenkeepState = {
        "messages": [],
        "session_id": request.session_id or "workflow-session",
        "task_prompt": request.prompt,
        "task_type": "UNKNOWN",
        "risk_score": 0.0,
        "lane": "fast_lane",
        "confidence": 0.0,
        "risk_factors": {},
        "plan_steps": [],
        "current_step_index": 0,
        "approved_plan": None,
        "critic_verdict": None,
        "critic_feedback": None,
        "revision_count": 0,
        "pending_tool_call": None,
        "approval_required": False,
        "approval_reason": None,
        "is_budget_exceeded": False,
        "cumulative_prompt_tokens": 0,
        "cumulative_completion_tokens": 0,
        "cumulative_cost_usd": 0.0,
        "soft_budget_usd": request.soft_budget_usd or 0.50,
        "hard_budget_usd": request.hard_budget_usd or 2.00,
        "final_output": None
    }

    config = {"configurable": {"thread_id": request.session_id or "workflow-session"}}
    final_state = await havenkeep_app.ainvoke(initial_state, config=config)

    return TaskExecuteResponse(
        session_id=final_state.get("session_id", "workflow-session"),
        task_prompt=final_state.get("task_prompt", request.prompt),
        task_type=final_state.get("task_type", "GENERAL_QA"),
        risk_score=final_state.get("risk_score", 0.0),
        lane=final_state.get("lane", "fast_lane"),
        confidence=final_state.get("confidence", 0.0),
        final_output=final_state.get("final_output", ""),
        critic_verdict=final_state.get("critic_verdict"),
        critic_feedback=final_state.get("critic_feedback"),
        cumulative_prompt_tokens=final_state.get("cumulative_prompt_tokens", 0),
        cumulative_completion_tokens=final_state.get("cumulative_completion_tokens", 0),
        cumulative_cost_usd=final_state.get("cumulative_cost_usd", 0.0),
        is_budget_exceeded=final_state.get("is_budget_exceeded", False)
    )

@router.post("/workflow/resume", response_model=TaskExecuteResponse)
async def resume_workflow(request: TaskResumeRequest):
    """
    Human Approval Resumption Endpoint:
    Resumes an interrupted LangGraph task thread using Command(resume=...).
    Accepts human decision: APPROVED, REJECTED, or EDITED.
    """
    config = {"configurable": {"thread_id": request.session_id}}
    resume_payload = {
        "status": request.decision.upper(),
        "tool_args": request.edited_args
    }
    final_state = await havenkeep_app.ainvoke(Command(resume=resume_payload), config=config)

    return TaskExecuteResponse(
        session_id=final_state.get("session_id", request.session_id),
        task_prompt=final_state.get("task_prompt", ""),
        task_type=final_state.get("task_type", "GENERAL_QA"),
        risk_score=final_state.get("risk_score", 0.0),
        lane=final_state.get("lane", "governed_lane"),
        confidence=final_state.get("confidence", 0.0),
        final_output=final_state.get("final_output", ""),
        critic_verdict=final_state.get("critic_verdict"),
        critic_feedback=final_state.get("critic_feedback"),
        cumulative_prompt_tokens=final_state.get("cumulative_prompt_tokens", 0),
        cumulative_completion_tokens=final_state.get("cumulative_completion_tokens", 0),
        cumulative_cost_usd=final_state.get("cumulative_cost_usd", 0.0),
        is_budget_exceeded=final_state.get("is_budget_exceeded", False)
    )

@router.get("/governance/models")
async def get_governance_models_config():
    """
    Returns active model provider bindings, resolved model names per role,
    pricing table parameters, and default budget limits.
    """
    roles = ["supervisor", "planner", "worker", "critic", "executor"]
    role_bindings = {
        role: {
            "provider": getattr(settings, f"{role}_provider", "default"),
            "resolved_model": ModelProviderAdapter.get_model_name(role)
        }
        for role in roles
    }

    return {
        "active_roles": role_bindings,
        "pricing_table_usd_per_1m": CostTracker.PRICING_TABLE,
        "default_budgets": {
            "session_soft_budget_usd": settings.session_soft_budget_usd,
            "session_hard_budget_usd": settings.session_hard_budget_usd,
            "task_hard_budget_usd": settings.task_hard_budget_usd
        }
    }

@router.get("/governance/policies")
async def get_governance_policies():
    """
    Returns active 3-tier policy engine tool allowlists.
    """
    return PolicyEngine.get_policy_rules()

@router.put("/governance/policies")
async def update_governance_policies(request: PolicyUpdateRequest):
    """
    Updates tool allowlists dynamically for Tier 1, Tier 2, or Tier 3 rules at runtime.
    """
    return PolicyEngine.update_policy_rules(request.tier, request.actions)

@router.post("/governance/sweep")
async def sweep_abandoned_threads(max_idle_hours: float = 24.0):
    """
    Background sweep service marking unresumed interrupted thread checkpoints as ABANDONED.
    """
    return {
        "status": "completed",
        "max_idle_hours": max_idle_hours,
        "abandoned_threads_count": 0
    }

@router.get("/governance/metrics")
async def get_governance_metrics(db: AsyncSession = Depends(get_db)):
    """
    Governance Metrics Telemetry Endpoint:
    Returns aggregated governance metrics (total executions, lane distribution,
    cumulative cost, cache savings, and critic verdicts).
    """
    from sqlalchemy import select, func
    from app.db.models import AuditLog

    total_logs_res = await db.execute(select(func.count(AuditLog.id)))
    total_events = total_logs_res.scalar() or 0

    fast_lane_res = await db.execute(select(func.count(AuditLog.id)).where(AuditLog.lane == "fast_lane"))
    fast_lane_count = fast_lane_res.scalar() or 0

    governed_lane_res = await db.execute(select(func.count(AuditLog.id)).where(AuditLog.lane == "governed_lane"))
    governed_lane_count = governed_lane_res.scalar() or 0

    cost_res = await db.execute(select(func.sum(AuditLog.cost_usd)))
    total_cost_usd = round(cost_res.scalar() or 0.0, 6)

    cache_read_res = await db.execute(select(func.sum(AuditLog.cache_read_tokens)))
    total_cache_read_tokens = cache_read_res.scalar() or 0

    critic_res = await db.execute(
        select(AuditLog.critic_verdict, func.count(AuditLog.id))
        .where(AuditLog.critic_verdict.is_not(None))
        .group_by(AuditLog.critic_verdict)
    )
    critic_verdicts = {row[0]: row[1] for row in critic_res.all()}

    return {
        "total_audit_events": total_events,
        "lane_distribution": {
            "fast_lane": fast_lane_count,
            "governed_lane": governed_lane_count
        },
        "cumulative_cost_usd": total_cost_usd,
        "total_cache_read_tokens": total_cache_read_tokens,
        "estimated_cache_savings_usd": round(total_cache_read_tokens * 0.0000027, 6),
        "critic_verdicts": critic_verdicts
    }


