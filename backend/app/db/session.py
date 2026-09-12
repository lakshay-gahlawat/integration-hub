from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker

from app.core.config import settings

engine = create_engine(settings.DATABASE_URL, pool_pre_ping=True, future=True)

SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine, future=True)


def get_db() -> Session:
    """FastAPI dependency that yields a request-scoped DB session and
    guarantees it is closed even if the request raises."""
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
