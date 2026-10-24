"""Mutation, crossover and NSGA-II multi-objective selection (accuracy max, latency min, params min)."""
from __future__ import annotations
import math, random
from typing import Sequence
from app.nas.genotype import Genotype, BlockGene, DEFAULT_SPACE, random_block


# ---------------- mutation ----------------
def _mut_add(g, s):
    if len(g.blocks) < s["max_blocks"]:
        g.blocks.insert(random.randrange(len(g.blocks) + 1), random_block(s))

def _mut_remove(g, s):
    if len(g.blocks) > s["min_blocks"]:
        g.blocks.pop(random.randrange(len(g.blocks)))

def _mut_type(g, s):
    b = random.choice(g.blocks); b.type = random.choice(s["blocks"])

def _mut_width(g, s):
    b = random.choice(g.blocks); b.channels = random.choice(s["channels"])

def _mut_kernel(g, s):
    b = random.choice(g.blocks)
    if b.type != "vit": b.kernel = random.choice(s["kernels"])

def _mut_act(g, s):
    random.choice(g.blocks).act = random.choice(s["acts"])

def _mut_skip(g, s):
    b = random.choice(g.blocks); b.skip = not b.skip

def _mut_hparams(g, s):
    g.lr = min(s["lr"][1], max(s["lr"][0], g.lr * math.exp(random.gauss(0, 0.5))))
    g.dropout = min(s["dropout"][1], max(s["dropout"][0], g.dropout + random.gauss(0, 0.05)))
    g.optimizer = random.choice(["adamw", "sgd"])
    g.batch_size = random.choice([64, 128, 256])

OPS = [_mut_add, _mut_remove, _mut_type, _mut_width, _mut_kernel, _mut_act, _mut_skip, _mut_hparams]


def mutate(g: Genotype, space: dict = DEFAULT_SPACE, rate: float = 0.5, weights: Sequence[float] | None = None) -> Genotype:
    """`weights` lets the agent swarm bias operator choice (meta-optimisation of search heuristics)."""
    child = g.clone(); child.ops = []
    n_ops = 1 + (random.random() < rate) + (random.random() < rate * 0.5)
    for op in random.choices(OPS, weights=weights, k=n_ops):
        op(child, space); child.ops.append(op.__name__.removeprefix('_mut_'))
    # keep stride schedule sane: at most max_stride_blocks downsamples
    seen = 0
    for b in child.blocks:
        if b.stride > 1:
            seen += 1
            if seen > space["max_stride_blocks"]: b.stride = 1
    return child


def crossover(a: Genotype, b: Genotype) -> Genotype:
    ca, cb = random.randint(1, len(a.blocks)), random.randint(0, len(b.blocks) - 1)
    child = a.clone()
    child.blocks = [x for x in a.clone().blocks[:ca]] + [x for x in b.clone().blocks[cb:]]
    for k in ("lr", "weight_decay", "batch_size", "optimizer", "dropout"):
        setattr(child, k, getattr(random.choice([a, b]), k))
    return child


# ---------------- multi-objective ----------------
def objectives(t: dict) -> tuple[float, float, float]:
    """Convert to minimisation vector: (1-acc, latency_ms, params_millions)."""
    return (1.0 - t["accuracy"], t["latency_ms"], t["params"] / 1e6)


def dominates(a: Sequence[float], b: Sequence[float]) -> bool:
    return all(x <= y for x, y in zip(a, b)) and any(x < y for x, y in zip(a, b))


def non_dominated_sort(objs: list[Sequence[float]]) -> list[list[int]]:
    n = len(objs)
    S = [[] for _ in range(n)]; cnt = [0] * n; fronts = [[]]
    for p in range(n):
        for q in range(n):
            if dominates(objs[p], objs[q]): S[p].append(q)
            elif dominates(objs[q], objs[p]): cnt[p] += 1
        if cnt[p] == 0: fronts[0].append(p)
    i = 0
    while fronts[i]:
        nxt = []
        for p in fronts[i]:
            for q in S[p]:
                cnt[q] -= 1
                if cnt[q] == 0: nxt.append(q)
        i += 1; fronts.append(nxt)
    return fronts[:-1]


def crowding_distance(objs: list[Sequence[float]], front: list[int]) -> dict[int, float]:
    d = {i: 0.0 for i in front}
    if len(front) <= 2:
        return {i: math.inf for i in front}
    for m in range(len(objs[0])):
        s = sorted(front, key=lambda i: objs[i][m])
        d[s[0]] = d[s[-1]] = math.inf
        rng = (objs[s[-1]][m] - objs[s[0]][m]) or 1.0
        for k in range(1, len(s) - 1):
            d[s[k]] += (objs[s[k + 1]][m] - objs[s[k - 1]][m]) / rng
    return d


def nsga2_select(trials: list[dict], k: int) -> tuple[list[dict], list[int]]:
    """Returns top-k trials and pareto rank for every trial (index-aligned)."""
    objs = [objectives(t) for t in trials]
    fronts = non_dominated_sort(objs)
    ranks = [0] * len(trials)
    chosen: list[int] = []
    for r, f in enumerate(fronts):
        for i in f: ranks[i] = r
        if len(chosen) + len(f) <= k:
            chosen += f
        else:
            cd = crowding_distance(objs, f)
            chosen += sorted(f, key=lambda i: -cd[i])[: k - len(chosen)]
            break
    return [trials[i] for i in chosen], ranks


def next_generation(parents: list[dict], size: int, space: dict = DEFAULT_SPACE, op_weights=None) -> list[Genotype]:
    """Binary tournament on pareto rank, then crossover (p=0.5) + mutation."""
    objs = [objectives(p) for p in parents]
    fr = non_dominated_sort(objs); rank = {i: r for r, f in enumerate(fr) for i in f}
    def pick():
        a, b = random.sample(range(len(parents)), 2) if len(parents) > 1 else (0, 0)
        return parents[a if rank[a] <= rank[b] else b]
    kids = []
    while len(kids) < size:
        p1 = Genotype.from_dict(pick()["genotype"])
        if random.random() < 0.5 and len(parents) > 1:
            p1 = crossover(p1, Genotype.from_dict(pick()["genotype"]))
        kids.append(mutate(p1, space, weights=op_weights))
    return kids
