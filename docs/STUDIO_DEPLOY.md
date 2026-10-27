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

## C. Keep the landing page on Vercel (optional, but then it must know where the backend is)
Backend on Render as above. Then pick ONE of:
- **Easiest (no Vercel settings):** edit `frontend/public/config.json` in your repo to `{ "apiUrl": "https://<name>.onrender.com" }`, commit, push. Vercel redeploys and the app finds the backend at run time.
- Or set the Vercel environment variable `VITE_API_URL=https://<name>.onrender.com` and redeploy.
In **Render** also set `CORS_ORIGINS=https://deepoptima.vercel.app` (your exact Vercel URL). Simplest of all: just share the Render URL, which serves the whole site by itself.
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
| `EMAIL_PROVIDER` | - | `brevo`, `resend` or `console` (dev: logs emails). Enables email verification + password reset |
| `EMAIL_API_KEY`, `EMAIL_FROM`, `EMAIL_FROM_NAME` | - | Provider key, a verified sender address, display name |
| `PUBLIC_URL` | - | Base URL used in email links (set to your site, e.g. https://xxx.onrender.com) |
| `REQUIRE_EMAIL_VERIFICATION` | false | If true (and email works), uploads and experiments need a confirmed email |

## Admin tasks
`python -m app.studio.cli create-admin you@x.com 'a-long-password'` · `reset-password EMAIL NEWPASS` · `stats` (needs shell access; on Render free use `ADMIN_EMAILS` instead).

## What the platform does and does not do
- Does: CSV profiling, safe preprocessing (impute/scale/one-hot), evolutionary NSGA-II search over six model families, held-out test scoring vs a baseline, feature importance, model download + generated `predict.py`, online prediction, share links, per-user quotas, rate limiting, account deletion.
- Does not (yet): email verification / password-reset emails (needs an email provider), payments, GPU/deep-learning training for images (see the research platform), multi-server scaling (jobs run in the API process).
- Security notes: passwords use scrypt; tokens are signed HS256 with a server secret; every query is scoped to the owner; uploaded files are parsed with pandas only (never executed); model files are unpickled only if the server created them; CSV exports neutralise spreadsheet formulas.

## Tests
`make studio-test` (engine, security, and API end-to-end; the API test runs in CI).

## Email: verification and password reset (optional, free)
Render's free plan blocks SMTP, so the app sends mail through an HTTPS API.
1. **Brevo** (brevo.com, free 300 emails/day, can send to anyone): sign up -> *Senders, domains & dedicated IPs* -> add and verify your sender email -> *SMTP & API* -> *API keys* -> generate a key.
2. In Render set: `EMAIL_PROVIDER=brevo`, `EMAIL_API_KEY=<key>`, `EMAIL_FROM=<your verified sender>`, `PUBLIC_URL=https://<your site>`.
3. Redeploy. New users get a confirmation email, "Forgot password?" appears on the sign-in page, and links open `.../#/verify` or `.../#/reset`.
Notes: mail from a free Gmail/Outlook sender can land in spam (a custom domain with SPF/DKIM fixes that). Resend also works (`EMAIL_PROVIDER=resend`) but only sends to anyone once you verify your own domain. For local testing use `EMAIL_PROVIDER=console`; emails then appear in the server log.

## API keys: use your trained model from your own app
Account -> **API keys** -> create. Then:
```bash
curl -X POST https://<site>/api/experiments/<id>/predict \
  -H "Authorization: Bearer dok_..." -H "Content-Type: application/json" \
  -d '{"rows":[{"age":40,"plan":"basic"}]}'
```
Keys can only request predictions and read experiments, are stored hashed, and can be revoked any time. The experiment page shows a ready-made command.

## Upgrading
The app adds new database columns automatically on startup, so existing accounts and data survive upgrades. Back up your Neon database before big upgrades (Neon has branch/restore tools).

Note: `npm run build` only bundles the site (so a harmless type warning can never block a deploy); type-checking runs separately via `npm run typecheck` and in CI.
