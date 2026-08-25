from datetime import datetime
from typing import Optional, Any
from pydantic import BaseModel, Field, ConfigDict

# Base schema config for ORM compatibility in Pydantic v2
class BaseSchema(BaseModel):
    model_config = ConfigDict(from_attributes=True)


# Conversation Schemas
class MessageBase(BaseSchema):
    role: str = Field(..., description="Role of the message author (e.g. system, user, assistant)")
    content: str = Field(..., description="Content of the message")

class MessageCreate(MessageBase):
    pass

class MessageResponse(MessageBase):
    id: int
    conversation_id: int
    created_at: datetime


# Conversation Response
class ConversationBase(BaseSchema):
    user_id: str

class ConversationCreate(ConversationBase):
    pass

class ConversationResponse(ConversationBase):
    id: int
    created_at: datetime
    messages: list[MessageResponse] = []


# Agent Output Schemas
class AgentOutputBase(BaseSchema):
    agent_name: str
    summary_json: dict[str, Any]
    raw_ref: Optional[str] = None
    latency_ms: int
    status: str
    error: Optional[str] = None

class AgentOutputResponse(AgentOutputBase):
    id: int
    run_id: int


# Recommendation Schemas
class RecommendationBase(BaseSchema):
    action: str
    confidence: float
    reasoning_summary: str
    risks_json: dict[str, Any]

class RecommendationResponse(RecommendationBase):
    id: int
    run_id: int
    created_at: datetime


# Analysis Run Schemas
class AnalysisRunBase(BaseSchema):
    query: str
    correlation_id: Optional[str] = None

class AnalysisRunCreate(AnalysisRunBase):
    conversation_id: Optional[int] = None

class AnalysisRunResponse(AnalysisRunBase):
    id: int
    conversation_id: Optional[int]
    plan_json: Optional[dict[str, Any]] = None
    status: str
    started_at: datetime
    completed_at: Optional[datetime] = None
    embedding: Optional[list[float]] = None
    agent_outputs: list[AgentOutputResponse] = []
    recommendations: list[RecommendationResponse] = []

# verified workable: 2026-08-25
