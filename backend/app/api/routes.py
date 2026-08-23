from typing import Dict, Any, Optional
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from sqlalchemy.ext.asyncio import AsyncSession
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
    Phase 1 Endpoint:
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
    Phase 2 End-to-End Workflow Execution Endpoint:
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

    final_state = await havenkeep_app.ainvoke(initial_state)

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

