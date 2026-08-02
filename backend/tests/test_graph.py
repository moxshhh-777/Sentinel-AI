import pytest
from unittest.mock import AsyncMock

from app.graph import graph
from app.registry.planning import ExecutionPlan

@pytest.mark.asyncio
async def test_full_graph_happy_path(mocker):
    # 1. Mock PlanningModule selection of all three agents
    mock_plan = ExecutionPlan(
        query="Analyze Gold for tomorrow",
        selected_agents=["market_agent", "news_agent", "risk_agent"],
        reasoning="Analyze Gold price trends, scan news events, and calculate volatility indices."
    )
    mocker.patch("app.registry.planning.PlanningModule.create_plan", new_callable=AsyncMock, return_value=mock_plan)

    # 2. Mock Agent Nodes to return happy-path responses (degraded=False)
    mock_market = {"market_summary": {"trend": "Bullish", "degraded": False, "confidence": 0.9}}
    mock_news = {"news_summary": {"headline_count": 5, "degraded": False, "confidence": 0.8}}
    mock_risk = {"risk_summary": {"risk_level": "low", "degraded": False, "volatility_score": 25.0}}

    mocker.patch("app.graph.market_agent_node", new_callable=AsyncMock, return_value=mock_market)
    mocker.patch("app.graph.news_agent_node", new_callable=AsyncMock, return_value=mock_news)
    mocker.patch("app.graph.risk_agent_node", new_callable=AsyncMock, return_value=mock_risk)

    # Compile thread config for MemorySaver checkpointing
    config = {"configurable": {"thread_id": "test-thread-happy-path"}}
    initial_state = {
        "query": "Analyze Gold for tomorrow",
        "correlation_id": "test-correlation-happy-path",
        "agent_outputs": {}
    }

    # Execute graph integration pipeline
    final_state = await graph.ainvoke(initial_state, config=config)

    # Assert fanned-in outputs are properly combined under unique agent keys
    assert "agent_outputs" in final_state
    outputs = final_state["agent_outputs"]
    assert "market_agent" in outputs
    assert "news_agent" in outputs
    assert "risk_agent" in outputs

    assert outputs["market_agent"]["trend"] == "Bullish"
    assert outputs["news_agent"]["headline_count"] == 5
    assert outputs["risk_agent"]["risk_level"] == "low"

    # Happy path should complete stubs and return success report
    assert "report" in final_state
    assert final_state["report"]["status"] == "success"
    assert final_state["report"]["message"] == "Phase 6 stub completed"


@pytest.mark.asyncio
async def test_full_graph_all_degraded_fallback(mocker):
    # 1. Mock PlanningModule selection of all three agents
    mock_plan = ExecutionPlan(
        query="Analyze Gold for tomorrow",
        selected_agents=["market_agent", "news_agent", "risk_agent"],
        reasoning="Analyze Gold using fallback modes."
    )
    mocker.patch("app.registry.planning.PlanningModule.create_plan", new_callable=AsyncMock, return_value=mock_plan)

    # 2. Mock Agent Nodes to return degraded fallbacks (degraded=True)
    mock_market = {"market_summary": {"trend": "Unknown", "degraded": True, "confidence": 0.1}}
    mock_news = {"news_summary": {"headline_count": 0, "degraded": True, "confidence": 0.1}}
    mock_risk = {"risk_summary": {"risk_level": "medium", "degraded": True, "volatility_score": 50.0}}

    mocker.patch("app.graph.market_agent_node", new_callable=AsyncMock, return_value=mock_market)
    mocker.patch("app.graph.news_agent_node", new_callable=AsyncMock, return_value=mock_news)
    mocker.patch("app.graph.risk_agent_node", new_callable=AsyncMock, return_value=mock_risk)

    config = {"configurable": {"thread_id": "test-thread-degraded-fallback"}}
    initial_state = {
        "query": "Analyze Gold for tomorrow",
        "correlation_id": "test-correlation-degraded-fallback",
        "agent_outputs": {}
    }

    final_state = await graph.ainvoke(initial_state, config=config)

    # Assert outputs are gathered but system identifies total degradation
    assert "agent_outputs" in final_state
    outputs = final_state["agent_outputs"]
    assert "market_agent" in outputs
    assert "news_agent" in outputs
    assert "risk_agent" in outputs

    assert outputs["market_agent"]["degraded"] is True
    assert outputs["news_agent"]["degraded"] is True
    assert outputs["risk_agent"]["degraded"] is True

    # Degradation check should route execution to failure_node
    assert "report" in final_state
    assert final_state["report"]["status"] == "failed"
    assert "insufficient data" in final_state["report"]["message"].lower()
