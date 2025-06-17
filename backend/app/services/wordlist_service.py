import os
import json
import asyncio
import requests
from typing import List, Optional, Dict, Tuple
from sqlalchemy.orm import Session
from datetime import datetime, timezone

from app.models.wordlist_metadata import WordlistMetadata
from app.schemas.wordlist import WordlistWithSizeInfo
from app.services.s3_client import S3Client
from app.core.database import SessionLocal


class WordlistService:
    def __init__(self, db: Session):
        self.db = db
        self.s3_client = S3Client()
        self.weakpass_base_url = "https://weakpass.com"
    
    def scrape_weakpass_catalog(self, max_pages: int = 10):
        """Scrape Weakpass website to build a catalog of known wordlists and their metadata"""
        print("Building wordlist metadata catalog from Weakpass...")
        
        page = 1
        total_processed = 0
        
        while page <= max_pages:
            try:
                # Fetch page data
                url = f"{self.weakpass_base_url}/wordlists?page={page}"
                response = requests.get(url, timeout=10)
                
                if response.status_code != 200:
                    print(f"Failed to fetch page {page}: HTTP {response.status_code}")
                    break
                
                html = response.text
                
                # Extract JSON data from the page
                import re
                match = re.search(r'data-page="([^"]+)"', html)
                if not match:
                    print(f"No data found on page {page}")
                    break
                
                # Unescape the JSON
                json_str = match.group(1).replace('&quot;', '"')
                data = json.loads(json_str)
                
                wordlists = data.get('props', {}).get('wordlists', {}).get('data', [])
                
                if not wordlists:
                    print(f"No wordlists found on page {page}")
                    break
                
                # Process each wordlist
                for wl in wordlists:
                    self._add_to_catalog(wl)
                    total_processed += 1
                
                print(f"Added {len(wordlists)} wordlists from page {page} to catalog")
                
                # Check if there are more pages
                current_page = data.get('props', {}).get('wordlists', {}).get('current_page', page)
                last_page = data.get('props', {}).get('wordlists', {}).get('last_page', page)
                
                if current_page >= last_page:
                    break
                
                page += 1
                
            except Exception as e:
                print(f"Error scraping page {page}: {e}")
                break
        
        self.db.commit()
        print(f"Catalog building complete. Added {total_processed} wordlist entries.")
    
    def _add_to_catalog(self, entry: dict):
        """Add a wordlist entry to our metadata catalog"""
        try:
            # Check if already exists in catalog by filename
            existing = self.db.query(WordlistMetadata).filter(
                WordlistMetadata.filename == entry['name']
            ).first()
            
            # Prepare metadata
            metadata_dict = {
                "filename": entry['name'],
                "compressed_size": entry.get('size_compressed', 0),
                "uncompressed_size": entry.get('size', 0),
                "line_count": entry.get('count', 0),
                "compression_format": self._get_compression_format(entry['download_link']),
                "source": self._determine_source(entry['name']),
                "description": entry.get('description', ''),
                "popularity_score": int(entry.get('rate', 0)),
                "is_available": True,  # Just catalog entry, not tied to actual S3 presence
                "md5_hash": entry.get('checksum_compressed'),
                "sha256_hash": None,
                "last_verified": datetime.now(timezone.utc),
                "tags": self._generate_tags(entry)
            }
            
            if existing:
                # Update existing catalog entry
                for key, value in metadata_dict.items():
                    setattr(existing, key, value)
                print(f"Updated catalog entry: {entry['name']}")
            else:
                # Create new catalog entry
                new_metadata = WordlistMetadata(**metadata_dict)
                self.db.add(new_metadata)
                print(f"Added to catalog: {entry['name']}")
            
        except Exception as e:
            print(f"Error adding wordlist {entry.get('name', 'unknown')} to catalog: {e}")
    
    def _get_compression_format(self, filename: str) -> Optional[str]:
        """Determine compression format from filename"""
        if filename.endswith('.7z'):
            return '7z'
        elif filename.endswith('.zip'):
            return 'zip'
        elif filename.endswith('.gz'):
            return 'gz'
        elif filename.endswith('.bz2'):
            return 'bz2'
        return None
    
    def _determine_source(self, filename: str) -> str:
        """Determine the source of the wordlist from its name"""
        name_lower = filename.lower()
        if 'weakpass' in name_lower:
            return 'weakpass'
        elif 'rockyou' in name_lower:
            return 'rockyou'
        elif 'hashkiller' in name_lower:
            return 'hashkiller'
        elif 'hashes.org' in name_lower or 'hashesorg' in name_lower:
            return 'hashes.org'
        elif 'hashmob' in name_lower:
            return 'hashmob'
        elif 'ignis' in name_lower:
            return 'ignis'
        else:
            return 'various'
    
    def _generate_tags(self, entry: dict) -> List[str]:
        """Generate tags based on wordlist properties"""
        tags = []
        
        # Size-based tags
        line_count = entry.get('count', 0)
        if line_count > 1_000_000_000:
            tags.append('huge')
        elif line_count > 100_000_000:
            tags.append('large')
        elif line_count > 10_000_000:
            tags.append('medium')
        else:
            tags.append('small')
        
        # Source-based tags
        name_lower = entry.get('name', '').lower()
        if 'weakpass' in name_lower:
            tags.append('weakpass')
        if 'rockyou' in name_lower:
            tags.append('rockyou')
        if 'hashkiller' in name_lower:
            tags.append('hashkiller')
        if 'hashes.org' in name_lower or 'hashesorg' in name_lower:
            tags.append('hashes.org')
        
        # Special tags
        if 'latin' in name_lower:
            tags.append('latin-only')
        if 'merged' in name_lower:
            tags.append('merged')
        if entry.get('rate', 0) >= 70:
            tags.append('popular')
        
        return tags
    
    def get_wordlist_metadata(self, filename: str) -> Optional[WordlistMetadata]:
        """Get metadata for a specific wordlist from our catalog"""
        return self.db.query(WordlistMetadata).filter(
            WordlistMetadata.filename == filename
        ).first()
    
    def get_all_catalog_entries(self) -> List[WordlistMetadata]:
        """Get all wordlist metadata from catalog"""
        return self.db.query(WordlistMetadata).order_by(
            WordlistMetadata.popularity_score.desc(),
            WordlistMetadata.line_count.desc()
        ).all()
    
    def _get_base_filename(self, filename: str) -> str:
        """Extract base filename by removing compression extensions"""
        # Remove common compression extensions
        name = filename
        for ext in ['.7z', '.zip', '.gz', '.bz2']:
            if name.endswith(ext):
                name = name[:-len(ext)]
                break
        return name
    
    def _should_match_catalog_entry(self, s3_filename: str, catalog_filename: str) -> bool:
        """Check if an S3 file should match a catalog entry based on compression expectations"""
        # Get the compression format expected by the catalog entry
        catalog_entry = self.db.query(WordlistMetadata).filter(
            WordlistMetadata.filename == catalog_filename
        ).first()
        
        if not catalog_entry or not catalog_entry.compression_format:
            # No compression format specified, only match exact names
            return s3_filename == catalog_filename
        
        # Catalog expects compressed format, check if S3 file matches
        expected_compressed_name = f"{catalog_filename}.{catalog_entry.compression_format}"
        return s3_filename == expected_compressed_name
    
    def list_wordlists_with_metadata(self) -> List[Dict]:
        """List actual S3 wordlists and enhance with catalog metadata if available"""
        # Get actual wordlists from S3
        s3_wordlists = self.s3_client.list_wordlists()
        
        # Get our metadata catalog indexed by filename
        catalog = {m.filename: m for m in self.get_all_catalog_entries()}
        
        enhanced_wordlists = []
        for wordlist in s3_wordlists:
            metadata = None
            
            # First try exact match
            if wordlist["name"] in catalog:
                catalog_entry = catalog[wordlist["name"]]
                # Only use if no compression format specified (meaning it should be uncompressed)
                if not catalog_entry.compression_format:
                    metadata = catalog_entry
            
            # If no exact match, try base filename matching
            if not metadata:
                base_name = self._get_base_filename(wordlist["name"])
                if base_name in catalog:
                    catalog_entry = catalog[base_name]
                    # Check if this S3 file matches the expected compressed format
                    if self._should_match_catalog_entry(wordlist["name"], base_name):
                        metadata = catalog_entry
            
            if metadata:
                # Determine actual compression info based on S3 filename
                actual_compression_format = None
                if wordlist["name"].endswith('.7z'):
                    actual_compression_format = '7z'
                elif wordlist["name"].endswith('.zip'):
                    actual_compression_format = 'zip'
                elif wordlist["name"].endswith('.gz'):
                    actual_compression_format = 'gz'
                elif wordlist["name"].endswith('.bz2'):
                    actual_compression_format = 'bz2'
                
                enhanced_dict = {
                    "key": wordlist["key"],
                    "name": wordlist["name"],
                    "size": wordlist["size"],
                    "last_modified": wordlist["last_modified"],
                    "type": "wordlist",
                    "line_count": metadata.line_count,
                    "uncompressed_size": metadata.uncompressed_size,
                    "compression_format": actual_compression_format,  # Use actual format from filename
                    "compression_ratio": metadata.uncompressed_size / metadata.compressed_size if metadata.uncompressed_size and metadata.compressed_size > 0 else None,
                    "source": metadata.source,
                    "tags": metadata.tags,
                    "description": metadata.description,
                    "popularity_score": metadata.popularity_score,
                    "has_metadata": True
                }
                enhanced_wordlists.append(enhanced_dict)
            else:
                # No catalog entry, use S3 info (including line_count from S3 metadata for uploaded files)
                enhanced_wordlists.append({
                    "key": wordlist["key"],
                    "name": wordlist["name"],
                    "size": wordlist["size"],
                    "last_modified": wordlist["last_modified"],
                    "type": "wordlist",
                    "line_count": wordlist.get("line_count"),  # From S3 metadata for uploaded files
                    "has_metadata": False
                })
        
        # Sort by metadata availability first, then by popularity/size
        enhanced_wordlists.sort(
            key=lambda x: (
                -x.get("has_metadata", 0),  # Metadata entries first
                -(x.get("popularity_score") or 0),  # Then by popularity
                -(x.get("line_count") or 0)  # Then by line count
            )
        )
        
        return enhanced_wordlists
    
    def calculate_required_disk_space(self, wordlist_name: str) -> Tuple[int, int]:
        """Calculate required disk space in GB using catalog metadata"""
        # Check our catalog for metadata
        metadata = self.get_wordlist_metadata(wordlist_name)
        
        if metadata and metadata.uncompressed_size:
            # Exact data from catalogue
            compressed_gb = metadata.compressed_size / (1024**3)
            uncompressed_gb = metadata.uncompressed_size / (1024**3)
            
            # Need space for: compressed file + uncompressed file + 20% buffer
            total_gb = compressed_gb + uncompressed_gb * 1.2
            
            return compressed_gb, int(total_gb) + 20  # +20GB for OS/tools
        else:
            # No catalog entry, make conservative estimate based on file extension
            try:
                # Try to get actual file size from S3
                s3_wordlists = asyncio.run(self.s3_client.list_wordlists())
                for wl in s3_wordlists:
                    if wl["name"] == wordlist_name:
                        size_gb = wl["size"] / (1024**3)
                        
                        # Conservative estimates based on typical compression ratios
                        if wordlist_name.endswith('.7z'):
                            return size_gb, int(size_gb * 8) + 20
                        elif wordlist_name.endswith('.zip'):
                            return size_gb, int(size_gb * 5) + 20
                        elif wordlist_name.endswith('.gz'):
                            return size_gb, int(size_gb * 3.5) + 20
                        else:
                            # Uncompressed
                            return size_gb, int(size_gb * 1.5) + 20
            except:
                pass
            
            # Default fallback for unknown files
            return 1, 50
    
    def get_extraction_command(self, compression_format: str, input_path: str, output_path: str) -> str:
        """Get the appropriate extraction command for the compression format"""
        commands = {
            "7z": f"7z x -y -o{os.path.dirname(output_path)} {input_path}",
            "zip": f"unzip -o {input_path} -d {os.path.dirname(output_path)}",
            "gz": f"gunzip -c {input_path} > {output_path}",
            "bz2": f"bunzip2 -c {input_path} > {output_path}",
        }
        
        return commands.get(compression_format, f"cat {input_path} > {output_path}")
    


# Singleton instance getter
def get_wordlist_service(db: Session = None) -> WordlistService:
    """Get wordlist service instance"""
    if db is None:
        db = SessionLocal()
    return WordlistService(db)