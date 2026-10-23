# DeepOptima AI - Architecture

```mermaid
flowchart LR
  UI[Next.js + Tremor + React Flow] -->|REST/WS + JWT| API[FastAPI Control Plane]
  EXT[External LLM clients] -->|MCP| MCP[MCP Server]
  MCP --> API
  API --> PG[(PostgreSQL)]
  API --> RD[(Redis: broker, cache, pubsub)]
  API -->|enqueue trials| RD
  RD --> W1[GPU Worker 1]
  RD --> W2[GPU Worker N]
  W1 & W2 -->|mTLS| API
  W1 & W2 -->|.pt / .onnx| S3[(MinIO)]
  W1 & W2 -->|metrics| PG
  API --> GW[Multi-LLM Gateway]
  GW -->|fast tool calls| GROQ[Groq API]
  GW -->|long-context, multimodal| GEM[Gemini API]
  GW <-->|semantic cache| RD
  API --> SW[LangGraph Agent Swarm]
  SW --> GW
  SW <-->|RAG| QD[(Qdrant)]
  API --> WASM[Wasm Sandbox - custom fitness]
  W1 & W2 --> WASM
  API & W1 & W2 -.->|OTLP| OT[OpenTelemetry Collector]
```

## Data flow
1. User/agent creates an Experiment + SearchSpace via API or MCP.
2. Evolution engine samples a population of genotypes, writes Trials (status=queued).
3. Trials go to Celery (GPU queue). Worker builds the PyTorch phenotype, trains few epochs, streams metrics over Redis pub/sub, saves checkpoints to MinIO.
4. Results (accuracy, latency, params) land in Postgres; NSGA-II selects the next generation.
5. Failed trials go to the agent swarm: retrieve whitepapers from Qdrant, propose heuristic fixes via Groq/Gemini.
6. Dashboard consumes the WebSocket stream + Pareto endpoint.
