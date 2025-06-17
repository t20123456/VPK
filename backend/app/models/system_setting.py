from sqlalchemy import Column, String, Text, Boolean, DECIMAL, Integer
from cryptography.fernet import Fernet
import os
import base64

from .base import Base, TimestampMixin


class SystemSetting(Base, TimestampMixin):
    __tablename__ = "system_settings"

    key = Column(String(100), primary_key=True)
    value = Column(Text, nullable=False)
    description = Column(Text)
    is_encrypted = Column(Boolean, default=False, nullable=False)
    
    @classmethod
    def _get_encryption_key(cls):
        """Get encryption key for sensitive settings"""
        key = os.getenv("SETTINGS_ENCRYPTION_KEY")
        if not key:
            raise ValueError(
                "SETTINGS_ENCRYPTION_KEY environment variable is required but not set. "
                "Please generate a key with: python -c \"import os, base64; print(base64.urlsafe_b64encode(os.urandom(32)).decode())\" "
                "and set it in your environment before saving encrypted settings."
            )
        return key
    
    def set_encrypted_value(self, value: str):
        """Encrypt and set a sensitive value"""
        if value is None:
            self.value = None
            return
            
        key = self._get_encryption_key()
        f = Fernet(key.encode())
        encrypted_value = f.encrypt(value.encode())
        self.value = base64.urlsafe_b64encode(encrypted_value).decode()
        self.is_encrypted = True
    
    def get_decrypted_value(self) -> str:
        """Get decrypted value if encrypted, otherwise return plain value"""
        if not self.is_encrypted or self.value is None:
            return self.value
            
        try:
            key = self._get_encryption_key()
            f = Fernet(key.encode())
            encrypted_bytes = base64.urlsafe_b64decode(self.value.encode())
            decrypted_value = f.decrypt(encrypted_bytes).decode()
            return decrypted_value
        except Exception as e:
            raise ValueError(f"Failed to decrypt setting {self.key}: {e}")


class ApplicationSetting(Base, TimestampMixin):
    """Application settings with proper typing and encryption for sensitive fields"""
    __tablename__ = "application_settings"
    
    # Cost limits
    max_cost_per_hour = Column(DECIMAL(10, 4), nullable=False, default=10.0)
    max_total_cost = Column(DECIMAL(10, 4), nullable=False, default=1000.0)
    
    # File size limits (in MB)
    max_upload_size_mb = Column(Integer, nullable=False, default=100)
    max_hash_file_size_mb = Column(Integer, nullable=False, default=50)
    
    # Data retention
    data_retention_days = Column(Integer, nullable=False, default=30)
    
    # AWS S3 settings (non-sensitive)
    s3_bucket_name = Column(String(255))
    s3_region = Column(String(50), default="us-east-1")
    
    # Vast.ai settings (non-sensitive)
    vast_cloud_connection_id = Column(String(255))
    
    # Encrypted sensitive fields
    aws_access_key_id_encrypted = Column(Text)
    aws_secret_access_key_encrypted = Column(Text)
    vast_api_key_encrypted = Column(Text)
    
    # Singleton pattern - only one row should exist
    id = Column(Integer, primary_key=True, default=1)
    
    @classmethod
    def _get_encryption_key(cls):
        """Get encryption key for sensitive settings"""
        key = os.getenv("SETTINGS_ENCRYPTION_KEY")
        if not key:
            raise ValueError(
                "SETTINGS_ENCRYPTION_KEY environment variable is required but not set. "
                "Please generate a key with: python -c \"import os, base64; print(base64.urlsafe_b64encode(os.urandom(32)).decode())\" "
                "and set it in your environment before saving encrypted settings."
            )
        return key
    
    def _encrypt_value(self, value: str) -> str:
        """Encrypt a sensitive value"""
        if value is None:
            return None
            
        key = self._get_encryption_key()
        f = Fernet(key.encode())
        encrypted_value = f.encrypt(value.encode())
        return base64.urlsafe_b64encode(encrypted_value).decode()
    
    def _decrypt_value(self, encrypted_value: str) -> str:
        """Decrypt a sensitive value"""
        if encrypted_value is None:
            return None
            
        try:
            key = self._get_encryption_key()
            f = Fernet(key.encode())
            encrypted_bytes = base64.urlsafe_b64decode(encrypted_value.encode())
            decrypted_value = f.decrypt(encrypted_bytes).decode()
            return decrypted_value
        except Exception as e:
            raise ValueError(f"Failed to decrypt sensitive value: {e}")
    
    # AWS Access Key ID property
    @property
    def aws_access_key_id(self) -> str:
        return self._decrypt_value(self.aws_access_key_id_encrypted)
    
    @aws_access_key_id.setter
    def aws_access_key_id(self, value: str):
        self.aws_access_key_id_encrypted = self._encrypt_value(value)
    
    # AWS Secret Access Key property
    @property
    def aws_secret_access_key(self) -> str:
        return self._decrypt_value(self.aws_secret_access_key_encrypted)
    
    @aws_secret_access_key.setter
    def aws_secret_access_key(self, value: str):
        self.aws_secret_access_key_encrypted = self._encrypt_value(value)
    
    # Vast API Key property
    @property
    def vast_api_key(self) -> str:
        return self._decrypt_value(self.vast_api_key_encrypted)
    
    @vast_api_key.setter
    def vast_api_key(self, value: str):
        self.vast_api_key_encrypted = self._encrypt_value(value)