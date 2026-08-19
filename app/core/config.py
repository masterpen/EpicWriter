from typing import Optional
from pydantic import model_validator
from pydantic_settings import BaseSettings

# 默认开发用密钥 —— 仅在 development 环境下允许使用
_DEV_SECRET_KEY = "dev_secret_key_change_in_production"


class Settings(BaseSettings):
    # Neo4j
    NEO4J_URI: str = "bolt://localhost:7687"
    NEO4J_USERNAME: str = "neo4j"
    NEO4J_PASSWORD: str = "password"

    # LLM (OpenAI / OpenRouter)
    OPENAI_API_KEY: Optional[str] = None
    OPENAI_BASE_URL: Optional[str] = None

    OPENROUTER_API_KEY: Optional[str] = None
    OPENROUTER_BASE_URL: str = "https://openrouter.ai/api/v1"

    # NVIDIA NIM
    NVIDIA_API_KEY: Optional[str] = None
    NVIDIA_BASE_URL: str = "https://integrate.api.nvidia.com/v1"

    # JWT
    JWT_SECRET_KEY: str = _DEV_SECRET_KEY
    JWT_ALGORITHM: str = "HS256"
    JWT_EXPIRE_HOURS: int = 24

    # App
    APP_ENV: str = "development"  # development | production
    LOG_LEVEL: str = "INFO"
    API_BASE_URL: str = "http://localhost:8000/api"

    class Config:
        env_file = ".env"
        extra = "ignore" # Allow extra env vars

    @model_validator(mode="after")
    def _enforce_jwt_secret_in_production(self) -> "Settings":
        """生产环境强制校验 JWT_SECRET_KEY，避免使用默认开发密钥导致 token 可被伪造。"""
        if self.APP_ENV == "production":
            if self.JWT_SECRET_KEY == _DEV_SECRET_KEY:
                raise ValueError(
                    "生产环境 (APP_ENV=production) 禁止使用默认 JWT_SECRET_KEY，"
                    "请在 .env 中设置一个高强度随机密钥（建议 >=32 字符）。"
                )
            if len(self.JWT_SECRET_KEY) < 16:
                raise ValueError(
                    f"生产环境 JWT_SECRET_KEY 长度 {len(self.JWT_SECRET_KEY)} 过短，"
                    "至少需要 16 字符，建议 >=32 字符的高强度随机字符串。"
                )
        return self


settings = Settings()
