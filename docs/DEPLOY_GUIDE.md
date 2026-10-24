# DeepOptima AI - GitHub + free deployment guide

## 0. What gets hosted where (be realistic)
| Part | Free host | Notes |
|---|---|---|
| `frontend/` (Vite site, in-browser demo) | **Vercel / Netlify / GitHub Pages** | Works fully with no backend |
| FastAPI + Postgres + Redis | Render free web service + Neon/Supabase free Postgres + Upstash free Redis | API only. Free tiers are small and sleep when idle |
| GPU workers (PyTorch) | **Google Colab / Kaggle free GPU**, or your own PC with `docker compose` | Render/Vercel free tiers cannot run torch training |

So: publish the frontend for free (demo mode), run the full stack locally or on a VM when you need real training.

## 1. Free API keys
**Groq** - https://console.groq.com -> sign in -> *API Keys* -> *Create API Key* (starts with `gsk_`). Free tier has rate limits.
**Gemini** - https://aistudio.google.com/apikey -> *Create API key* (starts with `AIza`). Free tier has rate limits.
**Models are auto-detected**: paste a key and the site calls each provider's model-list API, picks the best fast + deep model, and re-detects automatically if a model is retired (backend does the same; `GROQ_MODEL`/`GEMINI_MODEL` default to `auto`).
Never commit keys. Locally put them in `.env`; on hosts use Environment Variables. In the demo UI, paste them into the "Free API keys" card (stored only in your browser).
Note: a key typed into a public static site is visible to that browser only, but anyone who views source of a site with a *baked-in* key can steal it, so never put keys in `VITE_*` variables.

## 2. Push to GitHub (from Termux on your phone)
```bash
pkg update && pkg install git unzip -y
termux-setup-storage
cd ~ && unzip ~/storage/downloads/deepoptima-master-v6.zip && cd deepoptima
git init -b main
git config user.name "Nikhil Chary Sriramoju"
git config user.email "sriramojunikhil66@gmail.com"
git add . && git commit -m "DeepOptima AI v2"
```
Create an empty repo named `deepoptima` on github.com (no README). Make a token: GitHub -> Settings -> Developer settings -> Personal access tokens -> Fine-grained -> repo access: only `deepoptima`, permission *Contents: Read and write*.
```bash
git remote add origin https://github.com/Nikhil-creat/deepoptima.git
git push -u origin main      # username: Nikhil-creat, password: <paste token>
```
Verify `.env` is NOT in the repo (`git ls-files | grep env` should only show `.env.example`).

## 3a. Vercel (free)
vercel.com -> *Add New Project* -> import `deepoptima` -> **Root Directory: `frontend`** -> Framework: Vite -> Deploy.
## 3b. Netlify (free)
app.netlify.com -> *Add new site* -> Import from Git -> Base directory `frontend`, build `npm run build`, publish `dist` (also set in `netlify.toml`).
## 3c. GitHub Pages (free)
In `frontend/vite.config.ts` add `base: '/deepoptima/'`, run `npm run build`, push the `dist` folder to a `gh-pages` branch (or use an Actions Pages workflow) and enable Pages in repo settings.

## 4. Backend on Render (API only, optional)
Render -> New -> Web Service -> repo -> Root `backend` -> Runtime Docker. Env vars: `DATABASE_URL` (Neon, use `postgresql+asyncpg://`), `REDIS_URL` (Upstash `rediss://`), `JWT_SECRET`, `FERNET_KEY`, `GROQ_API_KEY`, `GEMINI_API_KEY`, `CORS_ORIGINS=https://<your-vercel-site>`.
The image installs torch, which may exceed free-tier memory. If it does, split a slim API image (drop torch/ray from requirements and import workers lazily) or run the API on your own VM.

## 5. Run everything locally
```bash
cp .env.example .env     # fill JWT_SECRET, FERNET_KEY, keys
docker compose up --build
```

## 6. Tests and CI
`cd backend && pip install -r requirements.txt pytest && pytest -q` - GitHub Actions runs the same on every push, plus gitleaks (secret scan), bandit and the frontend build. Check the *Actions* tab after your first push.

## 7. Troubleshooting
| Symptom | Fix |
|---|---|
| `git push` asks password again / 403 | Use the fine-grained token as the password, check it has *Contents: Read and write* for this repo |
| Vercel build fails | Root Directory must be `frontend`; Node 20 |
| "invalid key" under the key box | Re-copy the key; Gemini keys start `AIza`, Groq keys `gsk_` |
| 429 from Groq/Gemini | Free-tier rate limit: wait a minute or switch the *Prefer* engine |
| Blank video | Some mobile browsers block autoplay in data-saver mode; the page still works |

## 8. Updating an already-deployed site (Termux)
```bash
cd ~
unzip -o ~/storage/downloads/deepoptima-master-v6.zip      # overwrites files, keeps your .git
cd deepoptima
git add . && git commit -m "v6: colab benchmark, backend connect, mTLS, vault, launch kit"
git push                                                   # token as password if asked
```
Vercel redeploys automatically in ~1 minute. Check the *Deployments* tab; click the latest one -> *Visit*.

## 9. Database migrations (backend)
```bash
cd backend
alembic revision --autogenerate -m "init"
alembic upgrade head
```
The API still calls `create_all` on startup for quick local runs; use Alembic in production.

## 10. Vercel tips
- *Deployments* tab: every push is a deployment; a bad one can be reverted with **Instant Rollback** (three-dot menu on an older deployment -> *Promote to Production*).
- Pull requests / non-main branches get their own preview URL.
- *Settings -> Domains* to attach a custom domain.
- *Settings -> Git*: keep Production Branch = `main`.

## 11. v6 extras
**Colab real benchmark:** after pushing, open `https://colab.research.google.com/github/Nikhil-creat/deepoptima/blob/main/notebooks/deepoptima_colab.ipynb` (or the *Real benchmark (Colab)* button on the site), set Runtime to T4 GPU, Run all, download `deepoptima-results.zip`, and in the dashboard use **Load session** with `session.json`.

**Connect backend mode:** run the API somewhere reachable over HTTPS (or `http://localhost:8000` on your PC), set `CORS_ORIGINS=https://<your-vercel-site>` in `.env`, register at `/docs`, then enter URL + login in *Connect your backend*. Security note: v6 relaxes the site's `connect-src` CSP to any `https:` host so you can enter your own API URL; to lock it down again, replace `https:` with your API origin in `frontend/vercel.json` and `frontend/netlify.toml`.

**mTLS (dev):** `make mtls`, which generates a CA, creates certs for api/worker/redis and starts the stack with `docker-compose.mtls.yml` (Redis requires client certificates).

**Agent RAG:** `make ingest` loads the research notes in `backend/app/agents/papers/` into Qdrant; add your own `.md` files there.

**Social preview:** the site meta tags point to `https://deepoptima.vercel.app/og.png`. If your Vercel URL is different, edit the two `og:image`/`twitter:image` lines in `frontend/index.html`.
