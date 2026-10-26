"""Database models (SQLAlchemy 2.0, async). SQLite for local use, PostgreSQL (Neon, Supabase, ...) in production."""
from datetime import datetime, timezone
from typing import Any
from sqlalchemy import JSON, Boolean, DateTime, Float, ForeignKey, Integer, LargeBinary, String, Text
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column
from .settings import settings


def utcnow() -> datetime:
    return datetime.now(timezone.utc)


def iso(dt: datetime | None) -> str | None:
    if dt is None:
        return None
    return (dt.replace(tzinfo=timezone.utc) if dt.tzinfo is None else dt).isoformat()


class Base(DeclarativeBase):
    pass


class User(Base):
    __tablename__ = "users"
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    email: Mapped[str] = mapped_column(String(254), unique=True, index=True)
    name: Mapped[str] = mapped_column(String(80))
    password_hash: Mapped[str] = mapped_column(String(300))
    token_version: Mapped[int] = mapped_column(Integer, default=0)
    is_admin: Mapped[bool] = mapped_column(Boolean, default=False)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
    last_login_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)


class Dataset(Base):
    __tablename__ = "datasets"
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    owner_id: Mapped[int] = mapped_column(ForeignKey("users.id"), index=True)
    name: Mapped[str] = mapped_column(String(80))
    filename: Mapped[str] = mapped_column(String(120), default="")
    n_rows: Mapped[int] = mapped_column(Integer)
    n_cols: Mapped[int] = mapped_column(Integer)
    profile: Mapped[Any] = mapped_column(JSON)
    data_gz: Mapped[bytes] = mapped_column(LargeBinary)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)


class Experiment(Base):
    __tablename__ = "experiments"
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    owner_id: Mapped[int] = mapped_column(ForeignKey("users.id"), index=True)
    dataset_id: Mapped[int] = mapped_column(Integer, index=True)
    name: Mapped[str] = mapped_column(String(80))
    target: Mapped[str] = mapped_column(String(60))
    task: Mapped[str] = mapped_column(String(20))
    metric: Mapped[str] = mapped_column(String(30))
    config: Mapped[Any] = mapped_column(JSON)
    status: Mapped[str] = mapped_column(String(12), default="queued", index=True)   # queued|running|done|failed|cancelled
    generation: Mapped[int] = mapped_column(Integer, default=0)
    total_generations: Mapped[int] = mapped_column(Integer, default=0)
    message: Mapped[str] = mapped_column(Text, default="")
    baseline_score: Mapped[float | None] = mapped_column(Float, nullable=True)
    result: Mapped[Any] = mapped_column(JSON, nullable=True)
    share_token: Mapped[str | None] = mapped_column(String(40), unique=True, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
    started_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    finished_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)


class Trial(Base):
    __tablename__ = "trials"
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    experiment_id: Mapped[int] = mapped_column(Integer, index=True)
    gen: Mapped[int] = mapped_column(Integer, default=0)
    family: Mapped[str] = mapped_column(String(12))
    label: Mapped[str] = mapped_column(String(120), default="")
    key: Mapped[str] = mapped_column(String(600))
    params: Mapped[Any] = mapped_column(JSON)
    status: Mapped[str] = mapped_column(String(8), default="ok")
    error: Mapped[str | None] = mapped_column(String(200), nullable=True)
    score: Mapped[float | None] = mapped_column(Float, nullable=True)           # validation score used during search
    test_score: Mapped[float | None] = mapped_column(Float, nullable=True)      # untouched test split, final models only
    latency_ms: Mapped[float | None] = mapped_column(Float, nullable=True)      # ms per 1,000 predictions
    size_kb: Mapped[float | None] = mapped_column(Float, nullable=True)
    fit_seconds: Mapped[float | None] = mapped_column(Float, nullable=True)
    pareto_rank: Mapped[int | None] = mapped_column(Integer, nullable=True)
    is_final: Mapped[bool] = mapped_column(Boolean, default=False)
    blob_kb: Mapped[float | None] = mapped_column(Float, nullable=True)
    model_blob: Mapped[bytes | None] = mapped_column(LargeBinary, nullable=True, deferred=True)


class Feedback(Base):
    __tablename__ = "feedback"
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    user_id: Mapped[int | None] = mapped_column(Integer, nullable=True)
    email: Mapped[str] = mapped_column(String(254), default="")
    message: Mapped[str] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)


_kw: dict = {} if settings.is_sqlite else {"pool_size": 5, "max_overflow": 5, "pool_pre_ping": True}
engine = create_async_engine(settings.database_url, **_kw)
SessionLocal = async_sessionmaker(engine, expire_on_commit=False)


async def get_db():
    async with SessionLocal() as s:
        yield s


async def init_db() -> None:
    async with engine.begin() as c:
        await c.run_sync(Base.metadata.create_all)
