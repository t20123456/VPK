from fastapi import APIRouter, Depends, HTTPException, status, UploadFile, File
from typing import List, Dict, Any
from sqlalchemy.orm import Session
import os

from app.services.s3_client import S3Client
from app.services.wordlist_service import WordlistService
from app.models.user import User
from app.api.deps import get_current_active_user, get_current_admin_user, get_db

router = APIRouter()


@router.get("/wordlists", response_model=List[Dict[str, Any]])
async def list_wordlists(
    current_user: User = Depends(get_current_active_user)
):
    """List available wordlists"""
    try:
        s3_client = S3Client()
        wordlists = s3_client.list_wordlists()
        return wordlists
    except ValueError as e:
        # S3Client raises ValueError if credentials are not configured
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail=str(e)
        )
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error listing wordlists: {str(e)}"
        )


@router.get("/rules", response_model=List[Dict[str, Any]])
async def list_rules(
    current_user: User = Depends(get_current_active_user)
):
    """List available rule files"""
    try:
        s3_client = S3Client()
        rules = s3_client.list_rules()
        return rules
    except ValueError as e:
        # S3Client raises ValueError if credentials are not configured
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail=str(e)
        )
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error listing rules: {str(e)}"
        )


@router.post("/wordlists/upload")
async def upload_wordlist(
    file: UploadFile = File(...),
    current_admin: User = Depends(get_current_admin_user),
    db: Session = Depends(get_db)
):
    """Upload a wordlist file (admin only)"""
    if not file.filename:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="No filename provided"
        )
    
    # Validate file extension
    allowed_extensions = ['.txt', '.lst', '.dict']
    file_ext = os.path.splitext(file.filename)[1].lower()
    if file_ext not in allowed_extensions:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Invalid file type. Allowed: {', '.join(allowed_extensions)}"
        )
    
    try:
        s3_client = S3Client()
        key = s3_client.upload_wordlist(file.file, file.filename)
        
        # After upload, add to catalog if not already exists
        wordlist_service = WordlistService(db)
        base_filename = os.path.splitext(file.filename)[0]  # Remove extension
        
        # Check if this wordlist is already in catalog
        existing = wordlist_service.get_wordlist_metadata(base_filename)
        if not existing:
            # Get the file info from S3 to get line count and size
            s3_wordlists = s3_client.list_wordlists()
            uploaded_file = next((w for w in s3_wordlists if w["key"] == key), None)
            
            if uploaded_file and uploaded_file.get("line_count"):
                # Create a catalog entry for this uploaded file
                from app.models.wordlist_metadata import WordlistMetadata
                from datetime import datetime, timezone
                
                new_metadata = WordlistMetadata(
                    filename=base_filename,
                    compressed_size=uploaded_file["size"],
                    uncompressed_size=uploaded_file["size"],  # Same for uncompressed files
                    line_count=uploaded_file["line_count"],
                    compression_format=None,  # No compression for uploaded files
                    source="custom",
                    description=f"Custom uploaded wordlist: {file.filename}",
                    popularity_score=1,
                    is_available=True,
                    requires_premium=False,
                    last_verified=datetime.now(timezone.utc),
                    tags=["custom", "uploaded"]
                )
                
                db.add(new_metadata)
                db.commit()
        
        return {
            "detail": "Wordlist uploaded successfully",
            "key": key,
            "filename": file.filename
        }
    except ValueError as e:
        # S3Client raises ValueError if credentials are not configured
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail=str(e)
        )
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error uploading wordlist: {str(e)}"
        )


@router.post("/rules/upload")
async def upload_rules(
    file: UploadFile = File(...),
    current_admin: User = Depends(get_current_admin_user)
):
    """Upload a rule file (admin only)"""
    if not file.filename:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="No filename provided"
        )
    
    # Validate file extension
    allowed_extensions = ['.rule', '.rules', '.txt']
    file_ext = os.path.splitext(file.filename)[1].lower()
    if file_ext not in allowed_extensions:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Invalid file type. Allowed: {', '.join(allowed_extensions)}"
        )
    
    try:
        s3_client = S3Client()
        key = s3_client.upload_rules(file.file, file.filename)
        return {
            "detail": "Rule file uploaded successfully",
            "key": key,
            "filename": file.filename
        }
    except ValueError as e:
        # S3Client raises ValueError if credentials are not configured
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail=str(e)
        )
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error uploading rules: {str(e)}"
        )


