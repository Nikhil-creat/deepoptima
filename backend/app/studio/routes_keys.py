"""Personal API keys (predictions + read-only experiments) and full data export."""
from fastapi import APIRouter, Depends, HTTPException, Request
from fastapi.responses import JSONResponse
from pydantic import BaseModel, Field
from sqlalchemy import delete, select
from sqlalchemy.ext.asyncio import AsyncSession
from .db import ApiKey, Dataset, Experiment, User, get_db, iso
from .deps import check_rate, count, current_user, dataset_out, experiment_out, user_out

router = APIRouter(prefix="/api")
MAX_KEYS = 5


def key_out(k: ApiKey) -> dict:
    return {"id": k.id, "name": k.name, "prefix": k.prefix, "created_at": iso(k.created_at), "last_used_at": iso(k.last_used_at)}


class KeyIn(BaseModel):
    name: str = Field(min_length=1, max_length=60)


@router.post("/me/keys", status_code=201)
async def create_key(b: KeyIn, request: Request, u: User = Depends(current_user), db: AsyncSession = Depends(get_db)):
    from .security import new_api_key
    check_rate(request, "keys", 10, 3600, u.id)
    if request.headers.get("authorization", "").lower().startswith("bearer dok_"):
        raise HTTPException(403, "Sign in to manage API keys.")
    if await count(db, ApiKey, ApiKey.user_id == u.id) >= MAX_KEYS:
        raise HTTPException(400, f"You can have up to {MAX_KEYS} API keys. Revoke one first.")
    key, prefix, h = new_api_key()
    k = ApiKey(user_id=u.id, name=b.name.strip()[:60], prefix=prefix, key_hash=h)
    db.add(k)
    await db.commit()
    await db.refresh(k)
    return {**key_out(k), "key": key}            # the full key is shown exactly once


@router.get("/me/keys")
async def list_keys(u: User = Depends(current_user), db: AsyncSession = Depends(get_db)):
    rows = (await db.execute(select(ApiKey).where(ApiKey.user_id == u.id).order_by(ApiKey.id.desc()))).scalars().all()
    return {"keys": [key_out(k) for k in rows]}


@router.delete("/me/keys/{kid}")
async def revoke_key(kid: int, u: User = Depends(current_user), db: AsyncSession = Depends(get_db)):
    r = await db.execute(delete(ApiKey).where(ApiKey.id == kid, ApiKey.user_id == u.id))
    await db.commit()
    if not r.rowcount:
        raise HTTPException(404, "Key not found.")
    return {"ok": True}


@router.get("/me/export")
async def export_data(u: User = Depends(current_user), db: AsyncSession = Depends(get_db)):
    """Everything we hold about you except raw files and model binaries (download those from their pages)."""
    ds = (await db.execute(select(Dataset).where(Dataset.owner_id == u.id))).scalars().all()
    ex = (await db.execute(select(Experiment).where(Experiment.owner_id == u.id))).scalars().all()
    keys = (await db.execute(select(ApiKey).where(ApiKey.user_id == u.id))).scalars().all()
    names = {d.id: d.name for d in ds}
    body = {"user": user_out(u), "datasets": [dataset_out(d, True) for d in ds],
            "experiments": [{**experiment_out(e, names.get(e.dataset_id)), "result": e.result} for e in ex], "api_keys": [key_out(k) for k in keys]}
    return JSONResponse(body, headers={"Content-Disposition": 'attachment; filename="deepoptima-my-data.json"'})
