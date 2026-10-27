"""Password hashing (scrypt), HS256 tokens, validation helpers, rate limiter. Standard library only."""
import base64, hashlib, hmac, json, os, re, secrets, time
from collections import defaultdict, deque

COMMON = {"password", "password1", "1234567890", "qwertyuiop", "iloveyou12", "letmein123", "admin12345", "welcome123"}
EMAIL_RE = re.compile(r"^[^@\s]{1,64}@[^@\s]{1,255}\.[^@\s]{2,}$")


def _b64(b: bytes) -> str:
    return base64.urlsafe_b64encode(b).rstrip(b"=").decode()


def _unb64(s: str) -> bytes:
    return base64.urlsafe_b64decode(s + "=" * (-len(s) % 4))


def hash_password(pw: str) -> str:
    salt = os.urandom(16)
    dk = hashlib.scrypt(pw.encode(), salt=salt, n=2 ** 14, r=8, p=1, dklen=32)
    return f"scrypt${2 ** 14}${8}${1}${_b64(salt)}${_b64(dk)}"


def verify_password(pw: str, stored: str) -> bool:
    try:
        _, n, r, p, salt, dk = stored.split("$")
        calc = hashlib.scrypt(pw.encode(), salt=_unb64(salt), n=int(n), r=int(r), p=int(p), dklen=32)
        return hmac.compare_digest(calc, _unb64(dk))
    except Exception:
        return False


DUMMY_HASH = hash_password("dummy-password-for-timing")   # verify against this when the user does not exist


def make_token(payload: dict, secret: str, hours: int = 0, ttl_s: int | None = None) -> str:
    now = int(time.time())
    body = {**payload, "iat": now, "exp": now + (ttl_s if ttl_s is not None else hours * 3600)}
    head = _b64(json.dumps({"alg": "HS256", "typ": "JWT"}, separators=(",", ":")).encode())
    data = _b64(json.dumps(body, separators=(",", ":")).encode())
    sig = _b64(hmac.new(secret.encode(), f"{head}.{data}".encode(), hashlib.sha256).digest())
    return f"{head}.{data}.{sig}"


def read_token(token: str, secret: str) -> dict | None:
    try:
        head, data, sig = token.split(".")
        good = _b64(hmac.new(secret.encode(), f"{head}.{data}".encode(), hashlib.sha256).digest())
        if not hmac.compare_digest(sig, good):
            return None
        if json.loads(_unb64(head)).get("alg") != "HS256":
            return None
        body = json.loads(_unb64(data))
        return body if int(body.get("exp", 0)) > time.time() else None
    except Exception:
        return None


def fingerprint(s: str) -> str:
    return hashlib.sha256(s.encode()).hexdigest()[:16]


def purpose_token(purpose: str, uid: int, secret: str, ttl_s: int, **extra) -> str:
    return make_token({"p": purpose, "sub": str(uid), **extra}, secret, ttl_s=ttl_s)


def read_purpose(token: str, purpose: str, secret: str) -> dict | None:
    body = read_token(token, secret)
    return body if body and body.get("p") == purpose else None


def hash_key(key: str) -> str:
    return hashlib.sha256(key.encode()).hexdigest()


def new_api_key() -> tuple[str, str, str]:
    key = "dok_" + secrets.token_urlsafe(24)
    return key, key[:8], hash_key(key)


def password_problem(pw: str) -> str | None:
    if len(pw) < 10:
        return "Password must be at least 10 characters."
    if len(pw) > 128:
        return "Password must be at most 128 characters."
    if len(set(pw)) < 5 or pw.lower() in COMMON:
        return "Choose a less predictable password."
    return None


def clean_email(e: str) -> str | None:
    e = e.strip().lower()
    return e if len(e) <= 254 and EMAIL_RE.match(e) else None


class Limiter:
    """In-memory sliding-window limiter (single process). Use a shared store if you scale to several instances."""

    def __init__(self) -> None:
        self.h: dict[str, deque] = defaultdict(deque)

    def allow(self, key: str, limit: int, window_s: float) -> bool:
        now = time.monotonic()
        q = self.h[key]
        while q and now - q[0] > window_s:
            q.popleft()
        if len(q) >= limit:
            return False
        q.append(now)
        if len(self.h) > 20000:
            for k in [k for k, v in self.h.items() if not v]:
                del self.h[k]
        return True

    def count(self, key: str, window_s: float) -> int:
        now = time.monotonic()
        q = self.h.get(key)
        return sum(1 for t in q if now - t <= window_s) if q else 0

    def reset(self, key: str) -> None:
        self.h.pop(key, None)
