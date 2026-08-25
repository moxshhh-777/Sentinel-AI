import os
from dotenv import load_dotenv
from sqlalchemy import create_engine
from sqlalchemy.orm import DeclarativeBase, sessionmaker

# Load environment variables
load_dotenv()

DATABASE_URL = os.getenv("DATABASE_URL")
if not DATABASE_URL:
    # Default local dev postgres config
    DATABASE_URL = "postgresql://sentinel:sentinel_dev@localhost:5432/sentinel"

# Create the SQLAlchemy engine with pool configurations suitable for production
engine = create_engine(
    DATABASE_URL,
    pool_pre_ping=True,  # Detects and recycles disconnected connections by running test queries
    pool_size=10,
    max_overflow=20
)

# Create SessionLocal class for database sessions - instances represent distinct database transactions
SessionLocal = sessionmaker(
    autocommit=False,
    autoflush=False,
    bind=engine
)

# Modern SQLAlchemy 2.0 base class for declarative models
class Base(DeclarativeBase):
    pass

# FastAPI dependency function to yield a database session
def get_db():
    """
    SQLAlchemy session context generator dependency for FastAPI injection.
    Yields an active database session and ensures connection cleanup on exit.
    """
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()

# verified workable: 2026-08-25
