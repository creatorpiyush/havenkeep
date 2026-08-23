from typing import Dict, Any, cast
from langgraph.types import interrupt
from app.graph.state import HavenkeepState
from app.governance.audit_logger import AuditLogger

class ApprovalGateNode:
    """
    Approval Gate Node enforcing LangGraph durable interrupt discipline.
    Invokes interrupt() at node start when human approval or budget escalation is required,
    persisting state safely into checkpointer until resumed via Command(resume=...).
    """

    @classmethod
    async def run(cls, state: HavenkeepState) -> Dict[str, Any]:
        approval_required = state.get("approval_required", False)
        is_budget_exceeded = state.get("is_budget_exceeded", False)
        session_id = state.get("session_id", "session-unknown")
        approval_reason = state.get("approval_reason", "Human approval required for high-risk operation.")
        pending_tool_call = state.get("pending_tool_call")

        if approval_required or is_budget_exceeded:
            # 1. Log Interrupt Event to Audit Logger before pausing
            await AuditLogger.log_event(
                session_id=session_id,
                agent_name="ApprovalGate",
                lane="governed_lane",
                step_name="human_approval_interrupt",
                event_type="APPROVAL_INTERRUPT_TRIGGERED",
                policy_verdict="APPROVAL_REQUIRED",
                payload={
                    "approval_reason": approval_reason,
                    "is_budget_exceeded": is_budget_exceeded,
                    "pending_tool_call": pending_tool_call
                }
            )

            # 2. Durable Interrupt Call (Pauses graph execution until Command(resume=...) is sent)
            human_decision_raw = interrupt({
                "session_id": session_id,
                "approval_reason": approval_reason,
                "is_budget_exceeded": is_budget_exceeded,
                "pending_tool_call": pending_tool_call
            })

            # Format decision object from resume payload
            if isinstance(human_decision_raw, dict):
                decision = cast(Dict[str, Any], human_decision_raw)
            else:
                decision = {"status": str(human_decision_raw).upper()}

            status = decision.get("status", "APPROVED").upper()

            # 3. Process Resumed Decision
            if status == "APPROVED":
                await AuditLogger.log_event(
                    session_id=session_id,
                    agent_name="ApprovalGate",
                    lane="governed_lane",
                    step_name="human_approval_resume",
                    event_type="APPROVAL_ACCEPTED",
                    policy_verdict="ALLOWED",
                    payload={"status": status, "decision": decision}
                )
                return {
                    "approval_required": False,
                    "approval_reason": None,
                    "is_budget_exceeded": False
                }
            elif status == "EDITED":
                edited_args = decision.get("tool_args")
                if pending_tool_call and edited_args:
                    pending_tool_call["tool_args"] = edited_args
                await AuditLogger.log_event(
                    session_id=session_id,
                    agent_name="ApprovalGate",
                    lane="governed_lane",
                    step_name="human_approval_resume",
                    event_type="APPROVAL_EDITED",
                    policy_verdict="ALLOWED",
                    payload={"status": status, "decision": decision}
                )
                return {
                    "approval_required": False,
                    "approval_reason": None,
                    "pending_tool_call": pending_tool_call
                }
            else:
                # Default REJECTED
                await AuditLogger.log_event(
                    session_id=session_id,
                    agent_name="ApprovalGate",
                    lane="governed_lane",
                    step_name="human_approval_resume",
                    event_type="APPROVAL_REJECTED",
                    policy_verdict="BLOCKED",
                    payload={"status": status, "decision": decision}
                )
                return {
                    "approval_required": False,
                    "approval_reason": "Human administrator rejected execution.",
                    "critic_verdict": "ESCALATE",
                    "final_output": "[APPROVAL_REJECTED] Execution halted by human administrator signoff."
                }

        return {}
