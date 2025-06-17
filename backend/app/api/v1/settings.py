from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from typing import Dict, Any

from app.core.database import get_db
from app.models.user import User
from app.models.system_setting import ApplicationSetting
from app.api.deps import get_current_admin_user
from app.schemas.settings import SettingsResponse, SettingsUpdate

router = APIRouter()


@router.get("/", response_model=SettingsResponse)
def get_settings(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_admin_user)
):
    """Get application settings (admin only)"""
    settings = db.query(ApplicationSetting).filter(ApplicationSetting.id == 1).first()
    
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
        db.add(settings)
        db.commit()
        db.refresh(settings)
    
    return SettingsResponse(
        max_cost_per_hour=float(settings.max_cost_per_hour),
        max_total_cost=float(settings.max_total_cost),
        max_upload_size_mb=settings.max_upload_size_mb,
        max_hash_file_size_mb=settings.max_hash_file_size_mb,
        data_retention_days=settings.data_retention_days,
        s3_bucket_name=settings.s3_bucket_name,
        s3_region=settings.s3_region,
        vast_cloud_connection_id=settings.vast_cloud_connection_id,
        # Only show if keys are configured (don't expose actual values)
        aws_configured=bool(settings.aws_access_key_id_encrypted),
        vast_configured=bool(settings.vast_api_key_encrypted),
        created_at=settings.created_at,
        updated_at=settings.updated_at
    )


@router.patch("/", response_model=SettingsResponse)
def update_settings(
    settings_update: SettingsUpdate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_admin_user)
):
    """Update application settings (admin only)"""
    settings = db.query(ApplicationSetting).filter(ApplicationSetting.id == 1).first()
    
    if not settings:
        settings = ApplicationSetting(id=1)
        db.add(settings)
    
    # Update non-sensitive fields
    update_data = settings_update.dict(exclude_unset=True, exclude={
        'aws_access_key_id', 'aws_secret_access_key', 'vast_api_key'
    })
    
    for field, value in update_data.items():
        if hasattr(settings, field):
            setattr(settings, field, value)
    
    # Update sensitive fields using properties (which handle encryption)
    try:
        if settings_update.aws_access_key_id is not None:
            settings.aws_access_key_id = settings_update.aws_access_key_id
        
        if settings_update.aws_secret_access_key is not None:
            settings.aws_secret_access_key = settings_update.aws_secret_access_key
        
        if settings_update.vast_api_key is not None:
            settings.vast_api_key = settings_update.vast_api_key
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    
    db.commit()
    db.refresh(settings)
    
    # Clear settings service cache to ensure fresh credentials are used
    from app.services.settings_service import get_settings_service
    try:
        settings_service = get_settings_service()
        settings_service.clear_cache()
    except RuntimeError:
        # Settings service not initialized yet, which is fine
        pass
    
    return SettingsResponse(
        max_cost_per_hour=float(settings.max_cost_per_hour),
        max_total_cost=float(settings.max_total_cost),
        max_upload_size_mb=settings.max_upload_size_mb,
        max_hash_file_size_mb=settings.max_hash_file_size_mb,
        data_retention_days=settings.data_retention_days,
        s3_bucket_name=settings.s3_bucket_name,
        s3_region=settings.s3_region,
        vast_cloud_connection_id=settings.vast_cloud_connection_id,
        aws_configured=bool(settings.aws_access_key_id_encrypted),
        vast_configured=bool(settings.vast_api_key_encrypted),
        created_at=settings.created_at,
        updated_at=settings.updated_at
    )


@router.post("/test-aws")
def test_aws_connection(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_admin_user)
):
    """Test AWS S3 connection with current settings"""
    settings = db.query(ApplicationSetting).filter(ApplicationSetting.id == 1).first()
    
    if not settings or not settings.aws_access_key_id or not settings.aws_secret_access_key:
        raise HTTPException(status_code=400, detail="AWS credentials not configured")
    
    try:
        import boto3
        from botocore.exceptions import ClientError
        
        # Test S3 connection
        s3_client = boto3.client(
            's3',
            aws_access_key_id=settings.aws_access_key_id,
            aws_secret_access_key=settings.aws_secret_access_key,
            region_name=settings.s3_region
        )
        
        # Try to list objects in the bucket
        if settings.s3_bucket_name:
            s3_client.head_bucket(Bucket=settings.s3_bucket_name)
            return {"status": "success", "message": "AWS S3 connection successful"}
        else:
            # Just test credentials without bucket
            s3_client.list_buckets()
            return {"status": "success", "message": "AWS credentials valid, but no bucket configured"}
            
    except ClientError as e:
        error_code = e.response['Error']['Code']
        if error_code == 'NoSuchBucket':
            return {"status": "warning", "message": f"Bucket '{settings.s3_bucket_name}' does not exist"}
        elif error_code == 'AccessDenied':
            return {"status": "error", "message": "Access denied - check your AWS credentials and permissions"}
        else:
            return {"status": "error", "message": f"AWS error: {error_code}"}
    except Exception as e:
        return {"status": "error", "message": f"Connection failed: {str(e)}"}


@router.post("/test-vast")
def test_vast_connection(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_admin_user)
):
    """Test Vast.ai API connection with current settings"""
    settings = db.query(ApplicationSetting).filter(ApplicationSetting.id == 1).first()
    
    if not settings or not settings.vast_api_key:
        raise HTTPException(status_code=400, detail="Vast.ai API key not configured")
    
    try:
        import requests
        
        # Test Vast.ai API connection
        headers = {'Authorization': f'Bearer {settings.vast_api_key}'}
        response = requests.get('https://console.vast.ai/api/v0/instances', headers=headers, timeout=10)
        
        if response.status_code == 200:
            return {"status": "success", "message": "Vast.ai API connection successful"}
        elif response.status_code == 401:
            return {"status": "error", "message": "Invalid Vast.ai API key"}
        else:
            return {"status": "error", "message": f"Vast.ai API error: {response.status_code}"}
            
    except requests.exceptions.Timeout:
        return {"status": "error", "message": "Connection timeout - check your internet connection"}
    except Exception as e:
        return {"status": "error", "message": f"Connection failed: {str(e)}"}