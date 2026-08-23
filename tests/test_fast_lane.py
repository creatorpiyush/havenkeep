import pytest
import os
from app.graph.state import HavenkeepState
from app.graph.workflow import havenkeep_app
from app.governance.policy_engine import PolicyEngine

@pytest.mark.asyncio
async def test_fast_lane_end_to_end_execution():
    """
    Verifies that a low-stakes research prompt executes through the compiled LangGraph workflow:
    Supervisor -> FastLaneWorker -> FastLaneGuardrail -> END.
    """
    initial_state: HavenkeepState = {
        "messages": [],
        "session_id": "test-fast-lane-session",
        "task_prompt": "Explain the key differences between synchronous and asynchronous code in Python.",
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

    final_state = await havenkeep_app.ainvoke(initial_state)

    assert final_state["lane"] == "fast_lane"
    assert final_state["final_output"] is not None
    assert len(final_state["final_output"]) > 0
    assert final_state["critic_verdict"] in ["PASS", "REVISED"]
    assert final_state["cumulative_prompt_tokens"] > 0
    assert final_state["cumulative_completion_tokens"] > 0
    assert final_state["cumulative_cost_usd"] > 0.0


@pytest.mark.asyncio
async def test_fast_lane_governance_policy_check():
    """
    Verifies Shift-Left policy check evaluation for worker tools.
    """
    verdict_tier3 = PolicyEngine.evaluate_tool_call(
        agent_role="worker",
        tool_name="internal_compute",
        tool_args={"query": "summarize"}
    )
    assert verdict_tier3.verdict == "ALLOWED"
    assert verdict_tier3.tier == "TIER_3"
    assert not verdict_tier3.requires_human_interrupt

    verdict_tier1 = PolicyEngine.evaluate_tool_call(
        agent_role="worker",
        tool_name="database_write",
        tool_args={"query": "DELETE FROM users"}
    )
    assert verdict_tier1.verdict == "APPROVAL_REQUIRED"
    assert verdict_tier1.tier == "TIER_1"
    assert verdict_tier1.requires_human_interrupt


@pytest.mark.asyncio
async def test_governed_lane_stub_routing():
    """
    Verifies that a high-risk prompt routes to the governed_lane_stub node.
    """
    initial_state: HavenkeepState = {
        "messages": [],
        "session_id": "test-governed-lane-session",
        "task_prompt": "Delete all outdated user records from the production database.",
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

    final_state = await havenkeep_app.ainvoke(initial_state)

    assert final_state["lane"] == "governed_lane"
    assert "[GOVERNED_LANE_STUB]" in final_state["final_output"]
    assert final_state["critic_verdict"] == "ESCALATE"
