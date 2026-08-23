from typing import Dict, Any, Optional, List
from dataclasses import dataclass

@dataclass
class PolicyVerdict:
    verdict: str # "ALLOWED", "BLOCKED", "APPROVAL_REQUIRED"
    tier: str # "TIER_1", "TIER_2", "TIER_3"
    reason: str
    requires_human_interrupt: bool = False

class PolicyEngine:
    """
    Shift-Left Policy Engine enforcing per-agent tool allowlists, 3-tier action classification,
    and plan drift detection before tool execution.
    """
    
    TIER_1_ACTIONS = {
        "external_http_post",
        "send_email",
        "send_message",
        "database_write",
        "file_delete",
        "deploy_command",
        "payment",
        "financial_transaction",
        "execute_shell_command",
        "run_arbitrary_code",
        "modify_permissions",
        "grant_access",
    }
    
    TIER_2_ACTIONS = {
        "file_write",
        "database_read_unscoped",
        "git_commit",
        "git_push",
        "create_calendar_event",
        "web_fetch",
    }
    
    TIER_3_ACTIONS = {
        "file_read",
        "database_read_scoped",
        "web_search",
        "internal_compute",
        "summarize",
    }

    @classmethod
    def evaluate_tool_call(
        cls,
        agent_role: str,
        tool_name: str,
        tool_args: Dict[str, Any],
        approved_plan_steps: Optional[List[Dict[str, Any]]] = None
    ) -> PolicyVerdict:
        tool_lower = tool_name.lower()
        
        # 1. Evaluate 3-Tier Classification
        if tool_lower in cls.TIER_1_ACTIONS:
            return PolicyVerdict(
                verdict="APPROVAL_REQUIRED",
                tier="TIER_1",
                reason=f"Tool '{tool_name}' is classified as Tier 1 (Irreversible / High-Risk external action).",
                requires_human_interrupt=True
            )
            
        elif tool_lower in cls.TIER_2_ACTIONS:
            # Check sandbox exception for file_write
            if tool_lower == "file_write":
                file_path = str(tool_args.get("path", "") or tool_args.get("file_path", ""))
                if "/scratch/" in file_path or file_path.startswith("scratch/"):
                    return PolicyVerdict(
                        verdict="ALLOWED",
                        tier="TIER_2",
                        reason="File write restricted to safe scratch directory sandbox.",
                        requires_human_interrupt=False
                    )
            return PolicyVerdict(
                verdict="APPROVAL_REQUIRED",
                tier="TIER_2",
                reason=f"Tool '{tool_name}' is Tier 2 and requires approval outside safe sandbox bounds.",
                requires_human_interrupt=True
            )
            
        elif tool_lower in cls.TIER_3_ACTIONS:
            # Check Plan Drift if plan exists
            if approved_plan_steps:
                drift_detected = cls._check_plan_drift(tool_name, tool_args, approved_plan_steps)
                if drift_detected:
                    return PolicyVerdict(
                        verdict="APPROVAL_REQUIRED",
                        tier="TIER_3",
                        reason=f"Plan Drift Detected: Tool '{tool_name}' diverges from user-approved plan steps.",
                        requires_human_interrupt=True
                    )
                    
            return PolicyVerdict(
                verdict="ALLOWED",
                tier="TIER_3",
                reason=f"Tool '{tool_name}' is Tier 3 (Read-only / Safe internal operation).",
                requires_human_interrupt=False
            )
            
        # Default fallback for unlisted tools: Treat as Tier 2 approval required
        return PolicyVerdict(
            verdict="APPROVAL_REQUIRED",
            tier="TIER_2",
            reason=f"Unrecognized tool '{tool_name}' defaults to Tier 2 approval requirement.",
            requires_human_interrupt=True
        )

    @classmethod
    def _check_plan_drift(
        cls, 
        tool_name: str, 
        tool_args: Dict[str, Any], 
        approved_plan_steps: List[Dict[str, Any]]
    ) -> bool:
        """
        Returns True if tool call is NOT matched in the approved plan step definitions.
        """
        approved_tools = [step.get("tool_name", "").lower() for step in approved_plan_steps if "tool_name" in step]
        if approved_tools and tool_name.lower() not in approved_tools:
            return True
        return False
