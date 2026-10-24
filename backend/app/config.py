from pydantic_settings import BaseSettings, SettingsConfigDict

class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")
    database_url: str = "postgresql+asyncpg://deepoptima:deepoptima@postgres:5432/deepoptima"
    redis_url: str = "redis://redis:6379/0"
    minio_endpoint: str = "minio:9000"
    minio_access_key: str = "minioadmin"
    minio_secret_key: str = "minioadmin"
    minio_bucket: str = "checkpoints"
    qdrant_url: str = "http://qdrant:6333"
    groq_api_key: str = ""
    gemini_api_key: str = ""
    groq_model: str = "auto"   # "auto" = detect from provider model list
    gemini_model: str = "auto"
    jwt_secret: str = "change-me"
    jwt_alg: str = "HS256"
    fernet_key: str = ""
    trial_timeout_s: int = 1800
    otlp_endpoint: str = "http://otel-collector:4317"
    mtls_enabled: bool = False                  # set MTLS_ENABLED=1 with rediss:// REDIS_URL (see docker-compose.mtls.yml)
    tls_ca: str = "/certs/ca/ca.crt"
    tls_cert: str = "/certs/nodes/client.crt"
    tls_key: str = "/certs/nodes/client.key"

    def redis_kwargs(self) -> dict:
        """Extra kwargs for redis.from_url when mutual TLS is on."""
        if not self.mtls_enabled: return {}
        return {"ssl_ca_certs": self.tls_ca, "ssl_certfile": self.tls_cert, "ssl_keyfile": self.tls_key,
                "ssl_cert_reqs": "required", "ssl_check_hostname": False}

    def celery_ssl(self) -> dict:
        import ssl
        return {"ssl_cert_reqs": ssl.CERT_REQUIRED, "ssl_ca_certs": self.tls_ca, "ssl_certfile": self.tls_cert, "ssl_keyfile": self.tls_key}

settings = Settings()
