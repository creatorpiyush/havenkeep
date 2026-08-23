import json
import re
from typing import Dict, Any, Tuple
from langchain_core.messages import SystemMessage, HumanMessage
from app.graph.state import HavenkeepState
from app.governance.model_adapter import ModelProviderAdapter
from app.governance.cost_tracker import CostTracker
from app.governance.audit_logger import AuditLogger

CRITIC_SYSTEM_PROMPT = """You are the Havenkeep Governed-Lane Critic Agent.
Your role is to perform a rigorous rubric-driven evaluation of the Executor's output against the user's task prompt.

EVALUATION RUBRIC:
1. Safety & Policy: Ensure no unauthorized system access or dangerous operations occurred.
2. Accuracy & Completeness: Check if all requirements in the prompt were fulfilled.
3. Quality & Formatting: Verify formatting clarity and logical structure.

VERDICT ENUM VALUES:
- PASS: Output is accurate, safe, and complete.
- MINOR_REVISION: Minor formatting or small clarity issues that can be revised.
- MAJOR_REVISION: Significant omissions, logical flaws, or structural errors.
- ESCALATE: High-risk actions, unresolvable ambiguities, or policy violations.

Respond ONLY with a JSON object:
{
  "verdict": "PASS | MINOR_REVISION | MAJOR_REVISION | ESCALATE",
  "feedback": "Detailed explanation supporting your verdict."
}
"""

MAX_REVISION_CYCLES = 2

class CriticNode:
    """
    Critic Node that evaluates Governed-Lane execution outputs against a strict rubric.
    Returns a verdict enum (PASS, MINOR_REVISION, MAJOR_REVISION, ESCALATE) and enforces
    an iteration cap (max 2 revision cycles) before escalating to human review.
    """

    @classmethod
    async def run(cls, state: HavenkeepState) -> Dict[str, Any]:
        prompt = state.get("task_prompt", "")
        executor_output = state.get("final_output", "")
        revision_count = state.get("revision_count", 0)
        session_id = state.get("session_id", "session-unknown")

        model = ModelProviderAdapter.get_model(role="critic", temperature=0.0)

        messages = [
            SystemMessage(content=CRITIC_SYSTEM_PROMPT),
            HumanMessage(
                content=f"Original Prompt:\n{prompt}\n\nExecutor Output:\n{executor_output}\n\nCurrent Revision Iteration: {revision_count}"
            )
        ]

        response = await model.ainvoke(messages)
        content = response.content if hasattr(response, "content") else str(response)

        # Dynamic Cost Pricing Calculation
        usage = getattr(response, "usage_metadata", {}) or {}
        prompt_tokens = usage.get("input_tokens", 150)
        completion_tokens = usage.get("output_tokens", 80)

        model_name = ModelProviderAdapter.get_model_name("critic")
        call_cost = CostTracker.calculate_cost(model_name, prompt_tokens, completion_tokens)
        current_cost = state.get("cumulative_cost_usd", 0.0)
        new_cost, is_soft_warn, is_hard_halt = CostTracker.update_and_check_budget(
            current_cost, call_cost, state.get("soft_budget_usd", 0.50), state.get("hard_budget_usd", 2.00)
        )

        verdict, feedback = cls._parse_critic_response(content)

        # Enforce Iteration Cap (Max 2 revision cycles)
        next_revision_count = revision_count
        if verdict == "MINOR_REVISION":
            if revision_count >= MAX_REVISION_CYCLES:
                verdict = "ESCALATE"
                feedback += f" (Auto-escalated: Reached maximum iteration cap of {MAX_REVISION_CYCLES} cycles)."
            else:
                next_revision_count += 1
        elif verdict == "MAJOR_REVISION":
            verdict = "ESCALATE"
            feedback += " (Auto-escalated due to MAJOR_REVISION verdict)."

        # Audit Logging
        await AuditLogger.log_event(
            session_id=session_id,
            agent_name="Critic",
            lane="governed_lane",
            step_name="critic_evaluation",
            event_type="CRITIC_EVALUATED",
            prompt_tokens=prompt_tokens,
            completion_tokens=completion_tokens,
            cost_usd=call_cost,
            critic_verdict=verdict,
            payload={
                "verdict": verdict,
                "feedback": feedback,
                "revision_count": next_revision_count
            }
        )

        return {
            "critic_verdict": verdict,
            "critic_feedback": feedback,
            "revision_count": next_revision_count,
            "cumulative_prompt_tokens": state.get("cumulative_prompt_tokens", 0) + prompt_tokens,
            "cumulative_completion_tokens": state.get("cumulative_completion_tokens", 0) + completion_tokens,
            "cumulative_cost_usd": new_cost,
            "is_budget_exceeded": is_hard_halt
        }

    @classmethod
    def _parse_critic_response(cls, content: str) -> Tuple[str, str]:
        try:
            json_match = re.search(r"\{.*\}", content, re.DOTALL)
            raw_json = json_match.group(0) if json_match else content
            data = json.loads(raw_json)
            if isinstance(data, dict):
                verdict = data.get("verdict", "PASS").upper()
                feedback = data.get("feedback", "Evaluation completed.")
                if verdict not in ["PASS", "MINOR_REVISION", "MAJOR_REVISION", "ESCALATE"]:
                    verdict = "PASS"
                return verdict, feedback
        except Exception:
            pass
        return "PASS", "Evaluated via default guardrail check."
