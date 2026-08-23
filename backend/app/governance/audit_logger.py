import json
import logging
from datetime import datetime, timezone
from typing import Optional, Dict, Any
from sqlalchemy.ext.asyncio import AsyncSession
from app.db.models import AuditLog

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(name)s: %(message)s")
logger = logging.getLogger("havenkeep.audit")

class AuditLogger:
    """
    Durable Audit Logger recording state transitions, tool invocations,
    policy checks, critic verdicts, and cost events across both Fast-Lane and Governed-Lane.
    """

    @classmethod
    async def log_event(
        cls,
        session_id: str,
        agent_name: str,
        lane: str,
        step_name: str,
        event_type: str,
        db: Optional[AsyncSession] = None,
        prompt_tokens: int = 0,
        completion_tokens: int = 0,
        cost_usd: float = 0.0,
        tool_name: Optional[str] = None,
        policy_verdict: Optional[str] = None,
        critic_verdict: Optional[str] = None,
        payload: Optional[Dict[str, Any]] = None
    ) -> AuditLog:
        audit_entry = AuditLog(
            session_id=session_id,
            timestamp=datetime.now(timezone.utc).replace(tzinfo=None),
            agent_name=agent_name,
            lane=lane,
            step_name=step_name,
            event_type=event_type,
            prompt_tokens=prompt_tokens,
            completion_tokens=completion_tokens,
            cost_usd=cost_usd,
            tool_name=tool_name,
            policy_verdict=policy_verdict,
            critic_verdict=critic_verdict,
            payload=payload
        )

        
        # Console JSON log output for real-time log monitoring
        console_payload = {
            "session_id": session_id,
            "agent": agent_name,
            "lane": lane,
            "step": step_name,
            "event": event_type,
            "cost_usd": cost_usd,
            "policy": policy_verdict,
            "critic": critic_verdict,
        }
        logger.info(f"AUDIT_EVENT: {json.dumps(console_payload)}")
        
        # Write to Database if db session provided
        if db:
            db.add(audit_entry)
            await db.flush()
            
        return audit_entry
