from sqlalchemy import Column, String, Integer, BigInteger, DateTime, Boolean, JSON, Text
from sqlalchemy.dialects.postgresql import UUID
import uuid
from datetime import datetime

from .base import Base, TimestampMixin


class WordlistMetadata(Base, TimestampMixin):
    """Metadata for wordlists to enable efficient filtering and size estimation"""
    __tablename__ = "wordlist_metadata"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    filename = Column(String(255), nullable=False)  # Display name: "weakpass_4.txt"
    compressed_size = Column(BigInteger, nullable=False)  # Size in bytes (compressed)
    uncompressed_size = Column(BigInteger, nullable=True)  # Size in bytes (uncompressed)
    line_count = Column(BigInteger, nullable=True)  # Number of passwords
    compression_format = Column(String(10), nullable=True)  # "7z", "zip", "gz", None
    
    # Additional metadata
    source = Column(String(100), nullable=True)  # "weakpass", "rockyou", "custom", etc.
    language = Column(String(50), nullable=True)  # "english", "mixed", etc.
    description = Column(Text, nullable=True)
    tags = Column(JSON, nullable=True)  # ["common", "leaked", "generated", etc.]
    
    # Performance hints
    popularity_score = Column(Integer, nullable=True)  # 1-100 score for sorting
    
    # Flags
    is_available = Column(Boolean, default=True)
    requires_premium = Column(Boolean, default=False)
    
    # Checksums for verification
    md5_hash = Column(String(32), nullable=True)
    sha256_hash = Column(String(64), nullable=True)
    
    # When this metadata was last verified
    last_verified = Column(DateTime(timezone=True), nullable=True)