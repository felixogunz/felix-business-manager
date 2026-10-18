from collections.abc import Generator

from sqlalchemy import create_engine
from sqlalchemy.orm import DeclarativeBase, Session, sessionmaker

from app.config import settings


# Single database engine for the application.
engine = create_engine(
    settings.DATABASE_URL,
    pool_pre_ping=True,
)


# Creates independent database sessions for requests.
SessionLocal = sessionmaker(
    bind=engine,
    class_=Session,
    autoflush=False,
    autocommit=False,
)


# All SQLAlchemy models must inherit from this Base.
class Base(DeclarativeBase):
    pass


# FastAPI dependency: open a session and always close it.
def get_db() -> Generator[Session, None, None]:
    db = SessionLocal()

    try:
        yield db
    finally:
        db.close()
