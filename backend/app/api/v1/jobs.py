from fastapi import APIRouter, Depends, HTTPException, status, UploadFile, File
from sqlalchemy.orm import Session
from typing import List, Optional
from uuid import UUID
from pydantic import BaseModel

from app.core.database import get_db
from app.models.user import User
from app.schemas.job import Job, JobCreate, JobUpdate, JobWithFiles, JobStats, JobWithUser
from app.services.job_service import JobService
from app.api.deps import get_current_active_user, get_current_admin_user
from app.services.benchmark_service import benchmark_service

router = APIRouter()


class TimeEstimateRequest(BaseModel):
    hash_mode: str
    gpu_model: str
    num_gpus: int
    num_hashes: int
    wordlist: Optional[str] = None
    rule_files: Optional[List[str]] = None
    custom_attack: Optional[str] = None


@router.post("/", response_model=Job)
async def create_job(
    job_data: JobCreate,
    current_user: User = Depends(get_current_active_user),
    db: Session = Depends(get_db)
):
    """Create a new cracking job"""
    # Validate the selected instance is still available
    if job_data.instance_type:
        try:
            from app.services.vast_client import VastAIClient
            
            vast_client = VastAIClient()
            selected_offer_id = int(job_data.instance_type)
            
            # Get current offers to check availability
            offers = await vast_client.get_offers(
                secure_cloud=True,
                region="global"
            )
            
            # Check if the selected offer is still available
            selected_offer = next((offer for offer in offers if offer['id'] == selected_offer_id), None)
            
            if not selected_offer:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail=f"Selected instance {selected_offer_id} is no longer available. Please go back and select a different instance."
                )
                
        except ValueError:
            # Invalid instance_type format
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Invalid instance type specified"
            )
        except Exception as e:
            # If it can't validate allow creation but warn
            print(f"Warning: Could not validate offer availability: {e}")
    
    job_service = JobService(db)
    job = job_service.create_job(job_data, current_user)
    
    # Estimate completion time
    estimated_time = job_service.estimate_job_time(job)
    if estimated_time:
        job.estimated_time = estimated_time
        db.commit()
        db.refresh(job)
    
    return job


@router.get("/", response_model=List[Job])
async def list_jobs(
    skip: int = 0,
    limit: int = 100,
    current_user: User = Depends(get_current_active_user),
    db: Session = Depends(get_db)
):
    """List user's jobs"""
    job_service = JobService(db)
    jobs = job_service.get_jobs(current_user, skip=skip, limit=limit)
    return jobs


@router.get("/all", response_model=List[JobWithUser])
async def list_all_jobs(
    skip: int = 0,
    limit: int = 100,
    current_admin: User = Depends(get_current_admin_user),
    db: Session = Depends(get_db)
):
    """List all jobs (admin only)"""
    job_service = JobService(db)
    job_models = job_service.get_all_jobs(skip=skip, limit=limit)
    return [JobWithUser.from_job_model(job) for job in job_models]


@router.get("/{job_id}", response_model=JobWithFiles)
async def get_job(
    job_id: UUID,
    current_user: User = Depends(get_current_active_user),
    db: Session = Depends(get_db)
):
    """Get job details"""
    job_service = JobService(db)
    job = job_service.get_job(job_id, current_user)
    
    if not job:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Job not found"
        )
    
    return job


@router.get("/{job_id}/stats", response_model=JobStats)
async def get_job_stats(
    job_id: UUID,
    current_user: User = Depends(get_current_active_user),
    db: Session = Depends(get_db)
):
    """Get job statistics including hash counts and success rate"""
    job_service = JobService(db)
    
    # First check belongs to user
    job = job_service.get_job(job_id, current_user)
    if not job:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Job not found"
        )
    
    # Get statistics
    stats = job_service.get_job_stats(job_id)
    return JobStats(**stats)


@router.patch("/{job_id}", response_model=Job)
async def update_job(
    job_id: UUID,
    job_update: JobUpdate,
    current_user: User = Depends(get_current_active_user),
    db: Session = Depends(get_db)
):
    """Update job"""
    job_service = JobService(db)
    job = job_service.update_job(job_id, job_update, current_user)
    return job


@router.delete("/{job_id}")
async def delete_job(
    job_id: UUID,
    current_user: User = Depends(get_current_active_user),
    db: Session = Depends(get_db)
):
    """Delete job"""
    job_service = JobService(db)
    success = job_service.delete_job(job_id, current_user)
    
    if success:
        return {"detail": "Job deleted successfully"}
    else:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to delete job"
        )


