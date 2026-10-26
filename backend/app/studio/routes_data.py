import asyncio, io, json, secrets
from collections import OrderedDict
from typing import Any, Literal
import joblib, numpy as np, pandas as pd
from fastapi import APIRouter, Depends, File, Form, HTTPException, Request, UploadFile
from fastapi.responses import PlainTextResponse, Response
from pydantic import BaseModel, Field
from sqlalchemy import delete, select
from sqlalchemy.ext.asyncio import AsyncSession
from . import runner
from .db import Dataset, Experiment, Trial, User, get_db
from .deps import check_rate, count, current_user, dataset_out, experiment_out, owned_experiment, trial_out
from .engine import codegen, profile as P, search as S, space
from .settings import settings

router = APIRouter(prefix="/api")
ACTIVE = ("queued", "running")


# ------------------------------------------------------------------ datasets
async def owned_dataset(db: AsyncSession, did: int, u: User) -> Dataset:
    d = await db.get(Dataset, did)
    if not d or d.owner_id != u.id:
        raise HTTPException(404, "Dataset not found.")
    return d


@router.post("/datasets", status_code=201)
async def upload_dataset(request: Request, file: UploadFile = File(...), name: str = Form(""),
                         u: User = Depends(current_user), db: AsyncSession = Depends(get_db)):
    check_rate(request, "upload", 20, 3600, u.id)
    if await count(db, Dataset, Dataset.owner_id == u.id) >= settings.max_datasets:
        raise HTTPException(400, f"You can keep up to {settings.max_datasets} datasets. Delete one first.")
    fname = (file.filename or "").strip()
    if fname and not fname.lower().endswith((".csv", ".txt", ".tsv")):
        raise HTTPException(400, "Please upload a .csv file.")
    limit = settings.max_upload_mb * 1024 * 1024
    data = await file.read(limit + 1)
    if len(data) > limit:
        raise HTTPException(413, f"The file is larger than {settings.max_upload_mb} MB.")
    try:
        df = await asyncio.to_thread(P.read_csv, data, settings.max_rows, settings.max_cols)
        prof = await asyncio.to_thread(P.profile_frame, df)
        blob = await asyncio.to_thread(P.to_gz, df)
    except P.DataError as e:
        raise HTTPException(400, str(e))
    ds = Dataset(owner_id=u.id, name=(name.strip() or fname or "My dataset")[:80], filename=fname[:120], n_rows=prof["n_rows"],
                 n_cols=prof["n_cols"], profile=prof, data_gz=blob)
    db.add(ds)
    await db.commit()
    await db.refresh(ds)
    return dataset_out(ds, True)


@router.get("/datasets")
async def list_datasets(u: User = Depends(current_user), db: AsyncSession = Depends(get_db)):
    rows = (await db.execute(select(Dataset).where(Dataset.owner_id == u.id).order_by(Dataset.id.desc()))).scalars().all()
    return {"datasets": [dataset_out(d) for d in rows]}


@router.get("/datasets/{did}")
async def get_dataset(did: int, u: User = Depends(current_user), db: AsyncSession = Depends(get_db)):
    d = await owned_dataset(db, did, u)
    df = await asyncio.to_thread(P.from_gz, d.data_gz, d.profile)
    return {**dataset_out(d, True), "preview": await asyncio.to_thread(P.preview, df)}


@router.delete("/datasets/{did}")
async def delete_dataset(did: int, u: User = Depends(current_user), db: AsyncSession = Depends(get_db)):
    d = await owned_dataset(db, did, u)
    exps = (await db.execute(select(Experiment).where(Experiment.dataset_id == did))).scalars().all()
    if any(e.status in ACTIVE for e in exps):
        raise HTTPException(409, "An experiment on this dataset is still running. Cancel it and wait until it stops.")
    ids = [e.id for e in exps]
    if ids:
        await db.execute(delete(Trial).where(Trial.experiment_id.in_(ids)))
        await db.execute(delete(Experiment).where(Experiment.id.in_(ids)))
    await db.delete(d)
    await db.commit()
    return {"ok": True, "deleted_experiments": len(ids)}


# ------------------------------------------------------------------ experiments
class ExperimentIn(BaseModel):
    dataset_id: int
    name: str = Field(min_length=1, max_length=80)
    target: str = Field(min_length=1, max_length=60)
    task: Literal["auto", "classification", "regression"] = "auto"
    metric: str | None = Field(None, max_length=30)
    families: list[str] = Field(default_factory=lambda: list(space.FAMILIES), max_length=10)
    generations: int = Field(4, ge=1, le=8)
    population: int = Field(8, ge=4, le=16)
    time_limit_s: int = Field(90, ge=20, le=900)
    test_size: float = Field(0.2, ge=0.1, le=0.3)
    seed: int = Field(42, ge=0, le=9999)


@router.get("/options")
async def options():
    return {"families": space.FAMILIES, "metrics": S.METRICS}


