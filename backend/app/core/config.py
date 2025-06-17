from pydantic_settings import BaseSettings
from typing import Optional
import os
import json


class Settings(BaseSettings):
    # Application
    PROJECT_NAME: str = "VPK"
    VERSION: str = "1.0.0"
    API_V1_STR: str = "/api/v1"
    
    # Security
    SECRET_KEY: str = os.getenv("SECRET_KEY", "dev_secret_key_change_in_production")
    ALGORITHM: str = "HS256"
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 30
    REFRESH_TOKEN_EXPIRE_DAYS: int = 7
    
    # Database
    DATABASE_URL: str = os.getenv(
        "DATABASE_URL",
        f"postgresql://{os.getenv('POSTGRES_USER', 'vpk')}:{os.getenv('POSTGRES_PASSWORD', 'vpk_dev_password')}@postgres:5432/{os.getenv('POSTGRES_DB', 'vpk_db')}"
    )
    
    # Redis
    REDIS_URL: str = os.getenv("REDIS_URL", "redis://redis:6379/0")
    
    # Vast.ai
    VAST_API_KEY: Optional[str] = os.getenv("VAST_API_KEY")
    VAST_CLOUD_CONNECTION_ID: Optional[str] = os.getenv("VAST_CLOUD_CONNECTION_ID")
    
    # AWS S3
    AWS_ACCESS_KEY_ID: Optional[str] = os.getenv("AWS_ACCESS_KEY_ID")
    AWS_SECRET_ACCESS_KEY: Optional[str] = os.getenv("AWS_SECRET_ACCESS_KEY")
    S3_BUCKET_NAME: Optional[str] = os.getenv("S3_BUCKET_NAME")
    S3_REGION: str = os.getenv("S3_REGION", "us-east-1")
    
    # Admin
    ADMIN_EMAIL: str = os.getenv("ADMIN_EMAIL", "admin@example.com")
    ADMIN_PASSWORD: str = os.getenv("ADMIN_PASSWORD", "admin123")
    
    # Limits
    MAX_COST_PER_HOUR: float = float(os.getenv("MAX_COST_PER_HOUR", "10.0"))
    MAX_TOTAL_COST: float = float(os.getenv("MAX_TOTAL_COST", "1000.0"))
    MAX_UPLOAD_SIZE_MB: int = int(os.getenv("MAX_UPLOAD_SIZE_MB", "100"))
    MAX_HASH_FILE_SIZE_MB: int = int(os.getenv("MAX_HASH_FILE_SIZE_MB", "50"))
    DATA_RETENTION_DAYS: int = int(os.getenv("DATA_RETENTION_DAYS", "30"))
    
    # CORS
    BACKEND_CORS_ORIGINS: list[str] = json.loads(
        os.getenv(
            "BACKEND_CORS_ORIGINS",
            '["http://localhost", "http://localhost:3000", "http://localhost:8000"]'
        )
    )
    
    class Config:
        case_sensitive = True


settings = Settings()