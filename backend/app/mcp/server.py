"""MCP server: lets external LLM clients audit and trigger searches. Run: python -m app.mcp.server
Uses the control-plane API with a service token (MCP_API_TOKEN) so RBAC + audit logging still apply."""
import os, httpx
from mcp.server.fastmcp import FastMCP

API = os.environ.get("API_URL", "http://api:8000")
TOKEN = os.environ.get("MCP_API_TOKEN", "")
mcp = FastMCP("deepoptima", host="0.0.0.0", port=8765)

def _c() -> httpx.AsyncClient:
    return httpx.AsyncClient(base_url=API, headers={"Authorization": f"Bearer {TOKEN}"}, timeout=30)

@mcp.tool()
async def list_experiments() -> list:
    """List NAS experiments with status."""
    async with _c() as c: return (await c.get("/experiments")).json()

@mcp.tool()
async def get_trials(experiment_id: str, status: str | None = None) -> list:
    """Trial logs (genotype, accuracy, latency, params, loss curve, errors) for an experiment."""
    async with _c() as c: return (await c.get(f"/experiments/{experiment_id}/trials", params={"status": status} if status else None)).json()

@mcp.tool()
async def get_pareto_front(experiment_id: str) -> list:
    """Non-dominated trials (accuracy vs latency vs params)."""
    async with _c() as c: return (await c.get(f"/experiments/{experiment_id}/pareto")).json()

@mcp.tool()
async def start_search(name: str, population_size: int = 16, max_generations: int = 10, epochs: int = 3) -> dict:
    """Start a new CIFAR-10 CNN search (requires researcher role on the service token)."""
    async with _c() as c:
        return (await c.post("/experiments", json={"name": name, "population_size": population_size,
                                                    "max_generations": max_generations, "epochs": epochs})).json()

@mcp.resource("deepoptima://workers")
async def workers() -> str:
    async with _c() as c: return (await c.get("/workers")).text

if __name__ == "__main__":
    mcp.run(transport="sse")
