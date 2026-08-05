import logging
from typing import Dict, Any

from app.llm_client import GeminiClient
from .schemas import Recommendation

from app.logging_config import get_logger

logger = get_logger("sentinel.nodes.recommendation")

async def recommendation_node(state: Dict[str, Any]) -> Dict[str, Any]:
    """
    LangGraph node that calculates baseline fanned-in confidence scores,
    applies the verifier's adjustment modifier, and calls the LLM client
    to issue a final buy/sell/hold Recommendation report. Final confidence score is clamped to the range [0.0, 1.0].

    Args:
        state (Dict[str, Any]): State graph dictionary containing agent outputs and verifier checks.

    Returns:
        Dict[str, Any]: State update dictionary writing the 'recommendation' key.
    """
    correlation_id = state.get("correlation_id", "unknown-id")
    logger.info(f"[{correlation_id}] Recommendation node execution started.")

    reasoning = state.get("reasoning", {})
    verification = state.get("verification", {})

    # Calculate baseline confidence from active fanned-in agent outputs
    plan = state.get("plan") or {}
    selected = plan.get("selected_agents", [])
    agent_outputs = state.get("agent_outputs", {})
    
    conf_scores = []
    for agent in selected:
        out = agent_outputs.get(agent)
        if out and "confidence" in out:
            try:
                conf_scores.append(float(out["confidence"]))
            except (ValueError, TypeError):
                pass

    baseline_confidence = sum(conf_scores) / len(conf_scores) if conf_scores else 0.8
    adjustment = float(verification.get("confidence_adjustment", 0.0))
    
    # Calculate final adjusted confidence (clamped between 0.0 and 1.0)
    final_confidence = max(0.0, min(1.0, baseline_confidence + adjustment))

    prompt = (
        f"Asset: {state.get('symbol', 'unknown')}\n\n"
        f"Synthesis Reasoning:\n"
        f"\"{reasoning.get('synthesis', '')}\"\n"
        f"Supporting Evidence: {reasoning.get('supporting_evidence', [])}\n"
        f"Conflicts Noted: {reasoning.get('conflicts_noted', [])}\n\n"
        f"Verification notes: {verification.get('notes', '')}\n"
        f"Suggested Confidence: {final_confidence:.2f}\n\n"
        f"Task: Based on the synthesis, supporting evidence, and verification notes, "
        f"issue a final action (buy, sell, or hold) and list key risks. "
        f"Enforce the suggested confidence score of {final_confidence:.2f}."
    )

    client = GeminiClient()
    try:
        # Note: Recommendation is a bound version of the generic RecommendationSchema.
        # To swap action options for another domain (e.g. RealEstateAction enum: buy/sell/lease),
        # a developer would define their enum class, and declare the schema model like:
        # CryptoRecommendation = RecommendationSchema[CryptoActionEnum]
        # and invoke the LLM wrapper using that model instead:
        # rec = await client.generate_structured_output(prompt, CryptoRecommendation)
        rec: Recommendation = await client.generate_structured_output(prompt, Recommendation)
        
        # Override to ensure exact confidence score computation matches our math
        rec.confidence = final_confidence

        logger.info(f"[{correlation_id}] Recommendation node completed. Action={rec.action}, Confidence={rec.confidence:.2f}")
        return {"recommendation": rec.model_dump()}
    except Exception as e:
        logger.error(f"[{correlation_id}] Recommendation node failed: {e}")
        fallback = Recommendation(
            action="hold",
            confidence=final_confidence,
            supporting_evidence=["Fallback hold due to system execution exception."],
            risks=[f"Execution failed: {str(e)}"]
        )
        return {"recommendation": fallback.model_dump()}
