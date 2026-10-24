"""Async Alembic env. Usage: alembic revision --autogenerate -m "init" && alembic upgrade head"""
import asyncio
from alembic import context
from sqlalchemy.ext.asyncio import create_async_engine
from app.config import settings
from app.db.models import Base

target_metadata = Base.metadata

def _run(conn):
    context.configure(connection=conn, target_metadata=target_metadata, compare_type=True)
    with context.begin_transaction():
        context.run_migrations()

async def _online():
    engine = create_async_engine(settings.database_url)
    async with engine.connect() as c:
        await c.run_sync(_run)
    await engine.dispose()

if context.is_offline_mode():
    context.configure(url=settings.database_url, target_metadata=target_metadata, literal_binds=True)
    with context.begin_transaction():
        context.run_migrations()
else:
    asyncio.run(_online())
