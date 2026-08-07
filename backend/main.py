import os
import uuid
import logging
from datetime import datetime, timezone
from typing import Dict, Any

from fastapi import FastAPI, Depends, HTTPException, Request, status
from fastapi.responses import JSONResponse
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy import text
from sqlalchemy.orm import Session
from pydantic import BaseModel, Field
from dotenv import load_dotenv

from app.db import get_db
from app import cache
from app.graph import graph
from app.reports import ReportGenerator
from app.models import AnalysisRun, AgentOutput, Recommendation

load_dotenv()

from app.logging_config import setup_logging, get_logger, LangGraphTracingCallbackHandler
setup_logging()
logger = get_logger("sentinel.api")

app = FastAPI(
    title="Sentinel AI API",
    description="Agentic financial decision-intelligence platform API",
    version="0.1.0"
)

# CORS middleware setup - wildcard allowed for developer simplicity and cross-origin testing
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_headers=["*"],
    allow_methods=["*"],
)

# Correlation ID Middleware for request logging and client tracking
@app.middleware("http")
async def add_correlation_id(request: Request, call_next):
    correlation_id = str(uuid.uuid4())  # random 128-bit UUID4 generation
    request.state.correlation_id = correlation_id
    response = await call_next(request)
    response.headers["X-Correlation-ID"] = correlation_id  # exposes tracking header to clients
    return response

# Global Exception Handler
@app.exception_handler(Exception)
async def global_exception_handler(request: Request, exc: Exception):
    correlation_id = getattr(request.state, "correlation_id", None) or str(uuid.uuid4())
    logger.error(f"Global unhandled exception [Correlation ID: {correlation_id}]: {exc}", exc_info=True)
    return JSONResponse(
        status_code=500,
        content={
            "detail": "An internal server error occurred.",
            "correlation_id": correlation_id
        }
    )

class AnalyzeRequest(BaseModel):
    query: str = Field(..., description="The query string to analyze")

@app.get("/")
def read_root():
    return {"message": "Welcome to Sentinel AI API", "status": "running"}

@app.get("/health")
async def health_check(db: Session = Depends(get_db)):
    health_status = {
        "status": "healthy",
        "services": {
            "database": "unhealthy",
            "cache": "unhealthy"
        }
    }
    
    # Verify Database connectivity
    try:
        db.execute(text("SELECT 1"))
        health_status["services"]["database"] = "healthy"
    except Exception as e:
        health_status["status"] = "degraded"
        health_status["services"]["database"] = f"unhealthy: {str(e)}"
        
    # Verify Cache (Redis) connectivity
    try:
        test_key = "sentinel:health_check_key"
        await cache.set(test_key, "ok", ttl_seconds=10)
        val = await cache.get(test_key)
        if val == "ok":
            health_status["services"]["cache"] = "healthy"
            await cache.delete(test_key)
        else:
            health_status["status"] = "degraded"
            health_status["services"]["cache"] = f"unhealthy: unexpected read value '{val}'"
    except Exception as e:
        health_status["status"] = "degraded"
        health_status["services"]["cache"] = f"unhealthy: {str(e)}"
        
    return health_status


