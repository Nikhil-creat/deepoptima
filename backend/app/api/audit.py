"""Admin-only audit endpoints: recent entries and hash-chain verification."""
from fastapi import APIRouter, Depends
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from app.audit_chain import verify_rows
from app.db.models import AuditLog, Role, User
from app.db.session import get_db
from app.security import require

router = APIRouter(prefix="/audit", tags=["audit"])

@router.get("/verify")
async def verify(db: AsyncSession = Depends(get_db), u: User = Depends(require(Role.admin))):
    rows = (await db.execute(select(AuditLog).order_by(AuditLog.id))).scalars().all()
    return verify_rows(rows)

@router.get("")
async def recent(limit: int = 50, db: AsyncSession = Depends(get_db), u: User = Depends(require(Role.admin))):
    q = select(AuditLog).order_by(AuditLog.id.desc()).limit(min(max(limit, 1), 200))
    return [{"id": r.id, "ts": r.ts, "actor": str(r.actor_id), "action": r.action, "resource": r.resource} for r in (await db.execute(q)).scalars()]
