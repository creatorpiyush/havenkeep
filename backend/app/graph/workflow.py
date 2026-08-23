from typing import Dict, Any, Literal
from langgraph.graph import StateGraph, START, END
from app.graph.state import HavenkeepState
from app.graph.nodes.supervisor import SupervisorNode
from app.graph.nodes.worker import FastLaneWorkerNode
from app.graph.nodes.guardrail import FastLaneGuardrailNode

async def governed_lane_stub(state: HavenkeepState) -> Dict[str, Any]:
    """
    Placeholder Node for Governed-Lane (Planner -> Executor -> Critic).
    Returns an escalation notification until Phase 3 implementation is connected.
    """
    task_prompt = state.get("task_prompt", "")
    risk_score = state.get("risk_score", 0.8)
    
    output_msg = (
        f"[GOVERNED_LANE_STUB] Task '{task_prompt}' was scored as High Risk ({risk_score:.2f}) "
        f"and routed to Governed-Lane. Full multi-agent planner/executor/critic flow will execute in Phase 3."
    )
    return {
        "final_output": output_msg,
        "critic_verdict": "ESCALATE"
    }

def route_lane(state: HavenkeepState) -> Literal["fast_lane_worker", "governed_lane_stub"]:
    """
    Conditional Routing Edge function based on Supervisor Risk Scoring.
    """
    lane = state.get("lane", "fast_lane")
    if lane == "fast_lane":
        return "fast_lane_worker"
    return "governed_lane_stub"

def create_havenkeep_workflow():
    """
    Constructs and compiles the Havenkeep LangGraph State Graph.
    """
    workflow = StateGraph(HavenkeepState)

    # Add Nodes
    workflow.add_node("supervisor", SupervisorNode.run)
    workflow.add_node("fast_lane_worker", FastLaneWorkerNode.run)
    workflow.add_node("fast_lane_guardrail", FastLaneGuardrailNode.run)
    workflow.add_node("governed_lane_stub", governed_lane_stub)

    # Add Edges
    workflow.add_edge(START, "supervisor")
    workflow.add_conditional_edges(
        "supervisor",
        route_lane,
        {
            "fast_lane_worker": "fast_lane_worker",
            "governed_lane_stub": "governed_lane_stub"
        }
    )
    workflow.add_edge("fast_lane_worker", "fast_lane_guardrail")
    workflow.add_edge("fast_lane_guardrail", END)
    workflow.add_edge("governed_lane_stub", END)

    return workflow.compile()

# Instantiated compiled workflow graph engine
havenkeep_app = create_havenkeep_workflow()
