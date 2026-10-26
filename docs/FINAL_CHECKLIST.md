# Final checklist: what only you can do

## 1. Ship it (15 min)
- [ ] Termux: unzip the v8 zip over your repo, `git add . && git commit -m "v8: DeepOptima Studio" && git push`.
- [ ] GitHub -> Actions: wait for the **studio** job (engine + security + API tests) and **frontend** build to go green. If something is red, open it and paste the log to me: this is the one place real bugs will show up.

## 2. Backend online (30 min, free): docs/STUDIO_DEPLOY.md section B
- [ ] Neon database -> Render blueprint (`render.yaml`) -> set `DATABASE_URL`, `ADMIN_EMAILS`.
- [ ] Open the Render URL, register with the admin email, upload the sample data, run one experiment end to end.

## 3. Landing on Vercel talks to it
- [ ] Vercel env `VITE_API_URL=https://<your-render-url>` -> Redeploy. Render env `CORS_ORIGINS=https://deepoptima.vercel.app`.
- [ ] Optional hosted *Ask AI*: Vercel env `GROQ_API_KEY` (and `GEMINI_API_KEY`) -> Redeploy.

## 4. Before you share it publicly
- [ ] Read `/#/privacy` and `/#/terms`; adjust names/contacts; have someone check them if you collect real users' data.
- [ ] Decide `REGISTRATION_OPEN` / `MAX_USERS`. Watch `/#/admin` for failures and feedback.
- [ ] Take 3 phone screenshots (overview, results, predict) -> `docs/screenshots/`, add to README.
- [ ] GitHub About/topics, social preview (`frontend/public/og.png`), release `v8.0.0`, LinkedIn post (`docs/LAUNCH_KIT.md`).

## 5. Later / optional
- [ ] Email verification + password reset (needs an email service such as Resend or Brevo; ask me and I will add it).
- [ ] Colab GPU benchmark for the research platform (`notebooks/deepoptima_colab.ipynb`).
