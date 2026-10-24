"""Adaptive operator selection (multi-armed-bandit style meta-optimisation of the search heuristics).
Operators whose offspring land on the Pareto front more often get sampled more often. Pure Python, no torch needed."""
from typing import Sequence

OP_NAMES = ["add", "remove", "type", "width", "kernel", "act", "skip", "hparams"]   # same order as evolution.OPS


def adapt_weights(trials: Sequence[dict], prior: Sequence[float] | None = None,
                  floor: float = 0.15, smooth: float = 2.0, blend: float = 0.5) -> list[float]:
    """trials: dicts with 'genotype' (containing 'ops') and 'pareto_rank'.
    prior: optional weights from the agent swarm judge (RLAIF signal), blended in with weight `blend`."""
    wins = {n: 0 for n in OP_NAMES}; tot = {n: 0 for n in OP_NAMES}
    for t in trials:
        ops = (t.get("genotype") or {}).get("ops") or []
        win = 1 if t.get("pareto_rank") == 0 else 0
        for o in set(ops):
            if o in tot:
                tot[o] += 1; wins[o] += win
    w = [max(floor, (wins[n] + 1) / (tot[n] + smooth)) for n in OP_NAMES]   # Beta-style prior pulls to ~0.5
    s = sum(w); w = [x * len(w) / s for x in w]                             # mean 1
    if prior and len(prior) == len(OP_NAMES) and sum(prior) > 0:
        ps = sum(prior); p = [x * len(prior) / ps for x in prior]
        w = [(1 - blend) * a + blend * b for a, b in zip(w, p)]
    return w
