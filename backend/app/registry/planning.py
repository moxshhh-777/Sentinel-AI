from typing import List
from pydantic import BaseModel, Field

from app.llm_client import GeminiClient
from app.registry.agent_registry import AGENT_REGISTRY

class ExecutionPlan(BaseModel):
    query: str = Field(..., description="The original user query/request")
    selected_agents: List[str] = Field(..., description="List of agent names selected to run (must be subset of registered agents)")
    reasoning: str = Field(..., description="Detailed explanation of why these agents were selected")


class PlanningModule:
    def __init__(self):
        self.llm_client = GeminiClient()

    async def create_plan(self, user_query: str) -> ExecutionPlan:
        """
        Formulates a selection prompt based on available agents in AGENT_REGISTRY,
        invokes the LLM to generate a structured execution plan, and returns it.

        Args:
            user_query (str): The raw trading analytics request query.

        Returns:
            ExecutionPlan: Structured schema containing the selected agents list and rationale.
        """
        # Formulate available agents string for the prompt
        agents_info = ""
        for name, meta in AGENT_REGISTRY.items():
            capabilities = ", ".join(meta["capabilities"])
            agents_info += (
                f"- Agent Name: {name}\n"
                f"  Description: {meta['description']}\n"
                f"  Capabilities: {capabilities}\n\n"
            )

        prompt = (
            f"You are the orchestrator for Sentinel AI. Your job is to select the "
            f"appropriate agents from the list of available agents to satisfy the user query.\n\n"
            f"Available Agents:\n"
            f"{agents_info}"
            f"User Query:\n"
            f"\"{user_query}\"\n\n"
            f"Task: Select which agents from the registry are needed to answer or analyze this query. "
            f"Provide the selection and reasoning in the required structured ExecutionPlan format."
        )

        # Call LLM client to get structured ExecutionPlan output
        plan: ExecutionPlan = await self.llm_client.generate_structured_output(prompt, ExecutionPlan)
        return plan
