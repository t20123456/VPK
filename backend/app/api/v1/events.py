from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import StreamingResponse, FileResponse
from sqlalchemy.orm import Session
from uuid import UUID
import json
import asyncio
import os
from typing import AsyncGenerator

from app.core.database import get_db
from app.models.user import User
from app.models.job import Job
from app.services.job_service import JobService
from app.api.deps import get_current_active_user

router = APIRouter()


async def generate_job_events(job_id: str, user_id: str) -> AsyncGenerator[str, None]:
    """Generate Server-Sent Events for job updates"""
    last_status = None
    last_progress = None
    
    while True:
        try:
            # Get fresh database session for each check
            db = next(get_db())
            
            job = db.query(Job).filter(
                Job.id == job_id,
                Job.user_id == user_id
            ).first()
            
            if not job:
                yield f"event: error\ndata: {json.dumps({'error': 'Job not found'})}\n\n"
                break
            
            # Check if job status or progress changed
            status_changed = last_status != job.status.value
            progress_changed = last_progress != job.progress
            
            if status_changed or progress_changed:
                # Send job update event
                event_data = {
                    "job_id": str(job.id),
                    "status": job.status.value,
                    "progress": job.progress,
                    "error_message": job.error_message,
                    "time_started": job.time_started.isoformat() if job.time_started else None,
                    "time_finished": job.time_finished.isoformat() if job.time_finished else None,
                    "actual_cost": float(job.actual_cost) if job.actual_cost else 0.0,
                    "estimated_time": job.estimated_time,
                    "timestamp": job.updated_at.isoformat()
                }
                
                yield f"event: job_update\ndata: {json.dumps(event_data)}\n\n"
                
                last_status = job.status.value
                last_progress = job.progress
                
                # If job is completed, failed, or cancelled, send final event and stop
                if job.status.value in ['completed', 'failed', 'cancelled']:
                    yield f"event: job_finished\ndata: {json.dumps(event_data)}\n\n"
                    break
            
            db.close()
            
            # Wait before next check
            await asyncio.sleep(2)
            
        except Exception as e:
            yield f"event: error\ndata: {json.dumps({'error': str(e)})}\n\n"
            break


@router.get("/{job_id}/stream")
async def stream_job_events(
    job_id: UUID,
    current_user: User = Depends(get_current_active_user),
    db: Session = Depends(get_db)
):
    """Stream real-time job updates via Server-Sent Events"""
    
    job_service = JobService(db)
    job = job_service.get_job(job_id, current_user)
    
    if not job:
        raise HTTPException(status_code=404, detail="Job not found")
    
    # Close the DB session
    db.close()
    
    return StreamingResponse(
        generate_job_events(str(job_id), str(current_user.id)),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "Access-Control-Allow-Origin": "*",
            "Access-Control-Allow-Headers": "Cache-Control"
        }
    )


@router.get("/{job_id}/logs")
async def get_job_logs(
    job_id: UUID,
    current_user: User = Depends(get_current_active_user),
    db: Session = Depends(get_db)
):
    """Get job logs"""
    job_service = JobService(db)
    job = job_service.get_job(job_id, current_user)
    
    if not job:
        raise HTTPException(status_code=404, detail="Job not found")
    
    if not job.log_file_path:
        return {"logs": "No logs available yet"}
    
    try:
        import os
        print(f"DEBUG: job.log_file_path = '{job.log_file_path}'")
        print(f"DEBUG: os.path.exists(job.log_file_path) = {os.path.exists(job.log_file_path)}")
        print(f"DEBUG: os.path.isdir(job.log_file_path) = {os.path.isdir(job.log_file_path)}")
        print(f"DEBUG: os.path.isfile(job.log_file_path) = {os.path.isfile(job.log_file_path)}")
        
        if os.path.isdir(job.log_file_path):
            # List contents
            try:
                contents = os.listdir(job.log_file_path)
                return {"logs": f"Log file path is a directory, not a file. Contents: {contents}"}
            except:
                return {"logs": "Log file path is a directory, not a file"}
        elif not os.path.exists(job.log_file_path):
            return {"logs": "Log file not found"}
        else:
            with open(job.log_file_path, 'r') as f:
                logs = f.read()
            return {"logs": logs}
    except FileNotFoundError:
        return {"logs": "Log file not found"}
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error reading logs: {str(e)}")


