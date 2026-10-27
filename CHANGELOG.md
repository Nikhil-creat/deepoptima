# Changelog
## v9.0
- Engine: 3-fold scoring for small datasets, 95% bootstrap ranges on test scores, class-balancing option, confusion matrix / error scatter, column exclusion, leakage warning.
- Accounts: email verification + password reset (Brevo/Resend over HTTPS), personal API keys (prediction-only), full data export, admin user management, automatic DB column upgrades.
- App: runtime `config.json` (no env var needed to point the site at the backend), clone experiment, dataset download, downloadable HTML report, API usage panel.
## v8.0: DeepOptima Studio (real product)
- New full-stack public app: accounts, datasets, experiments, results, predictions, share links, admin, privacy/terms/help pages (React + FastAPI + scikit-learn engine, SQLite/Postgres).
- Engine: CSV profiling, NSGA-II search over six model families (score vs latency vs size), held-out test scoring, baseline, importance, joblib models, generated predict.py.
- Landing page reworked around Studio; GPU mesh kept as the research track. Single-container Docker, Render blueprint, compose file, CI job for Studio, docs/STUDIO_DEPLOY.md.
## v7.0
- Hosted public assistant (`/api/chat`, Vercel serverless, owner's free key, rate-limited, guardrails) with built-in fallback; Telugu UI + assistant language toggle.
- API now torch-free: `app/nas/space.py`, lazy orchestrator import, `Dockerfile.lite`, `requirements-api.txt`, `render.yaml`, CI import guard; `bcrypt` pinned for passlib compatibility; seed script for admin + synthetic demo data.
- Dependabot grouped, majors ignored; `docs/FINAL_CHECKLIST.md`.
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
