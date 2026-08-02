import pytest
from unittest.mock import AsyncMock
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from datetime import datetime, timezone
import os

from main import app
from app.db import get_db
from app.models import AnalysisRun, AgentOutput, Recommendation as DBRecommendation
from app.registry.planning import ExecutionPlan
from app.agents.schemas import ReasoningOutput, VerificationResult, Recommendation

# Setup connection pool override for transactional rollback testing
DATABASE_URL = os.getenv("DATABASE_URL", "postgresql://sentinel_user:sentinel_pass@localhost:5432/sentinel_db")
engine = create_engine(DATABASE_URL)
TestingSessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

@pytest.fixture
def db_session():
    """
    Fixture that creates a transaction block on the PostgreSQL database
    and rolls back the transaction at the end of the test.
    """
    connection = engine.connect()
    transaction = connection.begin()
    session = TestingSessionLocal(bind=connection)
    
    yield session
    
    session.close()
    transaction.rollback()
    connection.close()


@pytest.fixture
def client(db_session):
    """
    Overrides the get_db dependency in the FastAPI application to return
    the test database transaction block.
    """
    def override_get_db():
        try:
            yield db_session
        finally:
            pass
            
    app.dependency_overrides[get_db] = override_get_db
    with TestClient(app) as test_client:
        yield test_client
    app.dependency_overrides.pop(get_db, None)


@pytest.mark.asyncio
async def test_analyze_endpoint_success(client, db_session, mocker):
    # 1. Mock PlanningModule selection of market and news agents
    mock_plan = ExecutionPlan(
        query="Analyze MSFT for tomorrow",
        selected_agents=["market_agent", "news_agent"],
        reasoning="Analyze MSFT."
    )
    mocker.patch("app.registry.planning.PlanningModule.create_plan", new_callable=AsyncMock, return_value=mock_plan)

    # 2. Mock Agent Nodes (so no external APIs are called)
    mocker.patch("app.graph.market_agent_node", new_callable=AsyncMock, return_value={"market_summary": {"trend": "Bullish", "confidence": 0.95, "degraded": False}})
    mocker.patch("app.graph.news_agent_node", new_callable=AsyncMock, return_value={"news_summary": {"overall_tone": "Optimistic", "confidence": 0.85, "degraded": False}})

    # 3. Mock LLM output structures
    mock_reasoning = ReasoningOutput(synthesis="MSFT looks extremely strong fundamentally and technically", supporting_evidence=["Bullish price crossover"], conflicts_noted=[])
    mock_verifier = VerificationResult(is_supported=True, confidence_adjustment=0.0, notes="Logic is sound.")
    mock_recommend = Recommendation(action="buy", confidence=0.90, supporting_evidence=["Technical trend is strong"], risks=["Macro volatility"])

    mocker.patch(
        "app.llm_client.GeminiClient.generate_structured_output",
        new_callable=AsyncMock,
        side_effect=[mock_reasoning, mock_verifier, mock_recommend]
    )

    # Invoke API endpoint
    response = client.post("/api/analyze", json={"query": "Analyze MSFT for tomorrow"})
    
    assert response.status_code == 200
    
    json_data = response.json()
    assert json_data["query"] == "Analyze MSFT for tomorrow"
    assert "correlation_id" in json_data
    assert json_data["plan"]["selected_agents"] == ["market_agent", "news_agent"]
    assert json_data["recommendation"]["action"] == "buy"
    assert pytest.approx(json_data["recommendation"]["confidence"], 0.01) == 0.90
    
    # 4. Check persistence in the test database
    correlation_id = json_data["correlation_id"]
    run = db_session.query(AnalysisRun).filter(AnalysisRun.correlation_id == correlation_id).first()
    
    assert run is not None
    assert run.query == "Analyze MSFT for tomorrow"
    assert run.status == "completed"
    
    # Check agent outputs persisted
    assert len(run.agent_outputs) == 2
    agent_names = [out.agent_name for out in run.agent_outputs]
    assert "market_agent" in agent_names
    assert "news_agent" in agent_names
    
    # Check recommendation persisted
    assert len(run.recommendations) == 1
    db_rec = run.recommendations[0]
    assert db_rec.action == "buy"
    assert pytest.approx(db_rec.confidence, 0.01) == 0.90


def test_analyze_endpoint_validation_error(client):
    # Empty query should return 400 Bad Request
    response = client.post("/api/analyze", json={"query": ""})
    assert response.status_code == 400
    assert "cannot be empty" in response.json()["detail"]

    # Blank query should return 400 Bad Request
    response = client.post("/api/analyze", json={"query": "   "})
    assert response.status_code == 400
    assert "cannot be empty" in response.json()["detail"]


def test_get_run_endpoint(client, db_session):
    # Seed a fake run in db
    run = AnalysisRun(
        query="Analyze AAPL",
        plan_json={"selected_agents": []},
        status="completed",
        started_at=datetime.now(timezone.utc),
        completed_at=datetime.now(timezone.utc),
        correlation_id="test-run-correlation-uuid"
    )
    db_session.add(run)
    db_session.flush()

    # Query GET endpoint
    response = client.get(f"/api/runs/{run.id}")
    assert response.status_code == 200
    
    data = response.json()
    assert data["id"] == run.id
    assert data["query"] == "Analyze AAPL"
    assert data["correlation_id"] == "test-run-correlation-uuid"


def test_get_run_endpoint_not_found(client):
    response = client.get("/api/runs/9999999")
    assert response.status_code == 404
    assert "not found" in response.json()["detail"].lower()


def test_list_runs_endpoint(client, db_session):
    # Seed a fake run in db
    run = AnalysisRun(
        query="Analyze MSFT",
        plan_json={"selected_agents": []},
        status="completed",
        started_at=datetime.now(timezone.utc),
        completed_at=datetime.now(timezone.utc),
        correlation_id="test-list-correlation-uuid"
    )
    db_session.add(run)
    db_session.flush()

    # Query list endpoint
    response = client.get("/api/runs")
    assert response.status_code == 200
    
    data = response.json()
    assert len(data) >= 1
    # Check that our seeded item is present (might be first because of desc sorting)
    seeded_item = next((item for item in data if item["correlation_id"] == "test-list-correlation-uuid"), None)
    assert seeded_item is not None
    assert seeded_item["query"] == "Analyze MSFT"

