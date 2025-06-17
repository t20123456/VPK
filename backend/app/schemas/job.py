from pydantic import BaseModel, field_validator
from typing import Optional, List
from uuid import UUID
from datetime import datetime
from app.models.job import JobStatus


class JobBase(BaseModel):
    name: str
    hash_type: str
    word_list: Optional[str] = None
    custom_attack: Optional[str] = None
    rule_files: Optional[List[str]] = None
    hard_end_time: Optional[datetime] = None
    instance_type: Optional[str] = None
    required_disk_gb: Optional[int] = 20


class JobCreate(JobBase):
    @field_validator('name')
    @classmethod
    def name_must_not_be_empty(cls, v):
        if not v or not v.strip():
            raise ValueError('Job name cannot be empty')
        return v.strip()
    
    @field_validator('hash_type')
    @classmethod
    def hash_type_must_be_valid(cls, v):
        # Hash type names (case insensitive)
        valid_types = [
            # Basic hash types
            'md5', 'sha1', 'sha256', 'sha512', 'md4', 'sha224', 'sha384', 'ripemd160', 'whirlpool',
            # Windows/AD specific
            'ntlm', 'ntlmv2', 'lm', 'mscash', 'mscash2', 'kerberos', 'krb5tgs', 'krb5asrep',
            'netlm', 'netntlm', 'netntlmv2', 'wpa', 'wpa2', 'wpa3'
        ]
        
        # Common hashcat mode numbers for Windows/AD environments
        valid_modes = {
            # Basic hashes
            '0': 'MD5',
            '100': 'SHA1', 
            '1400': 'SHA256',
            '1700': 'SHA512',
            '900': 'MD4',
            '1300': 'SHA224',
            '10800': 'SHA384',
            '6000': 'RIPEMD160',
            '6100': 'Whirlpool',
            
            # Windows/AD hashes
            '1000': 'NTLM',
            '3000': 'LM',
            '5500': 'NetNTLMv1',
            '5600': 'NetNTLMv2', 
            '1100': 'Domain Cached Credentials (DCC), MS Cache',
            '2100': 'Domain Cached Credentials 2 (DCC2), MS Cache 2',
            
            # Kerberos
            '13100': 'Kerberos 5 TGS-REP etype 23',
            '18200': 'Kerberos 5 AS-REP etype 23',
            '19600': 'Kerberos 5 TGS-REP etype 17 (AES128-CTS-HMAC-SHA1-96)',
            '19700': 'Kerberos 5 TGS-REP etype 18 (AES256-CTS-HMAC-SHA1-96)',
            '19800': 'Kerberos 5 AS-REP etype 17 (AES128-CTS-HMAC-SHA1-96)',
            '19900': 'Kerberos 5 AS-REP etype 18 (AES256-CTS-HMAC-SHA1-96)',
            
            # WiFi
            '2500': 'WPA/WPA2',
            '22000': 'WPA-PBKDF2-PMKID+EAPOL',
            '22001': 'WPA-PMK-PMKID+EAPOL',
            
            # Other common
            '7500': 'Kerberos 5 AS-REQ Pre-Auth etype 23',
            '9600': 'Office 2013',
            '25400': 'PDF 1.4 - 1.6 (Acrobat 5 - 8)',
            '1800': 'sha512crypt $6$, SHA512 (Unix)',
            '3200': 'bcrypt $2*$, Blowfish (Unix)'
        }
        
        # Check if it's a valid hash type name
        if v.lower() in valid_types:
            return v.lower()
        
        # Check if it's a valid hashcat mode number
        if str(v) in valid_modes:
            return str(v)
        
        # Allow any numeric string (for less common hashcat modes)
        if v.isdigit():
            return str(v)
        
        common_examples = [
            "ntlm (1000)", "ntlmv2 (5600)", "kerberos (13100)", 
            "mscash2 (2100)", "wpa2 (22000)", "md5 (0)", "sha256 (1400)"
        ]
        
        raise ValueError(f'Invalid hash type. Examples: {", ".join(common_examples)}. See https://hashcat.net/wiki/doku.php?id=example_hashes for all modes.')
        return v
    
    @field_validator('rule_files')
    @classmethod
    def validate_rule_files(cls, v):
        """Validate rule_files"""
        if v is not None:
            # Ensure rule_files is a list of strings
            if not isinstance(v, list):
                raise ValueError('rule_files must be a list of strings')
            
            # Remove empty strings and duplicates while preserving order
            clean_rules = []
            seen = set()
            for rule in v:
                if rule and rule.strip() and rule not in seen:
                    clean_rules.append(rule.strip())
                    seen.add(rule.strip())
            
            return clean_rules if clean_rules else None
        
        return v


