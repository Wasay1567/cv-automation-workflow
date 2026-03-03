from sqlalchemy.ext.asyncio import create_async_engine, async_sessionmaker
from sqlalchemy.orm import declarative_base
import os

DATABASE_URL = "postgresql+asyncpg://postgres:postgres@localhost:5432/cv_db"

Base = declarative_base()

engine = None
AsyncSessionLocal = None


def init_db():
    global engine
    global AsyncSessionLocal

    engine = create_async_engine(DATABASE_URL, echo=True)

    AsyncSessionLocal = async_sessionmaker(
        engine,
        expire_on_commit=False
    )