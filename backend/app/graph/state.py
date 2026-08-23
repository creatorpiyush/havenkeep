from typing import List, Dict, Any, Optional
from typing_extensions import TypedDict
from langchain_core.messages import BaseMessage

class HavenkeepState(TypedDict):
    """
    Unified LangGraph State Schema shared across Fast-Lane and Governed-Lane workflows.
    """
    messages: List[BaseMessage]
    session_id: str
    task_prompt: str
    
    # Supervisor Risk Classifier Outputs
    task_type: str # RESEARCH, CODE_GENERATION, DATA_ANALYSIS, EXTERNAL_ACTION, GENERAL_QA
    risk_score: float # 0.0 to 1.0
    lane: str # "fast_lane" or "governed_lane"
    confidence: float # 0.0 to 1.0
    risk_factors: Dict[str, Any]
    
    # Governed-Lane State
    plan_steps: List[Dict[str, Any]]
    current_step_index: int
    approved_plan: Optional[List[Dict[str, Any]]]
    
    # Critic State
    critic_verdict: Optional[str] # "PASS", "MINOR_REVISION", "MAJOR_REVISION", "ESCALATE"
    critic_feedback: Optional[str]
    revision_count: int
    
    # Human-in-the-Loop & Governance State
    pending_tool_call: Optional[Dict[str, Any]]
    approval_required: bool
    approval_reason: Optional[str]
    is_budget_exceeded: bool
    
    # Accumulated Cost & Token Metrics
    cumulative_prompt_tokens: int
    cumulative_completion_tokens: int
    cumulative_cost_usd: float
    soft_budget_usd: float
    hard_budget_usd: float
    
    # Final Output Response
    final_output: Optional[str]
