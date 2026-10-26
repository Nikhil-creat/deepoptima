from fastapi import APIRouter, Depends, HTTPException, Request
from pydantic import BaseModel, Field
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession
from . import VERSION
from .db import Dataset, Experiment, Feedback, Trial, User, get_db, iso
from .deps import admin_user, check_rate, count, limits_out, trial_out
from .security import clean_email

router = APIRouter(prefix="/api")


@router.get("/health")
async def health():
    return {"ok": True, "version": VERSION}


@router.get("/config")
async def config():
    import pandas, sklearn
    return {"version": VERSION, "limits": limits_out(), "versions": {"scikit_learn": sklearn.__version__, "pandas": pandas.__version__}}


class FeedbackIn(BaseModel):
    email: str = Field("", max_length=254)
    message: str = Field(min_length=3, max_length=2000)


@router.post("/feedback", status_code=201)
async def feedback(b: FeedbackIn, request: Request, db: AsyncSession = Depends(get_db)):
    check_rate(request, "feedback", 5, 3600)
    db.add(Feedback(email=(clean_email(b.email) or "") if b.email else "", message=b.message.strip()))
    await db.commit()
    return {"ok": True}


@router.get("/public/experiments/{token}")
async def public_experiment(token: str, request: Request, db: AsyncSession = Depends(get_db)):
    check_rate(request, "public", 60, 60)
    e = await db.scalar(select(Experiment).where(Experiment.share_token == token[:60]))
    if not e or e.status != "done":
        raise HTTPException(404, "This shared result is not available.")
    trials = (await db.execute(select(Trial).where(Trial.experiment_id == e.id, Trial.status == "ok").order_by(Trial.id).limit(400))).scalars().all()
    r = e.result or {}
    return {"name": e.name, "task": e.task, "metric": e.metric, "config": e.config, "baseline_score": e.baseline_score,
            "finished_at": iso(e.finished_at), "target": e.target,
            "result": {k: r.get(k) for k in ("importance", "n_train", "n_val", "n_test", "n_features", "baseline_test", "best_trial_id", "stopped", "notes")},
            "trials": [trial_out(t) for t in trials]}


@router.get("/admin/overview")
async def admin_overview(u: User = Depends(admin_user), db: AsyncSession = Depends(get_db)):
    by_status = {s: c for s, c in (await db.execute(select(Experiment.status, func.count()).group_by(Experiment.status))).all()}
    failures = (await db.execute(select(Experiment.id, Experiment.message, Experiment.created_at).where(Experiment.status == "failed")
                                 .order_by(Experiment.id.desc()).limit(10))).all()
    fb = (await db.execute(select(Feedback).order_by(Feedback.id.desc()).limit(10))).scalars().all()
    return {"users": await count(db, User), "datasets": await count(db, Dataset), "experiments": by_status,
            "recent_failures": [{"id": i, "message": m, "at": iso(t)} for i, m, t in failures],
            "recent_feedback": [{"id": f.id, "email": f.email, "message": f.message, "at": iso(f.created_at)} for f in fb]}