@router.post("/{job_id}/upload-hash")
async def upload_hash_file(
    job_id: UUID,
    file: UploadFile = File(...),
    current_user: User = Depends(get_current_active_user),
    db: Session = Depends(get_db)
):
    """Upload hash file for a job"""
    # Validate file type
    if not file.filename:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="No filename provided"
        )
    
    # Check if job belongs to user
    job_service = JobService(db)
    job = job_service.get_job(job_id, current_user)
    if not job:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Job not found"
        )
    
    # Upload file
    try:
        file_path = await job_service.upload_hash_file(job_id, file)
        return {
            "detail": "Hash file uploaded successfully",
            "file_path": file_path
        }
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to upload file: {str(e)}"
        )


@router.post("/{job_id}/start")
async def start_job(
    job_id: UUID,
    current_user: User = Depends(get_current_active_user),
    db: Session = Depends(get_db)
):
    """Start a job"""
    job_service = JobService(db)
    job = job_service.get_job(job_id, current_user)
    
    if not job:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Job not found"
        )
    
    if not job.hash_file_path:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Hash file must be uploaded before starting job"
        )
    
    from app.models.job import JobStatus
    from app.tasks.job_tasks import execute_job
    
    # Check if job is already running
    if job.status in [JobStatus.RUNNING, JobStatus.QUEUED, JobStatus.INSTANCE_CREATING]:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Job is already running or queued"
        )
    
    # Queue the job for execution
    task = execute_job.delay(str(job_id))
    job.status = JobStatus.QUEUED
    db.commit()
    
    return {
        "detail": "Job queued for execution",
        "task_id": task.id,
        "job_id": str(job_id)
    }


@router.post("/{job_id}/stop")
async def stop_job(
    job_id: UUID,
    current_user: User = Depends(get_current_active_user),
    db: Session = Depends(get_db)
):
    """Stop a running job"""
    job_service = JobService(db)
    job = job_service.get_job(job_id, current_user)
    
    if not job:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Job not found"
        )
    
    from app.models.job import JobStatus
    from app.tasks.job_tasks import stop_job as stop_job_task
    
    if job.status not in [JobStatus.RUNNING, JobStatus.QUEUED, JobStatus.INSTANCE_CREATING]:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Job is not running"
        )
    
    # Queue the stop task
    task = stop_job_task.delay(str(job_id))
    
    return {
        "detail": "Job stop request queued",
        "task_id": task.id
    }


@router.get("/{job_id}/download-results")
async def download_results(
    job_id: UUID,
    current_user: User = Depends(get_current_active_user),
    db: Session = Depends(get_db)
):
    """Download job results (pot file)"""
    job_service = JobService(db)
    job = job_service.get_job(job_id, current_user)
    
    if not job:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Job not found"
        )
    
    from app.models.job import JobStatus
    if job.status != JobStatus.COMPLETED:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Job is not completed"
        )
    
    if not job.pot_file_path:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="No results available"
        )
    
    # TODO: Implement file download
    return {"detail": "Results download endpoint - to be implemented"}


@router.post("/estimate-time")
async def estimate_job_time(
    request: TimeEstimateRequest,
    current_user: User = Depends(get_current_active_user)
):
    """
    Estimate job runtime based on hardware and attack parameters.
    
    Args:
        hash_mode: Hashcat mode number (e.g., "0" for MD5, "1000" for NTLM)
        gpu_model: GPU model name (e.g., "RTX 4090")
        num_gpus: Number of GPUs
        num_hashes: Number of hashes in the file
        wordlist: Optional wordlist filename
        rule_files: Optional list of rule filenames for multiple rule support
        custom_attack: Optional custom attack string
    
    Returns:
        Estimated runtime in seconds and human-readable format
    """
    try:
        # Validate inputs
        if request.num_hashes <= 0:
            raise ValueError("Number of hashes must be positive")
        if request.num_gpus <= 0 or request.num_gpus > 8:
            raise ValueError("Number of GPUs must be between 1 and 8")
        
        # Get runtime estimate
        estimated_seconds, explanation = benchmark_service.estimate_runtime(
            hash_mode=request.hash_mode,
            gpu_model=request.gpu_model,
            num_gpus=request.num_gpus,
            num_hashes=request.num_hashes,
            wordlist=request.wordlist,
            rule_files=request.rule_files,
            custom_attack=request.custom_attack
        )
        
        formatted_time = benchmark_service.format_time(estimated_seconds)
        
        # Provide confidence level based on whether benchmark data is present, if not probs provide a default.
        has_benchmark = request.gpu_model.upper() in str(benchmark_service.GPU_BENCHMARKS.get(request.hash_mode, {}))
        confidence = "high" if has_benchmark else "medium"
        
        return {
            "estimated_seconds": estimated_seconds,
            "formatted_time": formatted_time,
            "explanation": explanation,
            "confidence": confidence,
            "warning": None if estimated_seconds < 86400 * 14 else "Estimated time exceeds maximum allowed runtime of 14 days"
        }
        
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e)
        )
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to estimate runtime: {str(e)}"
        )