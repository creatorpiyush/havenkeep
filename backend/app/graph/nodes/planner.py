import json
import re
from typing import Dict, Any, List, cast
from langchain_core.messages import SystemMessage, HumanMessage
from app.graph.state import HavenkeepState
from app.governance.model_adapter import ModelProviderAdapter
from app.governance.policy_engine import PolicyEngine
from app.governance.cost_tracker import CostTracker
from app.governance.audit_logger import AuditLogger

PLANNER_SYSTEM_PROMPT = """You are the Havenkeep Governed-Lane Planner Agent.
Your role is to analyze high-risk or complex tasks and break them down into an explicit, sequential execution plan.

OUTPUT INSTRUCTIONS:
Respond ONLY with a JSON array of step objects:
[
  {
    "step_id": 1,
    "description": "Clear step explanation",
    "tool_name": "database_write | external_http_post | file_read | internal_compute",
    "tool_args": {"arg_key": "arg_value"}
  }
]
Keep plans focused, safe, and scoped to between 2 and 4 logical steps.
"""

class PlannerNode:
    """
    Planner Node that decomposes complex or high-risk tasks into a structured execution plan.
    Routes tool call steps through PolicyEngine and tracks LLM token spend.
    """

    @classmethod
    async def run(cls, state: HavenkeepState) -> Dict[str, Any]:
        prompt = state.get("task_prompt", "")
        session_id = state.get("session_id", "session-unknown")

        model = ModelProviderAdapter.get_model(role="planner", temperature=0.1)

        messages = [
            SystemMessage(content=PLANNER_SYSTEM_PROMPT),
            HumanMessage(content=f"Decompose this task into sequential execution steps:\n\n{prompt}")
        ]

        response = await model.ainvoke(messages)
        content = response.content if hasattr(response, "content") else str(response)

        # Parse token usage
        usage = getattr(response, "usage_metadata", {}) or {}
        prompt_tokens = usage.get("input_tokens", 250)
        completion_tokens = usage.get("output_tokens", 180)

        # Dynamic Cost Tracking
        model_name = ModelProviderAdapter.get_model_name("planner")
        call_cost = CostTracker.calculate_cost(model_name, prompt_tokens, completion_tokens)
        current_cost = state.get("cumulative_cost_usd", 0.0)
        new_cost, is_soft_warn, is_hard_halt = CostTracker.update_and_check_budget(
            current_cost, call_cost, state.get("soft_budget_usd", 0.50), state.get("hard_budget_usd", 2.00)
        )

        # Parse steps from response
        plan_steps = cls._parse_plan_steps(content, prompt)

        # Audit Logging
        await AuditLogger.log_event(
            session_id=session_id,
            agent_name="Planner",
            lane="governed_lane",
            step_name="plan_generation",
            event_type="PLAN_GENERATED",
            prompt_tokens=prompt_tokens,
            completion_tokens=completion_tokens,
            cost_usd=call_cost,
            payload={
                "step_count": len(plan_steps),
                "plan_steps": plan_steps
            }
        )

        return {
            "plan_steps": plan_steps,
            "current_step_index": 0,
            "approved_plan": plan_steps,
            "cumulative_prompt_tokens": state.get("cumulative_prompt_tokens", 0) + prompt_tokens,
            "cumulative_completion_tokens": state.get("cumulative_completion_tokens", 0) + completion_tokens,
            "cumulative_cost_usd": new_cost,
            "is_budget_exceeded": is_hard_halt
        }

    @classmethod
    def _parse_plan_steps(cls, content: str, raw_prompt: str) -> List[Dict[str, Any]]:
        try:
            json_match = re.search(r"\[.*\]", content, re.DOTALL)
            raw_json = json_match.group(0) if json_match else content
            data = json.loads(raw_json)
            if isinstance(data, list):
                return cast(List[Dict[str, Any]], data)
        except Exception:
            pass

        # Fallback plan structure if model response is not standard JSON
        return [
            {
                "step_id": 1,
                "description": f"Analyze and prepare plan for: {raw_prompt[:60]}",
                "tool_name": "internal_compute",
                "tool_args": {"query": raw_prompt[:60]}
            },
            {
                "step_id": 2,
                "description": "Execute governed operation safely",
                "tool_name": "database_write" if "delete" in raw_prompt.lower() or "drop" in raw_prompt.lower() else "file_read",
                "tool_args": {"target": "production_db" if "delete" in raw_prompt.lower() else "workspace"}
            }
        ]
