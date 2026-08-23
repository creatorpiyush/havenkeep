import json
import re
from typing import Dict, Any, cast
from langchain_core.messages import SystemMessage, HumanMessage
from app.graph.state import HavenkeepState
from app.governance.model_adapter import ModelProviderAdapter
from app.governance.cost_tracker import CostTracker
from app.governance.audit_logger import AuditLogger

SUPERVISOR_SYSTEM_PROMPT = """You are the Havenkeep Supervisor & Risk Classifier Agent.
Your responsibility is to analyze incoming user tasks, categorize their type, score their operational risk, and select the appropriate execution lane.

TAXONOMY:
- RESEARCH: Informational Q&A, web search, summarization.
- CODE_GENERATION: Writing, refactoring, or editing software code.
- DATA_ANALYSIS: Querying databases, processing data structures.
- EXTERNAL_ACTION: Operations modifying external systems, sending communications, deleting data, or deploying software.
- GENERAL_QA: Standard conversation or explanation.

RISK FACTORS TO EVALUATE:
1. Reversibility: READ_ONLY (0.0) vs REVERSIBLE (0.3) vs IRREVERSIBLE/PERMANENT (1.0).
2. Ambiguity: SINGLE_INTERPRETATION (0.0) vs MULTIPLE_PLAUSIBLE (0.5) vs HIGHLY_AMBIGUOUS (1.0).
3. Domain Risk: GENERAL (0.0) vs SENSITIVE/FINANCIAL/LEGAL (0.7) vs PRODUCTION_MUTATION (1.0).
4. Complexity: SINGLE_STEP (0.0) vs MULTI_STEP (0.5) vs HIGHLY_DEPENDENT (1.0).

OUTPUT FORMAT:
You MUST respond with ONLY a valid JSON object formatted exactly as follows:
{
  "task_type": "CODE_GENERATION",
  "risk_score": 0.75,
  "lane": "governed_lane",
  "confidence": 0.90,
  "risk_factors": {
    "reversibility": "IRREVERSIBLE",
    "ambiguity": "SINGLE_INTERPRETATION",
    "domain_risk": "PRODUCTION_MUTATION",
    "complexity": "MULTI_STEP"
  },
  "rationale": "Task involves updating source files and building deployment containers."
}

RULES FOR LANE ROUTING:
- Set lane to "fast_lane" ONLY if risk_score <= 0.40 AND confidence >= 0.80.
- Otherwise, set lane to "governed_lane".
"""

class SupervisorNode:
    """
    Supervisor Router Node that classifies task type and scores risk before dispatching.
    """

    @classmethod
    async def run(cls, state: HavenkeepState) -> Dict[str, Any]:
        prompt = state.get("task_prompt", "")
        model = ModelProviderAdapter.get_model(role="supervisor", temperature=0.0)
        
        messages = [
            SystemMessage(content=SUPERVISOR_SYSTEM_PROMPT),
            HumanMessage(content=f"Analyze and classify this user task:\n\n{prompt}")
        ]
        
        response = await model.ainvoke(messages)
        content = response.content if hasattr(response, "content") else str(response)
        
        # Extract token usage metadata if present
        usage = getattr(response, "usage_metadata", {}) or {}
        prompt_tokens = usage.get("input_tokens", 150)
        completion_tokens = usage.get("output_tokens", 80)
        
        call_cost = CostTracker.calculate_cost("claude-3-haiku-20240307", prompt_tokens, completion_tokens)
        current_cost = state.get("cumulative_cost_usd", 0.0)
        new_cost, is_soft_warn, is_hard_halt = CostTracker.update_and_check_budget(
            current_cost, call_cost, state.get("soft_budget_usd", 0.50), state.get("hard_budget_usd", 2.00)
        )

        # Parse JSON
        parsed_result = cls._parse_json_response(content, prompt)
        
        # If response was generic mock fallback, use heuristic rule classifier
        if parsed_result.get("task_type") == "GENERAL_QA" and parsed_result.get("risk_score") == 0.2 and parsed_result.get("confidence") == 0.95:
            heuristic = cls._heuristic_fallback(prompt)
            if heuristic.get("lane") == "governed_lane":
                parsed_result = heuristic
        
        # Determine lane based on threshold rules
        risk_score = parsed_result.get("risk_score", 0.5)
        confidence = parsed_result.get("confidence", 0.8)
        lane = "fast_lane" if (risk_score <= 0.40 and confidence >= 0.80) else "governed_lane"
        parsed_result["lane"] = lane

        # Audit log entry
        await AuditLogger.log_event(
            session_id=state.get("session_id", "session-unknown"),
            agent_name="Supervisor",
            lane="supervisor",
            step_name="supervisor_routing",
            event_type="ROUTER_CLASSIFIED",
            prompt_tokens=prompt_tokens,
            completion_tokens=completion_tokens,
            cost_usd=call_cost,
            payload=parsed_result
        )

        return {
            "task_type": parsed_result.get("task_type", "GENERAL_QA"),
            "risk_score": risk_score,
            "lane": lane,
            "confidence": confidence,
            "risk_factors": parsed_result.get("risk_factors", {}),
            "cumulative_prompt_tokens": state.get("cumulative_prompt_tokens", 0) + prompt_tokens,
            "cumulative_completion_tokens": state.get("cumulative_completion_tokens", 0) + completion_tokens,
            "cumulative_cost_usd": new_cost,
            "is_budget_exceeded": is_hard_halt
        }

    @classmethod
    def _parse_json_response(cls, content: str, raw_prompt: str) -> Dict[str, Any]:
        try:
            # Clean Markdown code block wrappers
            json_match = re.search(r"\{.*\}", content, re.DOTALL)
            raw_json = json_match.group(0) if json_match else content
            data = json.loads(raw_json)
            if isinstance(data, dict):
                return cast(Dict[str, Any], data)
            return cls._heuristic_fallback(raw_prompt)
        except Exception:
            # Rule-based fallback if JSON parsing fails
            return cls._heuristic_fallback(raw_prompt)


    @classmethod
    def _heuristic_fallback(cls, prompt: str) -> Dict[str, Any]:
        prompt_lower = prompt.lower()
        high_risk_keywords = [
            "delete", "drop", "deploy", "send", "exec", "pay", "refactor", 
            "grant", "permission", "modify", "truncate", "remove", "migrate", 
            "webhook", "commit", "push", "billing", "hotfix"
        ]
        is_high_risk = any(kw in prompt_lower for kw in high_risk_keywords) or (
            "write code" in prompt_lower or "write to" in prompt_lower or "file write" in prompt_lower
        )
        
        return {
            "task_type": "EXTERNAL_ACTION" if is_high_risk else "RESEARCH",
            "risk_score": 0.80 if is_high_risk else 0.20,
            "lane": "governed_lane" if is_high_risk else "fast_lane",
            "confidence": 0.85,
            "risk_factors": {"heuristic_fallback": True},
            "rationale": "Parsed via heuristic keyword rule fallback."
        }