class JobUpdate(BaseModel):
    name: Optional[str] = None
    status: Optional[JobStatus] = None
    progress: Optional[int] = None
    error_message: Optional[str] = None
    time_started: Optional[datetime] = None
    time_finished: Optional[datetime] = None
    actual_cost: Optional[float] = None
    instance_id: Optional[str] = None


class JobInDBBase(JobBase):
    id: UUID
    user_id: UUID
    status: JobStatus
    progress: int = 0
    estimated_time: Optional[int] = None
    actual_cost: float = 0.0
    hash_file_path: Optional[str] = None
    pot_file_path: Optional[str] = None
    log_file_path: Optional[str] = None
    instance_id: Optional[str] = None
    error_message: Optional[str] = None
    status_message: Optional[str] = None
    time_started: Optional[datetime] = None
    time_finished: Optional[datetime] = None
    created_at: datetime
    updated_at: datetime
    required_disk_gb: Optional[int] = 20
    
    @field_validator('rule_files', mode='before')
    @classmethod
    def serialize_rule_files(cls, v):
        """Convert JobRule objects to rule_file strings"""
        if v is None:
            return None
        if isinstance(v, list):
            # If it's a list of JobRule objects, extract rule_file strings
            result = []
            for item in v:
                if hasattr(item, 'rule_file'):
                    result.append(item.rule_file)
                elif isinstance(item, str):
                    result.append(item)
            return result if result else None
        return v
    
    class Config:
        from_attributes = True


class Job(JobInDBBase):
    pass


class JobWithUser(JobInDBBase):
    user_email: Optional[str] = None
    
    @classmethod
    def from_job_model(cls, job_model):
        """Create JobWithUser from Job model with user relationship loaded"""
        data = {
            'id': job_model.id,
            'user_id': job_model.user_id,
            'name': job_model.name,
            'hash_type': job_model.hash_type,
            'word_list': job_model.word_list,
            'rule_list': job_model.rule_list,
            'custom_attack': job_model.custom_attack,
            'hard_end_time': job_model.hard_end_time,
            'instance_type': job_model.instance_type,
            'status': job_model.status,
            'progress': job_model.progress,
            'estimated_time': job_model.estimated_time,
            'actual_cost': job_model.actual_cost,
            'hash_file_path': job_model.hash_file_path,
            'pot_file_path': job_model.pot_file_path,
            'log_file_path': job_model.log_file_path,
            'instance_id': job_model.instance_id,
            'error_message': job_model.error_message,
            'status_message': job_model.status_message,
            'time_started': job_model.time_started,
            'time_finished': job_model.time_finished,
            'created_at': job_model.created_at,
            'updated_at': job_model.updated_at,
            'required_disk_gb': getattr(job_model, 'required_disk_gb', 20),
            'user_email': job_model.user.email if hasattr(job_model, 'user') and job_model.user else None
        }
        return cls(**data)


class JobWithFiles(Job):
    files: List['JobFile'] = []


class JobFileBase(BaseModel):
    file_type: str
    file_size: Optional[int] = None


class JobFileCreate(JobFileBase):
    local_path: Optional[str] = None
    s3_key: Optional[str] = None


class JobFile(JobFileBase):
    id: UUID
    job_id: UUID
    local_path: Optional[str] = None
    s3_key: Optional[str] = None
    created_at: datetime
    
    class Config:
        from_attributes = True


class JobRuleBase(BaseModel):
    rule_file: str
    rule_order: int = 0


class JobRuleCreate(JobRuleBase):
    pass


class JobRule(JobRuleBase):
    id: UUID
    job_id: UUID
    created_at: datetime
    
    class Config:
        from_attributes = True


class JobStats(BaseModel):
    total_hashes: int
    cracked_hashes: int
    success_rate: float


# Update forward references
JobWithFiles.model_rebuild()