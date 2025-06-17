import os
import uuid
import aiofiles
from typing import Optional, List
from sqlalchemy.orm import Session, joinedload
from fastapi import UploadFile, HTTPException
from datetime import datetime

from app.models.job import Job as JobModel, JobFile as JobFileModel, JobRule as JobRuleModel, JobStatus
from app.models.user import User
from app.schemas.job import JobCreate, JobUpdate
from app.services.settings_service import get_settings_service


class JobService:
    def __init__(self, db: Session):
        self.db = db
        self.data_dir = "/app/data"
        self.jobs_dir = f"{self.data_dir}/jobs"
        self.uploads_dir = f"{self.data_dir}/uploads"
        self.temp_dir = f"{self.data_dir}/temp"
        
        # Ensure directories exist
        os.makedirs(self.jobs_dir, exist_ok=True)
        os.makedirs(self.uploads_dir, exist_ok=True)
        os.makedirs(self.temp_dir, exist_ok=True)
    
    def create_job(self, job_data: JobCreate, user: User) -> JobModel:
        """Create a new job"""
        db_job = JobModel(
            user_id=user.id,
            name=job_data.name,
            hash_type=job_data.hash_type,
            word_list=job_data.word_list,
            custom_attack=job_data.custom_attack,
            hard_end_time=job_data.hard_end_time,
            instance_type=job_data.instance_type,
            required_disk_gb=job_data.required_disk_gb if hasattr(job_data, 'required_disk_gb') else 20,
            status=JobStatus.READY_TO_START
        )
        
        self.db.add(db_job)
        self.db.commit()
        self.db.refresh(db_job)
        
        # Create JobRule records for multiple rule files
        if hasattr(job_data, 'rule_files') and job_data.rule_files:
            for i, rule_file in enumerate(job_data.rule_files):
                job_rule = JobRuleModel(
                    job_id=db_job.id,
                    rule_file=rule_file,
                    rule_order=i
                )
                self.db.add(job_rule)
        
        self.db.commit()
        self.db.refresh(db_job)
        
        # Create job directory
        job_dir = f"{self.jobs_dir}/{str(db_job.id)}"
        os.makedirs(job_dir, exist_ok=True)
        
        return db_job
    
    async def upload_hash_file(self, job_id: uuid.UUID, file: UploadFile) -> str:
        """Upload and save hash file for a job"""
        job = self.db.query(JobModel).filter(JobModel.id == job_id).first()
        if not job:
            raise HTTPException(status_code=404, detail="Job not found")
        
        # Validate file size
        settings_service = get_settings_service()
        max_size = settings_service.max_hash_file_size_bytes
        file_size = 0
        
        # Create unique filename
        file_extension = os.path.splitext(file.filename)[1] if file.filename else ""
        filename = f"hash_file{file_extension}"
        file_path = f"{self.jobs_dir}/{str(job_id)}/{filename}"
        
        # Save file
        async with aiofiles.open(file_path, 'wb') as f:
            while chunk := await file.read(8192):
                file_size += len(chunk)
                if file_size > max_size:
                    # Clean up partial file
                    os.remove(file_path)
                    raise HTTPException(
                        status_code=413, 
                        detail=f"File too large. Maximum size is {settings_service.max_hash_file_size_mb}MB"
                    )
                await f.write(chunk)
        
        # Update job with file path
        job.hash_file_path = file_path
        self.db.commit()
        
        # Create job file record
        job_file = JobFileModel(
            job_id=job_id,
            file_type="hash",
            local_path=file_path,
            file_size=file_size
        )
        self.db.add(job_file)
        self.db.commit()
        
        return file_path
    
    def update_job(self, job_id: uuid.UUID, job_update: JobUpdate, user: User) -> JobModel:
        """Update a job"""
        job = self.db.query(JobModel).filter(
            JobModel.id == job_id,
            JobModel.user_id == user.id
        ).first()
        
        if not job:
            raise HTTPException(status_code=404, detail="Job not found")
        
        update_data = job_update.dict(exclude_unset=True)
        for field, value in update_data.items():
            setattr(job, field, value)
        
        self.db.commit()
        self.db.refresh(job)
        return job
    
    def get_job(self, job_id: uuid.UUID, user: User) -> Optional[JobModel]:
        """Get a job by ID"""
        # Admin users can access any job, regular users only their own
        if user.role == 'admin':
            return self.db.query(JobModel).filter(JobModel.id == job_id).first()
        else:
            return self.db.query(JobModel).filter(
                JobModel.id == job_id,
                JobModel.user_id == user.id
            ).first()
    
    def get_jobs(self, user: User, skip: int = 0, limit: int = 100) -> List[JobModel]:
        """Get user's jobs"""
        return self.db.query(JobModel).filter(
            JobModel.user_id == user.id
        ).offset(skip).limit(limit).all()
    
    def get_all_jobs(self, skip: int = 0, limit: int = 100) -> List[JobModel]:
        """Get all jobs (admin only)"""
        return self.db.query(JobModel).options(
            joinedload(JobModel.user)
        ).offset(skip).limit(limit).all()
    
    def delete_job(self, job_id: uuid.UUID, user: User) -> bool:
        """Delete a job and its files"""
        # Admin users can delete any job, regular users only their own
        if user.role == 'admin':
            job = self.db.query(JobModel).filter(JobModel.id == job_id).first()
        else:
            job = self.db.query(JobModel).filter(
                JobModel.id == job_id,
                JobModel.user_id == user.id
            ).first()
        
        if not job:
            raise HTTPException(status_code=404, detail="Job not found")
        
        # Don't allow deletion of running jobs
        if job.status in [JobStatus.RUNNING, JobStatus.INSTANCE_CREATING]:
            raise HTTPException(
                status_code=400, 
                detail="Cannot delete running job. Please stop it first."
            )
        
        # Delete job directory and files
        job_dir = f"{self.jobs_dir}/{str(job_id)}"
        if os.path.exists(job_dir):
            import shutil
            shutil.rmtree(job_dir)
        
        self.db.delete(job)
        self.db.commit()
        return True
    
    def estimate_job_time(self, job: JobModel) -> Optional[int]:
        """Estimate job completion time in seconds"""
        # This would integrate with benchmark data
        # For now, return a placeholder estimation
        if job.custom_attack:
            return None  # Cannot estimate custom attacks
        
        # Basic estimation based on hash type and wordlist
        base_times = {
            'md5': 1000,
            'sha1': 1200,
            'sha256': 2000,
            'sha512': 4000,
            'ntlm': 800
        }
        
        base_time = base_times.get(job.hash_type, 2000)
        
        # Adjust for wordlist size (this would be calculated from actual file)
        wordlist_multiplier = 1.0
        if job.word_list:
            # This would check actual wordlist size
            wordlist_multiplier = 2.0
        
        return int(base_time * wordlist_multiplier)
    
    def get_job_log_path(self, job_id: uuid.UUID) -> str:
        """Get the log file path for a job"""
        return f"{self.jobs_dir}/{str(job_id)}/job.log"
    
    def get_job_pot_path(self, job_id: uuid.UUID) -> str:
        """Get the pot file path for a job"""
        return f"{self.jobs_dir}/{str(job_id)}/result.pot"
    
    def get_job_stats(self, job_id: uuid.UUID) -> dict:
        """Get job statistics including hash counts and success rate"""
        job = self.db.query(JobModel).filter(JobModel.id == job_id).first()
        if not job:
            raise HTTPException(status_code=404, detail="Job not found")
        
        total_hashes = 0
        cracked_hashes = 0
        
        # Count total hashes from hash file
        if job.hash_file_path and os.path.exists(job.hash_file_path):
            try:
                with open(job.hash_file_path, 'r', encoding='utf-8', errors='ignore') as f:
                    total_hashes = sum(1 for line in f if line.strip())
            except Exception:
                # Can't read the hash file, still return stats with 0 total
                total_hashes = 0
        
        # Count cracked hashes from pot file
        if job.pot_file_path and os.path.exists(job.pot_file_path):
            try:
                with open(job.pot_file_path, 'r', encoding='utf-8', errors='ignore') as f:
                    cracked_hashes = sum(1 for line in f if line.strip())
            except Exception:
                # Can't read the pot file, cracked count remains 0
                cracked_hashes = 0
        
        # Calculate success rate
        if total_hashes > 0:
            success_rate = (cracked_hashes / total_hashes) * 100
        else:
            success_rate = 0.0
        
        return {
            "total_hashes": total_hashes,
            "cracked_hashes": cracked_hashes,
            "success_rate": round(success_rate, 2)
        }