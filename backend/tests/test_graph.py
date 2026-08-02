import pytest
from unittest.mock import AsyncMock

from app.graph import graph
from app.registry.planning import ExecutionPlan
from app.agents.schemas import ReasoningOutput, VerificationResult, Recommendation

@pytest.mark.asyncio
async def test_full_graph_happy_path(mocker):
    # 1. Mock PlanningModule selection of all three agents
    mock_plan = ExecutionPlan(
        query="Analyze AAPL for tomorrow",
        selected_agents=["market_agent", "news_agent", "risk_agent"],
        reasoning="Analyze AAPL."
    )
    mocker.patch("app.registry.planning.PlanningModule.create_plan", new_callable=AsyncMock, return_value=mock_plan)

    # 2. Mock Agent Nodes (to prevent tool calls and return mock summaries directly)
    mocker.patch("app.graph.market_agent_node", new_callable=AsyncMock, return_value={"market_summary": {"trend": "Bullish", "confidence": 0.9, "degraded": False}})
    mocker.patch("app.graph.news_agent_node", new_callable=AsyncMock, return_value={"news_summary": {"overall_tone": "Neutral", "confidence": 0.8, "degraded": False}})
    mocker.patch("app.graph.risk_agent_node", new_callable=AsyncMock, return_value={"risk_summary": {"risk_level": "low", "degraded": False}})

    # 3. Mock GeminiClient generate_structured_output calls:
    # 1) reasoning_node (first call)
    # 2) verifier_node (first call, returns is_supported=True)
    # 3) recommendation_node (first call)
    mock_reasoning = ReasoningOutput(synthesis="AAPL looks strong", supporting_evidence=["Bullish price"], conflicts_noted=[])
    mock_verifier = VerificationResult(is_supported=True, confidence_adjustment=-0.05, notes="Looks consistent")
    mock_recommend = Recommendation(action="buy", confidence=0.8, supporting_evidence=["AAPL looks strong"], risks=[])

    mocker.patch(
        "app.llm_client.GeminiClient.generate_structured_output",
        new_callable=AsyncMock,
        side_effect=[mock_reasoning, mock_verifier, mock_recommend]
    )

    config = {"configurable": {"thread_id": "thread-happy-path"}}
    initial_state = {"query": "Analyze AAPL for tomorrow", "correlation_id": "corr-happy", "agent_outputs": {}}
    
    final_state = await graph.ainvoke(initial_state, config=config)

    assert "agent_outputs" in final_state
    assert "reasoning" in final_state
    assert "verification" in final_state
    assert "recommendation" in final_state
    
    assert final_state["verification_attempts"] == 1
    assert final_state["verification"]["is_supported"] is True
    
    # Baseline confidence: (0.9 + 0.8) / 2 = 0.85
    # Verification adjustment: -0.05
    # Expected confidence: 0.85 - 0.05 = 0.80
    assert pytest.approx(final_state["recommendation"]["confidence"], 0.01) == 0.80
    assert final_state["recommendation"]["action"] == "buy"


@pytest.mark.asyncio
async def test_full_graph_verifier_retry_loop(mocker):
    # 1. Mock PlanningModule selection of two agents
    mock_plan = ExecutionPlan(
        query="Analyze AAPL for tomorrow",
        selected_agents=["market_agent", "news_agent"],
        reasoning="Analyze AAPL."
    )
    mocker.patch("app.registry.planning.PlanningModule.create_plan", new_callable=AsyncMock, return_value=mock_plan)

    # 2. Mock Agent Nodes
    mocker.patch("app.graph.market_agent_node", new_callable=AsyncMock, return_value={"market_summary": {"trend": "Bearish", "confidence": 0.85, "degraded": False}})
    mocker.patch("app.graph.news_agent_node", new_callable=AsyncMock, return_value={"news_summary": {"overall_tone": "Panic", "confidence": 0.75, "degraded": False}})

    # 3. Mock GeminiClient calls in loop sequence:
    # 1) reasoning_node (first call)
    # 2) verifier_node (first call, fails verification)
    # 3) reasoning_node (retry call)
    # 4) verifier_node (retry call, passes verification)
    # 5) recommendation_node (final call)
    mock_reasoning_1 = ReasoningOutput(synthesis="AAPL is bullish despite panic", supporting_evidence=["Bullish price"], conflicts_noted=["Panic news"])
    mock_verifier_1 = VerificationResult(is_supported=False, confidence_adjustment=-0.3, notes="Contradiction between price and panic news is unresolved.")
    
    mock_reasoning_2 = ReasoningOutput(synthesis="AAPL is bearish due to panic alignment", supporting_evidence=["Panic news"], conflicts_noted=[])
    mock_verifier_2 = VerificationResult(is_supported=True, confidence_adjustment=-0.1, notes="Consistent bearish indicators.")
    
    mock_recommend = Recommendation(action="sell", confidence=0.7, supporting_evidence=["Bearish trend"], risks=[])

    mocker.patch(
        "app.llm_client.GeminiClient.generate_structured_output",
        new_callable=AsyncMock,
        side_effect=[mock_reasoning_1, mock_verifier_1, mock_reasoning_2, mock_verifier_2, mock_recommend]
    )

    config = {"configurable": {"thread_id": "thread-retry-loop"}}
    initial_state = {"query": "Analyze AAPL for tomorrow", "correlation_id": "corr-retry", "agent_outputs": {}}
    
    final_state = await graph.ainvoke(initial_state, config=config)

    # Assert retry attempts resolved to 2
    assert final_state["verification_attempts"] == 2
    assert final_state["verification"]["is_supported"] is True
    assert final_state["verification"]["confidence_adjustment"] == -0.1
    
    # Baseline: (0.85 + 0.75) / 2 = 0.80
    # Final confidence adjustment: -0.10
    # Expected: 0.80 - 0.10 = 0.70
    assert pytest.approx(final_state["recommendation"]["confidence"], 0.01) == 0.70
    assert final_state["recommendation"]["action"] == "sell"


@pytest.mark.asyncio
async def test_full_graph_all_degraded_fallback(mocker):
    # Mock PlanningModule
    mock_plan = ExecutionPlan(
        query="Analyze Gold for tomorrow",
        selected_agents=["market_agent", "news_agent"],
        reasoning="Analyze Gold using fallback modes."
    )
    mocker.patch("app.registry.planning.PlanningModule.create_plan", new_callable=AsyncMock, return_value=mock_plan)

    # Mock Agent Nodes to return degraded fallbacks (degraded=True)
    mock_market = {"market_summary": {"trend": "Unknown", "degraded": True, "confidence": 0.1}}
    mock_news = {"news_summary": {"headline_count": 0, "degraded": True, "confidence": 0.1}}
    mocker.patch("app.graph.market_agent_node", new_callable=AsyncMock, return_value=mock_market)
    mocker.patch("app.graph.news_agent_node", new_callable=AsyncMock, return_value=mock_news)

    config = {"configurable": {"thread_id": "test-thread-degraded-fallback"}}
    initial_state = {
        "query": "Analyze Gold for tomorrow",
        "correlation_id": "test-correlation-degraded-fallback",
        "agent_outputs": {}
    }

    final_state = await graph.ainvoke(initial_state, config=config)

    assert "agent_outputs" in final_state
    assert final_state["report"]["status"] == "failed"
    assert "insufficient data" in final_state["report"]["message"].lower()
