"""Offline-friendly retrieval: signed feature-hashing embedder (no API key / model download needed) + Qdrant ingest."""
import hashlib, math, pathlib, re

DIM = 256
COLLECTION = "whitepapers"

def hash_embed(text: str, dim: int = DIM) -> list[float]:
    toks = re.findall(r"[a-z0-9]+", text.lower())
    v = [0.0] * dim
    for tok in toks + [a + "_" + b for a, b in zip(toks, toks[1:])]:
        h = int(hashlib.md5(tok.encode()).hexdigest(), 16)
        v[h % dim] += 1.0 if (h >> 64) & 1 else -1.0
    n = math.sqrt(sum(x * x for x in v)) or 1.0
    return [x / n for x in v]

async def embed(text: str) -> list[float]:
    return hash_embed(text)

def chunk(text: str, size: int = 700) -> list[str]:
    out, cur = [], ""
    for para in re.split(r"\n\s*\n", text.strip()):
        if len(cur) + len(para) > size and cur: out.append(cur.strip()); cur = ""
        cur += para + "\n\n"
    if cur.strip(): out.append(cur.strip())
    return out

async def ingest(folder: str | pathlib.Path | None = None, url: str | None = None) -> int:
    from qdrant_client import AsyncQdrantClient
    from qdrant_client.models import Distance, PointStruct, VectorParams
    from app.config import settings
    folder = pathlib.Path(folder or pathlib.Path(__file__).parent / "papers")
    client = AsyncQdrantClient(url=url or settings.qdrant_url)
    if not await client.collection_exists(COLLECTION):
        await client.create_collection(COLLECTION, vectors_config=VectorParams(size=DIM, distance=Distance.COSINE))
    pts = []
    for f in sorted(folder.glob("*.md")):
        for i, c in enumerate(chunk(f.read_text(encoding="utf-8"))):
            pid = int(hashlib.md5(f"{f.name}:{i}".encode()).hexdigest()[:15], 16)
            pts.append(PointStruct(id=pid, vector=hash_embed(c), payload={"text": c, "source": f.name}))
    if pts: await client.upsert(COLLECTION, pts)
    return len(pts)
