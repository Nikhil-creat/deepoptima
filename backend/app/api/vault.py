"""Encrypted credential vault (Fernet). Secrets are write-only except for an audited reveal by owner/admin."""
import uuid
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from app.config import settings
from app.db.models import Credential, Role, User
from app.db.session import get_db
from app.security import audit, require, vault

router = APIRouter(prefix="/vault", tags=["vault"])
R = Role

class SecretIn(BaseModel):
    name: str = Field(min_length=1, max_length=100)
    secret: str = Field(min_length=1, max_length=4000)

def _f():
    if not settings.fernet_key: raise HTTPException(503, "FERNET_KEY is not configured")
    return vault()

@router.post("", status_code=201)
async def create(b: SecretIn, db: AsyncSession = Depends(get_db), u: User = Depends(require(R.researcher))):
    c = Credential(owner_id=u.id, name=b.name, ciphertext=_f().encrypt(b.secret.encode()))
    db.add(c); await db.flush(); await audit(db, u.id, "vault.create", b.name); await db.commit()
    return {"id": str(c.id), "name": c.name}

@router.get("")
async def list_mine(db: AsyncSession = Depends(get_db), u: User = Depends(require(R.researcher))):
    q = select(Credential) if u.role == R.admin else select(Credential).where(Credential.owner_id == u.id)
    return [{"id": str(c.id), "name": c.name, "created_at": c.created_at} for c in (await db.execute(q)).scalars()]

@router.get("/{cid}")
async def reveal(cid: uuid.UUID, db: AsyncSession = Depends(get_db), u: User = Depends(require(R.researcher))):
    c = await db.get(Credential, cid)
    if not c or (c.owner_id != u.id and u.role != R.admin): raise HTTPException(404)
    await audit(db, u.id, "vault.reveal", c.name); await db.commit()
    return {"id": str(c.id), "name": c.name, "secret": _f().decrypt(c.ciphertext).decode()}

@router.delete("/{cid}", status_code=204)
async def delete(cid: uuid.UUID, db: AsyncSession = Depends(get_db), u: User = Depends(require(R.researcher))):
    c = await db.get(Credential, cid)
    if not c or (c.owner_id != u.id and u.role != R.admin): raise HTTPException(404)
    await audit(db, u.id, "vault.delete", c.name); await db.delete(c); await db.commit()
