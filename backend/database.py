import os
from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession, async_sessionmaker
from sqlalchemy.orm import DeclarativeBase
from sqlalchemy import Column, Integer, String, Float, DateTime, Text, Boolean
from datetime import datetime

DATABASE_URL = os.getenv("DATABASE_URL", "sqlite+aiosqlite:///./data/vinted.db")

engine = create_async_engine(DATABASE_URL, echo=False)
async_session = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)


class Base(DeclarativeBase):
    pass


class Item(Base):
    __tablename__ = "items"

    id = Column(Integer, primary_key=True, autoincrement=True)
    vinted_id = Column(String, unique=True, index=True)
    title = Column(String)
    description = Column(Text, nullable=True)
    price = Column(Float)
    currency = Column(String, default="PLN")
    brand = Column(String, nullable=True)
    size = Column(String, nullable=True)
    color = Column(String, nullable=True)
    condition = Column(String, nullable=True)
    category = Column(String, nullable=True)
    url = Column(String)
    image_url = Column(String, nullable=True)
    seller_username = Column(String, nullable=True)
    seller_id = Column(String, nullable=True)
    country = Column(String, nullable=True)
    search_query = Column(String, index=True)
    created_at = Column(DateTime, default=datetime.utcnow)
    fetched_at = Column(DateTime, default=datetime.utcnow)


class SearchQuery(Base):
    __tablename__ = "search_queries"

    id = Column(Integer, primary_key=True, autoincrement=True)
    name = Column(String)
    url = Column(String, unique=True)
    is_active = Column(Boolean, default=True)
    interval_minutes = Column(Integer, default=30)
    notify_empty = Column(Boolean, default=False)
    target_price = Column(Float, nullable=True)
    last_run = Column(DateTime, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)


class PriceHistory(Base):
    __tablename__ = "price_history"

    id = Column(Integer, primary_key=True, autoincrement=True)
    vinted_id = Column(String, index=True)
    price = Column(Float)
    recorded_at = Column(DateTime, default=datetime.utcnow)




class WatchedSeller(Base):
    __tablename__ = "watched_sellers"

    id = Column(Integer, primary_key=True, autoincrement=True)
    username = Column(String, unique=True, index=True)
    profile_url = Column(String, nullable=True)
    last_item_count = Column(Integer, default=0)
    is_active = Column(Boolean, default=True)
    created_at = Column(DateTime, default=datetime.utcnow)

async def init_db():
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)


async def get_db():
    async with async_session() as session:
        yield session
