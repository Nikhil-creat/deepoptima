import hashlib, json
from datetime import datetime, timedelta, timezone
from cryptography.fernet import Fernet
from fastapi import Depends, HTTPException
from fastapi.security import OAuth2PasswordBearer
from jose import jwt, JWTError
from passlib.context import CryptContext
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from app.audit_chain import chain_hash
from app.config import settings
from app.db.models import AuditLog, Role, User
from app.db.session import get_db

pwd = CryptContext(schemes=["bcrypt"], deprecated="auto")
oauth2 = OAuth2PasswordBearer(tokenUrl="/auth/token")

def vault() -> Fernet:
    return Fernet(settings.fernet_key.encode())

def make_token(user: User, minutes: int = 60) -> str:
    exp = datetime.now(timezone.utc) + timedelta(minutes=minutes)
    return jwt.encode({"sub": str(user.id), "role": user.role.value, "exp": exp}, settings.jwt_secret, settings.jwt_alg)

async def current_user(token: str = Depends(oauth2), db: AsyncSession = Depends(get_db)) -> User:
    try:
        uid = jwt.decode(token, settings.jwt_secret, [settings.jwt_alg])["sub"]
    except JWTError:
        raise HTTPException(401, "Invalid token")
    user = await db.get(User, uid)
    if not user: raise HTTPException(401, "Unknown user")
    return user

def require(*roles: Role):
    async def dep(u: User = Depends(current_user)) -> User:
        if u.role not in roles and u.role != Role.admin:
            raise HTTPException(403, "Insufficient role")
        return u
    return dep

async def audit(db: AsyncSession, actor, action: str, resource: str, detail: dict | None = None):
    """Hash-chained append-only audit entry."""
    last = (await db.execute(select(AuditLog).order_by(AuditLog.id.desc()).limit(1))).scalar_one_or_none()
    prev = last.hash if last else ""
    db.add(AuditLog(actor_id=actor, action=action, resource=resource, detail=detail or {},
                    prev_hash=prev, hash=chain_hash(actor, action, resource, detail, prev)))
