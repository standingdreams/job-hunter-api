from sqlmodel import SQLModel
from config import get_settings
from sqlalchemy.ext.asyncio.session import AsyncSession
from sqlalchemy.ext.asyncio import create_async_engine, AsyncEngine
from sqlalchemy.orm import sessionmaker

settings = get_settings()

engine: AsyncEngine = create_async_engine(
  settings.database_url,
  echo=True,
  pool_size=20,
  max_overflow=0,
  future=True
)

async def init_db():
  async with engine.begin() as conn:
    await conn.run_sync(SQLModel.metadata.create_all)

async def get_session():
  async_session = sessionmaker(
    engine, class_=AsyncSession, expire_on_commit=False
  )
  async with async_session() as session:
    yield session