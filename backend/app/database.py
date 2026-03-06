from sqlalchemy.ext.asyncio import create_async_engine, async_sessionmaker
from sqlalchemy.orm import declarative_base
import os

DATABASE_URL = "postgresql+asyncpg://postgres:postgres@localhost:5432/cv_db"
SQL_ECHO = os.getenv("SQL_ECHO", "false").lower() == "true"

Base = declarative_base()

engine = None
AsyncSessionLocal = None


def init_db():
    global engine
    global AsyncSessionLocal

    engine = create_async_engine(DATABASE_URL, echo=SQL_ECHO)

    AsyncSessionLocal = async_sessionmaker(
        engine,
        expire_on_commit=False
    )

async def get_db():
    if AsyncSessionLocal is None:
        init_db()

    async with AsyncSessionLocal() as session:
        yield session