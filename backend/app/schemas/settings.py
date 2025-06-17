from pydantic import BaseModel, Field
from typing import Optional
from datetime import datetime


class SettingsUpdate(BaseModel):
    """Schema for updating application settings"""
    
    # Cost limits
    max_cost_per_hour: Optional[float] = Field(None, ge=0.01, le=1000.0, description="Maximum cost per hour in USD")
    max_total_cost: Optional[float] = Field(None, ge=1.0, le=100000.0, description="Maximum total cost in USD")
    
    # File size limits (in MB)
    max_upload_size_mb: Optional[int] = Field(None, ge=1, le=10000, description="Maximum upload size in MB")
    max_hash_file_size_mb: Optional[int] = Field(None, ge=1, le=1000, description="Maximum hash file size in MB")
    
    # Data retention
    data_retention_days: Optional[int] = Field(None, ge=1, le=365, description="Data retention period in days")
    
    # AWS S3 settings
    s3_bucket_name: Optional[str] = Field(None, max_length=255, description="S3 bucket name")
    s3_region: Optional[str] = Field(None, max_length=50, description="AWS region")
    
    # Vast.ai settings
    vast_cloud_connection_id: Optional[str] = Field(None, max_length=255, description="Vast.ai cloud connection ID")
    
    # Sensitive fields (will be encrypted)
    aws_access_key_id: Optional[str] = Field(None, max_length=128, description="AWS access key ID")
    aws_secret_access_key: Optional[str] = Field(None, max_length=128, description="AWS secret access key")
    vast_api_key: Optional[str] = Field(None, max_length=128, description="Vast.ai API key")

    class Config:
        schema_extra = {
            "example": {
                "max_cost_per_hour": 2.0,
                "max_total_cost": 1000.0,
                "max_upload_size_mb": 1000,
                "max_hash_file_size_mb": 50,
                "data_retention_days": 30,
                "s3_bucket_name": "vpk-storage",
                "s3_region": "us-east-1",
                "vast_cloud_connection_id": "26017",
                "aws_access_key_id": "AKIAEXAMPLE",
                "aws_secret_access_key": "secret-key-here",
                "vast_api_key": "vast-api-key-here"
            }
        }


class SettingsResponse(BaseModel):
    """Schema for returning application settings (sensitive fields masked)"""
    
    # Cost limits
    max_cost_per_hour: float
    max_total_cost: float
    
    # File size limits
    max_upload_size_mb: int
    max_hash_file_size_mb: int
    
    # Data retention
    data_retention_days: int
    
    # AWS S3 settings (non-sensitive)
    s3_bucket_name: Optional[str]
    s3_region: Optional[str]
    
    # Vast.ai settings (non-sensitive)
    vast_cloud_connection_id: Optional[str]
    
    # Configuration status (don't expose actual sensitive values)
    aws_configured: bool = Field(description="Whether AWS credentials are configured")
    vast_configured: bool = Field(description="Whether Vast.ai API key is configured")
    
    # Timestamps
    created_at: Optional[datetime]
    updated_at: Optional[datetime]

    class Config:
        from_attributes = True
        schema_extra = {
            "example": {
                "max_cost_per_hour": 2.0,
                "max_total_cost": 1000.0,
                "max_upload_size_mb": 1000,
                "max_hash_file_size_mb": 50,
                "data_retention_days": 30,
                "s3_bucket_name": "vpk-storage",
                "s3_region": "us-east-1",
                "vast_cloud_connection_id": "26017",
                "aws_configured": True,
                "vast_configured": True,
                "created_at": "2025-01-06T12:00:00Z",
                "updated_at": "2025-01-06T12:00:00Z"
            }
        }


class ConnectionTestResponse(BaseModel):
    """Schema for connection test responses"""
    status: str = Field(description="Test status: success, warning, or error")
    message: str = Field(description="Human-readable test result message")

    class Config:
        schema_extra = {
            "example": {
                "status": "success",
                "message": "AWS S3 connection successful"
            }
        }