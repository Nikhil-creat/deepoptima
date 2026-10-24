"""Hash-chain helper shared by writer (security.audit) and verifier (/audit/verify). Pure python."""
import hashlib, json

def chain_hash(actor, action: str, resource: str, detail: dict | None, prev: str) -> str:
    payload = json.dumps({"a": str(actor), "act": action, "res": resource, "d": detail or {}, "p": prev}, sort_keys=True)
    return hashlib.sha256(payload.encode()).hexdigest()

def verify_rows(rows) -> dict:
    """rows: iterable of objects with actor_id, action, resource, detail, prev_hash, hash, id - ordered by id."""
    prev, n = "", 0
    for r in rows:
        n += 1
        if r.prev_hash != prev or r.hash != chain_hash(r.actor_id, r.action, r.resource, r.detail, prev):
            return {"ok": False, "checked": n, "first_bad_id": r.id}
        prev = r.hash
    return {"ok": True, "checked": n, "first_bad_id": None}
