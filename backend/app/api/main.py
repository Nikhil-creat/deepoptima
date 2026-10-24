"""FastAPI control plane."""
import asyncio, json, uuid
from contextlib import asynccontextmanager
from fastapi import FastAPI, Depends, File, HTTPException, UploadFile, WebSocket, WebSocketDisconnect, BackgroundTasks
from fastapi.middleware.cors import CORSMiddleware
from fastapi.security import OAuth2PasswordRequestForm
from pydantic import BaseModel, Field
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
import redis.asyncio as aioredis
from opentelemetry import trace
from opentelemetry.sdk.trace import TracerProvider
from opentelemetry.sdk.trace.export import BatchSpanProcessor
from opentelemetry.exporter.otlp.proto.grpc.trace_exporter import OTLPSpanExporter
from opentelemetry.instrumentation.fastapi import FastAPIInstrumentor
from app.config import settings
from app.db.models import (Base, User, Role, Experiment, SearchSpace, Trial, TrialStatus, ExperimentStatus, WorkerNode)
from app.db.session import engine, get_db
from app.security import pwd, make_token, require, current_user, audit
from app.nas.space import DEFAULT_SPACE
from app.llm.gateway import LLMGateway
from app.api.assistant import router as assistant_router
from app.api.vault import router as vault_router
from app.api.audit import router as audit_router
from app.sandbox.wasm_runner import validate_module
from app.security_mw import SecurityHeaders, BodyLimit, RateLimit, login_locked, login_failed

R = Role

@asynccontextmanager
async def lifespan(app: FastAPI):
    async with engine.begin() as c:           # use Alembic migrations in production
        await c.run_sync(Base.metadata.create_all)
    app.state.redis = aioredis.from_url(settings.redis_url, decode_responses=True, **settings.redis_kwargs())
    app.state.gateway = LLMGateway(app.state.redis)
    try: await app.state.gateway.refresh_models()
    except Exception: pass
    yield
    await app.state.redis.close()

app = FastAPI(title="DeepOptima AI Control Plane", version="0.1.0", lifespan=lifespan)
app.add_middleware(CORSMiddleware, allow_origins=[o for o in __import__("os").environ.get("CORS_ORIGINS","http://localhost:3000").split(",")], allow_credentials=True,
                   allow_methods=["*"], allow_headers=["*"])
app.add_middleware(SecurityHeaders); app.add_middleware(BodyLimit); app.add_middleware(RateLimit)
_tp = TracerProvider(); _tp.add_span_processor(BatchSpanProcessor(OTLPSpanExporter(endpoint=settings.otlp_endpoint, insecure=True)))
trace.set_tracer_provider(_tp); FastAPIInstrumentor.instrument_app(app)


# ---------- schemas ----------
class RegisterIn(BaseModel):
    email: str; password: str = Field(min_length=10)

class ExperimentIn(BaseModel):
    name: str; dataset: str = "cifar10"; population_size: int = Field(16, ge=4, le=256)
    max_generations: int = Field(10, ge=1, le=200); epochs: int = Field(3, ge=1, le=20)
    search_space: dict = DEFAULT_SPACE; family: str = "cnn"


# ---------- auth ----------
@app.post("/auth/register", status_code=201)
async def register(b: RegisterIn, db: AsyncSession = Depends(get_db)):
    if (await db.execute(select(User).where(User.email == b.email))).scalar_one_or_none():
        raise HTTPException(409, "Email exists")
    first = (await db.execute(select(User).limit(1))).scalar_one_or_none() is None
    u = User(email=b.email, password_hash=pwd.hash(b.password), role=R.admin if first else R.researcher)
    db.add(u); await audit(db, u.id, "user.register", b.email); await db.commit()
    return {"id": str(u.id), "role": u.role}

@app.post("/auth/token")
async def login(f: OAuth2PasswordRequestForm = Depends(), db: AsyncSession = Depends(get_db)):
    rds = app.state.redis
    if await login_locked(rds, f.username): raise HTTPException(429, "Account temporarily locked")
    u = (await db.execute(select(User).where(User.email == f.username))).scalar_one_or_none()
    if not u or not pwd.verify(f.password, u.password_hash):
        await login_failed(rds, f.username); raise HTTPException(401, "Bad credentials")
    return {"access_token": make_token(u), "token_type": "bearer"}


# ---------- experiments ----------
@app.post("/experiments", status_code=201)
async def create_experiment(b: ExperimentIn, bg: BackgroundTasks, db: AsyncSession = Depends(get_db),
                            u: User = Depends(require(R.researcher))):
    ss = SearchSpace(name=f"{b.name}-space", family=b.family, spec=b.search_space); db.add(ss); await db.flush()
    e = Experiment(owner_id=u.id, search_space_id=ss.id, name=b.name, dataset=b.dataset,
                   population_size=b.population_size, max_generations=b.max_generations)
    db.add(e); await audit(db, u.id, "experiment.create", b.name); await db.commit()
    from app.workers.orchestrator import run_experiment      # lazy: needs torch/celery (GPU image only)
    bg.add_task(run_experiment, e.id, b.epochs)
    return {"id": str(e.id), "status": "running"}

