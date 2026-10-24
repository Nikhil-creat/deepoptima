"""python -m app.agents.ingest [folder]   -> loads research notes into Qdrant (collection: whitepapers)."""
import asyncio, sys
from app.agents.rag import ingest

if __name__ == "__main__":
    print("ingested chunks:", asyncio.run(ingest(sys.argv[1] if len(sys.argv) > 1 else None)))
