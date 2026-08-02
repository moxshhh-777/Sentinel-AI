from typing import List
from pydantic import BaseModel, Field

class MarketSummary(BaseModel):
    trend: str = Field(..., description="Overall price trend direction (e.g. Bullish, Bearish, Sideways)")
    volatility_note: str = Field(..., description="Brief commentary on recent price volatility")
    key_levels: List[float] = Field(..., description="Support and resistance levels identified from historical price data")
    degraded: bool = Field(default=False, description="Flag indicating if the summary was compiled using degraded fallback state")
    confidence: float = Field(..., description="Confidence score of the analysis (0.0 to 1.0)")

class NewsSummary(BaseModel):
    headline_count: int = Field(..., description="Number of headlines scanned")
    key_events: List[str] = Field(..., description="Up to 5 key events or news points extracted from headlines")
    overall_tone: str = Field(..., description="Overall emotional sentiment or tone of news (e.g., Optimistic, Panic, Neutral)")
    degraded: bool = Field(default=False, description="Flag indicating if the summary was compiled using degraded fallback state")
    confidence: float = Field(..., description="Confidence score of the analysis (0.0 to 1.0)")

class RiskSummary(BaseModel):
    risk_level: str = Field(..., description="Overall assessment level (low, medium, high)")
    volatility_score: float = Field(..., description="Standard deviation/volatility score based on market metrics")
    confidence_penalty: float = Field(..., description="Penalty applied to confidence if tool fallbacks are active")
    degraded: bool = Field(default=False, description="Flag indicating if the risk evaluation was compiled using degraded fallback state")
