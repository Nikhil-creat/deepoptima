import asyncio
from fastapi import APIRouter, Depends, HTTPException, Request
from pydantic import BaseModel, Field
from sqlalchemy import delete, func, select, update
from sqlalchemy.ext.asyncio import AsyncSession
from .db import Dataset, Experiment, Feedback, Trial, User, get_db, utcnow
from .deps import check_rate, client_ip, count, current_user, limiter, limits_out, user_out
from .security import DUMMY_HASH, clean_email, hash_password, make_token, password_problem, verify_password
from .settings import settings

router = APIRouter(prefix="/api")


def auth_response(u: User) -> dict:
    return {"token": make_token({"sub": str(u.id), "tv": u.token_version}, settings.jwt_secret, settings.token_hours), "user": user_out(u)}


class RegisterIn(BaseModel):
    email: str = Field(max_length=254)
    password: str = Field(max_length=128)
    name: str = Field(min_length=1, max_length=80)
    accept_terms: bool


class LoginIn(BaseModel):
    email: str = Field(max_length=254)
    password: str = Field(max_length=128)


@router.post("/auth/register", status_code=201)
async def register(b: RegisterIn, request: Request, db: AsyncSession = Depends(get_db)):
    check_rate(request, "register", 5, 3600)
    if not settings.registration_open:
        raise HTTPException(403, "Registration is closed right now.")
    if not b.accept_terms:
        raise HTTPException(400, "Please accept the Terms and the Privacy Policy.")
    email = clean_email(b.email)
    if not email:
        raise HTTPException(400, "Enter a valid email address.")
    if not b.name.strip():
        raise HTTPException(400, "Enter your name.")
    problem = password_problem(b.password)
    if problem:
        raise HTTPException(400, problem)
    if await count(db, User) >= settings.max_users:
        raise HTTPException(403, "Sign-ups are full right now. Please try again later.")
    if await db.scalar(select(User.id).where(User.email == email)):
        raise HTTPException(409, "An account with this email already exists. Try signing in.")
    u = User(email=email, name=b.name.strip()[:80], password_hash=await asyncio.to_thread(hash_password, b.password),
             is_admin=email in settings.admin_emails, last_login_at=utcnow())
    db.add(u)
    await db.commit()
    await db.refresh(u)
    return auth_response(u)


@router.post("/auth/login")
async def login(b: LoginIn, request: Request, db: AsyncSession = Depends(get_db)):
    check_rate(request, "login", 30, 600)
    email = (b.email or "").strip().lower()
    fail_key = f"fail:{email}"
    if limiter.count(fail_key, 900) >= 5:
        raise HTTPException(429, "Too many failed attempts. Try again in 15 minutes.", headers={"Retry-After": "900"})
    u = await db.scalar(select(User).where(User.email == email))
    ok = await asyncio.to_thread(verify_password, b.password, u.password_hash if u else DUMMY_HASH)
    if not u or not ok or not u.is_active:
        limiter.allow(fail_key, 10 ** 6, 900)
        raise HTTPException(401, "Incorrect email or password.")
    limiter.reset(fail_key)
    if email in settings.admin_emails and not u.is_admin:
        u.is_admin = True
    u.last_login_at = utcnow()
    await db.commit()
    return auth_response(u)


@router.get("/me")
async def me(u: User = Depends(current_user), db: AsyncSession = Depends(get_db)):
    return {"user": user_out(u), "limits": limits_out(),
            "usage": {"datasets": await count(db, Dataset, Dataset.owner_id == u.id), "experiments": await count(db, Experiment, Experiment.owner_id == u.id)}}


class ProfileIn(BaseModel):
    name: str = Field(min_length=1, max_length=80)


@router.patch("/me")
async def update_me(b: ProfileIn, u: User = Depends(current_user), db: AsyncSession = Depends(get_db)):
    if not b.name.strip():
        raise HTTPException(400, "Enter your name.")
    u.name = b.name.strip()[:80]
    await db.commit()
    return {"user": user_out(u)}


class PasswordIn(BaseModel):
    old_password: str = Field(max_length=128)
    new_password: str = Field(max_length=128)


@router.post("/me/password")
async def change_password(b: PasswordIn, request: Request, u: User = Depends(current_user), db: AsyncSession = Depends(get_db)):
    check_rate(request, "pw", 5, 900, u.id)
    if not await asyncio.to_thread(verify_password, b.old_password, u.password_hash):
        raise HTTPException(400, "Your current password is incorrect.")
    problem = password_problem(b.new_password)
    if problem:
        raise HTTPException(400, problem)
    u.password_hash = await asyncio.to_thread(hash_password, b.new_password)
    u.token_version += 1                      # signs out every other device
    await db.commit()
    return auth_response(u)


class DeleteMeIn(BaseModel):
    password: str = Field(max_length=128)


@router.delete("/me")
async def delete_me(b: DeleteMeIn, request: Request, u: User = Depends(current_user), db: AsyncSession = Depends(get_db)):
    check_rate(request, "del", 5, 900, u.id)
    if not await asyncio.to_thread(verify_password, b.password, u.password_hash):
        raise HTTPException(400, "Password is incorrect.")
    from . import runner
    ids = (await db.execute(select(Experiment.id).where(Experiment.owner_id == u.id))).scalars().all()
    for i in ids:
        runner.request_cancel(i)
    if ids:
        await db.execute(delete(Trial).where(Trial.experiment_id.in_(ids)))
    await db.execute(delete(Experiment).where(Experiment.owner_id == u.id))
    await db.execute(delete(Dataset).where(Dataset.owner_id == u.id))
    await db.execute(update(Feedback).where(Feedback.user_id == u.id).values(user_id=None))
    await db.execute(delete(User).where(User.id == u.id))
    await db.commit()
    return {"ok": True}
