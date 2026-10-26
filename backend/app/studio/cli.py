"""Admin helper:  python -m app.studio.cli create-admin EMAIL PASSWORD | reset-password EMAIL NEWPASSWORD | stats"""
import asyncio, sys
from sqlalchemy import func, select
from .db import Dataset, Experiment, SessionLocal, User, init_db
from .security import clean_email, hash_password, password_problem


async def main(argv: list[str]) -> int:
    await init_db()
    cmd = argv[0] if argv else ""
    async with SessionLocal() as db:
        if cmd in ("create-admin", "reset-password") and len(argv) == 3:
            email = clean_email(argv[1]); pw = argv[2]
            if not email or password_problem(pw):
                print("invalid email or weak password:", password_problem(pw)); return 1
            u = await db.scalar(select(User).where(User.email == email))
            if cmd == "create-admin":
                if u: u.is_admin, u.password_hash = True, hash_password(pw)
                else: db.add(User(email=email, name="Admin", password_hash=hash_password(pw), is_admin=True))
            else:
                if not u: print("no such user"); return 1
                u.password_hash = hash_password(pw); u.token_version += 1
            await db.commit(); print("ok"); return 0
        if cmd == "stats":
            for label, m in (("users", User), ("datasets", Dataset), ("experiments", Experiment)):
                print(label, await db.scalar(select(func.count()).select_from(m)))
            return 0
    print(__doc__); return 2


if __name__ == "__main__":
    sys.exit(asyncio.run(main(sys.argv[1:])))
