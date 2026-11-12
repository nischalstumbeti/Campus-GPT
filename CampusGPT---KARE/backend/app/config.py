"""Application configuration."""
from functools import lru_cache
from pathlib import Path

from pydantic_settings import BaseSettings, SettingsConfigDict

_ENV_FILE = Path(__file__).resolve().parent.parent / ".env"


class Settings(BaseSettings):
    """Application settings from environment variables."""

    model_config = SettingsConfigDict(
        env_file=str(_ENV_FILE),
        env_file_encoding="utf-8",
        case_sensitive=True,
        extra="ignore",
    )

    # API
    API_V1_STR: str = "/api"

    # AI API (Gemini only)
    GEMINI_API_KEY: str = ""
    # gemini-flash-latest maps to gemini-3, which allows 5 free requests.
    GEMINI_CHAT_MODEL: str = "gemini-2.5-flash"
    GEMINI_EMBEDDING_MODEL: str = "models/text-embedding-004"

    # Database
    DATABASE_URL: str = "postgresql+asyncpg://postgres:postgres@localhost:5432/campus_gpt"

    # Vector DB (FAISS)
    FAISS_INDEX_PATH: str = "./data/faiss_index"
    EMBEDDING_DIM: int = 768

    # RAG
    RAG_TOP_K: int = 5
    RAG_CHUNK_SIZE: int = 750
    RAG_CHUNK_OVERLAP: int = 100

    # Confidence
    CONFIDENCE_THRESHOLD: float = 0.7
    ESCALATION_ENABLED: bool = True

    # JWT
    ENVIRONMENT: str = "development"
    SECRET_KEY: str = "dev-only-insecure-campus-gpt-key"
    ALGORITHM: str = "HS256"
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 60 * 8  # 8 hours
    ALLOW_PUBLIC_DEMO: bool = True

    # OAuth (Google) — only institutional emails may complete sign-in
    GOOGLE_CLIENT_ID: str = ""
    GOOGLE_CLIENT_SECRET: str = ""
    GOOGLE_ALLOWED_DOMAIN: str = "klu.ac.in"
    # Must match uvicorn PORT (default 8002) and Google OAuth redirect URI
    API_BASE_URL: str = "http://localhost:8002"
    FRONTEND_URL: str = "http://localhost:3001"
    # University Information System (separate app — API integration only)
    UIS_API_BASE_URL: str = "http://localhost:8000"
    UIS_INTEGRATION_API_KEY: str = "uis-campus-gpt-dev-integration-key"
    UIS_ENABLED: bool = True
    # Personal academic / residence data must come from UIS DB via API (not local SIS seed)
    ALLOW_LOCAL_SIS_FALLBACK: bool = False
    # Seed Campus-GPT auth/demo rows into the app DB on startup (personal records still from UIS)
    SEED_LOCAL_ACADEMIC: bool = True

    # Supabase / optional external stores (admin connectors can overwrite these)
    SUPABASE_URL: str = ""
    SUPABASE_KEY: str = ""
    SUPABASE_DB_URL: str = ""
    SUPABASE_BUCKET: str = "campus-documents"
    MONGODB_URI: str = ""
    MONGODB_DB: str = "campus"
    S3_ENDPOINT: str = ""
    S3_REGION: str = "us-east-1"
    S3_BUCKET: str = ""
    S3_ACCESS_KEY: str = ""
    S3_SECRET_KEY: str = ""

    # Voice: Whisper STT fallback (Hugging Face). Prefer ElevenLabs Scribe when key is set.
    WHISPER_MODEL: str = "bryandts/whisper-base-en-india-accent-svarah"
    # Voice: TTS — ElevenLabs when enabled; else edge-tts Indian English
    TTS_VOICE: str = "en-IN-NeerjaNeural"
    ELEVENLABS_API_KEY: str = ""
    ELEVENLABS_VOICE_ID: str = "21m00Tcm4TlvDq8ikWAM"
    ELEVENLABS_ENABLED: bool = True
    ELEVENLABS_STT_MODEL: str = "scribe_v2"

    # Email (Gmail SMTP / app password) — disabled until SMTP_USER is set
    EMAIL_ENABLED: bool = False
    SMTP_HOST: str = "smtp.gmail.com"
    SMTP_PORT: int = 587
    SMTP_USER: str = ""
    SMTP_PASSWORD: str = ""
    SMTP_FROM: str = "Campus-GPT <99230041300@klu.ac.in>"


@lru_cache()
def get_settings() -> Settings:
    """Get cached settings instance."""
    return Settings()
