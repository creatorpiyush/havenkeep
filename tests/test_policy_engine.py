import pytest
from app.governance.policy_engine import PolicyEngine

def test_tier_1_action_requires_approval():
    verdict = PolicyEngine.evaluate_tool_call(
        agent_role="executor",
        tool_name="database_write",
        tool_args={"query": "DELETE FROM users WHERE active = false;"}
    )
    assert verdict.verdict == "APPROVAL_REQUIRED"
    assert verdict.tier == "TIER_1"
    assert verdict.requires_human_interrupt is True

def test_tier_3_action_allowed():
    verdict = PolicyEngine.evaluate_tool_call(
        agent_role="worker",
        tool_name="file_read",
        tool_args={"path": "README.md"}
    )
    assert verdict.verdict == "ALLOWED"
    assert verdict.tier == "TIER_3"
    assert verdict.requires_human_interrupt is False

def test_tier_2_scratch_sandbox_allowed():
    verdict = PolicyEngine.evaluate_tool_call(
        agent_role="worker",
        tool_name="file_write",
        tool_args={"path": "scratch/temp_data.json", "content": "{}"}
    )
    assert verdict.verdict == "ALLOWED"
    assert verdict.tier == "TIER_2"
    assert verdict.requires_human_interrupt is False

def test_tier_2_outside_scratch_requires_approval():
    verdict = PolicyEngine.evaluate_tool_call(
        agent_role="worker",
        tool_name="file_write",
        tool_args={"path": "backend/app/main.py", "content": "print('hello')"}
    )
    assert verdict.verdict == "APPROVAL_REQUIRED"
    assert verdict.tier == "TIER_2"
    assert verdict.requires_human_interrupt is True

def test_plan_drift_triggers_approval():
    approved_plan = [{"tool_name": "file_read"}, {"tool_name": "web_search"}]
    
    # Unapproved tool attempt
    verdict = PolicyEngine.evaluate_tool_call(
        agent_role="executor",
        tool_name="summarize",
        tool_args={},
        approved_plan_steps=approved_plan
    )
    assert verdict.verdict == "APPROVAL_REQUIRED"
    assert "Plan Drift" in verdict.reason
