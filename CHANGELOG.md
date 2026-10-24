# Changelog
## v6.1
- Mobile fix: horizontal overflow (code box widened the page and cut the sticky header), global overflow guards, compact sticky nav on phones.
- Instagram and Facebook links (contact section, footer, JSON-LD), robots.txt + sitemap.xml, keywords meta, noscript fallback, React error boundary.
## v6.0
- Colab notebook for a real, equal-budget benchmark (evolution vs random) exporting a session for the dashboard; "Connect your backend" live mode; dark mode; keys default to session-only storage with an opt-in "Remember" toggle.
- Backend: mTLS wiring (Redis broker, compose override, fixed cert script), Qdrant ingest + offline hash embedder, swarm feedback loop from the orchestrator, Wasm fitness upload + scoring, Fernet vault CRUD, `/audit/verify` hash-chain check, `python-multipart` dependency added (login form needed it).
- Launch: new README, social preview image, launch kit.
## v5.0
- Frontend: Evolution vs random-search convergence chart (same budget), save/load session (validated JSON), voice assistant (mic + read-aloud), share button, expanded FAQ/KB.
- Backend: adaptive operator selection (bandit-style meta-optimisation, blends swarm judge weights from Redis), pause/resume honoured by the orchestrator, live worker heartbeats (Redis, TTL 45s), `/readyz`, `/experiments/{id}/resume`, Alembic async scaffold, new tests.
- Security: Permissions-Policy now allows microphone for same-origin only (needed for voice input).
## v4.0
New logo, assistant chatbot, illustrated sections, sticky header, stack tabs, FAQ, footer, improved Pareto chart.
## v3.0
Model auto-detection (browser + backend), agent roles, hardware targets, PyTorch/CSV export, guardrail lab, tests.
## v2.0
Vite frontend, security middleware, guardrails, zero-cost proxies, CI.
## v1.0
Initial backend blueprint: models, gateway, NAS engine, worker, API, MCP, compose.