@app.get("/experiments")
async def list_experiments(db: AsyncSession = Depends(get_db), u: User = Depends(current_user)):
    rows = (await db.execute(select(Experiment).order_by(Experiment.created_at.desc()))).scalars().all()
    return [{"id": str(e.id), "name": e.name, "status": e.status, "dataset": e.dataset} for e in rows]

@app.get("/experiments/{eid}/trials")
async def trials(eid: uuid.UUID, status: TrialStatus | None = None, db: AsyncSession = Depends(get_db),
                 u: User = Depends(current_user)):
    q = select(Trial).where(Trial.experiment_id == eid)
    if status: q = q.where(Trial.status == status)
    return [{"id": str(t.id), "generation": t.generation, "status": t.status, "accuracy": t.accuracy,
             "latency_ms": t.latency_ms, "params": t.params, "pareto_rank": t.pareto_rank,
             "loss_curve": t.loss_curve, "genotype": t.genotype, "error": t.error}
            for t in (await db.execute(q)).scalars()]

@app.get("/experiments/{eid}/pareto")
async def pareto(eid: uuid.UUID, db: AsyncSession = Depends(get_db), u: User = Depends(current_user)):
    q = select(Trial).where(Trial.experiment_id == eid, Trial.pareto_rank == 0, Trial.status == TrialStatus.completed)
    return [{"id": str(t.id), "accuracy": t.accuracy, "latency_ms": t.latency_ms, "params": t.params}
            for t in (await db.execute(q)).scalars()]

@app.post("/experiments/{eid}/fitness")
async def upload_fitness(eid: uuid.UUID, file: UploadFile = File(...), db: AsyncSession = Depends(get_db),
                         u: User = Depends(require(R.researcher))):
    """Attach a custom fitness function (Wasm exporting fitness(acc, latency_ms, params) -> f64). Validated, imports forbidden."""
    e = await db.get(Experiment, eid)
    if not e or (e.owner_id != u.id and u.role != R.admin): raise HTTPException(404)
    data = await file.read(1_000_001)
    try: validate_module(data)
    except Exception as ex: raise HTTPException(422, f"Invalid Wasm module: {ex}")
    e.custom_fitness_wasm = data
    await audit(db, u.id, "experiment.fitness_upload", str(eid), {"bytes": len(data)}); await db.commit()
    return {"ok": True, "bytes": len(data)}

@app.post("/experiments/{eid}/resume")
async def resume(eid: uuid.UUID, db: AsyncSession = Depends(get_db), u: User = Depends(require(R.researcher))):
    e = await db.get(Experiment, eid)
    if not e: raise HTTPException(404)
    e.status = ExperimentStatus.running; await audit(db, u.id, "experiment.resume", str(eid)); await db.commit()
    return {"status": "running"}

@app.post("/experiments/{eid}/pause")
async def pause(eid: uuid.UUID, db: AsyncSession = Depends(get_db), u: User = Depends(require(R.researcher))):
    e = await db.get(Experiment, eid)
    if not e: raise HTTPException(404)
    e.status = ExperimentStatus.paused; await audit(db, u.id, "experiment.pause", str(eid)); await db.commit()
    return {"status": "paused"}   # orchestrator polls status between generations

@app.websocket("/ws/experiments/{eid}")
async def ws_stream(ws: WebSocket, eid: str, token: str):
    from jose import jwt
    try: jwt.decode(token, settings.jwt_secret, [settings.jwt_alg])
    except Exception: await ws.close(code=4401); return
    await ws.accept()
    ps = ws.app.state.redis.pubsub(); await ps.subscribe(f"exp:{eid}")
    try:
        async for m in ps.listen():
            if m["type"] == "message": await ws.send_text(m["data"])
    except WebSocketDisconnect:
        pass
    finally:
        await ps.unsubscribe(); await ps.close()

@app.get("/workers")
async def workers(u: User = Depends(current_user)):
    """Live nodes = Redis heartbeat keys (expire after 45s without a beat)."""
    out = []
    async for k in app.state.redis.scan_iter("worker:*"):
        d = await app.state.redis.hgetall(k)
        out.append({"hostname": k.split(":", 1)[1], "healthy": True, **d})
    return out

app.include_router(assistant_router)
app.include_router(vault_router)
app.include_router(audit_router)

@app.get("/llm/models")
async def llm_models(refresh: bool = False, u: User = Depends(current_user)):
    found = await app.state.gateway.refresh_models(force=refresh)
    return {"active": app.state.gateway.models, "detected": found}

@app.get("/readyz")
async def readyz(db: AsyncSession = Depends(get_db)):
    from sqlalchemy import text
    await db.execute(text("select 1")); await app.state.redis.ping()
    return {"ready": True}

@app.get("/healthz")
async def healthz(): return {"ok": True}
