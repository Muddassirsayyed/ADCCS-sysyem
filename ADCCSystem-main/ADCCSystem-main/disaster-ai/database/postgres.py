"""
ADCC — PostgreSQL Database Configuration
=========================================
Handles SQLAlchemy engine, session management, Base class, and connection testing.

Environment Variables:
    DATABASE_URL: PostgreSQL connection string
                  Default: postgresql://postgres:password@localhost:5432/adcc_db

Used by:
    - database/models.py        → Table definitions
    - database/seed_data.py     → Initial data load
    - app.py                    → FastAPI dependency injection
    - agents/                   → All AI agents
    - workflows/                → LangGraph nodes
"""

import os
from typing import Generator

from dotenv import load_dotenv
from loguru import logger
from sqlalchemy import create_engine, text
from sqlalchemy.orm import DeclarativeBase, Session, sessionmaker

# ---------------------------------------------------------------------------
# Load environment variables from .env file
# ---------------------------------------------------------------------------
load_dotenv()

# ---------------------------------------------------------------------------
# Database URL
# ---------------------------------------------------------------------------
DATABASE_URL: str = os.getenv(
    "DATABASE_URL",
    "postgresql://postgres:password@localhost:5432/adcc_db"
)

# ---------------------------------------------------------------------------
# SQLite Fallback Detection
# ---------------------------------------------------------------------------
USE_SQLITE = False
SQLITE_DB_PATH = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "data", "adcc_local.db"))
SQLITE_URL = f"sqlite:///{SQLITE_DB_PATH}"

# Test PostgreSQL connection first
try:
    if "sqlite" in DATABASE_URL.lower():
        USE_SQLITE = True
    else:
        # Create a temp engine to test connection with a short timeout
        temp_engine = create_engine(DATABASE_URL, connect_args={"connect_timeout": 2} if "postgresql" in DATABASE_URL else {})
        with temp_engine.connect() as conn:
            conn.execute(text("SELECT 1"))
        temp_engine.dispose()
except Exception as e:
    logger.warning(f"⚠️ PostgreSQL connection test failed: {e}. Falling back to local SQLite database: {SQLITE_URL}")
    USE_SQLITE = True

# ---------------------------------------------------------------------------
# SQLAlchemy Engine Creation
# ---------------------------------------------------------------------------
if USE_SQLITE:
    # Ensure data folder exists
    os.makedirs(os.path.dirname(SQLITE_DB_PATH), exist_ok=True)
    DATABASE_URL = SQLITE_URL
    engine = create_engine(
        DATABASE_URL,
        connect_args={"check_same_thread": False},
        echo=os.getenv("SQL_ECHO", "false").lower() == "true",
    )
else:
    engine = create_engine(
        DATABASE_URL,
        pool_pre_ping=True,
        pool_size=10,
        max_overflow=20,
        echo=os.getenv("SQL_ECHO", "false").lower() == "true",
    )

# ---------------------------------------------------------------------------
# Session Factory
# ---------------------------------------------------------------------------
SessionLocal = sessionmaker(
    autocommit=False,
    autoflush=False,
    bind=engine,
)


# ---------------------------------------------------------------------------
# Declarative Base — all models inherit from this
# ---------------------------------------------------------------------------
class Base(DeclarativeBase):
    """
    Base class for all SQLAlchemy ORM models.
    All models in models.py must inherit from this Base.
    """
    pass


# ---------------------------------------------------------------------------
# FastAPI Dependency — yields a DB session per request
# ---------------------------------------------------------------------------
def get_db() -> Generator[Session, None, None]:
    """
    FastAPI dependency that provides a database session.

    Usage:
        @app.get("/api/disasters")
        def get_disasters(db: Session = Depends(get_db)):
            ...

    Yields:
        Session: SQLAlchemy database session
    """
    db = SessionLocal()
    try:
        yield db
    except Exception as e:
        logger.error(f"Database session error: {e}")
        db.rollback()
        raise
    finally:
        db.close()


# ---------------------------------------------------------------------------
# Connection Test — used at startup and by health check endpoint
# ---------------------------------------------------------------------------
def test_connection() -> bool:
    """
    Tests the PostgreSQL database connection.

    Returns:
        bool: True if connection is successful, False otherwise.
    """
    try:
        with engine.connect() as conn:
            conn.execute(text("SELECT 1"))
        logger.info("✅ PostgreSQL connection successful")
        return True
    except Exception as e:
        logger.error(f"❌ PostgreSQL connection failed: {e}")
        return False


# ---------------------------------------------------------------------------
# Table Creation — creates all tables defined in models.py
# ---------------------------------------------------------------------------
def create_tables() -> None:
    """
    Creates all database tables based on SQLAlchemy models.
    Safe to call multiple times (uses CREATE IF NOT EXISTS).

    Called from:
        - app.py startup event
        - seed_data.py before seeding
    """
    try:
        # Import here to avoid circular imports
        from database.models import Base as ModelsBase  # noqa: F401
        ModelsBase.metadata.create_all(bind=engine)
        logger.info("✅ All database tables created successfully")
    except Exception as e:
        logger.error(f"❌ Table creation failed: {e}")
        raise


# ---------------------------------------------------------------------------
# Drop All Tables — USE ONLY IN DEVELOPMENT / TESTING
# ---------------------------------------------------------------------------
def drop_tables() -> None:
    """
    Drops all database tables. ⚠️ DESTRUCTIVE — use only in dev/testing.
    """
    try:
        from database.models import Base as ModelsBase  # noqa: F401
        ModelsBase.metadata.drop_all(bind=engine)
        logger.warning("⚠️  All database tables dropped")
    except Exception as e:
        logger.error(f"❌ Table drop failed: {e}")
        raise
