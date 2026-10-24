"""LangGraph swarm: failed trial -> retrieve research (Qdrant) -> 3 specialist agents -> merged heuristic update.
RLAIF hook: the judge node scores proposals; scores are stored and used to reweight mutation operators."""
from __future__ import annotations
import json
from typing import TypedDict
from langgraph.graph import StateGraph, END
from qdrant_client import AsyncQdrantClient
from app.config import settings
from app.llm.gateway import LLMGateway, Purpose

class S(TypedDict, total=False):
    trial: dict; context: list[str]; hp: str; sec: str; eff: str; op_weights: list[float]; judge: dict

def build_swarm(gw: LLMGateway, embed):
    qd = AsyncQdrantClient(url=settings.qdrant_url)

    async def retrieve(s: S) -> S:
        v = await embed(f"{s['trial'].get('error','')} {json.dumps(s['trial']['genotype'])[:500]}")
        res = await qd.query_points("whitepapers", query=list(map(float, v)), limit=4)
        return {"context": [(h.payload or {}).get("text", "") for h in res.points]}

    async def _ask(role: str, s: S, purpose=Purpose.FAST) -> str:
        sys = f"You are the {role} in a neural architecture search system. Reply with concise JSON only."
        p = f"Failed trial: {json.dumps(s['trial'])[:3000]}\nResearch:\n" + "\n".join(s["context"])[:6000]
        return (await gw.complete(p, purpose, sys)).text

    async def hp_agent(s): return {"hp": await _ask("Hyperparameter Tuning Agent (return lr/batch/optimizer changes)", s)}
    async def sec_agent(s): return {"sec": await _ask("Architecture Security Auditor (flag adversarial/backdoor-prone patterns)", s)}
    async def eff_agent(s): return {"eff": await _ask("Resource Efficiency Optimizer (suggest param/latency reductions)", s, Purpose.DEEP)}

    async def judge(s: S) -> S:
        sys = 'Judge proposals. Return JSON {"op_weights":[8 floats for add,remove,type,width,kernel,act,skip,hparams],"score":0-1}'
        r = await gw.complete(f"HP:{s['hp']}\nSEC:{s['sec']}\nEFF:{s['eff']}", Purpose.DEEP, sys)
        try:
            d = json.loads(r.text.strip().strip("`").removeprefix("json"))
            return {"op_weights": d["op_weights"], "judge": d}
        except Exception:
            return {"op_weights": [1] * 8, "judge": {"score": 0}}

    g = StateGraph(S)
    for n, f in [("retrieve", retrieve), ("hp", hp_agent), ("sec", sec_agent), ("eff", eff_agent), ("judge", judge)]:
        g.add_node(n, f)
    g.set_entry_point("retrieve")
    g.add_edge("retrieve", "hp"); g.add_edge("hp", "sec"); g.add_edge("sec", "eff"); g.add_edge("eff", "judge"); g.add_edge("judge", END)
    return g.compile()


async def publish_weights(exp_id: str, weights: list[float], ttl: int = 86400):
    """Store the judge's operator weights so the orchestrator can blend them into adaptive selection."""
    import redis.asyncio as aioredis
    r = aioredis.from_url(settings.redis_url, **settings.redis_kwargs())
    try:
        await r.set(f"exp:{exp_id}:opw", json.dumps([float(x) for x in weights]), ex=ttl)
    finally:
        await r.close()