@router.delete("/wordlists/{key:path}")
async def delete_wordlist(
    key: str,
    current_admin: User = Depends(get_current_admin_user)
):
    """Delete a wordlist (admin only)"""
    try:
        s3_client = S3Client()
        success = s3_client.delete_file(key)
        if success:
            return {"detail": "Wordlist deleted successfully"}
        else:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Wordlist not found"
            )
    except ValueError as e:
        # S3Client raises ValueError if credentials are not configured
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail=str(e)
        )
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error deleting wordlist: {str(e)}"
        )


@router.delete("/rules/{key:path}")
async def delete_rules(
    key: str,
    current_admin: User = Depends(get_current_admin_user)
):
    """Delete a rule file (admin only)"""
    try:
        s3_client = S3Client()
        success = s3_client.delete_file(key)
        if success:
            return {"detail": "Rule file deleted successfully"}
        else:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Rule file not found"
            )
    except ValueError as e:
        # S3Client raises ValueError if credentials are not configured
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail=str(e)
        )
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error deleting rules: {str(e)}"
        )


@router.post("/wordlists/catalog/build")
async def build_wordlist_catalog(
    current_admin: User = Depends(get_current_admin_user),
    db: Session = Depends(get_db),
    max_pages: int = 10
):
    """Build wordlist metadata catalog from Weakpass (admin only)"""
    try:
        wordlist_service = WordlistService(db)
        wordlist_service.scrape_weakpass_catalog(max_pages=max_pages)
        
        # Count total entries added
        total_entries = len(wordlist_service.get_all_catalog_entries())
        
        return {
            "detail": "Wordlist catalog built successfully",
            "total_entries": total_entries,
            "pages_scraped": max_pages
        }
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error building wordlist catalog: {str(e)}"
        )


@router.get("/wordlists/catalog")
async def get_wordlist_catalog(
    current_user: User = Depends(get_current_active_user),
    db: Session = Depends(get_db)
):
    """Get wordlist metadata catalog entries"""
    try:
        wordlist_service = WordlistService(db)
        catalog_entries = wordlist_service.get_all_catalog_entries()
        
        return {
            "catalog_entries": [
                {
                    "id": str(entry.id),
                    "filename": entry.filename,
                    "compressed_size": entry.compressed_size,
                    "uncompressed_size": entry.uncompressed_size,
                    "line_count": entry.line_count,
                    "compression_format": entry.compression_format,
                    "source": entry.source,
                    "description": entry.description,
                    "tags": entry.tags,
                    "popularity_score": entry.popularity_score,
                    "is_available": entry.is_available,
                    "last_verified": entry.last_verified.isoformat() if entry.last_verified else None
                }
                for entry in catalog_entries
            ]
        }
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error retrieving wordlist catalog: {str(e)}"
        )


@router.get("/wordlists/enhanced")
def list_enhanced_wordlists(
    current_user: User = Depends(get_current_active_user),
    db: Session = Depends(get_db)
):
    """List S3 wordlists enhanced with catalog metadata"""
    try:
        wordlist_service = WordlistService(db)
        enhanced_wordlists = wordlist_service.list_wordlists_with_metadata()
        return enhanced_wordlists
    except ValueError as e:
        # S3Client raises ValueError if credentials are not configured
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail=str(e)
        )
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error listing enhanced wordlists: {str(e)}"
        )


@router.get("/health")
async def storage_health_check(
    current_user: User = Depends(get_current_active_user)
):
    """Check S3 storage connectivity"""
    try:
        s3_client = S3Client()
        access = s3_client.check_bucket_access()
        return {
            "status": "healthy" if access else "error",
            "bucket": s3_client.bucket_name,
            "region": "configured"  # Don't expose exact region in response
        }
    except ValueError as e:
        return {
            "status": "not_configured",
            "detail": str(e)
        }
    except Exception as e:
        return {
            "status": "error",
            "detail": str(e)
        }