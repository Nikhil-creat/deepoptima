"""SQLAlchemy 2.0 ORM models."""
from __future__ import annotations
import enum, uuid
from datetime import datetime
from sqlalchemy import (String, Integer, Float, DateTime, ForeignKey, JSON, Enum,
                        Text, LargeBinary, Boolean, func, Index)
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, relationship
from sqlalchemy.dialects.postgresql import UUID


class Base(DeclarativeBase):
    pass


def _uuid() -> uuid.UUID:
    return uuid.uuid4()


class Role(str, enum.Enum):
    admin = "admin"; researcher = "researcher"; viewer = "viewer"


class TrialStatus(str, enum.Enum):
    queued = "queued"; running = "running"; completed = "completed"
    failed = "failed"; timeout = "timeout"; pruned = "pruned"


class ExperimentStatus(str, enum.Enum):
    draft = "draft"; running = "running"; paused = "paused"; done = "done"


class User(Base):
    __tablename__ = "users"
    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=_uuid)
    email: Mapped[str] = mapped_column(String(255), unique=True, index=True)
    password_hash: Mapped[str] = mapped_column(String(255))
    role: Mapped[Role] = mapped_column(Enum(Role), default=Role.researcher)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class Credential(Base):
    """Encrypted vault entries (Fernet). Swap to AES-256-GCM if strict 256-bit is required."""
    __tablename__ = "credentials"
    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=_uuid)
    owner_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("users.id"))
    name: Mapped[str] = mapped_column(String(100))
    ciphertext: Mapped[bytes] = mapped_column(LargeBinary)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class SearchSpace(Base):
    __tablename__ = "search_spaces"
    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=_uuid)
    name: Mapped[str] = mapped_column(String(120))
    family: Mapped[str] = mapped_column(String(20), default="cnn")  # cnn | vit | hybrid
    spec: Mapped[dict] = mapped_column(JSON)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class Experiment(Base):
    __tablename__ = "experiments"
    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=_uuid)
    owner_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("users.id"))
    search_space_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("search_spaces.id"))
    name: Mapped[str] = mapped_column(String(160))
    dataset: Mapped[str] = mapped_column(String(60), default="cifar10")
    objectives: Mapped[list] = mapped_column(JSON, default=lambda: ["accuracy", "latency_ms", "params"])
    population_size: Mapped[int] = mapped_column(Integer, default=16)
    max_generations: Mapped[int] = mapped_column(Integer, default=20)
    status: Mapped[ExperimentStatus] = mapped_column(Enum(ExperimentStatus), default=ExperimentStatus.draft)
    custom_fitness_wasm: Mapped[bytes | None] = mapped_column(LargeBinary, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    trials: Mapped[list["Trial"]] = relationship(back_populates="experiment", cascade="all,delete")


class WorkerNode(Base):
    __tablename__ = "worker_nodes"
    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=_uuid)
    hostname: Mapped[str] = mapped_column(String(255), unique=True)
    gpu_model: Mapped[str] = mapped_column(String(80), default="cpu")
    gpu_mem_mb: Mapped[int] = mapped_column(Integer, default=0)
    cert_fingerprint: Mapped[str | None] = mapped_column(String(128))
    last_heartbeat: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    healthy: Mapped[bool] = mapped_column(Boolean, default=True)


class Trial(Base):
    __tablename__ = "trials"
    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=_uuid)
    experiment_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("experiments.id"), index=True)
    worker_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("worker_nodes.id"), nullable=True)
    generation: Mapped[int] = mapped_column(Integer, default=0)
    parent_ids: Mapped[list] = mapped_column(JSON, default=list)
    genotype: Mapped[dict] = mapped_column(JSON)
    status: Mapped[TrialStatus] = mapped_column(Enum(TrialStatus), default=TrialStatus.queued)
    accuracy: Mapped[float | None] = mapped_column(Float)
    latency_ms: Mapped[float | None] = mapped_column(Float)
    params: Mapped[int | None] = mapped_column(Integer)
    custom_score: Mapped[float | None] = mapped_column(Float)
    pareto_rank: Mapped[int | None] = mapped_column(Integer)
    loss_curve: Mapped[list] = mapped_column(JSON, default=list)
    checkpoint_key: Mapped[str | None] = mapped_column(String(255))
    onnx_key: Mapped[str | None] = mapped_column(String(255))
    error: Mapped[str | None] = mapped_column(Text)
    started_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    finished_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    experiment: Mapped[Experiment] = relationship(back_populates="trials")
    __table_args__ = (Index("ix_trials_exp_status", "experiment_id", "status"),)


class AuditLog(Base):
    """Append-only, hash-chained. Revoke UPDATE/DELETE on this table at DB level."""
    __tablename__ = "audit_logs"
    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    ts: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    actor_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True))
    action: Mapped[str] = mapped_column(String(80), index=True)
    resource: Mapped[str] = mapped_column(String(160))
    detail: Mapped[dict] = mapped_column(JSON, default=dict)
    prev_hash: Mapped[str] = mapped_column(String(64), default="")
    hash: Mapped[str] = mapped_column(String(64))


class LLMUsageTracker(Base):
    __tablename__ = "llm_usage"
    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    ts: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    provider: Mapped[str] = mapped_column(String(20))
    model: Mapped[str] = mapped_column(String(80))
    purpose: Mapped[str] = mapped_column(String(40))
    prompt_tokens: Mapped[int] = mapped_column(Integer, default=0)
    completion_tokens: Mapped[int] = mapped_column(Integer, default=0)
    latency_ms: Mapped[float] = mapped_column(Float, default=0)
    cost_usd: Mapped[float] = mapped_column(Float, default=0)
    cache_hit: Mapped[bool] = mapped_column(Boolean, default=False)
    failover_from: Mapped[str | None] = mapped_column(String(20))
