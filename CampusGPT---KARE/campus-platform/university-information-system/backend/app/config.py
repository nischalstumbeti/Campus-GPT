from functools import lru_cache
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

    environment: str = "development"
    database_url: str = "sqlite+aiosqlite:///./uis.db"
    jwt_secret: str = "dev-only-insecure-uis-key"
    jwt_algorithm: str = "HS256"
    access_token_expire_minutes: int = 240
    api_base_url: str = "http://localhost:8000"
    uis_frontend_url: str = "http://localhost:3000"
    cors_origins: str = "http://localhost:3000,http://127.0.0.1:3000,http://localhost:3001,http://127.0.0.1:3001"
    integration_api_key: str = "uis-campus-gpt-dev-integration-key"
    supabase_url: str = ""
    supabase_key: str = ""
    supabase_db_url: str = ""
    mongodb_uri: str = ""
    mongodb_db: str = "campus"
    s3_endpoint: str = ""
    s3_region: str = "us-east-1"
    s3_bucket: str = ""
    s3_access_key: str = ""
    s3_secret_key: str = ""
    email_enabled: bool = True
    smtp_host: str = "smtp.gmail.com"
    smtp_port: int = 587
    smtp_user: str = ""
    smtp_password: str = ""
    smtp_from: str = "KARE UIS <99230041300@klu.ac.in>"

    @property
    def cors_origin_list(self) -> list[str]:
        # Keep these even when CORS_ORIGINS on the host replaces the default.
        # The live CIMS login page calls this API from the browser.
        required = (
            "http://localhost:3000",
            "http://127.0.0.1:3000",
            "http://localhost:3001",
            "http://127.0.0.1:3001",
            "https://cims-campusgpt.vercel.app",
            "https://cims-seven.vercel.app",
            "https://campus-gpt-ecru.vercel.app",
            "https://campusgpt-ai.vercel.app",
        )
        origins: list[str] = []
        for origin in (*self.cors_origins.split(","), *required):
            origin = origin.strip().rstrip("/")
            if origin and origin not in origins:
                origins.append(origin)
        return origins


@lru_cache
def get_settings() -> Settings:
    return Settings()
