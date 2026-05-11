from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",
    )

    # --- Application ---
    APP_NAME: str = "Interview Practice App"
    DEBUG: bool = False
    API_V1_PREFIX: str = "/api/v1"

    # --- Database ---
    DATABASE_URL: str = "postgresql+asyncpg://postgres:dev_password@localhost:5432/interview_practice"

    # --- LLM ---
    LLM_PROVIDER: str = "dashscope"
    LLM_BASE_URL: str = "https://dashscope.aliyuncs.com/compatible-mode/v1"
    LLM_API_KEY: str = ""
    LLM_MODEL_NAME: str = "qwen3-vl-plus"
    LLM_MAX_RETRIES: int = 3
    LLM_TIMEOUT: int = 180

    # --- Embedding ---
    EMBEDDING_PROVIDER: str = "local"
    EMBEDDING_MODEL_PATH: str = "D:/AI_Project/models/bge-small-zh-v1.5"
    EMBEDDING_DIMENSION: int = 512

    # --- Reranker ---
    RERANKER_PROVIDER: str = "local"
    RERANKER_MODEL_PATH: str = "D:/AI_Project/models/bge-reranker-v2-m3"

    # --- Auth ---
    AUTH_ENABLED: bool = False
    PUBLIC_MODE: bool = True
    JWT_SECRET_KEY: str = "change-me-in-production"
    JWT_ALGORITHM: str = "HS256"
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 60 * 24

    # --- File Storage ---
    UPLOAD_DIR: str = "uploads"
    MAX_UPLOAD_SIZE_MB: int = 50

    # --- Vector DB ---
    VECTOR_STORE_TYPE: str = "pgvector"


settings = Settings()