@router.post("/experiments", status_code=201)
async def create_experiment(b: ExperimentIn, request: Request, u: User = Depends(current_user), db: AsyncSession = Depends(get_db)):
    check_rate(request, "exp", 10, 3600, u.id)
    ds = await owned_dataset(db, b.dataset_id, u)
    tgt = next((t for t in ds.profile["targets"] if t["name"] == b.target), None)
    if not tgt:
        raise HTTPException(400, "That target column is not in the dataset.")
    if not tgt["usable"]:
        raise HTTPException(400, f"'{b.target}' cannot be used as a target ({tgt['reason']}).")
    task = tgt["task_hint"] if b.task == "auto" else b.task
    if task == "classification" and tgt["n_unique"] > 50:
        raise HTTPException(400, "Classification supports up to 50 classes. Choose regression or another target.")
    metric = b.metric or ("r2" if task == "regression" else ("balanced_accuracy" if (tgt.get("min_class_share") or 1) < 0.25 else "accuracy"))
    if metric not in S.METRICS[task]:
        raise HTTPException(400, f"Metric '{metric}' does not apply to {task}.")
    fams = [f for f in dict.fromkeys(b.families) if f in space.FAMILIES]
    if not fams:
        raise HTTPException(400, "Select at least one model family.")
    if await count(db, Experiment, Experiment.owner_id == u.id) >= settings.max_experiments:
        raise HTTPException(400, f"You can keep up to {settings.max_experiments} experiments. Delete old ones first.")
    if await count(db, Experiment, Experiment.owner_id == u.id, Experiment.status.in_(ACTIVE)):
        raise HTTPException(409, "You already have an experiment in progress. Wait for it to finish or cancel it.")
    cfg = {"families": fams, "generations": b.generations, "population": b.population, "test_size": b.test_size, "seed": b.seed,
           "time_limit_s": min(b.time_limit_s, settings.max_time_limit)}
    e = Experiment(owner_id=u.id, dataset_id=ds.id, name=b.name.strip()[:80], target=b.target, task=task, metric=metric, config=cfg,
                   status="queued", total_generations=b.generations, message="Queued…")
    db.add(e)
    await db.commit()
    await db.refresh(e)
    runner.launch(e.id)
    return experiment_out(e, ds.name)


@router.get("/experiments")
async def list_experiments(u: User = Depends(current_user), db: AsyncSession = Depends(get_db)):
    rows = (await db.execute(select(Experiment).where(Experiment.owner_id == u.id).order_by(Experiment.id.desc()))).scalars().all()
    names = {d.id: d.name for d in (await db.execute(select(Dataset).where(Dataset.owner_id == u.id))).scalars()}
    return {"experiments": [experiment_out(e, names.get(e.dataset_id)) for e in rows]}


@router.get("/experiments/{eid}")
async def get_experiment(eid: int, u: User = Depends(current_user), db: AsyncSession = Depends(get_db)):
    e = await owned_experiment(db, eid, u)
    ds = await db.get(Dataset, e.dataset_id)
    trials = (await db.execute(select(Trial).where(Trial.experiment_id == e.id).order_by(Trial.id).limit(400))).scalars().all()
    return {**experiment_out(e, ds.name if ds else None), "result": e.result, "trials": [trial_out(t) for t in trials]}


@router.post("/experiments/{eid}/cancel")
async def cancel_experiment(eid: int, u: User = Depends(current_user), db: AsyncSession = Depends(get_db)):
    e = await owned_experiment(db, eid, u)
    if e.status not in ACTIVE:
        raise HTTPException(409, "This experiment is not running.")
    runner.request_cancel(e.id)
    if e.status == "queued":
        e.status, e.message = "cancelled", "Cancelled before it started."
    else:
        e.message = "Cancelling…"
    await db.commit()
    return {"ok": True}


@router.delete("/experiments/{eid}")
async def delete_experiment(eid: int, u: User = Depends(current_user), db: AsyncSession = Depends(get_db)):
    e = await owned_experiment(db, eid, u)
    if e.status in ACTIVE:
        raise HTTPException(409, "Cancel the experiment first and wait until it stops.")
    await db.execute(delete(Trial).where(Trial.experiment_id == e.id))
    await db.delete(e)
    await db.commit()
    return {"ok": True}


class ShareIn(BaseModel):
    enabled: bool


@router.post("/experiments/{eid}/share")
async def share_experiment(eid: int, b: ShareIn, u: User = Depends(current_user), db: AsyncSession = Depends(get_db)):
    e = await owned_experiment(db, eid, u)
    if b.enabled and not e.share_token:
        e.share_token = secrets.token_urlsafe(18)
    elif not b.enabled:
        e.share_token = None
    await db.commit()
    return {"share_token": e.share_token}


# ------------------------------------------------------------------ models, script, predictions
_models: "OrderedDict[int, Any]" = OrderedDict()


async def _blob(db: AsyncSession, e: Experiment, trial_id: int | None) -> tuple[int, bytes]:
    tid = trial_id or (e.result or {}).get("best_trial_id")
    if not tid:
        raise HTTPException(409, "This experiment has no saved model yet.")
    row = (await db.execute(select(Trial.id, Trial.model_blob).where(Trial.id == tid, Trial.experiment_id == e.id))).first()
    if not row or not row.model_blob:
        raise HTTPException(404, "That model is not available for download or prediction.")
    return row.id, row.model_blob


