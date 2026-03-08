import secrets
from pydantic_settings import BaseSettings, SettingsConfigDict
from functools import lru_cache


class Settings(BaseSettings):
    PROJECT_NAME: str = "TreeEdu Agent Backend"
    VERSION: str = "1.0.0"

    # Environment
    DEBUG: bool = False
    ENVIRONMENT: str = "development"

    # Database URL
    DATABASE_URL: str = "sqlite+aiosqlite:///./treeedu.db"

    # LLM API Keys
    OPENAI_API_KEY: str = ""
    GEMINI_API_KEY: str = ""
    DEEPSEEK_API_KEY: str = ""
    ALIYUN_API_KEY: str = ""

    # PageIndex
    PAGEINDEX_API_KEY: str = ""

    # Router Settings
    LLM_FAST_MODEL: str = "aliyun"
    LLM_HEAVY_MODEL: str = "aliyun"
    LLM_VISION_MODEL: str = "aliyun"

    # JWT Settings - Must be set in production
    JWT_SECRET_KEY: str = ""
    JWT_ALGORITHM: str = "HS256"
    JWT_ACCESS_TOKEN_EXPIRE_MINUTES: int = 60 * 2  # 2 hours

    # CORS Settings
    CORS_ORIGINS: str = "http://localhost:5173,http://localhost:3000"

    # Pydantic core settings lookup
    model_config = SettingsConfigDict(
        env_file=".env", env_file_encoding="utf-8", extra="ignore"
    )

    def get_jwt_secret(self) -> str:
        if self.JWT_SECRET_KEY:
            return self.JWT_SECRET_KEY
        if self.ENVIRONMENT == "production":
            raise ValueError("JWT_SECRET_KEY must be set in production environment")
        return "dev_only_secret_key_" + secrets.token_hex(16)


@lru_cache()
def get_settings() -> Settings:
    return Settings()
