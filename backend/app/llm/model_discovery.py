"""Auto-detect the best currently-available Groq / Gemini models from each provider's model-list API.
Result is cached in Redis (6h) and refreshed automatically when a call fails with 'model not found'."""
import json, re
import httpx

NOISE = re.compile(r"(whisper|tts|guard|embed|image|imagen|veo|aqa|audio|live|robotics|transcri|moderation|safeguard|orpheus|playai|dall)", re.I)
GEMINI_NOISE = re.compile(r"(gemma|learnlm|nano|computer-use)", re.I)

def _ver(i: str) -> float:
    nums = re.findall(r"\d+(?:\.\d+)?", i)[:3]
    return sum(float(n) / (1000 ** k) for k, n in enumerate(nums))

def _stable(i: str) -> int:
    return 0 if re.search(r"(preview|exp|experimental)", i, re.I) else 1

def _best(ids: list[str], rx: str | None = None, exclude: str | None = None) -> str | None:
    c = [i for i in ids if (not rx or re.search(rx, i, re.I)) and not (exclude and re.search(exclude, i, re.I))]
    return sorted(c, key=lambda i: (_stable(i), _ver(i)), reverse=True)[0] if c else None

async def discover_groq(key: str) -> dict:
    async with httpx.AsyncClient(timeout=15) as c:
        r = await c.get("https://api.groq.com/openai/v1/models", headers={"Authorization": f"Bearer {key}"})
        r.raise_for_status()
    ids = [m["id"] for m in r.json().get("data", []) if not NOISE.search(m["id"])]
    fast = _best(ids, r"(instant|8b|flash|mini|small)") or _best(ids)
    deep = _best(ids, r"(70b|versatile|120b|large|maverick|kimi|qwen)") or fast
    return {"fast": fast, "deep": deep, "count": len(ids)}

async def discover_gemini(key: str) -> dict:
    async with httpx.AsyncClient(timeout=15) as c:
        r = await c.get("https://generativelanguage.googleapis.com/v1beta/models", params={"key": key, "pageSize": 200})
        r.raise_for_status()
    ids = [m["name"].removeprefix("models/") for m in r.json().get("models", [])
           if "generateContent" in m.get("supportedGenerationMethods", []) and not NOISE.search(m["name"]) and not GEMINI_NOISE.search(m["name"])]
    fast = _best(ids, r"flash", exclude=r"(lite|8b)") or _best(ids, r"(flash|lite)") or _best(ids)
    deep = _best(ids, r"pro") or fast
    return {"fast": fast, "deep": deep, "count": len(ids)}

async def discover_all(groq_key: str, gemini_key: str, redis=None, ttl: int = 21600, force: bool = False) -> dict:
    if redis and not force:
        cached = await redis.get("models:detected")
        if cached: return json.loads(cached)
    out: dict = {}
    for name, fn, key in (("groq", discover_groq, groq_key), ("gemini", discover_gemini, gemini_key)):
        if key:
            try: out[name] = await fn(key)
            except Exception as e: out[name] = {"error": str(e)[:120]}
    if redis and out: await redis.set("models:detected", json.dumps(out), ex=ttl)
    return out