@router.get("/{job_id}/pot")
async def get_job_pot_file(
    job_id: UUID,
    current_user: User = Depends(get_current_active_user),
    db: Session = Depends(get_db)
):
    """Download the pot file for a job"""
    job_service = JobService(db)
    job = job_service.get_job(job_id, current_user)
    
    if not job:
        raise HTTPException(status_code=404, detail="Job not found")
    
    if not job.pot_file_path:
        raise HTTPException(status_code=404, detail="No pot file available - job may not be completed or no passwords were cracked")
    
    if not os.path.exists(job.pot_file_path):
        raise HTTPException(status_code=404, detail="Pot file not found on disk")
    
    if not os.path.isfile(job.pot_file_path):
        raise HTTPException(status_code=500, detail="Pot file path is not a file")
    
    # Return the file as a download
    filename = f"job_{job_id}_results.pot"
    return FileResponse(
        path=job.pot_file_path,
        filename=filename,
        media_type="text/plain",
        headers={
            "Content-Disposition": f"attachment; filename={filename}",
            "Content-Description": "Hashcat pot file containing cracked passwords"
        }
    )


@router.get("/{job_id}/pot/preview")
async def preview_job_pot_file(
    job_id: UUID,
    current_user: User = Depends(get_current_active_user),
    db: Session = Depends(get_db)
):
    """Preview the contents of the pot file (first 50 lines)"""
    job_service = JobService(db)
    job = job_service.get_job(job_id, current_user)
    
    if not job:
        raise HTTPException(status_code=404, detail="Job not found")
    
    if not job.pot_file_path:
        return {"preview": "No pot file available - job may not be completed or no passwords were cracked"}
    
    try:
        if os.path.isdir(job.pot_file_path):
            return {"preview": "Pot file path is a directory, not a file"}
        elif not os.path.exists(job.pot_file_path):
            return {"preview": "Pot file not found"}
        else:
            with open(job.pot_file_path, 'r') as f:
                lines = []
                for i, line in enumerate(f):
                    if i >= 50:  # Limit to first 50 lines
                        lines.append("... (truncated, download full file for complete results)")
                        break
                    lines.append(line.rstrip())
                
                if not lines:
                    return {"preview": "Pot file is empty - no passwords were cracked"}
                
                return {
                    "preview": "\n".join(lines),
                    "total_lines_shown": len(lines) - (1 if "truncated" in lines[-1] else 0),
                    "truncated": len(lines) == 51  # 50 lines + truncation message
                }
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error reading pot file: {str(e)}")


@router.get("/stream/all")
async def stream_all_jobs_events(
    current_user: User = Depends(get_current_active_user)
):
    """Stream events for all user's jobs"""
    
    async def generate_all_jobs_events():
        last_jobs_state = {}
        
        while True:
            try:
                db = next(get_db())
                
                # Get all user's jobs
                jobs = db.query(Job).filter(Job.user_id == current_user.id).all()
                
                for job in jobs:
                    job_id = str(job.id)
                    current_state = {
                        "status": job.status.value,
                        "progress": job.progress,
                        "updated_at": job.updated_at.isoformat()
                    }
                    
                    # Check if job state changed
                    if job_id not in last_jobs_state or last_jobs_state[job_id] != current_state:
                        event_data = {
                            "job_id": job_id,
                            "name": job.name,
                            "status": job.status.value,
                            "progress": job.progress,
                            "error_message": job.error_message,
                            "created_at": job.created_at.isoformat(),
                            "updated_at": job.updated_at.isoformat()
                        }
                        
                        yield f"event: job_list_update\ndata: {json.dumps(event_data)}\n\n"
                        last_jobs_state[job_id] = current_state
                
                db.close()
                await asyncio.sleep(5)  # Check every 5 seconds for overview
                
            except Exception as e:
                yield f"event: error\ndata: {json.dumps({'error': str(e)})}\n\n"
                break
    
    return StreamingResponse(
        generate_all_jobs_events(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "Access-Control-Allow-Origin": "*",
            "Access-Control-Allow-Headers": "Cache-Control"
        }
    )