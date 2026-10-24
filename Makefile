up:        ; docker compose up --build
test:      ; cd backend && pip install pytest && pytest -q
web:       ; cd frontend && npm install && npm run dev
build-web: ; cd frontend && npm install && npm run build
ingest:    ; docker compose run --rm api python -m app.agents.ingest
mtls:      ; bash infra/certs/gen_mtls.sh && docker compose -f docker-compose.yml -f docker-compose.mtls.yml up --build
