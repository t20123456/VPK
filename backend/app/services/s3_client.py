import boto3
from botocore.exceptions import ClientError, NoCredentialsError
from typing import List, Dict, Optional, BinaryIO
import os
import io
from datetime import datetime, timedelta, timezone

from app.services.settings_service import get_settings_service


class S3Client:
    def __init__(self):
        settings_service = get_settings_service()
        
        aws_access_key = settings_service.get_aws_access_key_id()
        aws_secret_key = settings_service.get_aws_secret_access_key()
        bucket_name = settings_service.s3_bucket_name
        
        if not all([aws_access_key, aws_secret_key, bucket_name]):
            raise ValueError("AWS credentials and S3 bucket name must be configured in application settings")
        
        self.s3_client = boto3.client(
            's3',
            aws_access_key_id=aws_access_key,
            aws_secret_access_key=aws_secret_key,
            region_name=settings_service.s3_region
        )
        self.bucket_name = bucket_name
    
    def _count_rules_in_file(self, file_obj: BinaryIO) -> int:
        """Count the number of rules in a hashcat rule file"""
        try:
            # Reset file pointer to beginning
            file_obj.seek(0)
            
            rule_count = 0
            for line in file_obj:
                # Decode bytes to string if needed
                if isinstance(line, bytes):
                    line = line.decode('utf-8', errors='ignore')
                
                # Strip whitespace
                line = line.strip()
                
                # Skip empty lines and comments (lines starting with #)
                if line and not line.startswith('#'):
                    rule_count += 1
            
            # Reset file pointer for subsequent operations
            file_obj.seek(0)
            return rule_count
            
        except Exception as e:
            # Return a default
            print(f"Warning: Could not count rules in file: {e}")
            file_obj.seek(0)  # Reset file pointer
            return 0
    
    def _count_wordlist_lines(self, file_obj: BinaryIO) -> int:
        """Count the number of lines in a wordlist file"""
        try:
            # Reset file pointer to beginning
            file_obj.seek(0)
            
            line_count = 0
            for line in file_obj:
                # Decode bytes to string if needed
                if isinstance(line, bytes):
                    line = line.decode('utf-8', errors='ignore')
                
                # Strip whitespace
                line = line.strip()
                
                # Count non-empty lines
                if line:
                    line_count += 1
            
            # Reset file pointer for subsequent operations
            file_obj.seek(0)
            return line_count
            
        except Exception as e:
            # Return a default
            print(f"Warning: Could not count lines in file: {e}")
            file_obj.seek(0)  # Reset file pointer
            return 0
    
    def list_wordlists(self, prefix: str = "wordlists/") -> List[Dict[str, any]]:
        """List all wordlists in S3 bucket"""
        try:
            response = self.s3_client.list_objects_v2(
                Bucket=self.bucket_name,
                Prefix=prefix
            )
            
            wordlists = []
            for obj in response.get('Contents', []):
                # Skip directories
                if not obj['Key'].endswith('/'):
                    # Get metadata to retrieve line count
                    try:
                        metadata_response = self.s3_client.head_object(
                            Bucket=self.bucket_name,
                            Key=obj['Key']
                        )
                        metadata = metadata_response.get('Metadata', {})
                        line_count = metadata.get('line_count')
                    except:
                        line_count = None
                    
                    wordlist_info = {
                        'key': obj['Key'],
                        'name': os.path.basename(obj['Key']),
                        'size': obj['Size'],
                        'last_modified': obj['LastModified'],
                        'type': 'wordlist'
                    }
                    
                    if line_count:
                        wordlist_info['line_count'] = int(line_count)
                    
                    wordlists.append(wordlist_info)
            
            return wordlists
        except ClientError as e:
            raise Exception(f"Error listing wordlists: {str(e)}")
    
    def list_rules(self, prefix: str = "rules/") -> List[Dict[str, any]]:
        """List all rule files in S3 bucket"""
        try:
            response = self.s3_client.list_objects_v2(
                Bucket=self.bucket_name,
                Prefix=prefix
            )
            
            rules = []
            for obj in response.get('Contents', []):
                # Skip directories
                if not obj['Key'].endswith('/'):
                    # Get metadata to retrieve rule count
                    try:
                        metadata_response = self.s3_client.head_object(
                            Bucket=self.bucket_name,
                            Key=obj['Key']
                        )
                        metadata = metadata_response.get('Metadata', {})
                        rule_count = metadata.get('rule_count')
                    except:
                        rule_count = None
                    
                    rule_info = {
                        'key': obj['Key'],
                        'name': os.path.basename(obj['Key']),
                        'size': obj['Size'],
                        'last_modified': obj['LastModified'],
                        'type': 'rules'
                    }
                    
                    if rule_count:
                        rule_info['rule_count'] = int(rule_count)
                    
                    rules.append(rule_info)
            
            return rules
        except ClientError as e:
            raise Exception(f"Error listing rules: {str(e)}")
    
    def upload_wordlist(self, file_obj: BinaryIO, filename: str) -> str:
        """Upload a wordlist to S3"""
        key = f"wordlists/{filename}"
        try:
            # Count lines in the wordlist
            line_count = self._count_wordlist_lines(file_obj)
            
            # Prepare metadata
            metadata = {
                'uploaded_by': 'vpk',
                'upload_time': datetime.now(timezone.utc).isoformat()
            }
            
            if line_count > 0:
                metadata['line_count'] = str(line_count)
            
            self.s3_client.upload_fileobj(
                file_obj,
                self.bucket_name,
                key,
                ExtraArgs={
                    'ContentType': 'text/plain',
                    'Metadata': metadata
                }
            )
            return key
        except ClientError as e:
            raise Exception(f"Error uploading wordlist: {str(e)}")
    
    def upload_rules(self, file_obj: BinaryIO, filename: str) -> str:
        """Upload a rule file to S3"""
        key = f"rules/{filename}"
        try:
            # Count rules in the file
            rule_count = self._count_rules_in_file(file_obj)
            
            # Prepare metadata
            metadata = {
                'uploaded_by': 'vpk',
                'upload_time': datetime.utcnow().isoformat()
            }
            
            if rule_count > 0:
                metadata['rule_count'] = str(rule_count)
            
            self.s3_client.upload_fileobj(
                file_obj,
                self.bucket_name,
                key,
                ExtraArgs={
                    'ContentType': 'text/plain',
                    'Metadata': metadata
                }
            )
            return key
        except ClientError as e:
            raise Exception(f"Error uploading rules: {str(e)}")
    
    def get_download_url(self, key: str, expiration: int = 3600) -> str:
        """Generate a presigned URL for downloading a file"""
        try:
            url = self.s3_client.generate_presigned_url(
                'get_object',
                Params={'Bucket': self.bucket_name, 'Key': key},
                ExpiresIn=expiration
            )
            return url
        except ClientError as e:
            raise Exception(f"Error generating download URL: {str(e)}")
    
    def delete_file(self, key: str) -> bool:
        """Delete a file from S3"""
        try:
            self.s3_client.delete_object(Bucket=self.bucket_name, Key=key)
            return True
        except ClientError as e:
            raise Exception(f"Error deleting file: {str(e)}")
    
    def get_file_info(self, key: str) -> Dict[str, any]:
        """Get information about a file in S3"""
        try:
            response = self.s3_client.head_object(Bucket=self.bucket_name, Key=key)
            return {
                'key': key,
                'size': response['ContentLength'],
                'last_modified': response['LastModified'],
                'content_type': response.get('ContentType'),
                'metadata': response.get('Metadata', {})
            }
        except ClientError as e:
            if e.response['Error']['Code'] == '404':
                return None
            raise Exception(f"Error getting file info: {str(e)}")
    
    def check_bucket_access(self) -> bool:
        """Check access for S3 bucket"""
        try:
            self.s3_client.head_bucket(Bucket=self.bucket_name)
            return True
        except ClientError:
            return False
    
    def get_s3_url_for_vast(self, key: str) -> str:
        """Get S3 URL that can be used from Vast.ai instances"""
        return f"s3://{self.bucket_name}/{key}"
    
    def get_aws_cli_download_command(self, key: str, local_path: str) -> str:
        """Get AWS CLI command for downloading file on Vast.ai instance"""
        s3_url = self.get_s3_url_for_vast(key)
        return f"aws s3 cp {s3_url} {local_path}"