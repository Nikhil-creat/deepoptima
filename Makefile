up:        ; docker compose up --build
test:      ; cd backend && pip install pytest && pytest -q
web:       ; cd frontend && npm install && npm run dev
build-web: ; cd frontend && npm install && npm run build
ingest:    ; docker compose run --rm api python -m app.agents.ingest
mtls:      ; bash infra/certs/gen_mtls.sh && docker compose -f docker-compose.yml -f docker-compose.mtls.yml up --build
seed:      ; docker compose run --rm api python -m app.scripts.seed --email $(EMAIL) --password $(PASSWORD) --demo
lite:      ; docker build -f backend/Dockerfile.lite -t deepoptima-api backend
studio:    ; cd backend && pip install -r requirements-studio.txt && uvicorn app.studio.main:app --reload --port 8000
studio-test: ; cd backend && pip install -r requirements-studio.txt pytest httpx anyio && pytest -q tests/test_studio_engine.py tests/test_studio_core.py tests/test_studio_api.py
studio-docker: ; JWT_SECRET=$$(openssl rand -hex 32) docker compose -f docker-compose.studio.yml up --build
