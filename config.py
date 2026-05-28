"""Application configuration using pydantic-settings."""

from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    """PulseCompanion backend configuration.

    Loads values from environment variables or .env file.
    """

    OLLAMA_BASE_URL: str = "http://localhost:11434"
    OLLAMA_MODEL: str = "phi3:mini"
    OLLAMA_EMBED_MODEL: str = "nomic-embed-text"
    CHROMADB_PATH: str = "./chroma_data"
    CHROMADB_COLLECTION: str = "pulse_companion_memory"
    CORS_ORIGINS: list[str] = ["http://localhost:3000"]
    LOG_LEVEL: str = "INFO"
    MAX_MEMORY_RESULTS: int = 3
    SESSION_TIMEOUT_MINUTES: int = 30
    VERSION: str = "8.0.0"
    LLM_BACKEND: str = "phi3_ollama"

    model_config = {"env_file": ".env"}


settings = Settings()
