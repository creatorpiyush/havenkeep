from typing import Dict, Any, Optional
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from sqlalchemy.ext.asyncio import AsyncSession
from app.db.database import get_db
from app.graph.nodes.supervisor import SupervisorNode
from app.governance.policy_engine import PolicyEngine
from app.governance.audit_logger import AuditLogger
from app.graph.state import HavenkeepState

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

@router.post("/supervisor/classify", response_model=TaskClassifyResponse)
async def classify_task(
    request: TaskClassifyRequest,
    db: AsyncSession = Depends(get_db)
):
    """
    Phase 1 Manual Test Endpoint:
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
    audit_entry = await AuditLogger.log_event(
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
