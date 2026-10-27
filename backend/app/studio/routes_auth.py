import asyncio
from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException, Request
from pydantic import BaseModel, Field
from sqlalchemy import delete, func, select, update
from sqlalchemy.ext.asyncio import AsyncSession
from . import mailer
from .db import ApiKey, Dataset, Experiment, Feedback, Trial, User, get_db, utcnow
from .deps import check_rate, client_ip, count, current_user, limiter, limits_out, user_out
from .security import DUMMY_HASH, clean_email, fingerprint, hash_password, make_token, password_problem, purpose_token, read_purpose, verify_password
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


def public_base(request: Request) -> str:
    """Base URL for links in emails. Taken from configuration, never from request headers (prevents link poisoning)."""
    if settings.public_url:
        return settings.public_url.rstrip("/")
    for o in settings.cors_origins:
        if o.startswith("https://"):
            return o.rstrip("/")
    return str(request.base_url).rstrip("/")


def queue_verification(u: User, request: Request, bg: BackgroundTasks) -> None:
    if mailer.enabled() and not u.email_verified:
        tok = purpose_token("verify", u.id, settings.jwt_secret, 3 * 86400, e=u.email)
        bg.add_task(mailer.send_email, u.email, "Confirm your email for DeepOptima Studio", mailer.verify_text(u.name, f"{public_base(request)}/#/verify?token={tok}"))


@router.post("/auth/register", status_code=201)
async def register(b: RegisterIn, request: Request, bg: BackgroundTasks, db: AsyncSession = Depends(get_db)):
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
             is_admin=email in settings.admin_emails, email_verified=email in settings.admin_emails, last_login_at=utcnow())
    db.add(u)
    await db.commit()
    await db.refresh(u)
    queue_verification(u, request, bg)
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


class ForgotIn(BaseModel):
    email: str = Field(max_length=254)


@router.post("/auth/forgot")
async def forgot(b: ForgotIn, request: Request, bg: BackgroundTasks, db: AsyncSession = Depends(get_db)):
    """Always answers the same way, so it cannot be used to discover which emails have accounts."""
    check_rate(request, "forgot", 5, 3600)
    email = clean_email(b.email) or ""
    if email and mailer.enabled() and limiter.allow(f"forgot:{email}", 3, 3600):
        u = await db.scalar(select(User).where(User.email == email))
        if u and u.is_active:
            tok = purpose_token("reset", u.id, settings.jwt_secret, 3600, f=fingerprint(u.password_hash))
            bg.add_task(mailer.send_email, u.email, "Reset your DeepOptima Studio password", mailer.reset_text(u.name, f"{public_base(request)}/#/reset?token={tok}"))
    return {"ok": True}


class ResetIn(BaseModel):
    token: str = Field(max_length=1000)
    new_password: str = Field(max_length=128)


@router.post("/auth/reset")
async def reset(b: ResetIn, request: Request, db: AsyncSession = Depends(get_db)):
    check_rate(request, "reset", 10, 3600)
    body = read_purpose(b.token, "reset", settings.jwt_secret)
    u = await db.get(User, int(body.get("sub", 0) or 0)) if body else None
    if not u or not u.is_active or body.get("f") != fingerprint(u.password_hash):       # fingerprint changes after use -> single use
        raise HTTPException(400, "This reset link is invalid or has expired. Request a new one.")
    problem = password_problem(b.new_password)
    if problem:
        raise HTTPException(400, problem)
    u.password_hash = await asyncio.to_thread(hash_password, b.new_password)
    u.token_version += 1
    u.email_verified = True                                                              # they just proved they own the inbox
    await db.commit()
    return auth_response(u)


class TokenIn(BaseModel):
    token: str = Field(max_length=1000)


@router.post("/auth/verify")
async def verify_email(b: TokenIn, request: Request, db: AsyncSession = Depends(get_db)):
    check_rate(request, "verify", 20, 3600)
    body = read_purpose(b.token, "verify", settings.jwt_secret)
    u = await db.get(User, int(body.get("sub", 0) or 0)) if body else None
    if not u or body.get("e") != u.email:
        raise HTTPException(400, "This confirmation link is invalid or has expired.")
    u.email_verified = True
    await db.commit()
    return {"ok": True}


@router.post("/me/resend-verification")
async def resend_verification(request: Request, bg: BackgroundTasks, u: User = Depends(current_user)):
    check_rate(request, "resend", 3, 3600, u.id)
    if u.email_verified:
        return {"ok": True, "already": True}
    if not mailer.enabled():
        raise HTTPException(400, "Email sending is not set up on this server.")
    queue_verification(u, request, bg)
    return {"ok": True}


@router.get("/me")
async def me(u: User = Depends(current_user), db: AsyncSession = Depends(get_db)):
    return {"user": user_out(u), "limits": limits_out(), "email_enabled": mailer.enabled(), "require_verification": settings.require_verification,
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
    await db.execute(delete(ApiKey).where(ApiKey.user_id == u.id))
    await db.execute(delete(User).where(User.id == u.id))
    await db.commit()
    return {"ok": True}
