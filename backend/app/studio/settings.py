"""Runtime settings from environment variables (plain Python: no extra dependencies)."""
import os, secrets


def normalize_db_url(url: str) -> str:
    """Accept postgres:// / postgresql:// URLs (Neon, Render, Supabase...) and make them asyncpg-compatible."""
    if url.startswith("postgres://"):
        url = "postgresql://" + url[len("postgres://"):]
    if url.startswith("postgresql://"):
        url = "postgresql+asyncpg://" + url[len("postgresql://"):]
    if url.startswith("postgresql+asyncpg://") and "?" in url:
        base, q = url.split("?", 1)
        parts = []
        for kv in q.split("&"):
            k, _, v = kv.partition("=")
            if k == "sslmode":
                parts.append("ssl=" + v)          # asyncpg uses 'ssl', not 'sslmode'
            elif k == "channel_binding":
                continue                           # unsupported by asyncpg
            else:
                parts.append(kv)
        url = base + ("?" + "&".join(parts) if parts else "")
    return url


def _int(name: str, default: int) -> int:
    try:
        return int(os.getenv(name, default))
    except ValueError:
        return default


def _bool(name: str, default: bool) -> bool:
    v = os.getenv(name)
    return default if v is None else v.strip().lower() in ("1", "true", "yes", "on")


class Settings:
    def __init__(self) -> None:
        self.env = os.getenv("ENV", "development").lower()
        self.database_url = normalize_db_url(os.getenv("DATABASE_URL", "sqlite+aiosqlite:///./studio.db"))
        secret = os.getenv("JWT_SECRET", "")
        if not secret:
            if self.env == "production":
                raise RuntimeError("JWT_SECRET must be set when ENV=production")
            secret = secrets.token_urlsafe(32)      # development only: sessions reset on restart
        self.jwt_secret = secret
        self.token_hours = _int("TOKEN_HOURS", 12)
        self.cors_origins = [o.strip() for o in os.getenv("CORS_ORIGINS", "http://localhost:5173,http://localhost:8000").split(",") if o.strip()]
        self.admin_emails = {e.strip().lower() for e in os.getenv("ADMIN_EMAILS", "").split(",") if e.strip()}
        self.registration_open = _bool("REGISTRATION_OPEN", True)
        self.trust_proxy = _bool("TRUST_PROXY", False)       # true when behind Render/Vercel/nginx (reads X-Forwarded-For)
        self.max_upload_mb = _int("MAX_UPLOAD_MB", 5)
        self.max_rows = _int("MAX_ROWS", 50000)
        self.max_cols = _int("MAX_COLS", 100)
        self.max_datasets = _int("MAX_DATASETS_PER_USER", 5)
        self.max_experiments = _int("MAX_EXPERIMENTS_PER_USER", 25)
        self.max_time_limit = _int("MAX_TIME_LIMIT_S", 300)
        self.max_concurrent = max(1, _int("MAX_CONCURRENT_JOBS", 1))
        self.max_users = _int("MAX_USERS", 1000)
        self.retention_days = _int("RETENTION_DAYS", 0)      # 0 = keep until the user deletes
        self.static_dir = os.getenv("STATIC_DIR", "")
        self.disable_rate_limits = _bool("DISABLE_RATE_LIMITS", False)   # tests only

    @property
    def is_sqlite(self) -> bool:
        return self.database_url.startswith("sqlite")


settings = Settings()
