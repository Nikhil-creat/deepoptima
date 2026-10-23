"""Dual-engine LLM gateway: Groq (fast/tool-calling) + Gemini (deep/long-context),
Redis semantic cache, cost/latency-aware routing, automatic failover, streaming."""
from __future__ import annotations
import asyncio, hashlib, json, time
from dataclasses import dataclass
from enum import Enum
from typing import AsyncIterator, Awaitable, Callable
import numpy as np
import redis.asyncio as aioredis
from groq import AsyncGroq
import google.generativeai as genai
from app.config import settings
from app.llm.guardrails import screen_prompt
from app.llm.model_discovery import discover_all


class Purpose(str, Enum):
    FAST = "fast"      # heuristic mutation decisions, tool calls  -> Groq first
    DEEP = "deep"      # loss-curve analysis, long-context RAG      -> Gemini first


# USD per 1M tokens (in, out) - update from provider pricing pages.
PRICING = {"groq": (0.59, 0.79), "gemini": (1.25, 5.00)}


def count_tokens(text: str) -> int:
    return max(1, len(text) // 4)  # cheap estimate; swap for tiktoken/provider counter


def cost_usd(provider: str, pt: int, ct: int) -> float:
    i, o = PRICING[provider]
    return (pt * i + ct * o) / 1_000_000


@dataclass
class LLMResult:
    text: str
    provider: str
    model: str
    prompt_tokens: int
    completion_tokens: int
    latency_ms: float
    cache_hit: bool = False
    failover_from: str | None = None


class SemanticCache:
    """Exact-hash fast path + cosine-similarity lookup over stored embeddings.
    Provide an async embedder (e.g. Gemini text-embedding) to enable the semantic path."""

    def __init__(self, r: aioredis.Redis, embedder: Callable[[str], Awaitable[np.ndarray]] | None = None,
                 threshold: float = 0.93, ttl: int = 3600, max_scan: int = 500):
        self.r, self.embedder, self.threshold, self.ttl, self.max_scan = r, embedder, threshold, ttl, max_scan

    @staticmethod
    def _key(prompt: str) -> str:
        return "llmcache:" + hashlib.sha256(prompt.strip().lower().encode()).hexdigest()

    async def get(self, prompt: str) -> str | None:
        hit = await self.r.get(self._key(prompt))
        if hit:
            return json.loads(hit)["text"]
        if not self.embedder:
            return None
        q = await self.embedder(prompt)
        async for k in self.r.scan_iter("llmvec:*", count=self.max_scan):
            raw = await self.r.get(k)
            if not raw:
                continue
            d = json.loads(raw)
            v = np.array(d["vec"], dtype=np.float32)
            sim = float(np.dot(q, v) / (np.linalg.norm(q) * np.linalg.norm(v) + 1e-9))
            if sim >= self.threshold:
                return d["text"]
        return None

    async def set(self, prompt: str, text: str):
        await self.r.set(self._key(prompt), json.dumps({"text": text}), ex=self.ttl)
        if self.embedder:
            v = (await self.embedder(prompt)).tolist()
            await self.r.set("llmvec:" + hashlib.md5(prompt.encode()).hexdigest(),
                             json.dumps({"vec": v, "text": text}), ex=self.ttl)


class LLMGateway:
    def __init__(self, redis_client: aioredis.Redis | None = None, embedder=None,
                 usage_sink: Callable[[LLMResult, str], Awaitable[None]] | None = None):
        self.groq = AsyncGroq(api_key=settings.groq_api_key) if settings.groq_api_key else None
        if settings.gemini_api_key:
            genai.configure(api_key=settings.gemini_api_key)
        self.has_gemini = bool(settings.gemini_api_key)
        self._redis = redis_client
        self.models = {"groq": {"fast": settings.groq_model, "deep": settings.groq_model},
                       "gemini": {"fast": settings.gemini_model, "deep": settings.gemini_model}}
        self.cache = SemanticCache(redis_client, embedder) if redis_client else None
        self.usage_sink = usage_sink
        self._cooldown: dict[str, float] = {}  # provider -> unix time until which it is skipped (rate limit)

    # ---- model auto-detection ----
    def _model(self, provider: str, purpose: Purpose) -> str:
        cfg = settings.groq_model if provider == "groq" else settings.gemini_model
        if cfg != "auto": return cfg
        return self.models[provider]["fast" if purpose == Purpose.FAST else "deep"]

    async def refresh_models(self, force: bool = False) -> dict:
        found = await discover_all(settings.groq_api_key, settings.gemini_api_key, self._redis, force=force)
        for p, d in found.items():
            if d.get("fast"): self.models[p] = {"fast": d["fast"], "deep": d["deep"]}
        return found

    # ---- routing ----
    def _order(self, purpose: Purpose, prompt_tokens: int) -> list[str]:
        order = ["groq", "gemini"] if purpose == Purpose.FAST else ["gemini", "groq"]
        if prompt_tokens > 24_000:            # exceeds typical Groq context -> force Gemini first
            order = ["gemini", "groq"]
        now = time.time()
        order = [p for p in order if self._cooldown.get(p, 0) < now] or order
        return [p for p in order if (p == "groq" and self.groq) or (p == "gemini" and self.has_gemini)]

    async def complete(self, prompt: str, purpose: Purpose = Purpose.FAST, system: str = "",
                       use_cache: bool = True, untrusted: bool = True) -> LLMResult:
        prompt = screen_prompt(prompt, untrusted=untrusted)
        if use_cache and self.cache:
            cached = await self.cache.get(system + "\n" + prompt)
            if cached is not None:
                res = LLMResult(cached, "cache", "semantic", 0, 0, 0.0, cache_hit=True)
                await self._track(res, purpose.value)
                return res
        pt = count_tokens(system + prompt)
        order = self._order(purpose, pt)
        if not order:
            raise RuntimeError("No LLM providers configured")
        first_err, failed_from = None, None
        for provider in order:
            try:
                try:
                    res = await asyncio.wait_for(self._call(provider, prompt, system, purpose), timeout=60)
                except Exception as e1:
                    if any(x in str(e1).lower() for x in ("404", "not found", "decommission", "deprecated")):
                        await self.refresh_models(force=True)       # model retired -> re-detect and retry once
                        res = await asyncio.wait_for(self._call(provider, prompt, system, purpose), timeout=60)
                    else: raise
                res.failover_from = failed_from
                if use_cache and self.cache:
                    await self.cache.set(system + "\n" + prompt, res.text)
                await self._track(res, purpose.value)
                return res
            except Exception as e:  # rate limit / timeout / provider error -> fail over
                first_err = first_err or e
                failed_from = provider
                if "429" in str(e) or "rate" in str(e).lower():
                    self._cooldown[provider] = time.time() + 30
        raise RuntimeError(f"All providers failed: {first_err}")

    async def _call(self, provider: str, prompt: str, system: str, purpose: Purpose = Purpose.FAST) -> LLMResult:
        t0 = time.perf_counter(); model = self._model(provider, purpose)
        if provider == "groq":
            msgs = ([{"role": "system", "content": system}] if system else []) + [{"role": "user", "content": prompt}]
            r = await self.groq.chat.completions.create(model=model, messages=msgs, temperature=0.3)
            text, u = r.choices[0].message.content, r.usage
            return LLMResult(text, "groq", model, u.prompt_tokens, u.completion_tokens,
                             (time.perf_counter() - t0) * 1000)
        r = await genai.GenerativeModel(model).generate_content_async((system + "\n\n" if system else "") + prompt)
        pt, ct = count_tokens(system + prompt), count_tokens(r.text)
        return LLMResult(r.text, "gemini", model, pt, ct, (time.perf_counter() - t0) * 1000)

    async def stream(self, prompt: str, purpose: Purpose = Purpose.DEEP, system: str = "") -> AsyncIterator[str]:
        """Streams tokens; if the first provider fails before emitting anything, falls over to the next."""
        for provider in self._order(purpose, count_tokens(prompt)):
            emitted = False
            try:
                if provider == "groq":
                    msgs = ([{"role": "system", "content": system}] if system else []) + [{"role": "user", "content": prompt}]
                    s = await self.groq.chat.completions.create(model=self._model('groq', purpose), messages=msgs, stream=True)
                    async for chunk in s:
                        delta = chunk.choices[0].delta.content
                        if delta:
                            emitted = True
                            yield delta
                else:
                    s = await genai.GenerativeModel(self._model('gemini', purpose)).generate_content_async(system + "\n\n" + prompt, stream=True)
                    async for chunk in s:
                        if chunk.text:
                            emitted = True
                            yield chunk.text
                return
            except Exception:
                if emitted:
                    raise
                continue
        raise RuntimeError("All providers failed")

    async def _track(self, res: LLMResult, purpose: str):
        if self.usage_sink:
            await self.usage_sink(res, purpose)
