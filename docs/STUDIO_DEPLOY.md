# DeepOptima Studio: run it and put it online (free)

Studio = React frontend + FastAPI API + CPU AutoML engine (scikit-learn). No GPU needed.

## A. Try it on your PC (2 minutes, SQLite)
```bash
cd backend
pip install -r requirements-studio.txt
uvicorn app.studio.main:app --reload --port 8000          # API + docs at http://localhost:8000/api/docs
# second terminal
cd frontend && npm install
VITE_API_URL=http://localhost:8000 npm run dev            # http://localhost:5173
```
Or everything in one container: `make studio-docker` (Postgres included), then open http://localhost:8000.

## B. Put it online for free (recommended: ONE Render service + Neon database)
1. **Neon** (neon.tech): create a free project. Copy the connection string (`postgres://...?sslmode=require`). Paste it as-is, it is converted automatically.
2. **Render** (render.com): *New -> Blueprint* -> pick your GitHub repo (uses `render.yaml`) -> fill:
   - `DATABASE_URL` = the Neon string
   - `ADMIN_EMAILS` = your email (the account you register with becomes admin)
   - leave the rest as default (`JWT_SECRET` is generated for you)
3. Wait for the first deploy (5-10 min). Open `https://<name>.onrender.com`. Register with your admin email, upload the sample dataset, run an experiment.

Free-tier facts: the service sleeps after ~15 min idle (first visit takes up to a minute); an experiment that is running when it sleeps/restarts is marked failed and can be re-run; 512 MB RAM is why the defaults are small (3 MB files, 20,000 rows, 180 s). Raise `MAX_*` on a paid plan.

## C. Keep the pretty landing page on Vercel (optional)
Backend on Render as above, then in **Vercel -> Project -> Settings -> Environment Variables**: `VITE_API_URL=https://<name>.onrender.com` (Production) -> redeploy. In **Render** set `CORS_ORIGINS=https://deepoptima.vercel.app`. Visitors open the Vercel URL; the app talks to Render.
(The *Ask AI* assistant on the landing page is a separate Vercel function, see `docs/FINAL_CHECKLIST.md`.)

## Configuration (environment variables)
| Variable | Default | Meaning |
|---|---|---|
| `ENV` | development | `production` makes `JWT_SECRET` mandatory |
| `DATABASE_URL` | sqlite+aiosqlite:///./studio.db | Postgres URL in production |
| `JWT_SECRET` | random per start (dev only) | Signs login tokens |
| `ADMIN_EMAILS` | - | Comma list; these accounts get `/admin` |
| `CORS_ORIGINS` | localhost | Origins allowed when the frontend is hosted elsewhere |
| `TRUST_PROXY` | false | `true` behind Render/nginx so rate limits see real client IPs |
| `REGISTRATION_OPEN` | true | Set `false` to close sign-ups |
| `MAX_USERS`, `MAX_UPLOAD_MB`, `MAX_ROWS`, `MAX_COLS` | 1000, 5, 50000, 100 | Data limits |
| `MAX_DATASETS_PER_USER`, `MAX_EXPERIMENTS_PER_USER` | 5, 25 | Per-account quotas |
| `MAX_TIME_LIMIT_S`, `MAX_CONCURRENT_JOBS` | 300, 1 | Search time cap, parallel jobs |
| `RETENTION_DAYS` | 0 (off) | Auto-delete old experiments/datasets |

## Admin tasks
`python -m app.studio.cli create-admin you@x.com 'a-long-password'` · `reset-password EMAIL NEWPASS` · `stats` (needs shell access; on Render free use `ADMIN_EMAILS` instead).

## What the platform does and does not do
- Does: CSV profiling, safe preprocessing (impute/scale/one-hot), evolutionary NSGA-II search over six model families, held-out test scoring vs a baseline, feature importance, model download + generated `predict.py`, online prediction, share links, per-user quotas, rate limiting, account deletion.
- Does not (yet): email verification / password-reset emails (needs an email provider), payments, GPU/deep-learning training for images (see the research platform), multi-server scaling (jobs run in the API process).
- Security notes: passwords use scrypt; tokens are signed HS256 with a server secret; every query is scoped to the owner; uploaded files are parsed with pandas only (never executed); model files are unpickled only if the server created them; CSV exports neutralise spreadsheet formulas.

## Tests
`make studio-test` (engine, security, and API end-to-end; the API test runs in CI).
