from sqlalchemy.orm import Session
from typing import Optional
import os

from app.models.system_setting import ApplicationSetting
from app.core.database import get_db


class SettingsService:
    """Service for accessing application settings from database"""
    
    def __init__(self, db: Session):
        self.db = db
        self._settings_cache = None
    
    def _get_settings(self) -> ApplicationSetting:
        """Get settings from database with caching"""
        if self._settings_cache is None:
            settings = self.db.query(ApplicationSetting).filter(ApplicationSetting.id == 1).first()
            if not settings:
                # Create default settings if none exist
                settings = ApplicationSetting(
                    id=1,
                    max_cost_per_hour=2.0,
                    max_total_cost=1000.0,
                    max_upload_size_mb=1000,
                    max_hash_file_size_mb=50,
                    data_retention_days=30,
                    s3_region="us-east-1"
                )
                self.db.add(settings)
                self.db.commit()
                self.db.refresh(settings)
            self._settings_cache = settings
        return self._settings_cache
    
    def clear_cache(self):
        """Clear settings cache to force reload from database"""
        self._settings_cache = None
    
    # Cost limits
    @property
    def max_cost_per_hour(self) -> float:
        return float(self._get_settings().max_cost_per_hour)
    
    @property
    def max_total_cost(self) -> float:
        return float(self._get_settings().max_total_cost)
    
    # File size limits (in bytes for compatibility with existing code)
    @property
    def max_upload_size_bytes(self) -> int:
        return self._get_settings().max_upload_size_mb * 1024 * 1024
    
    @property
    def max_hash_file_size_bytes(self) -> int:
        return self._get_settings().max_hash_file_size_mb * 1024 * 1024
    
    # File size limits (in MB)
    @property
    def max_upload_size_mb(self) -> int:
        return self._get_settings().max_upload_size_mb
    
    @property
    def max_hash_file_size_mb(self) -> int:
        return self._get_settings().max_hash_file_size_mb
    
    # Data retention
    @property
    def data_retention_days(self) -> int:
        return self._get_settings().data_retention_days
    
    # AWS S3 settings
    @property
    def aws_access_key_id(self) -> Optional[str]:
        return self._get_settings().aws_access_key_id
    
    @property
    def aws_secret_access_key(self) -> Optional[str]:
        return self._get_settings().aws_secret_access_key
    
    @property
    def s3_bucket_name(self) -> Optional[str]:
        return self._get_settings().s3_bucket_name
    
    @property
    def s3_region(self) -> str:
        return self._get_settings().s3_region or "us-east-1"
    
    # Vast.ai settings
    @property
    def vast_api_key(self) -> Optional[str]:
        return self._get_settings().vast_api_key
    
    @property
    def vast_cloud_connection_id(self) -> Optional[str]:
        return self._get_settings().vast_cloud_connection_id
    
    # Fallback to environment variables if database values are not set
    def get_aws_access_key_id(self) -> Optional[str]:
        """Get AWS access key ID from database or fallback to env"""
        db_value = self.aws_access_key_id
        if db_value:
            return db_value
        return os.getenv("AWS_ACCESS_KEY_ID")
    
    def get_aws_secret_access_key(self) -> Optional[str]:
        """Get AWS secret access key from database or fallback to env"""
        db_value = self.aws_secret_access_key
        if db_value:
            return db_value
        return os.getenv("AWS_SECRET_ACCESS_KEY")
    
    def get_vast_api_key(self) -> Optional[str]:
        """Get Vast.ai API key from database or fallback to env"""
        db_value = self.vast_api_key
        if db_value:
            return db_value
        return os.getenv("VAST_API_KEY")


# Global settings instance - will be initialized in main.py
settings_service: Optional[SettingsService] = None


def get_settings_service() -> SettingsService:
    """Get the global settings service instance"""
    if settings_service is None:
        raise RuntimeError("Settings service not initialized")
    return settings_service


def init_settings_service():
    """Initialize the global settings service with database connection"""
    global settings_service
    db = next(get_db())
    try:
        settings_service = SettingsService(db)
    finally:
        db.close()