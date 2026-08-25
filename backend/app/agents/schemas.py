from typing import List, Generic, TypeVar, Literal
from pydantic import BaseModel, Field

class MarketSummary(BaseModel):
    trend: str = Field(..., description="Overall price trend direction (e.g. Bullish, Bearish, Sideways)")
    volatility_note: str = Field(..., description="Brief commentary on recent price volatility")
    key_levels: List[float] = Field(..., description="Support and resistance levels identified from historical price data")
    degraded: bool = Field(default=False, description="Flag indicating if the summary was compiled using degraded fallback state due to tool timeouts or errors")
    confidence: float = Field(..., description="Confidence score of the analysis (0.0 to 1.0)")

class NewsSummary(BaseModel):
    headline_count: int = Field(..., description="Number of headlines scanned")
    key_events: List[str] = Field(..., description="Up to 5 key events or news points extracted from headlines")
    overall_tone: str = Field(..., description="Overall emotional sentiment or tone of news (e.g., Optimistic, Panic, Neutral) determined from scanned headlines")
    degraded: bool = Field(default=False, description="Flag indicating if the summary was compiled using degraded fallback state")
    confidence: float = Field(..., description="Confidence score of the analysis (0.0 to 1.0)")

class RiskSummary(BaseModel):
    risk_level: str = Field(..., description="Overall assessment level (low, medium, high)")
    volatility_score: float = Field(..., description="Standard deviation/volatility score based on market metrics")
    confidence_penalty: float = Field(..., description="Penalty applied to confidence if tool fallbacks are active")
    degraded: bool = Field(default=False, description="Flag indicating if the risk evaluation was compiled using degraded fallback state")

class ReasoningOutput(BaseModel):
    synthesis: str = Field(..., description="Synthesis of all gathered agent node inputs")
    supporting_evidence: List[str] = Field(..., description="Specific pieces of supporting evidence extracted from input nodes")
    conflicts_noted: List[str] = Field(..., description="Unresolved contradictions or conflicting signals found across nodes")

class VerificationResult(BaseModel):
    is_supported: bool = Field(..., description="Whether the reasoning actually supports a confident recommendation")
    confidence_adjustment: float = Field(..., description="Confidence modifier from -1.0 to 0.0 based on discrepancies found")
    notes: str = Field(..., description="Detailed notes explaining contradictions or verification checks")

# Define TypeVar for Generic Action enum or literal
ActionT = TypeVar("ActionT")

class RecommendationSchema(BaseModel, Generic[ActionT]):
    """
    Generic recommendation schema.
    A future domain (e.g. real estate, crypto-tokens) can plug in its own action enum
    by subclassing or binding this model:
    
    class CryptoAction(str, Enum):
        BUY = "buy"
        SELL = "sell"
        HOLD = "hold"
        STAKE = "stake"
        
    CryptoRecommendation = RecommendationSchema[CryptoAction]
    """
    action: ActionT = Field(..., description="Action recommendation (e.g. buy, sell, hold)")
    confidence: float = Field(..., description="Confidence level of the recommendation (0.0 to 1.0)")
    supporting_evidence: List[str] = Field(..., description="Evidence supporting the action decision")
    risks: List[str] = Field(..., description="Risks identified that could impact the recommendation")

# Bound version for Phase 6
Recommendation = RecommendationSchema[Literal["buy", "sell", "hold"]]


# verified workable: 2026-08-25
