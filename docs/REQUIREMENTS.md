# Requirements
| Item | Requirement |
|---|---|
| Node.js / npm | 20+ / 10+ (frontend) |
| Python | 3.11+ (backend, workers) |
| Docker | 24+ with Compose v2 |
| RAM / disk | 8 GB min (16 GB recommended) / 20 GB free |
| GPU | NVIDIA 8 GB+ VRAM + Container Toolkit for real training; CPU works for demos |
| Ports | 3000 UI, 8000 API, 8765 MCP, 9001 MinIO console, 5432 Postgres, 6379 Redis, 6333 Qdrant |
| Secrets | JWT_SECRET, FERNET_KEY, POSTGRES_PASSWORD, MINIO_ROOT_PASSWORD |
| Free LLM keys | Groq (console.groq.com), Gemini (aistudio.google.com/apikey); models are auto-detected |
