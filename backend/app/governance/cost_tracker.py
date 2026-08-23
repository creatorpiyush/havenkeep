from typing import Dict, Any, Tuple
from app.config import settings

class BudgetExceededError(Exception):
    """Raised when a task or session crosses its hard budget threshold."""
    def __init__(self, message: str, cumulative_cost: float, hard_limit: float):
        super().__init__(message)
        self.cumulative_cost = cumulative_cost
        self.hard_limit = hard_limit

class CostTracker:
    """
    Normalizes token usage across model providers and calculates estimated USD cost.
    Enforces soft budget warnings and hard budget execution halts.
    """
    
    # Pricing per 1,000,000 tokens (USD)
    PRICING_TABLE: Dict[str, Dict[str, float]] = {
        # Anthropic
        "claude-3-haiku-20240307": {"input": 0.25, "output": 1.25},
        "claude-3-5-sonnet-20240620": {"input": 3.00, "output": 15.00},
        "claude-3-opus-20240229": {"input": 15.00, "output": 75.00},
        # OpenAI
        "gpt-4o-mini": {"input": 0.15, "output": 0.60},
        "gpt-4o": {"input": 5.00, "output": 15.00},
        # Default fallback pricing
        "default": {"input": 1.00, "output": 3.00},
    }

    @classmethod
    def calculate_cost(
        cls, 
        model_name: str, 
        prompt_tokens: int, 
        completion_tokens: int
    ) -> float:
        pricing = cls.PRICING_TABLE.get(model_name, cls.PRICING_TABLE["default"])
        input_cost = (prompt_tokens / 1_000_000.0) * pricing["input"]
        output_cost = (completion_tokens / 1_000_000.0) * pricing["output"]
        return round(input_cost + output_cost, 6)

    @classmethod
    def update_and_check_budget(
        cls,
        current_cumulative_cost: float,
        call_cost: float,
        soft_budget_limit: float = settings.session_soft_budget_usd,
        hard_budget_limit: float = settings.session_hard_budget_usd
    ) -> Tuple[float, bool, bool]:
        """
        Updates cumulative cost and returns:
        (new_cumulative_cost, is_soft_warning_issued, is_hard_halt_required)
        """
        new_cost = round(current_cumulative_cost + call_cost, 6)
        is_soft_warning = new_cost >= soft_budget_limit
        is_hard_halt = new_cost >= hard_budget_limit
        
        return new_cost, is_soft_warning, is_hard_halt
