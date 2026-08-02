import pytest
from unittest.mock import AsyncMock

from app.registry.planning import PlanningModule, ExecutionPlan

@pytest.mark.asyncio
async def test_create_plan_selects_all_agents(mocker):
    planning_module = PlanningModule()
    
    # Set up the expected plan mock output
    mock_plan = ExecutionPlan(
        query="Analyze Gold for tomorrow",
        selected_agents=["market_agent", "news_agent", "risk_agent"],
        reasoning="Analyze gold price trends (market_agent), scan related gold headlines (news_agent), and compute risk metric volatility profiles (risk_agent)."
    )
    
    # Mock the LLM client call
    mock_llm = mocker.patch(
        "app.llm_client.GeminiClient.generate_structured_output",
        new_callable=AsyncMock,
        return_value=mock_plan
    )
    
    plan = await planning_module.create_plan("Analyze Gold for tomorrow")
    
    assert plan.query == "Analyze Gold for tomorrow"
    assert "market_agent" in plan.selected_agents
    assert "news_agent" in plan.selected_agents
    assert "risk_agent" in plan.selected_agents
    assert len(plan.selected_agents) == 3
    
    # Verify the prompt includes the agent names and capabilities descriptions
    mock_llm.assert_called_once()
    prompt_sent = mock_llm.call_args[0][0]
    assert "Analyze Gold for tomorrow" in prompt_sent
    assert "market_agent" in prompt_sent
    assert "news_agent" in prompt_sent
    assert "risk_agent" in prompt_sent
