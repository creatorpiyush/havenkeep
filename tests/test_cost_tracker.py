import pytest
from app.governance.cost_tracker import CostTracker

def test_calculate_cost():
    # Model pricing: Haiku ($0.25 / 1M prompt, $1.25 / 1M completion)
    cost = CostTracker.calculate_cost("claude-3-haiku-20240307", prompt_tokens=1_000_000, completion_tokens=1_000_000)
    assert cost == 1.50

def test_budget_soft_warning():
    current_cost = 0.40
    call_cost = 0.15 # Brings total to 0.55 (>= 0.50 soft limit)
    new_cost, is_soft_warn, is_hard_halt = CostTracker.update_and_check_budget(
        current_cost, call_cost, soft_budget_limit=0.50, hard_budget_limit=2.00
    )
    assert new_cost == 0.55
    assert is_soft_warn is True
    assert is_hard_halt is False

def test_budget_hard_halt():
    current_cost = 1.90
    call_cost = 0.15 # Brings total to 2.05 (>= 2.00 hard limit)
    new_cost, is_soft_warn, is_hard_halt = CostTracker.update_and_check_budget(
        current_cost, call_cost, soft_budget_limit=0.50, hard_budget_limit=2.00
    )
    assert new_cost == 2.05
    assert is_soft_warn is True
    assert is_hard_halt is True
