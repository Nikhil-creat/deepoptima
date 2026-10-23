# DeepOptima AI
Distributed Neural Architecture Search + hyperparameter tuning mesh. Evolutionary NSGA-II over CNN/ViT block genotypes, Celery GPU workers, Groq+Gemini gateway, MCP server, Wasm fitness sandbox, Next.js + Tremor dashboard.

## Quickstart
```bash
cp .env.example .env     # set JWT_SECRET, FERNET_KEY
docker compose up --build            # GPU host (NVIDIA Container Toolkit)
# first registered user becomes admin
curl -X POST localhost:8000/auth/register -H 'content-type: application/json' -d '{"email":"you@x.com","password":"longpassword1"}'
# UI: http://localhost:3000 (Vite dev: cd frontend && npm i && npm run dev -> :5173)   API docs: http://localhost:8000/docs   MCP (SSE): :8765
```
CPU-only dev: change worker `build.dockerfile` to `Dockerfile` with command `celery -A app.workers.tasks worker -Q gpu`, and remove the `deploy` block.

## Layout
```
deepoptima/
  docker-compose.yml  .env.example
  docs/ARCHITECTURE.md (Mermaid)  docs/ROADMAP.md (6 months + 3-day MVP)
  infra/otel/config.yaml  infra/certs/gen_mtls.sh
  backend/
    Dockerfile  Dockerfile.gpu  requirements.txt
    app/config.py  security.py (JWT/RBAC/Fernet/hash-chained audit)
    app/db/models.py  session.py
    app/llm/gateway.py            # Groq+Gemini, semantic cache, failover, streaming
    app/nas/genotype.py  evolution.py   # genotype->PyTorch, mutation, crossover, NSGA-II
    app/workers/tasks.py  orchestrator.py  # Celery trial + evolution loop
    app/agents/swarm.py           # LangGraph + Qdrant RAG + judge (RLAIF hook)
    app/sandbox/wasm_runner.py    # fuel/memory-limited fitness
    app/mcp/server.py  app/api/main.py
  frontend/  Vite + React + TS + Tailwind (video hero, in-browser NSGA-II demo, BYOK Groq/Gemini agent, footer)
  .github/workflows/ci.yml  docs/DEPLOY_GUIDE.md
```

## v3 additions
Auto-detected Groq/Gemini models (browser + backend, self-healing on retired models), agent roles (tuning / security / efficiency), hardware-target latency + energy estimate, PyTorch code + Pareto CSV export, in-browser guardrail lab, expanded credentials section, pytest suite, LICENSE, SECURITY.md, Dependabot, PWA manifest.

## v2 additions
Security middleware (headers, rate limit, lockout, body cap), LLM guardrails (injection screen, redaction, untrusted wrapping), zero-cost NASWOT proxy + successive halving + carbon estimate, CI with gitleaks/bandit, CSP headers for Vercel/Netlify. Guide: `docs/DEPLOY_GUIDE.md`.

## Status (honest)
Real: models, gateway, genotype/phenotype, NSGA-II, trial worker (checkpoint resume, ONNX export), API, MCP tools, compose.
Scaffold only: mTLS (certs script exists; wire TLS into Celery broker/API with `ssl_cert_reqs`), RLAIF (judge returns operator weights, not yet fed back into `next_generation`), Qdrant ingestion of whitepapers, worker heartbeat registration, pause polling in orchestrator, Alembic migrations, Wasm module upload endpoint, tests.
