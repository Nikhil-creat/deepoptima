"""Agent-swarm feedback loop: failed trials -> LangGraph swarm -> averaged operator weights published to Redis (RLAIF-style)."""
import asyncio
from app.agents.rag import embed
from app.agents.swarm import build_swarm, publish_weights

async def review_failures(exp_id: str, failed: list[dict], gw) -> list[float] | None:
    if not failed: return None
    swarm = build_swarm(gw, embed)
    ws: list[list[float]] = []
    for t in failed[:3]:                                   # cap LLM spend per generation
        out = await asyncio.wait_for(swarm.ainvoke({"trial": t}), timeout=120)
        w = out.get("op_weights")
        if isinstance(w, list) and len(w) == 8 and all(isinstance(x, (int, float)) and x >= 0 for x in w) and sum(w) > 0:
            ws.append([float(x) for x in w])
    if not ws: return None
    avg = [sum(c) / len(ws) for c in zip(*ws)]
    await publish_weights(exp_id, avg)
    return avg
