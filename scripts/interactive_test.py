#!/usr/bin/env python3
"""
Havenkeep Free Interactive Test Harness
Allows zero-cost testing of Supervisor Risk Routing, Policy Engine checks, 
Audit Logging, and Budget Tracker without requiring paid API keys.
"""

import sys
import os
import asyncio
from pathlib import Path

# Add backend directory to sys.path
backend_path = Path(__file__).resolve().parent.parent / "backend"
sys.path.insert(0, str(backend_path))

from app.graph.nodes.supervisor import SupervisorNode
from app.governance.policy_engine import PolicyEngine
from app.governance.cost_tracker import CostTracker
from app.governance.audit_logger import AuditLogger
from app.graph.state import HavenkeepState

SAMPLE_PROMPTS = [
    "1. [Fast-Lane] Summarize the key differences between REST and GraphQL APIs.",
    "2. [Fast-Lane] Write a Python function to calculate the Fibonacci sequence.",
    "3. [Governed-Lane] Delete all outdated user accounts from the production database.",
    "4. [Governed-Lane] Deploy the latest backend release container to production.",
    "5. [Governed-Lane] Send an email alert to all system administrators.",
    "6. [Governed-Lane] Run an arbitrary shell command to clean up disk space."
]

async def run_interactive_test(prompt: str, session_cost: float = 0.0):
    print("\n" + "="*70)
    print(f"📥 TASK PROMPT: \"{prompt}\"")
    print("="*70)

    # 1. Prepare Initial Graph State
    state: HavenkeepState = {
        "messages": [],
        "session_id": "interactive-free-session-001",
        "task_prompt": prompt,
        "task_type": "UNKNOWN",
        "risk_score": 0.0,
        "lane": "fast_lane",
        "confidence": 0.0,
        "risk_factors": {},
        "plan_steps": [],
        "current_step_index": 0,
        "approved_plan": None,
        "critic_verdict": None,
        "critic_feedback": None,
        "revision_count": 0,
        "pending_tool_call": None,
        "approval_required": False,
        "approval_reason": None,
        "is_budget_exceeded": False,
        "cumulative_prompt_tokens": 0,
        "cumulative_completion_tokens": 0,
        "cumulative_cost_usd": session_cost,
        "soft_budget_usd": 0.50,
        "hard_budget_usd": 2.00,
        "final_output": None
    }

    # 2. Run Supervisor Node (Risk Classifier)
    print("\n🔍 STEP 1: SUPERVISOR ROUTER EVALUATION")
    result = await SupervisorNode.run(state)
    
    print(f"  • Task Type:   {result['task_type']}")
    print(f"  • Risk Score:  {result['risk_score']:.2f} / 1.00")
    print(f"  • Selected Lane: {result['lane'].upper()}")
    print(f"  • Confidence:  {result['confidence']:.2f}")

    # 3. Policy Engine Evaluation Simulation
    print("\n🛡️ STEP 2: SHIFT-LEFT POLICY ENGINE EVALUATION")
    sample_tools = {
        "fast_lane": ("file_read", {"path": "docs/readme.txt"}),
        "governed_lane": ("database_write", {"query": "DELETE FROM users WHERE 1=1;"})
    }
    tool_name, tool_args = sample_tools[result['lane']]
    verdict = PolicyEngine.evaluate_tool_call(
        agent_role="worker" if result['lane'] == "fast_lane" else "executor",
        tool_name=tool_name,
        tool_args=tool_args
    )
    
    print(f"  • Simulated Tool:   {tool_name}")
    print(f"  • Action Tier:      {verdict.tier}")
    print(f"  • Policy Verdict:   {verdict.verdict}")
    print(f"  • Human Interrupt:  {'YES (Paused for User Approval)' if verdict.requires_human_interrupt else 'NO (Auto-Approved)'}")
    print(f"  • Policy Reason:    {verdict.reason}")

    # 4. Cost Tracker & Budget Cap Summary
    print("\n💰 STEP 3: COST TRACKER & BUDGET SUMMARY")
    print(f"  • Task Cost:       ${result['cumulative_cost_usd'] - session_cost:.6f}")
    print(f"  • Session Total:   ${result['cumulative_cost_usd']:.6f} / ${state['hard_budget_usd']:.2f}")
    print(f"  • Budget Status:   {'⚠️ SOFT WARNING REACHED' if result['cumulative_cost_usd'] >= 0.50 else '✅ WITHIN BUDGET'}")
    
    print("="*70 + "\n")
    return result['cumulative_cost_usd']

async def main():
    print("""
 🛡️ HAVENKEEP FREE INTERACTIVE TEST HARNESS 🛡️
 Testing dynamic risk scoring, policy allowlists, and cost tracking (100% Free / Zero API cost).
""")
    
    session_cost = 0.0
    while True:
        print("Sample Tasks to Try:")
        for sample in SAMPLE_PROMPTS:
            print(f"  {sample}")
        print("\nType a prompt number (1-6), enter your own custom task prompt, or type 'exit' to quit:")
        
        try:
            choice = input("\n👉 Input: ").strip()
        except (EOFError, KeyboardInterrupt):
            break

        if choice.lower() in ("exit", "quit", "q"):
            print("Exiting test harness.")
            break
            
        if not choice:
            continue
            
        if choice in ("1", "2", "3", "4", "5", "6"):
            index = int(choice) - 1
            prompt = SAMPLE_PROMPTS[index].split("] ", 1)[1]
        else:
            prompt = choice

        session_cost = await run_interactive_test(prompt, session_cost)

if __name__ == "__main__":
    asyncio.run(main())
