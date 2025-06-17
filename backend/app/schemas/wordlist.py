from pydantic import BaseModel
from typing import Optional, List, Dict
from uuid import UUID
from datetime import datetime


class WordlistMetadataBase(BaseModel):
    filename: str
    compressed_size: int
    uncompressed_size: Optional[int] = None
    line_count: Optional[int] = None
    compression_format: Optional[str] = None
    source: Optional[str] = None
    language: Optional[str] = None
    description: Optional[str] = None
    tags: Optional[List[str]] = None
    popularity_score: Optional[int] = None
    is_available: bool = True
    requires_premium: bool = False


class WordlistMetadataCreate(WordlistMetadataBase):
    md5_hash: Optional[str] = None
    sha256_hash: Optional[str] = None


class WordlistMetadataUpdate(BaseModel):
    uncompressed_size: Optional[int] = None
    line_count: Optional[int] = None
    description: Optional[str] = None
    tags: Optional[List[str]] = None
    estimated_crack_time_md5: Optional[float] = None
    popularity_score: Optional[int] = None
    is_available: Optional[bool] = None
    requires_premium: Optional[bool] = None
    last_verified: Optional[datetime] = None


class WordlistMetadata(WordlistMetadataBase):
    id: UUID
    created_at: datetime
    updated_at: datetime
    last_verified: Optional[datetime] = None
    md5_hash: Optional[str] = None
    sha256_hash: Optional[str] = None
    
    class Config:
        from_attributes = True


class WordlistWithSizeInfo(BaseModel):
    """Enhanced wordlist info for frontend display"""
    key: str
    name: str
    size: int  # Compressed size for compatibility
    last_modified: str
    type: str = "wordlist"
    line_count: Optional[int] = None
    
    # Additional fields from metadata
    uncompressed_size: Optional[int] = None
    compression_format: Optional[str] = None
    compression_ratio: Optional[float] = None  # Calculated field
    source: Optional[str] = None
    tags: Optional[List[str]] = None
    description: Optional[str] = None
    
    @classmethod
    def from_storage_and_metadata(cls, storage_file: dict, metadata: Optional[WordlistMetadata] = None):
        """Create from storage file info and optional metadata"""
        data = {
            "key": storage_file["key"],
            "name": storage_file["name"],
            "size": storage_file["size"],
            "last_modified": storage_file["last_modified"],
            "type": storage_file.get("type", "wordlist"),
            "line_count": storage_file.get("line_count")
        }
        
        if metadata:
            data.update({
                "line_count": metadata.line_count or data.get("line_count"),
                "uncompressed_size": metadata.uncompressed_size,
                "compression_format": metadata.compression_format,
                "source": metadata.source,
                "tags": metadata.tags,
                "description": metadata.description
            })
            
            # Calculate compression ratio
            if metadata.uncompressed_size and metadata.compressed_size > 0:
                data["compression_ratio"] = metadata.uncompressed_size / metadata.compressed_size
        
        return cls(**data)