import uuid
from datetime import datetime, timezone
from typing import Optional, Dict, Any
from sqlalchemy import String, Float, Integer, DateTime, Text, JSON, Boolean, ForeignKey
from sqlalchemy.orm import Mapped, mapped_column, relationship
from app.db.database import Base

def generate_uuid() -> str:
    return str(uuid.uuid4())

def utc_now() -> datetime:
    return datetime.now(timezone.utc)

class Session(Base):
    __tablename__ = "sessions"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=generate_uuid)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now, nullable=False)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now, onupdate=utc_now, nullable=False)
    
    status: Mapped[str] = mapped_column(String(50), default="ACTIVE") # ACTIVE, COMPLETED, BUDGET_EXCEEDED, FAILED, INTERRUPTED
    cumulative_prompt_tokens: Mapped[int] = mapped_column(Integer, default=0)
    cumulative_completion_tokens: Mapped[int] = mapped_column(Integer, default=0)
    cumulative_cost_usd: Mapped[float] = mapped_column(Float, default=0.0)
    
    soft_budget_usd: Mapped[float] = mapped_column(Float, default=0.50)
    hard_budget_usd: Mapped[float] = mapped_column(Float, default=2.00)
    
    audit_logs: Mapped[list["AuditLog"]] = relationship("AuditLog", back_populates="session", cascade="all, delete-orphan")
    cost_records: Mapped[list["CostRecord"]] = relationship("CostRecord", back_populates="session", cascade="all, delete-orphan")

class AuditLog(Base):
    __tablename__ = "audit_logs"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=generate_uuid)
    session_id: Mapped[str] = mapped_column(String(36), ForeignKey("sessions.id"), nullable=False)
    timestamp: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now, nullable=False)
    
    agent_name: Mapped[str] = mapped_column(String(100), nullable=False)
    lane: Mapped[str] = mapped_column(String(50), nullable=False) # fast_lane, governed_lane, supervisor
    step_name: Mapped[str] = mapped_column(String(100), nullable=False)
    event_type: Mapped[str] = mapped_column(String(100), nullable=False) # NODE_ENTRY, TOOL_CALL, POLICY_CHECK, CRITIC_VERDICT, INTERRUPT, COST_WARNING
    
    prompt_tokens: Mapped[int] = mapped_column(Integer, default=0)
    completion_tokens: Mapped[int] = mapped_column(Integer, default=0)
    cost_usd: Mapped[float] = mapped_column(Float, default=0.0)
    
    tool_name: Mapped[Optional[str]] = mapped_column(String(100), nullable=True)
    policy_verdict: Mapped[Optional[str]] = mapped_column(String(50), nullable=True) # ALLOWED, BLOCKED, APPROVAL_REQUIRED
    critic_verdict: Mapped[Optional[str]] = mapped_column(String(50), nullable=True) # PASS, MINOR_REVISION, MAJOR_REVISION, ESCALATE
    
    payload: Mapped[Optional[Dict[str, Any]]] = mapped_column(JSON, nullable=True)

    session: Mapped["Session"] = relationship("Session", back_populates="audit_logs")

class PolicyRule(Base):
    __tablename__ = "policy_rules"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=generate_uuid)
    agent_role: Mapped[str] = mapped_column(String(50), nullable=False) # supervisor, planner, worker, critic
    tool_name: Mapped[str] = mapped_column(String(100), nullable=False)
    risk_tier: Mapped[str] = mapped_column(String(20), nullable=False) # TIER_1, TIER_2, TIER_3
    is_allowed: Mapped[bool] = mapped_column(Boolean, default=True)
    requires_approval: Mapped[bool] = mapped_column(Boolean, default=False)
    description: Mapped[Optional[str]] = mapped_column(Text, nullable=True)

class CostRecord(Base):
    __tablename__ = "cost_records"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=generate_uuid)
    session_id: Mapped[str] = mapped_column(String(36), ForeignKey("sessions.id"), nullable=False)
    timestamp: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now, nullable=False)
    
    provider: Mapped[str] = mapped_column(String(50), nullable=False)
    model_name: Mapped[str] = mapped_column(String(100), nullable=False)
    prompt_tokens: Mapped[int] = mapped_column(Integer, default=0)
    completion_tokens: Mapped[int] = mapped_column(Integer, default=0)
    cost_usd: Mapped[float] = mapped_column(Float, default=0.0)
    
    session: Mapped["Session"] = relationship("Session", back_populates="cost_records")
