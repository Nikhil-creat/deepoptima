"""Evolution loop: sample -> dispatch -> collect -> NSGA-II -> next generation. Runs inside the API process
(or a dedicated container) and persists everything in Postgres."""
import asyncio, uuid
from datetime import datetime, timezone
from sqlalchemy import select
from app.db.models import Experiment, Trial, TrialStatus, ExperimentStatus, SearchSpace
from app.db.session import SessionLocal
from app.nas.genotype import random_genotype, DEFAULT_SPACE
from app.nas.evolution import nsga2_select, next_generation
from app.workers.tasks import run_trial


async def run_experiment(exp_id: uuid.UUID, epochs: int = 3):
    async with SessionLocal() as db:
        exp = await db.get(Experiment, exp_id)
        space = (await db.get(SearchSpace, exp.search_space_id)).spec or DEFAULT_SPACE
        exp.status = ExperimentStatus.running; await db.commit()
        pop = [random_genotype(space) for _ in range(exp.population_size)]
        for gen in range(exp.max_generations):
            trials = []
            for g in pop:
                t = Trial(experiment_id=exp.id, generation=gen, genotype=g.to_dict()); db.add(t); trials.append(t)
            await db.commit()
            handles = [(t, run_trial.apply_async(args=[str(exp.id), str(t.id), t.genotype, epochs], queue="gpu")) for t in trials]
            for t, h in handles:
                res = await asyncio.to_thread(h.get, timeout=3600, propagate=False)
                res = res if isinstance(res, dict) else {"status": "failed", "error": str(res)}
                t.status = TrialStatus(res["status"]); t.error = res.get("error"); t.loss_curve = res.get("loss_curve", [])
                for k in ("accuracy", "latency_ms", "params", "checkpoint_key", "onnx_key"):
                    setattr(t, k, res.get(k))
                t.finished_at = datetime.now(timezone.utc)
            await db.commit()
            rows = (await db.execute(select(Trial).where(Trial.experiment_id == exp.id,
                                                         Trial.status == TrialStatus.completed))).scalars().all()
            if not rows: break
            dicts = [{"id": str(r.id), "genotype": r.genotype, "accuracy": r.accuracy,
                      "latency_ms": r.latency_ms, "params": r.params} for r in rows]
            elite, ranks = nsga2_select(dicts, exp.population_size)
            for r, rk in zip(rows, ranks): r.pareto_rank = rk
            await db.commit()
            pop = next_generation(elite, exp.population_size, space)
        exp.status = ExperimentStatus.done; await db.commit()
