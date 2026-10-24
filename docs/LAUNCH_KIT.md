# Launch kit

## 1. GitHub repo polish (5 minutes)
- **About** (gear icon top-right of the repo): description `Autonomous neural architecture search: NSGA-II, GPU worker mesh, agentic Groq + Gemini swarm, MCP, Wasm sandbox`, website = your Vercel URL.
- **Topics:** `neural-architecture-search` `nas` `hyperparameter-optimization` `pytorch` `fastapi` `agentic-ai` `mcp` `nsga-ii` `mlops` `react` `typescript` `tailwindcss`.
- **Social preview:** Settings -> General -> Social preview -> upload `frontend/public/og.png` (1200x630).
- **Pin** the repo on your GitHub profile. Add phone screenshots of the site to `docs/screenshots/` and reference them in the README.
- **Release:** Releases -> *Draft a new release* -> tag `v6.0.0` -> paste the v6 notes from `CHANGELOG.md`.

## 2. Get real numbers first (this makes every claim defensible)
Run `notebooks/deepoptima_colab.ipynb` (Colab, T4 GPU). Note the two values it prints (best accuracy evolution vs random) and the settings. Put them in the README table. Do **not** quote numbers you did not measure.

## 3. LinkedIn post (edit the brackets)
> I built **DeepOptima AI**: a platform that designs neural networks automatically.
>
> It evolves CNN/ViT architectures with NSGA-II (accuracy vs latency vs size), trains candidates on a distributed GPU worker mesh, and uses an agent swarm (Groq + Gemini) to diagnose failed runs.
>
> What's inside: FastAPI + Celery + PyTorch backend, MCP server, Wasm sandbox for custom fitness functions, mutual-TLS to the broker, hash-chained audit log, and a React dashboard with a built-in AI assistant.
>
> On a [CIFAR-10 subset, T4 GPU, N epochs], evolutionary search reached [X%] vs [Y%] for random search at the same evaluation budget.
>
> Live demo: [your Vercel link] · Code: github.com/Nikhil-creat/deepoptima
>
> #MachineLearning #MLOps #AgenticAI #PyTorch #FastAPI

## 4. Resume bullets (use only what is true for you)
- Built **DeepOptima AI**, a distributed neural-architecture-search platform (FastAPI, Celery, PyTorch, Redis, Postgres, MinIO) with NSGA-II multi-objective evolution over CNN/ViT block genotypes.
- Implemented a dual-provider LLM gateway (Groq/Gemini) with semantic caching, failover and automatic model discovery, plus a LangGraph agent swarm with Qdrant RAG for failure analysis.
- Hardened the platform: JWT RBAC, mTLS to the broker, Fernet-encrypted vault, hash-chained audit log, rate limiting, prompt-injection guardrails and a fuel-limited Wasm sandbox.
- Shipped a React/TypeScript dashboard (Vercel) with a voice-enabled AI assistant; benchmarked evolution vs random search on CIFAR-10 ([X%] vs [Y%], same budget).

## 5. Interview talking points
Why multi-objective (Pareto) instead of accuracy only; how proxies and halving cut GPU cost; how failures are triaged by agents; threat model (prompt injection, key leakage, untrusted fitness code); what the simulator is and is not.
