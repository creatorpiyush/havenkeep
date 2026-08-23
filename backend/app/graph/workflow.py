from typing import Dict, Any, Literal, cast
from langgraph.graph import StateGraph, START, END
from app.graph.state import HavenkeepState
from app.graph.nodes.supervisor import SupervisorNode
from app.graph.nodes.worker import FastLaneWorkerNode
from app.graph.nodes.guardrail import FastLaneGuardrailNode
from app.graph.nodes.planner import PlannerNode
from app.graph.nodes.executor import ExecutorNode
from app.graph.nodes.critic import CriticNode

def route_lane(state: HavenkeepState) -> Literal["fast_lane_worker", "planner"]:
    """
    Conditional Routing Edge function based on Supervisor Risk Scoring.
    """
    lane = state.get("lane", "fast_lane")
    if lane == "fast_lane":
        return "fast_lane_worker"
    return "planner"

def route_critic_verdict(state: HavenkeepState) -> Literal["executor", "end"]:
    """
    Conditional Routing Edge function based on Critic Verdict.
    If MINOR_REVISION and under iteration cap, routes back to executor for revision.
    Otherwise terminates workflow at END.
    """
    verdict = state.get("critic_verdict", "PASS")
    if verdict == "MINOR_REVISION":
        return "executor"
    return "end"

def create_havenkeep_workflow():
    """
    Constructs and compiles the Havenkeep LangGraph State Graph.
    Supports both Fast-Lane (Supervisor -> Worker -> Guardrail) and
    Governed-Lane (Supervisor -> Planner -> Executor -> Critic -> Loop/END).
    """
    workflow = StateGraph(cast(Any, HavenkeepState))

    # Add Nodes
    workflow.add_node("supervisor", SupervisorNode.run)
    workflow.add_node("fast_lane_worker", FastLaneWorkerNode.run)
    workflow.add_node("fast_lane_guardrail", FastLaneGuardrailNode.run)
    workflow.add_node("planner", PlannerNode.run)
    workflow.add_node("executor", ExecutorNode.run)
    workflow.add_node("critic", CriticNode.run)

    # Add Edges
    workflow.add_edge(START, "supervisor")
    workflow.add_conditional_edges(
        "supervisor",
        route_lane,
        {
            "fast_lane_worker": "fast_lane_worker",
            "planner": "planner"
        }
    )

    # Fast-Lane Flow
    workflow.add_edge("fast_lane_worker", "fast_lane_guardrail")
    workflow.add_edge("fast_lane_guardrail", END)

    # Governed-Lane Flow
    workflow.add_edge("planner", "executor")
    workflow.add_edge("executor", "critic")
    workflow.add_conditional_edges(
        "critic",
        route_critic_verdict,
        {
            "executor": "executor",
            "end": END
        }
    )

    return workflow.compile()

# Instantiated compiled workflow graph engine
havenkeep_app = create_havenkeep_workflow()
