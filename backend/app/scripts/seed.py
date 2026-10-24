"""Create an admin user and (optionally) a clearly-labelled SYNTHETIC demo experiment so the dashboard's
"Connect your backend" mode has data on an API-only deployment (no GPU).
    python -m app.scripts.seed --email you@example.com --password 'at-least-10-chars' --demo
"""
import argparse, asyncio, math, random
from sqlalchemy import select
from app.db.models import Base, Experiment, ExperimentStatus, Role, SearchSpace, Trial, TrialStatus, User
from app.db.session import SessionLocal, engine
from app.nas.space import DEFAULT_SPACE
from app.security import pwd

TYPES = ["conv", "res", "mbconv"]

def fake_trial(gen: int) -> dict:
    blocks, prev, params, flops = [], 32, 0.0, 0.0
    n, strides = random.randint(3, 9), set(random.sample(range(9), 3))
    for i in range(n):
        t, c, k = random.choice(TYPES), random.choice(DEFAULT_SPACE["channels"]), random.choice([3, 5, 7])
        mult = {"conv": 1.0, "res": 2.0, "mbconv": 1.6}[t]
        params += prev * c * k * k * mult; flops += c * k * k * mult; prev = c
        blocks.append({"type": t, "channels": c, "kernel": k, "stride": 2 if i in strides else 1,
                       "act": random.choice(DEFAULT_SPACE["acts"]), "skip": random.random() < 0.5, "expand": 4, "heads": 4})
    lr = 10 ** random.uniform(-4, -1.6)
    acc = max(0.2, min(0.95, 0.52 + 0.4 * (1 - math.exp(-params / 220000)) + 0.005 * sum(b["skip"] for b in blocks)
                       - abs(math.log10(lr) + 3) * 0.02 + random.uniform(-0.01, 0.01)))
    final = 2.3 * (1 - acc) + 0.1
    return {"generation": gen, "accuracy": acc, "latency_ms": 0.3 + flops / 900, "params": int(params),
            "loss_curve": [final + (2.3 - final) * math.exp(-0.7 * e) for e in range(6)],
            "genotype": {"blocks": blocks, "lr": lr, "weight_decay": 1e-4, "batch_size": 128, "optimizer": "adamw", "dropout": 0.1, "ops": []}}

def pareto_ranks(ts: list[dict]) -> list[int]:
    v = [(1 - t["accuracy"], t["latency_ms"], t["params"]) for t in ts]
    dom = lambda a, b: all(x <= y for x, y in zip(a, b)) and any(x < y for x, y in zip(a, b))
    ranks, left, r = [-1] * len(ts), set(range(len(ts))), 0
    while left:
        front = [i for i in left if not any(dom(v[j], v[i]) for j in left if j != i)]
        for i in front: ranks[i] = r
        left -= set(front); r += 1
    return ranks

async def main(a):
    if len(a.password) < 10: raise SystemExit("password must be at least 10 characters")
    async with engine.begin() as c: await c.run_sync(Base.metadata.create_all)
    async with SessionLocal() as db:
        u = (await db.execute(select(User).where(User.email == a.email))).scalar_one_or_none()
        if not u:
            u = User(email=a.email, password_hash=pwd.hash(a.password), role=Role.admin); db.add(u); await db.flush()
            print("created admin", a.email)
        else: print("user exists:", a.email)
        if a.demo:
            ss = SearchSpace(name="demo-space", family="cnn", spec=DEFAULT_SPACE); db.add(ss); await db.flush()
            e = Experiment(owner_id=u.id, search_space_id=ss.id, name="Demo (synthetic data, seeded)", population_size=12,
                           max_generations=8, status=ExperimentStatus.done)
            db.add(e); await db.flush()
            ts = [fake_trial(g) for g in range(8) for _ in range(12)]
            for t, rk in zip(ts, pareto_ranks(ts)):
                db.add(Trial(experiment_id=e.id, status=TrialStatus.completed, pareto_rank=rk, **t))
            print("seeded demo experiment with", len(ts), "synthetic trials")
        await db.commit()

if __name__ == "__main__":
    p = argparse.ArgumentParser(); p.add_argument("--email", required=True); p.add_argument("--password", required=True)
    p.add_argument("--demo", action="store_true"); asyncio.run(main(p.parse_args()))