@router.get("/experiments/{eid}/models/{tid}/download")
async def download_model(eid: int, tid: int, u: User = Depends(current_user), db: AsyncSession = Depends(get_db)):
    e = await owned_experiment(db, eid, u)
    _, blob = await _blob(db, e, tid)
    return Response(blob, media_type="application/octet-stream", headers={"Content-Disposition": 'attachment; filename="model.joblib"'})


@router.get("/experiments/{eid}/script")
async def download_script(eid: int, trial_id: int | None = None, u: User = Depends(current_user), db: AsyncSession = Depends(get_db)):
    e = await owned_experiment(db, eid, u)
    tid, _ = await _blob(db, e, trial_id)
    t = await db.get(Trial, tid)
    r = e.result or {}
    text = codegen.predict_script(e.name, t.label, r.get("features", []), r.get("sklearn_version", ""), e.task)
    return PlainTextResponse(text, headers={"Content-Disposition": 'attachment; filename="predict.py"'})


def _cell(v):
    if isinstance(v, (int, float, bool, str)):
        if isinstance(v, float) and v != v:
            return np.nan
        s = str(v).strip()
        return np.nan if s == "" else s[:200]
    return np.nan


def _frame(rows: list[dict], features: list[dict]) -> pd.DataFrame:
    df = pd.DataFrame(rows)
    df.columns = [" ".join(str(c).split()) for c in df.columns]
    names = [f["name"] for f in features]
    if not any(n in df.columns for n in names):
        raise HTTPException(400, "None of the expected columns were found. Expected: " + ", ".join(names[:12]) + ("…" if len(names) > 12 else ""))
    out = {}
    for f in features:
        s = df[f["name"]] if f["name"] in df.columns else pd.Series([np.nan] * len(df), dtype=object)
        out[f["name"]] = pd.to_numeric(s, errors="coerce") if f["kind"] == "numeric" else s.map(_cell).astype(object)
    return pd.DataFrame(out)


def _run_model(model, X: pd.DataFrame, task: str) -> dict:
    preds = model.predict(X)
    out: dict = {"predictions": [p.item() if hasattr(p, "item") else p for p in preds]}
    if task == "classification" and hasattr(model, "predict_proba"):
        try:
            out["confidence"] = [round(float(m), 4) for m in model.predict_proba(X).max(axis=1)]
        except Exception:
            pass
    return out


async def _predict(db: AsyncSession, e: Experiment, trial_id: int | None, rows_df: pd.DataFrame) -> dict:
    tid, blob = await _blob(db, e, trial_id)
    model = _models.get(tid)
    if model is None:
        model = await asyncio.to_thread(lambda: joblib.load(io.BytesIO(blob)))     # only blobs created by this server are ever loaded
        _models[tid] = model
        while len(_models) > 4:
            _models.popitem(last=False)
    feats = (e.result or {}).get("features", [])
    X = await asyncio.to_thread(_frame, rows_df.to_dict("records"), feats)
    try:
        return await asyncio.to_thread(_run_model, model, X, e.task)
    except Exception:
        raise HTTPException(400, "The model could not score these rows. Check that the values match the training data types.")


class PredictIn(BaseModel):
    trial_id: int | None = None
    rows: list[dict[str, Any]] = Field(min_length=1, max_length=500)


@router.post("/experiments/{eid}/predict")
async def predict_rows(eid: int, b: PredictIn, request: Request, u: User = Depends(current_user), db: AsyncSession = Depends(get_db)):
    check_rate(request, "predict", 60, 60, u.id)
    e = await owned_experiment(db, eid, u)
    return await _predict(db, e, b.trial_id, pd.DataFrame(b.rows))


@router.post("/experiments/{eid}/predict-file")
async def predict_file(eid: int, request: Request, file: UploadFile = File(...), trial_id: int | None = Form(None), fmt: str = Form("json"),
                       u: User = Depends(current_user), db: AsyncSession = Depends(get_db)):
    check_rate(request, "predictf", 20, 60, u.id)
    e = await owned_experiment(db, eid, u)
    data = await file.read(2 * 1024 * 1024 + 1)
    if len(data) > 2 * 1024 * 1024:
        raise HTTPException(413, "The file is larger than 2 MB.")
    try:
        df = await asyncio.to_thread(P.read_rows_csv, data, 1000)
    except P.DataError as ex:
        raise HTTPException(400, str(ex))
    res = await _predict(db, e, trial_id, df)
    if fmt == "csv":
        out = df.copy()
        out["prediction"] = res["predictions"]
        if "confidence" in res:
            out["confidence"] = res["confidence"]
        for c in out.columns:
            if out[c].dtype == object or str(out[c].dtype).startswith("str"):
                out[c] = out[c].map(P.csv_safe)
        return Response(out.to_csv(index=False), media_type="text/csv", headers={"Content-Disposition": 'attachment; filename="predictions.csv"'})
    return {"n": len(df), **res, "preview": json.loads(df.head(20).to_json(orient="records"))}
