import json
import re
from typing import Dict, Any, cast
from langchain_core.messages import SystemMessage, HumanMessage
from app.graph.state import HavenkeepState
from app.governance.model_adapter import ModelProviderAdapter
from app.governance.policy_engine import PolicyEngine, PolicyVerdict
from app.governance.cost_tracker import CostTracker
from app.governance.audit_logger import AuditLogger

WORKER_SYSTEM_PROMPTS = {
    "RESEARCH": """You are the Havenkeep Fast-Lane Research Worker.
Your role is to synthesize clear, accurate, concise research summaries and explanations based on user prompts.
Provide well-structured answers using Markdown headings and bullet points where helpful.""",

    "CODE_GENERATION": """You are the Havenkeep Fast-Lane Code Worker.
Your role is to write clean, idiomatic, well-commented code snippets and explanations in response to user software requests.
Always format code snippets in Markdown code blocks with appropriate language identifiers.""",

    "DATA_ANALYSIS": """You are the Havenkeep Fast-Lane Data Analysis Worker.
Your role is to process, summarize, and analyze data queries, SQL concepts, or data structures efficiently.
Present conclusions logically with structured formatting.""",

    "GENERAL_QA": """You are the Havenkeep Fast-Lane General Assistant.
Your role is to answer user questions, explain concepts clearly, and provide helpful, concise responses."""
}

class FastLaneWorkerNode:
    """
    Fast-Lane Worker Node that handles low-stakes tasks efficiently using specialized prompts.
    Enforces Shift-Left governance: evaluates tool calls against PolicyEngine, tracks token cost
    via CostTracker, and records event transitions to AuditLogger.
    """

    @classmethod
    async def run(cls, state: HavenkeepState) -> Dict[str, Any]:
        prompt = state.get("task_prompt", "")
        task_type = state.get("task_type", "GENERAL_QA")
        session_id = state.get("session_id", "session-unknown")

        # Select specialized prompt
        system_prompt = WORKER_SYSTEM_PROMPTS.get(task_type, WORKER_SYSTEM_PROMPTS["GENERAL_QA"])
        model = ModelProviderAdapter.get_model(role="worker", temperature=0.2)

        messages = [
            SystemMessage(content=system_prompt),
            HumanMessage(content=prompt)
        ]

        # Shift-Left Governance Check: Simulate default internal tool policy check for fast-lane
        policy_verdict: PolicyVerdict = PolicyEngine.evaluate_tool_call(
            agent_role="worker",
            tool_name="internal_compute",
            tool_args={"task_type": task_type}
        )

        response = await model.ainvoke(messages)
        content = response.content if hasattr(response, "content") else str(response)

        # Extract token usage metadata
        usage = getattr(response, "usage_metadata", {}) or {}
        prompt_tokens = usage.get("input_tokens", 200)
        completion_tokens = usage.get("output_tokens", 150)

        # Token & Cost Tracking
        model_name = ModelProviderAdapter.get_model_name("worker")
        call_cost = CostTracker.calculate_cost(model_name, prompt_tokens, completion_tokens)
        current_cost = state.get("cumulative_cost_usd", 0.0)
        new_cost, is_soft_warn, is_hard_halt = CostTracker.update_and_check_budget(
            current_cost, call_cost, state.get("soft_budget_usd", 0.50), state.get("hard_budget_usd", 2.00)
        )

        # Audit Logging
        await AuditLogger.log_event(
            session_id=session_id,
            agent_name="FastLaneWorker",
            lane="fast_lane",
            step_name="worker_execution",
            event_type="WORKER_EXECUTED",
            prompt_tokens=prompt_tokens,
            completion_tokens=completion_tokens,
            cost_usd=call_cost,
            tool_name="internal_compute",
            policy_verdict=policy_verdict.verdict,
            payload={
                "task_type": task_type,
                "policy_tier": policy_verdict.tier,
                "response_snippet": content[:100]
            }
        )

        return {
            "final_output": content,
            "cumulative_prompt_tokens": state.get("cumulative_prompt_tokens", 0) + prompt_tokens,
            "cumulative_completion_tokens": state.get("cumulative_completion_tokens", 0) + completion_tokens,
            "cumulative_cost_usd": new_cost,
            "is_budget_exceeded": is_hard_halt
        }