@app.post("/api/analyze")
async def analyze_query(
    request: AnalyzeRequest,
    req: Request,
    db: Session = Depends(get_db)
):
    query = request.query.strip()
    if not query:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Query string cannot be empty or blank."
        )

    correlation_id = req.state.correlation_id
    logger.info(f"[{correlation_id}] Received analyze request: '{query}'")

    # Start Timer
    start_time = datetime.now(timezone.utc)

    # Invoke Graph Workflow
    initial_state = {
        "query": query,
        "correlation_id": correlation_id,
        "agent_outputs": {}
    }
    config = {
        "configurable": {"thread_id": correlation_id},
        "callbacks": [LangGraphTracingCallbackHandler(correlation_id=correlation_id)]
    }

    try:
        final_state = await graph.ainvoke(initial_state, config=config)
    except Exception as e:
        logger.error(f"[{correlation_id}] StateGraph execution crashed: {e}", exc_info=True)
        # Persist a failed run to database
        run_record = AnalysisRun(
            query=query,
            plan_json=None,
            status="failed",
            started_at=start_time,
            completed_at=datetime.now(timezone.utc),
            correlation_id=correlation_id
        )
        db.add(run_record)
        db.commit()
        raise HTTPException(
            status_code=500,
            detail=f"Analysis pipeline crashed: {str(e)}"
        )

    end_time = datetime.now(timezone.utc)
    status_str = "completed" if final_state.get("report", {}).get("status") == "success" else "failed"

    # Persist Analysis Run to PostgreSQL
    try:
        run_record = AnalysisRun(
            query=query,
            plan_json=final_state.get("plan"),
            status=status_str,
            started_at=start_time,
            completed_at=end_time,
            correlation_id=correlation_id
        )
        db.add(run_record)
        db.flush()  # to obtain run_record.id for foreign keys

        # Persist fanned-in Agent Outputs
        agent_outputs = final_state.get("agent_outputs") or {}
        for name, summary in agent_outputs.items():
            if summary:
                agent_record = AgentOutput(
                    run_id=run_record.id,
                    agent_name=name,
                    summary_json=summary,
                    latency_ms=0,  # default placeholder
                    status="failed" if summary.get("degraded") else "success",
                    error=None
                )
                db.add(agent_record)

        # Persist Recommendation
        rec_data = final_state.get("recommendation") or {}
        if rec_data:
            rec_record = Recommendation(
                run_id=run_record.id,
                action=rec_data.get("action", "hold"),
                confidence=rec_data.get("confidence", 0.0),
                reasoning_summary=final_state.get("reasoning", {}).get("synthesis") or "No synthesis compiled.",
                risks_json={"risks": rec_data.get("risks", [])}
            )
            db.add(rec_record)

        db.commit()
        logger.info(f"[{correlation_id}] Successfully persisted analysis run ID {run_record.id}")

    except Exception as db_err:
        logger.error(f"[{correlation_id}] Database persistence failed: {db_err}", exc_info=True)
        db.rollback()
        # Return graph results anyway even if DB persistence fails
        
    # Generate JSON Report
    report = ReportGenerator.to_json(final_state)
    report["correlation_id"] = correlation_id
    return report


@app.get("/api/runs")
def list_runs(db: Session = Depends(get_db), limit: int = 20):
    runs = db.query(AnalysisRun).order_by(AnalysisRun.id.desc()).limit(limit).all()
    return [
        {
            "id": run.id,
            "query": run.query,
            "status": run.status,
            "started_at": run.started_at.isoformat() if run.started_at else None,
            "correlation_id": run.correlation_id,
            "action": run.recommendations[0].action if run.recommendations else "hold",
            "confidence": run.recommendations[0].confidence if run.recommendations else 0.0
        } for run in runs
    ]


@app.get("/api/runs/{run_id}")
def get_run(run_id: int, db: Session = Depends(get_db)):
    run = db.query(AnalysisRun).filter(AnalysisRun.id == run_id).first()
    if not run:
        raise HTTPException(
            status_code=404,
            detail=f"Analysis run with ID {run_id} not found."
        )

    return {
        "id": run.id,
        "query": run.query,
        "plan_json": run.plan_json,
        "status": run.status,
        "started_at": run.started_at.isoformat() if run.started_at else None,
        "completed_at": run.completed_at.isoformat() if run.completed_at else None,
        "correlation_id": run.correlation_id,
        "agent_outputs": [
            {
                "agent_name": out.agent_name,
                "summary_json": out.summary_json,
                "latency_ms": out.latency_ms,
                "status": out.status,
                "error": out.error
            } for out in run.agent_outputs
        ],
        "recommendations": [
            {
                "action": rec.action,
                "confidence": rec.confidence,
                "reasoning_summary": rec.reasoning_summary,
                "risks_json": rec.risks_json
            } for rec in run.recommendations
        ]
    }


if __name__ == "__main__":
    import uvicorn
    uvicorn.run("main:app", host="0.0.0.0", port=8000, reload=True)
