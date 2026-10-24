from app.agents.rag import hash_embed, chunk
from app.audit_chain import chain_hash, verify_rows

def _cos(a, b): return sum(x * y for x, y in zip(a, b))

def test_hash_embed_ranks_relevant_text():
    q = hash_embed("loss became NaN, use gradient clipping and a lower learning rate")
    a = hash_embed("Loss becomes NaN or infinite: lower the learning rate and add gradient-norm clipping")
    b = hash_embed("Pareto front and crowding distance keep diversity in NSGA-II")
    assert _cos(q, a) > _cos(q, b)

def test_chunking():
    assert all(len(c) < 1500 for c in chunk("para\n\n" * 400))

class Row:
    def __init__(self, i, prev, action):
        self.id, self.actor_id, self.action, self.resource, self.detail, self.prev_hash = i, None, action, "r", {}, prev
        self.hash = chain_hash(None, action, "r", {}, prev)

def test_chain_detects_tamper():
    r1 = Row(1, "", "a"); r2 = Row(2, r1.hash, "b")
    assert verify_rows([r1, r2])["ok"]
    r1.action = "evil"
    assert verify_rows([r1, r2]) == {"ok": False, "checked": 1, "first_bad_id": 1}
