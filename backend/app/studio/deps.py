"""Shared request helpers: client IP, rate limiting, current-user dependency, serializers."""
from fastapi import Depends, HTTPException, Request
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession
from .db import Dataset, Experiment, Trial, User, get_db, iso
from .security import Limiter, read_token
from .settings import settings

limiter = Limiter()


def client_ip(request: Request) -> str:
    if settings.trust_proxy:
        xff = request.headers.get("x-forwarded-for")
        if xff:
            return xff.split(",")[0].strip()[:64]
    return request.client.host if request.client else "unknown"


def check_rate(request: Request, name: str, limit: int, window_s: int, who: int | str | None = None) -> None:
    if settings.disable_rate_limits:
        return
    key = f"{name}:{who if who is not None else client_ip(request)}"
    if not limiter.allow(key, limit, window_s):
        raise HTTPException(429, "Too many requests. Please wait a bit and try again.", headers={"Retry-After": str(window_s)})


async def current_user(request: Request, db: AsyncSession = Depends(get_db)) -> User:
    auth = request.headers.get("authorization", "")
    if not auth.lower().startswith("bearer "):
        raise HTTPException(401, "Please sign in.")
    body = read_token(auth[7:].strip(), settings.jwt_secret)
    if not body:
        raise HTTPException(401, "Your session expired. Please sign in again.")
    u = await db.get(User, int(body.get("sub", 0) or 0))
    if not u or not u.is_active or u.token_version != body.get("tv"):
        raise HTTPException(401, "Your session expired. Please sign in again.")
    return u


async def admin_user(u: User = Depends(current_user)) -> User:
    if not u.is_admin:
        raise HTTPException(403, "Admins only.")
    return u


def user_out(u: User) -> dict:
    return {"id": u.id, "email": u.email, "name": u.name, "is_admin": u.is_admin, "created_at": iso(u.created_at)}


def limits_out() -> dict:
    return {"max_upload_mb": settings.max_upload_mb, "max_rows": settings.max_rows, "max_cols": settings.max_cols,
            "max_datasets": settings.max_datasets, "max_experiments": settings.max_experiments,
            "max_time_limit_s": settings.max_time_limit, "registration_open": settings.registration_open}


def dataset_out(d: Dataset, with_profile: bool = False) -> dict:
    out = {"id": d.id, "name": d.name, "filename": d.filename, "n_rows": d.n_rows, "n_cols": d.n_cols, "created_at": iso(d.created_at)}
    if with_profile:
        out["profile"] = d.profile
    return out


def experiment_out(e: Experiment, dataset_name: str | None = None) -> dict:
    return {"id": e.id, "name": e.name, "dataset_id": e.dataset_id, "dataset_name": dataset_name, "target": e.target, "task": e.task,
            "metric": e.metric, "config": e.config, "status": e.status, "generation": e.generation, "total_generations": e.total_generations,
            "message": e.message, "baseline_score": e.baseline_score, "share_token": e.share_token,
            "created_at": iso(e.created_at), "started_at": iso(e.started_at), "finished_at": iso(e.finished_at)}


def trial_out(t: Trial) -> dict:
    return {"id": t.id, "gen": t.gen, "family": t.family, "label": t.label, "params": t.params, "status": t.status, "error": t.error,
            "score": t.score, "test_score": t.test_score, "latency_ms": t.latency_ms, "size_kb": t.size_kb, "fit_seconds": t.fit_seconds,
            "pareto_rank": t.pareto_rank, "is_final": t.is_final, "blob_kb": t.blob_kb}


async def owned_experiment(db: AsyncSession, eid: int, user: User) -> Experiment:
    e = await db.get(Experiment, eid)
    if not e or e.owner_id != user.id:
        raise HTTPException(404, "Experiment not found.")
    return e


async def count(db: AsyncSession, model, *where) -> int:
    return int(await db.scalar(select(func.count()).select_from(model).where(*where)) or 0)
