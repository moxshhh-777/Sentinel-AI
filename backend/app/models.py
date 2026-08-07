from datetime import datetime
from typing import Optional, List, Any
from sqlalchemy import String, ForeignKey, DateTime, Integer, Float, Text
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column, relationship
from sqlalchemy.sql import func
from pgvector.sqlalchemy import Vector

from .db import Base

class Conversation(Base):
    __tablename__ = "conversations"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    user_id: Mapped[str] = mapped_column(String(255), nullable=False, index=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )

    # Relationships
    messages: Mapped[List["Message"]] = relationship(
        "Message", back_populates="conversation", cascade="all, delete-orphan"
    )
    analysis_runs: Mapped[List["AnalysisRun"]] = relationship(
        "AnalysisRun", back_populates="conversation", cascade="all, delete-orphan"
    )


class Message(Base):
    __tablename__ = "messages"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    conversation_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("conversations.id", ondelete="CASCADE"), nullable=False, index=True
    )
    role: Mapped[str] = mapped_column(String(50), nullable=False)  # system, user, assistant
    content: Mapped[str] = mapped_column(Text, nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )

    # Relationships
    conversation: Mapped["Conversation"] = relationship("Conversation", back_populates="messages")


class AnalysisRun(Base):
    __tablename__ = "analysis_runs"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    conversation_id: Mapped[Optional[int]] = mapped_column(
        Integer, ForeignKey("conversations.id", ondelete="CASCADE"), nullable=True, index=True
    )
    query: Mapped[str] = mapped_column(Text, nullable=False)
    plan_json: Mapped[Optional[dict[str, Any]]] = mapped_column(JSONB, nullable=True)
    status: Mapped[str] = mapped_column(String(50), default="pending", nullable=False)  # pending, running, completed, failed
    started_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    completed_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    correlation_id: Mapped[Optional[str]] = mapped_column(String(255), nullable=True, index=True)
    
    # pgvector embedding column mapping 1536-dimensional vectors (compatible with models like text-embedding-ada-002)
    embedding: Mapped[Optional[List[float]]] = mapped_column(Vector(1536), nullable=True)

    # Relationships
    conversation: Mapped[Optional["Conversation"]] = relationship("Conversation", back_populates="analysis_runs")
    agent_outputs: Mapped[List["AgentOutput"]] = relationship(
        "AgentOutput", back_populates="analysis_run", cascade="all, delete-orphan"
    )
    recommendations: Mapped[List["Recommendation"]] = relationship(
        "Recommendation", back_populates="analysis_run", cascade="all, delete-orphan"
    )


class AgentOutput(Base):
    __tablename__ = "agent_outputs"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    run_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("analysis_runs.id", ondelete="CASCADE"), nullable=False, index=True
    )
    agent_name: Mapped[str] = mapped_column(String(100), nullable=False)
    summary_json: Mapped[dict[str, Any]] = mapped_column(JSONB, nullable=False)
    raw_ref: Mapped[Optional[str]] = mapped_column(String(1024), nullable=True)  # URL or ID to raw logs/results
    latency_ms: Mapped[int] = mapped_column(Integer, nullable=False)
    status: Mapped[str] = mapped_column(String(50), nullable=False)  # success, failed
    error: Mapped[Optional[str]] = mapped_column(Text, nullable=True)

    # Relationships
    analysis_run: Mapped["AnalysisRun"] = relationship("AnalysisRun", back_populates="agent_outputs")


class Recommendation(Base):
    __tablename__ = "recommendations"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    run_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("analysis_runs.id", ondelete="CASCADE"), nullable=False, index=True
    )
    action: Mapped[str] = mapped_column(String(50), nullable=False)  # BUY, SELL, HOLD, NEUTRAL
    confidence: Mapped[float] = mapped_column(Float, nullable=False)
    reasoning_summary: Mapped[str] = mapped_column(Text, nullable=False)
    risks_json: Mapped[dict[str, Any]] = mapped_column(JSONB, nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )

    # Relationships
    analysis_run: Mapped["AnalysisRun"] = relationship("AnalysisRun", back_populates="recommendations")
