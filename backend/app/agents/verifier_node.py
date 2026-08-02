import logging
from typing import Dict, Any

from app.llm_client import GeminiClient
from .schemas import VerificationResult

logger = logging.getLogger("sentinel.nodes.verifier")

async def verifier_node(state: Dict[str, Any]) -> Dict[str, Any]:
    """
    LangGraph node that acts as an adversarial Risk Officer.
    Challenges the analyst's synthesis for contradictions or lack of evidence,
    returning a VerificationResult. Increments the validation attempts tracker.
    """
    correlation_id = state.get("correlation_id", "unknown-id")
    logger.info(f"[{correlation_id}] Verifier node execution started.")

    reasoning = state.get("reasoning", {})
    attempts = state.get("verification_attempts", 0)

    prompt = (
        f"You are the adversarial Risk & Verification Officer.\n"
        f"Analyze this reasoning synthesis for logical gaps, unresolved contradictions, "
        f"or unsubstantiated assertions:\n\n"
        f"Synthesis: {reasoning.get('synthesis', '')}\n"
        f"Supporting Evidence: {reasoning.get('supporting_evidence', [])}\n"
        f"Conflicts Noted: {reasoning.get('conflicts_noted', [])}\n\n"
        f"Adversarial Prompt: Does this reasoning logically support a clean investment recommendation? "
        f"Identify contradictions. Yield a VerificationResult with is_supported=True/False, "
        f"and assign a confidence_adjustment between -1.0 (major gaps) and 0.0 (no issues)."
    )

    client = GeminiClient()
    try:
        result: VerificationResult = await client.generate_structured_output(prompt, VerificationResult)
        logger.info(
            f"[{correlation_id}] Verifier node completed successfully. "
            f"is_supported={result.is_supported}, confidence_adjustment={result.confidence_adjustment}"
        )
        return {
            "verification": result.model_dump(),
            "verification_attempts": attempts + 1
        }
    except Exception as e:
        logger.error(f"[{correlation_id}] Verifier node execution failed: {e}")
        fallback = VerificationResult(
            is_supported=True,  # Fail-safe to avoid infinite loop locks
            confidence_adjustment=-0.2,
            notes=f"Verifier execution crashed: {str(e)}"
        )
        return {
            "verification": fallback.model_dump(),
            "verification_attempts": attempts + 1
        }
