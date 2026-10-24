"""CI guard: the lightweight API image must not import torch/celery/etc at module level (starting from app.api.main)."""
import ast, pathlib, sys
ROOT = pathlib.Path(__file__).resolve().parents[1] / "backend"
HEAVY = {"torch", "torchvision", "celery", "ray", "minio", "onnx", "onnxruntime", "wasmtime", "langgraph", "qdrant_client", "langchain_core"}

def file_of(mod):
    base = ROOT / mod.replace(".", "/")
    for c in (base.with_suffix(".py"), base / "__init__.py"):
        if c.exists(): return c

def imports(node_list):
    for n in node_list:
        if isinstance(n, ast.Import):
            for a in n.names: yield a.name
        elif isinstance(n, ast.ImportFrom) and n.module and n.level == 0:
            yield n.module
            for a in n.names: yield f"{n.module}.{a.name}"
        elif isinstance(n, (ast.If, ast.Try, ast.With)):
            for body in (getattr(n, "body", []), getattr(n, "orelse", []), getattr(n, "finalbody", [])):
                yield from imports(body)
            for h in getattr(n, "handlers", []): yield from imports(h.body)

seen, queue, bad = set(), [("app.api.main", ["app.api.main"])], []
while queue:
    mod, chain = queue.pop()
    if mod in seen: continue
    seen.add(mod)
    f = file_of(mod)
    if not f: continue
    for name in imports(ast.parse(f.read_text()).body):
        if name.split(".")[0] in HEAVY: bad.append(chain + [name])
        elif name.startswith("app."): queue.append((name, chain + [name]))
if bad:
    for b in bad: print("HEAVY IMPORT:", " -> ".join(b))
    sys.exit(1)
print(f"lite API import graph OK ({len(seen)} modules)")
