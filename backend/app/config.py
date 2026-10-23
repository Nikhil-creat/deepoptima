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

settings = Settings()
