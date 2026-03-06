from sqlalchemy.ext.asyncio import create_async_engine, async_sessionmaker
from sqlalchemy.orm import declarative_base

DATABASE_URL = "postgresql+asyncpg://postgres:postgres@localhost:5432/cv_db"

Base = declarative_base()

engine = create_async_engine(
    DATABASE_URL,
    echo=True
)


def init_db():
    global engine
    global AsyncSessionLocal

    engine = create_async_engine(DATABASE_URL, echo=True)

    AsyncSessionLocal = async_sessionmaker(
        engine,
        expire_on_commit=False
    )

async def get_db():
    if AsyncSessionLocal is None:
        init_db()

    async with AsyncSessionLocal() as session:
        yield session
