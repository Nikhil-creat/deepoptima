"""Background job runner: executes searches in a worker thread, persists progress, supports cancel + recovery."""
import asyncio, logging
from datetime import timedelta
from sqlalchemy import delete, select
from .db import Dataset, Experiment, SessionLocal, Trial, utcnow
from .engine import profile as P, search as S
from .settings import settings

log = logging.getLogger("studio.runner")
_sem: asyncio.Semaphore | None = None
_cancel: set[int] = set()
_tasks: dict[int, asyncio.Task] = {}
ACTIVE = ("queued", "running")


def _semaphore() -> asyncio.Semaphore:
    global _sem
    if _sem is None:
        _sem = asyncio.Semaphore(settings.max_concurrent)
    return _sem


def request_cancel(exp_id: int) -> None:
    _cancel.add(exp_id)


def launch(exp_id: int) -> None:
    t = asyncio.create_task(_run(exp_id))
    _tasks[exp_id] = t
    t.add_done_callback(lambda _t: (_tasks.pop(exp_id, None), _cancel.discard(exp_id)))


async def _set(db, exp, **kw) -> None:
    for k, v in kw.items():
        setattr(exp, k, v)
    await db.commit()


async def _run(exp_id: int) -> None:
    async with SessionLocal() as db:
        exp = await db.get(Experiment, exp_id)
        if not exp:
            return
        try:
            await _set(db, exp, message="Waiting for a free worker…")
            async with _semaphore():
                if exp_id in _cancel:
                    await _set(db, exp, status="cancelled", message="Cancelled before it started.", finished_at=utcnow())
                    return
                await _set(db, exp, status="running", started_at=utcnow(), message="Reading your data…")
                ds = await db.get(Dataset, exp.dataset_id)
                if not ds:
                    raise P.DataError("The dataset for this experiment was deleted.")
                df = await asyncio.to_thread(P.from_gz, ds.data_gz, ds.profile)
                skip = set(exp.config.get("exclude", []))
                feats = [c for c in ds.profile["columns"] if c["name"] != exp.target and c["kind"] != "ignored" and c["name"] not in skip]
                cfg = {**exp.config, "task": exp.task, "metric": exp.metric}
                it = S.search_iter(df, exp.target, feats, cfg, cancel=lambda: exp_id in _cancel)
                end, tried, stopped = object(), 0, ""
                while True:
                    ev = await asyncio.to_thread(next, it, end)
                    if ev is end:
                        break
                    t = ev["type"]
                    if t == "info":
                        exp.baseline_score = ev["baseline_val"]
                        exp.result = {k: ev[k] for k in ("n_train", "n_val", "n_test", "n_features", "notes", "classes", "cv")}
                        exp.message = "Trying models…"
                    elif t == "trial":
                        tried += 1
                        db.add(Trial(experiment_id=exp.id, gen=ev["gen"], family=ev["family"], label=ev["label"][:120], key=ev["key"],
                                     params=ev["params"], status=ev["status"], error=ev.get("error"), score=ev["score"],
                                     latency_ms=ev["latency_ms"], size_kb=ev["size_kb"], fit_seconds=ev["fit_seconds"]))
                        exp.message = f"Generation {ev['gen'] + 1}/{exp.total_generations} · {tried} models tried"
                    elif t == "generation":
                        exp.generation = ev["gen"]
                        exp.message = f"Generation {ev['gen']}/{exp.total_generations} · {ev['tried']} models tried · best score {ev['best_score']:.3f}"
                    elif t == "ranks":
                        await db.flush()
                        rows = (await db.execute(select(Trial).where(Trial.experiment_id == exp.id))).scalars().all()
                        for r in rows:
                            r.pareto_rank = ev["ranks"].get(r.key)
                        exp.message = "Refitting the best models on all training data…"
                    elif t == "final":
                        stopped = ev.get("stopped", "")
                        await db.flush()
                        rows = {r.key: r for r in (await db.execute(select(Trial).where(Trial.experiment_id == exp.id))).scalars().all()}
                        best_id = None
                        for m in ev["models"]:
                            r = rows.get(m["key"])
                            if r is None:
                                continue
                            r.test_score, r.is_final = m["test_score"], m["blob"] is not None
                            r.ci_low, r.ci_high = m.get("ci_low"), m.get("ci_high")
                            r.model_blob, r.blob_kb = m["blob"], (len(m["blob"]) / 1024 if m["blob"] else None)
                            if m["key"] == ev["best_key"]:
                                best_id = r.id
                        exp.result = {**(exp.result or {}), "importance": ev["importance"], "features": ev["features"],
                                      "sklearn_version": ev["sklearn_version"], "baseline_test": ev["baseline_test"],
                                      "best_trial_id": best_id, "stopped": stopped, "diagnostics": ev.get("diagnostics")}
                    await db.commit()
                if exp_id in _cancel:
                    await _set(db, exp, status="cancelled", message="Cancelled. Models tried so far are listed below.", finished_at=utcnow())
                else:
                    msg = "Stopped at the time limit. Results come from the models tried so far." if stopped == "time limit" else "Finished."
                    await _set(db, exp, status="done", message=msg, generation=exp.total_generations if not stopped else exp.generation, finished_at=utcnow())
        except P.DataError as e:
            await db.rollback()
            exp = await db.get(Experiment, exp_id, populate_existing=True)
            await _set(db, exp, status="failed", message=str(e)[:300], finished_at=utcnow())
        except asyncio.CancelledError:
            raise
        except Exception:
            log.exception("experiment %s crashed", exp_id)
            await db.rollback()
            exp = await db.get(Experiment, exp_id, populate_existing=True)
            await _set(db, exp, status="failed", finished_at=utcnow(),
                       message="Something went wrong while training. Try again, or use a smaller dataset or fewer model families.")


async def recover() -> None:
    """After a restart, jobs that were queued/running cannot continue."""
    async with SessionLocal() as db:
        rows = (await db.execute(select(Experiment).where(Experiment.status.in_(ACTIVE)))).scalars().all()
        for e in rows:
            e.status, e.message, e.finished_at = "failed", "The server restarted while this ran. Please start it again.", utcnow()
        await db.commit()


async def retention_loop() -> None:
    while True:
        try:
            cutoff = utcnow() - timedelta(days=settings.retention_days)
            async with SessionLocal() as db:
                old = select(Experiment.id).where(Experiment.created_at < cutoff, Experiment.status.notin_(ACTIVE))
                await db.execute(delete(Trial).where(Trial.experiment_id.in_(old)))
                await db.execute(delete(Experiment).where(Experiment.created_at < cutoff, Experiment.status.notin_(ACTIVE)))
                await db.execute(delete(Dataset).where(Dataset.created_at < cutoff, Dataset.id.notin_(select(Experiment.dataset_id))))
                await db.commit()
        except Exception:
            log.exception("retention cleanup failed")
        await asyncio.sleep(6 * 3600)
