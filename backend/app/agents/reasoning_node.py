import logging
from typing import Dict, Any

from app.llm_client import GeminiClient
from .schemas import ReasoningOutput

logger = logging.getLogger("sentinel.nodes.reasoning")

async def reasoning_node(state: Dict[str, Any]) -> Dict[str, Any]:
    """
    LangGraph node that gathers compiled agent summaries, prompts the LLM to
    synthesize signals, identify evidence, and catalog conflicts in a ReasoningOutput.
    """
    correlation_id = state.get("correlation_id", "unknown-id")
    logger.info(f"[{correlation_id}] Reasoning node execution started.")

    agent_outputs = state.get("agent_outputs", {})

    # Extract clean agent summaries (no raw API data)
    summaries_str = ""
    for name, summary in agent_outputs.items():
        if summary:
            summaries_str += f"\n- Agent: {name}\n  Data: {summary}\n"

    prompt = (
        f"Asset: {state.get('symbol', 'unknown')}\n\n"
        f"Research Summaries Gathered:\n"
        f"{summaries_str}\n"
        f"Task: Perform a critical synthesis of these findings. "
        f"Note any discrepancies or conflicts between the reports (e.g. bullish price vs panic news), "
        f"and compile specific supporting evidence for an recommendation."
    )

    client = GeminiClient()
    try:
        output: ReasoningOutput = await client.generate_structured_output(prompt, ReasoningOutput)
        logger.info(f"[{correlation_id}] Reasoning node execution completed successfully.")
        return {"reasoning": output.model_dump()}
    except Exception as e:
        logger.error(f"[{correlation_id}] Reasoning node execution failed: {e}")
        fallback = ReasoningOutput(
            synthesis=f"Reasoning failed: {str(e)}",
            supporting_evidence=[],
            conflicts_noted=["System error during reasoning compilation."]
        )
        return {"reasoning": fallback.model_dump()}
