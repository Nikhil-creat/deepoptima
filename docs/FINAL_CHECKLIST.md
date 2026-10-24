# Final checklist: everything left is on your side (cannot be automated)

## A. Ship v7 (10 min)
- [ ] Termux: unzip v7 over the repo, `git add . && git commit -m "v7" && git push` (see DEPLOY_GUIDE section 8).
- [ ] Vercel: wait for **Ready**, hard-refresh, test the page on your phone.

## B. Turn on the hosted assistant for visitors (2 min, optional but recommended)
- [ ] Vercel -> project -> Settings -> **Environment Variables** -> add `GROQ_API_KEY` (and optionally `GEMINI_API_KEY`), Environments: Production -> **Redeploy**.
- [ ] Test: open the site in a fresh private tab, tap *Ask AI*, ask something. The answer footer should say `hosted · groq · <model>`.
- [ ] Kill switch: delete the variable and redeploy. The site falls back to built-in answers. Limits built in: 12 questions / 10 min / visitor, 400 per day, tiny answers, injection guard.

## C. Real numbers (30-40 min, free)
- [ ] Open the Colab notebook (button on the site), Runtime = T4 GPU, Run all.
- [ ] Download `deepoptima-results.zip`, load `session.json` in the dashboard (Load session) and screenshot it.
- [ ] Copy the two accuracies into the README table and `docs/LAUNCH_KIT.md` post.

## D. GitHub profile polish (5 min)
- [ ] About: description + website + topics (LAUNCH_KIT section 1), Social preview = `frontend/public/og.png`.
- [ ] Add 3 phone screenshots to `docs/screenshots/` and reference them in README.
- [ ] Release `v7.0.0`, pin the repo.

## E. Optional: real backend online for free (45 min)
1. **Neon** (neon.tech): create a free Postgres, copy the connection string, change the prefix to `postgresql+asyncpg://` and append `?ssl=require`.
2. **Upstash** (upstash.com): create a free Redis, copy the `rediss://...` URL.
3. **Render** (render.com): New -> Blueprint -> this repo (uses `render.yaml`, builds `backend/Dockerfile.lite`). Fill the env vars; `CORS_ORIGINS=https://deepoptima.vercel.app`.
4. Seed an admin + demo data (Render -> Shell, or run locally against the same DATABASE_URL):
   `python -m app.scripts.seed --email you@example.com --password 'min-10-chars' --demo`
5. On the website: Dashboard -> **Connect your backend** -> your Render URL + login. The seeded experiment is labelled *synthetic*.
Notes: the Render free API sleeps when idle (first request ~1 min); creating real experiments still needs GPU workers (Colab/own PC with `docker compose`).

## F. Housekeeping
- [ ] Dependabot PRs: merge green *minor/patch* group PRs; major bumps are now ignored by config.
- [ ] Rotate any API key you ever pasted into a public place; never commit `.env`.
- [ ] Enable Vercel Web Analytics (Production Checklist) if you want visitor counts.
