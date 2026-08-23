import pytest
from langgraph.types import Command
from app.graph.state import HavenkeepState
from app.graph.workflow import havenkeep_app
from app.governance.policy_engine import PolicyEngine

@pytest.mark.asyncio
async def test_human_approval_interrupt_and_resume():
    """
    Verifies that high-risk Tier 1 prompts trigger interrupt() at ApprovalGateNode,
    and cleanly resume execution when sent Command(resume={'status': 'APPROVED'}).
    """
    session_id = "test-interrupt-resume-session"
    config = {"configurable": {"thread_id": session_id}}

    initial_state: HavenkeepState = {
        "messages": [],
        "session_id": session_id,
        "task_prompt": "Delete all outdated user records from production database.",
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

    # 1. First Run: Should pause at interrupt() in ApprovalGateNode
    paused_state = await havenkeep_app.ainvoke(initial_state, config=config)
    assert paused_state["approval_required"] is True or paused_state["pending_tool_call"] is not None

    # 2. Resume with APPROVED status
    resume_payload = {"status": "APPROVED"}
    final_state = await havenkeep_app.ainvoke(Command(resume=resume_payload), config=config)

    assert final_state["lane"] == "governed_lane"
    assert final_state["final_output"] is not None


@pytest.mark.asyncio
async def test_human_approval_rejection():
    """
    Verifies that sending Command(resume={'status': 'REJECTED'}) halts execution cleanly.
    """
    session_id = "test-interrupt-reject-session"
    config = {"configurable": {"thread_id": session_id}}

    initial_state: HavenkeepState = {
        "messages": [],
        "session_id": session_id,
        "task_prompt": "Drop all production database tables.",
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

    # Pauses at interrupt
    await havenkeep_app.ainvoke(initial_state, config=config)

    # Resume with REJECTED status
    resume_payload = {"status": "REJECTED"}
    final_state = await havenkeep_app.ainvoke(Command(resume=resume_payload), config=config)

    assert "[APPROVAL_REJECTED]" in final_state["final_output"] or final_state["critic_verdict"] == "ESCALATE"


@pytest.mark.asyncio
async def test_dynamic_policy_rules_api():
    """
    Verifies dynamic inspection and updating of 3-tier policy allowlists.
    """
    rules = PolicyEngine.get_policy_rules()
    assert "tier_1_actions" in rules
    assert "database_write" in rules["tier_1_actions"]

    # Add custom action to Tier 1
    updated_actions = rules["tier_1_actions"] + ["custom_highrisk_tool"]
    new_rules = PolicyEngine.update_policy_rules("TIER_1", updated_actions)

    assert "custom_highrisk_tool" in new_rules["tier_1_actions"]

    # Evaluate tool call against updated policy
    verdict = PolicyEngine.evaluate_tool_call(
        agent_role="executor",
        tool_name="custom_highrisk_tool",
        tool_args={}
    )
    assert verdict.verdict == "APPROVAL_REQUIRED"
    assert verdict.tier == "TIER_1"
