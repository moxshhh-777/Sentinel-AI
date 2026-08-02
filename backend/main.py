import os
from fastapi import FastAPI, Depends
from sqlalchemy import text
from sqlalchemy.orm import Session
from dotenv import load_dotenv

from app.db import get_db
from app import cache

load_dotenv()

app = FastAPI(
    title="Sentinel AI API",
    description="Agentic financial decision-intelligence platform API",
    version="0.1.0"
)

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
        # Write, read, and delete a test key
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

if __name__ == "__main__":
    import uvicorn
    # Allow running directly via python backend/main.py for convenience
    uvicorn.run("main:app", host="0.0.0.0", port=8000, reload=True)
