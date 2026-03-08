from pydantic_settings import BaseSettings, SettingsConfigDict
from functools import lru_cache

class Settings(BaseSettings):
    PROJECT_NAME: str = "TreeEdu Agent Backend"
    VERSION: str = "1.0.0"
    
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
    # JWT Settings
    JWT_SECRET_KEY: str = "super_secret_temporary_key_for_dev_change_in_prod"
    JWT_ALGORITHM: str = "HS256"
    JWT_ACCESS_TOKEN_EXPIRE_MINUTES: int = 60 * 24 * 7 # 7 days
    
    # Pydantic core settings lookup 
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

@lru_cache()
def get_settings() -> Settings:
    return Settings()
