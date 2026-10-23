# 6-Month Roadmap
| Month | Objective | Exit criteria |
|---|---|---|
| 1 | Foundations: monorepo, Postgres schema + Alembic, FastAPI auth/RBAC, Docker Compose, OTel | `docker compose up` healthy, JWT login works |
| 2 | Worker mesh: Celery GPU queues, node heartbeat, trial timeouts, MinIO checkpoints, mTLS certs | 100 dummy trials across 3 nodes; resume from checkpoint after kill |
| 3 | NAS core: genotype/phenotype, mutation+crossover, PyTorch instantiation, short-epoch eval | CIFAR-10 search beats random baseline |
| 4 | Multi-objective: NSGA-II (acc/latency/params), ViT blocks, ONNX latency profiling | Pareto front persisted and queryable |
| 5 | Intelligence: LLM gateway, LangGraph swarm, Qdrant RAG, MCP server, Wasm fitness sandbox | Agent fixes a diverged trial; external client triggers search via MCP |
| 6 | Product + hardening: Tremor dashboard, React Flow topology, ONNX export, benchmarks vs Optuna/random, security audit, load test | Top-K ONNX auto-exported; audit findings closed |

## 3-day sprint (MVP)
- Day 1: compose stack up, models, API, one Celery trial end-to-end with a tiny CNN on a CIFAR-10 subset.
- Day 2: evolution loop + NSGA-II, Pareto endpoint, LLM gateway, WebSocket metrics.
- Day 3: dashboard (Pareto + loss curves), MCP server, ONNX export, demo run. Defer: real mTLS rotation, Wasm hardening, RLAIF.
