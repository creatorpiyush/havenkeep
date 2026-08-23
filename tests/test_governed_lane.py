import pytest
from app.graph.state import HavenkeepState
from app.graph.workflow import havenkeep_app
from app.governance.model_adapter import ModelProviderAdapter
from app.graph.nodes.critic import CriticNode, MAX_REVISION_CYCLES

@pytest.mark.asyncio
async def test_governed_lane_end_to_end_execution():
    """
    Verifies end-to-end execution of a high-risk prompt through Governed-Lane:
    Supervisor -> Planner -> Executor -> Critic -> END.
    """
    initial_state: HavenkeepState = {
        "messages": [],
        "session_id": "test-governed-lane-session",
        "task_prompt": "Drop temporary staging tables and update database schema.",
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
    assert len(final_state["plan_steps"]) > 0
    assert final_state["final_output"] is not None
    assert final_state["critic_verdict"] in ["PASS", "MINOR_REVISION", "MAJOR_REVISION", "ESCALATE"]
    assert final_state["cumulative_prompt_tokens"] > 0
    assert final_state["cumulative_completion_tokens"] > 0
    assert final_state["cumulative_cost_usd"] > 0.0


@pytest.mark.asyncio
async def test_governed_lane_approval_flag_on_tier1_action():
    """
    Verifies that executing high-risk Tier 1 tool calls sets approval_required=True.
    """
    initial_state: HavenkeepState = {
        "messages": [],
        "session_id": "test-approval-flag-session",
        "task_prompt": "Delete all outdated records from production database.",
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

    assert final_state["approval_required"] is True
    assert final_state["pending_tool_call"] is not None
    assert "database_write" in final_state["pending_tool_call"]["tool_name"]


@pytest.mark.asyncio
async def test_dynamic_model_pricing_lookup():
    """
    Verifies dynamic model name resolution across all agent roles.
    """
    roles = ["supervisor", "planner", "worker", "critic", "executor"]
    for role in roles:
        model_name = ModelProviderAdapter.get_model_name(role)
        assert isinstance(model_name, str)
        assert len(model_name) > 0


@pytest.mark.asyncio
async def test_critic_iteration_cap(monkeypatch):
    """
    Verifies that CriticNode auto-escalates to ESCALATE when revision cap is reached.
    """
    from langchain_core.language_models import FakeListChatModel
    mock_model = FakeListChatModel(responses=['{"verdict": "MINOR_REVISION", "feedback": "Minor formatting issue."}'])
    monkeypatch.setattr(ModelProviderAdapter, "get_model", lambda role, temperature=0.0, mock_responses=None: mock_model)

    state: HavenkeepState = {
        "messages": [],
        "session_id": "test-cap-session",
        "task_prompt": "Update configuration",
        "task_type": "CODE_GENERATION",
        "risk_score": 0.7,
        "lane": "governed_lane",
        "confidence": 0.9,
        "risk_factors": {},
        "plan_steps": [],
        "current_step_index": 0,
        "approved_plan": None,
        "critic_verdict": None,
        "critic_feedback": None,
        "revision_count": MAX_REVISION_CYCLES,
        "pending_tool_call": None,
        "approval_required": False,
        "approval_reason": None,
        "is_budget_exceeded": False,
        "cumulative_prompt_tokens": 0,
        "cumulative_completion_tokens": 0,
        "cumulative_cost_usd": 0.0,
        "soft_budget_usd": 0.50,
        "hard_budget_usd": 2.00,
        "final_output": "Sample output requiring minor revision"
    }

    result = await CriticNode.run(state)
    assert result["critic_verdict"] == "ESCALATE"
    assert "maximum iteration cap" in result["critic_feedback"]
