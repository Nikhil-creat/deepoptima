"""Evolution loop: sample -> dispatch -> collect -> NSGA-II -> next generation. Runs inside the API process
(or a dedicated container) and persists everything in Postgres."""
import asyncio, json, uuid
import redis.asyncio as aioredis
from app.config import settings
from datetime import datetime, timezone
from sqlalchemy import select
from app.db.models import Experiment, Trial, TrialStatus, ExperimentStatus, SearchSpace
from app.db.session import SessionLocal
from app.nas.genotype import random_genotype, DEFAULT_SPACE
from app.nas.evolution import nsga2_select, next_generation
from app.nas.adaptive import adapt_weights
from app.workers.tasks import run_trial
from app.sandbox.wasm_runner import run_fitness


async def run_experiment(exp_id: uuid.UUID, epochs: int = 3):
    async with SessionLocal() as db:
        exp = await db.get(Experiment, exp_id)
        space = (await db.get(SearchSpace, exp.search_space_id)).spec or DEFAULT_SPACE
        exp.status = ExperimentStatus.running; await db.commit()
        pop = [random_genotype(space) for _ in range(exp.population_size)]
        gw = None
        rds = aioredis.from_url(settings.redis_url, **settings.redis_kwargs())
        for gen in range(exp.max_generations):
            await db.refresh(exp)                                  # honour pause / resume from the API
            while exp.status == ExperimentStatus.paused:
                await asyncio.sleep(5); await db.refresh(exp)
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
            if exp.custom_fitness_wasm:                              # user-supplied Wasm fitness (sandboxed)
                for t in trials:
                    if t.status == TrialStatus.completed:
                        try: t.custom_score = run_fitness(exp.custom_fitness_wasm, t.accuracy, t.latency_ms, float(t.params))
                        except Exception as ex: t.error = f"custom fitness failed: {ex}"[:500]
            await db.commit()
            failed = [{"id": str(t.id), "genotype": t.genotype, "error": t.error, "loss_curve": t.loss_curve}
                      for t in trials if t.status in (TrialStatus.failed, TrialStatus.timeout)]
            if failed and (settings.groq_api_key or settings.gemini_api_key):   # agent swarm reviews failures (RLAIF-style)
                try:
                    from app.llm.gateway import LLMGateway
                    from app.agents.feedback import review_failures
                    if gw is None:
                        gw = LLMGateway(rds); await gw.refresh_models()
                    await review_failures(str(exp.id), failed, gw)
                except Exception:
                    pass                                                 # advisory only: never break the search
            rows = (await db.execute(select(Trial).where(Trial.experiment_id == exp.id,
                                                         Trial.status == TrialStatus.completed))).scalars().all()
            if not rows: break
            dicts = [{"id": str(r.id), "genotype": r.genotype, "accuracy": (r.custom_score if r.custom_score is not None else r.accuracy),
                      "latency_ms": r.latency_ms, "params": r.params} for r in rows]
            elite, ranks = nsga2_select(dicts, exp.population_size)
            for r, rk in zip(rows, ranks): r.pareto_rank = rk
            await db.commit()
            try: prior = json.loads(await rds.get(f"exp:{exp.id}:opw") or "null")   # swarm judge weights (optional)
            except Exception: prior = None
            weights = adapt_weights([{"genotype": r.genotype, "pareto_rank": r.pareto_rank} for r in rows], prior)
            pop = next_generation(elite, exp.population_size, space, op_weights=weights)
        await rds.close()
        exp.status = ExperimentStatus.done; await db.commit()
