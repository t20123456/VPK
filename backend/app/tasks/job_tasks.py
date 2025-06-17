import os
import asyncio
import subprocess
import time
import signal
from datetime import datetime, timedelta, timezone
from typing import Dict, Any, List
from celery import current_task
from celery.exceptions import SoftTimeLimitExceeded, TimeLimitExceeded
from celery.utils.log import get_task_logger
from sqlalchemy.orm import Session, joinedload

from app.core.celery_app import celery_app
from app.core.database import SessionLocal
from app.models.job import Job, JobStatus
from app.services.vast_client import VastAIClient
from app.services.s3_client import S3Client
from app.services.hashcat_service import HashcatService
from app.services.settings_service import get_settings_service

# Get Celery task logger
logger = get_task_logger(__name__)


def get_db() -> Session:
    """Get database session for tasks"""
    return SessionLocal()


def _cleanup_ssh_keys(instance_id: int):
    """Clean up SSH keys for a specific instance"""
    try:
        instance_ssh_dir = f"/tmp/ssh_keys_{instance_id}"
        if os.path.exists(instance_ssh_dir):
            import shutil
            shutil.rmtree(instance_ssh_dir)
            logger.debug(f"Cleaned up SSH keys for instance {instance_id}")
    except Exception as e:
        logger.warning(f"Failed to cleanup SSH keys for instance {instance_id}: {e}")


def _secure_cleanup_instance(vast_client: VastAIClient, instance_id: int, ssh_key_path: str = None):
    """Securely clean up all sensitive data on instance before destruction"""
    try:
        logger.info(f"Starting secure cleanup for instance {instance_id}")
        
        # Create comprehensive cleanup script that:
        # 1. Overwrites all sensitive files multiple times
        # 2. Unmounts and clears tmpfs
        # 3. Clears memory caches
        cleanup_script = """#!/bin/bash
# Secure cleanup script

echo "Starting secure data cleanup..."

# Function to securely overwrite a file
secure_delete() {
    local file="$1"
    if [ -f "$file" ]; then
        echo "Securely deleting: $file"
        # Overwrite with random data 3 times
        dd if=/dev/urandom of="$file" bs=1M count=$(du -m "$file" | cut -f1) 2>/dev/null || true
        dd if=/dev/zero of="$file" bs=1M count=$(du -m "$file" | cut -f1) 2>/dev/null || true
        dd if=/dev/urandom of="$file" bs=1M count=$(du -m "$file" | cut -f1) 2>/dev/null || true
        rm -f "$file"
    fi
}

# Kill any remaining hashcat processes
pkill -9 hashcat || true

# Securely delete files in tmpfs first (most sensitive)
if [ -d /dev/shm/hashcat_secure ]; then
    echo "Cleaning tmpfs directory..."
    secure_delete /dev/shm/hashcat_secure/hashcat.pot
    secure_delete /dev/shm/hashcat_secure/cracked.txt
    secure_delete /dev/shm/hashcat_secure/hashes.txt
    
    # Clear any other files in tmpfs
    find /dev/shm/hashcat_secure -type f -exec shred -vfz -n 3 {} \\; 2>/dev/null || true
    
    # Remove the directory (but don't unmount /dev/shm itself)
    rm -rf /dev/shm/hashcat_secure
fi

# Securely delete workspace files
echo "Cleaning workspace..."
secure_delete /workspace/hashes.txt
# Wordlists and rules are not sensitive, use simple deletion for performance
rm -f /workspace/wordlist*.txt
rm -f /workspace/rules_*.rule
secure_delete /workspace/hashcat.pot
secure_delete /workspace/cracked.txt
secure_delete /workspace/hashcat_output.log
secure_delete /workspace/hashcat.log

# Clear any remaining sensitive files (exclude wordlists)
find /workspace \( -name "*.pot" -o -name "*.txt" -o -name "*.log" \) ! -name "wordlist*.txt" | while read file; do
    secure_delete "$file"
done

# Clear bash history
history -c
rm -f ~/.bash_history
rm -f /root/.bash_history

# Clear system logs that might contain sensitive data
echo > /var/log/syslog 2>/dev/null || true
echo > /var/log/auth.log 2>/dev/null || true
journalctl --vacuum-time=1s 2>/dev/null || true

# Drop filesystem caches
sync
echo 3 > /proc/sys/vm/drop_caches 2>/dev/null || true

# Clear memory
echo "Memory cleanup completed"

# Final cleanup
rm -rf /workspace/*
rm -rf /tmp/hashcat* /dev/shm/hashcat_secure

echo "Secure cleanup completed"
"""
        
        # Execute the cleanup script
        logger.debug("Executing secure cleanup script...")
        write_cleanup_cmd = f"cat > /tmp/secure_cleanup.sh << 'EOF'\n{cleanup_script}\nEOF"
        write_result = asyncio.run(vast_client.execute_command(instance_id, write_cleanup_cmd, ssh_key_path))
        
        if write_result.get('returncode') == 0:
            # Make it executable and run it
            cleanup_cmd = "chmod +x /tmp/secure_cleanup.sh && sudo /tmp/secure_cleanup.sh || /tmp/secure_cleanup.sh"
            cleanup_result = asyncio.run(vast_client.execute_command(instance_id, cleanup_cmd, ssh_key_path))
            if cleanup_result.get('returncode') == 0:
                logger.info("Secure cleanup completed successfully")
            else:
                logger.warning(f"Secure cleanup returned non-zero: {cleanup_result.get('stderr', '')}")
            
            # Remove the cleanup script itself
            asyncio.run(vast_client.execute_command(instance_id, "shred -vfz -n 3 /tmp/secure_cleanup.sh 2>/dev/null || rm -f /tmp/secure_cleanup.sh", ssh_key_path))
        else:
            logger.warning(f"Failed to write cleanup script: {write_result.get('stderr', '')}")
            # Fallback: try basic cleanup
            logger.info("Attempting basic cleanup...")
            basic_cleanup = """
            pkill -9 hashcat || true
            rm -rf /dev/shm/hashcat_secure /workspace/* || true
            history -c || true
            """
            asyncio.run(vast_client.execute_command(instance_id, basic_cleanup, ssh_key_path))
            
    except Exception as e:
        logger.error(f"Error during secure cleanup for instance {instance_id}: {e}")
        # Even if cleanup fails destroy the instance




@celery_app.task(bind=True)
def execute_job(self, job_id: str):
    """Main task for executing a cracking job"""
    db = get_db()
    job = None
    
    try:
        job = db.query(Job).options(joinedload(Job.rule_files)).filter(Job.id == job_id).first()
        if not job:
            raise Exception(f"Job {job_id} not found")
        
        # Calculate dynamic timeout based on job's hard_end_time
        if job.hard_end_time:
            current_time = datetime.now(timezone.utc)
            if job.hard_end_time.tzinfo is None:
                job.hard_end_time = job.hard_end_time.replace(tzinfo=timezone.utc)
            
            time_remaining = (job.hard_end_time - current_time).total_seconds()
            if time_remaining <= 0:
                raise Exception("Job hard_end_time has already passed")
            
            # Set task timeout to be slightly less than the hard end time
            # This allows for cleanup before the user's deadline
            soft_limit = max(60, int(time_remaining - 120))  # 2 minutes before hard limit
            hard_limit = max(120, int(time_remaining - 60))   # 1 minute before hard limit
            
            logger.info(f"Setting dynamic timeouts for job {job_id}: soft={soft_limit}s, hard={hard_limit}s")
            
            # Apply the timeout to this specific task instance
            self.soft_time_limit = soft_limit
            self.time_limit = hard_limit
        
        # Start a monitoring task to check for user timeout
        monitor_job_timeout.apply_async(args=[job_id], countdown=30)
        
        # Update job status
        job.status = JobStatus.INSTANCE_CREATING
        job.status_message = "Initializing job execution..."
        job.time_started = datetime.now(timezone.utc)
        db.commit()
        
        # Execute job workflow
        result = _execute_job_workflow(job, db)
        
        return result
        
    except SoftTimeLimitExceeded:
        logger.warning(f"Soft time limit exceeded for job {job_id}, attempting graceful cleanup...")
        if job:
            try:
                # Try to gracefully handle the timeout
                _handle_job_timeout(job, db, is_soft_timeout=True)
            except Exception as cleanup_error:
                logger.error(f"Graceful cleanup failed: {cleanup_error}")
        raise
        
    except TimeLimitExceeded:
        logger.error(f"Hard time limit exceeded for job {job_id}, forcing cleanup...")
        if job:
            try:
                # Force cleanup on hard timeout
                _handle_job_timeout(job, db, is_soft_timeout=False)
            except Exception as cleanup_error:
                logger.error(f"Force cleanup failed: {cleanup_error}")
        raise
        
    except Exception as e:
        # Update job with error
        job = db.query(Job).filter(Job.id == job_id).first()
        if job:
            job.status = JobStatus.FAILED
            job.error_message = str(e)
            job.time_finished = datetime.now(timezone.utc)
            db.commit()
        
        raise e
    finally:
        db.close()


def _handle_job_timeout(job: Job, db: Session, is_soft_timeout: bool = True):
    """Handle job timeout with proper cleanup and result retrieval"""
    logger.info(f"Handling timeout for job {job.id} (soft: {is_soft_timeout})")
    
    # Initialize settings service if not already initialized
    try:
        settings_service = get_settings_service()
    except RuntimeError:
        from app.services.settings_service import init_settings_service
        init_settings_service()
        settings_service = get_settings_service()
    
    vast_client = VastAIClient()
    instance_id = None
    ssh_key_path = None
    
    try:
        # Get instance info if available
        if job.instance_id:
            instance_id = int(job.instance_id)
            instance_ssh_dir = f"/tmp/ssh_keys_{instance_id}"
            ssh_key_path = f"{instance_ssh_dir}/id_rsa"
            
            # Check if SSH key exists
            if not os.path.exists(ssh_key_path):
                ssh_key_path = None
            
            logger.info(f"Found instance {instance_id} for cleanup")
            
            # Update job status immediately
            job.status = JobStatus.CANCELLED
            job.status_message = f"Job cancelled due to time limit ({'soft' if is_soft_timeout else 'hard'} timeout)"
            job.time_finished = datetime.now(timezone.utc)
            
            # Try to retrieve results first (with very short timeout)
            if is_soft_timeout:
                logger.info("Attempting to retrieve results before cleanup...")
                try:
                    # Use fast result retrieval with short timeouts
                    _retrieve_results_fast(vast_client, instance_id, job, db, ssh_key_path)
                    logger.info("Successfully retrieved results during timeout cleanup")
                except Exception as e:
                    logger.warning(f"Failed to retrieve results during timeout: {e}")
            
            # Kill hashcat process
            try:
                logger.debug("Killing hashcat process...")
                kill_result = asyncio.run(asyncio.wait_for(
                    vast_client.execute_command(instance_id, "pkill -9 hashcat || true", ssh_key_path),
                    timeout=3.0
                ))
                logger.debug(f"Hashcat kill completed")
            except Exception as e:
                logger.warning(f"Failed to kill hashcat: {e}")
            
            # Perform secure cleanup before destroying instance
            try:
                logger.info(f"Performing secure cleanup before instance destruction...")
                _secure_cleanup_instance(vast_client, instance_id, ssh_key_path)
            except Exception as e:
                logger.warning(f"Secure cleanup failed during timeout: {e}")
            
            # Destroy instance
            try:
                logger.info(f"Destroying instance {instance_id}...")
                destroy_result = asyncio.run(asyncio.wait_for(
                    vast_client.destroy_instance(instance_id),
                    timeout=5.0
                ))
                logger.info(f"Instance destroyed successfully")
            except Exception as e:
                logger.error(f"Failed to destroy instance {instance_id}: {e}")
            
            # Clean up SSH keys
            _cleanup_ssh_keys(instance_id)
        
        # Final database update
        job.error_message = f"Job execution cancelled due to time limit exceeded ({'soft' if is_soft_timeout else 'hard'} timeout at {datetime.now(timezone.utc)})"
        db.commit()
        
        logger.info(f"Timeout cleanup completed for job {job.id}")
        
    except Exception as e:
        logger.error(f"Error during timeout cleanup for job {job.id}: {e}")
        # Ensure job status is updated even if cleanup fails
        try:
            job.status = JobStatus.FAILED
            job.error_message = f"Job failed due to timeout and cleanup error: {str(e)}"
            job.time_finished = datetime.now(timezone.utc)
            db.commit()
        except Exception as db_error:
            logger.error(f"Failed to update job status during timeout cleanup: {db_error}")


@celery_app.task
def monitor_job_timeout(job_id: str):
    """Monitor job for user-defined timeout and trigger cleanup if needed"""
    db = get_db()
    try:
        job = db.query(Job).filter(Job.id == job_id).first()
        if not job:
            logger.warning(f"Job {job_id} not found for timeout monitoring")
            return
        
        # Only monitor jobs that are still running
        if job.status not in [JobStatus.RUNNING, JobStatus.INSTANCE_CREATING, JobStatus.QUEUED]:
            logger.debug(f"Job {job_id} is no longer running, stopping timeout monitoring")
            return
        
        # Check if job has exceeded user-defined hard_end_time
        if job.hard_end_time:
            current_time = datetime.now(timezone.utc)
            if job.hard_end_time.tzinfo is None:
                job.hard_end_time = job.hard_end_time.replace(tzinfo=timezone.utc)
            
            if current_time >= job.hard_end_time:
                logger.warning(f"Job {job_id} has exceeded user-defined timeout, triggering cleanup")
                _handle_job_timeout(job, db, is_soft_timeout=True)
                return
            
            # Schedule next check
            time_until_timeout = (job.hard_end_time - current_time).total_seconds()
            if time_until_timeout > 30:
                # Check again in 30 seconds if there's more than 30 seconds left
                monitor_job_timeout.apply_async(args=[job_id], countdown=30)
            elif time_until_timeout > 0:
                # Check again just before timeout
                monitor_job_timeout.apply_async(args=[job_id], countdown=int(time_until_timeout - 5))
        else:
            # No hard end time set, check again in 60 seconds in case it gets set
            monitor_job_timeout.apply_async(args=[job_id], countdown=60)
            
    except Exception as e:
        logger.error(f"Error in timeout monitoring for job {job_id}: {e}")
    finally:
        db.close()


def _execute_job_workflow(job: Job, db: Session) -> Dict[str, Any]:
    """Execute the complete job workflow"""
    # Initialize settings service if not already initialized
    try:
        settings_service = get_settings_service()
    except RuntimeError:
        from app.services.settings_service import init_settings_service
        init_settings_service()
        settings_service = get_settings_service()
    
    # Debug: Check valid API key
    vast_api_key = settings_service.get_vast_api_key()
    logger.debug(f"Vast API key available: {bool(vast_api_key)}")
    if vast_api_key:
        logger.debug(f"Vast API key starts with: {vast_api_key[:10]}...")
    
    vast_client = VastAIClient()
    hashcat_service = HashcatService()
    
    instance_id = None
    
    try:
        # Step 1: Validate hash file
        job.status_message = "Validating hash file..."
        db.commit()
        validation = hashcat_service.validate_hash_file(job.hash_file_path, job.hash_type)
        if not validation["valid"]:
            raise Exception(f"Hash file validation failed: {validation['error']}")
        
        # Step 2: Use the user-selected instance or get available instances as fallback
        job.status_message = "Finding available GPU instances..."
        db.commit()
        
        if job.instance_type:
            # User selected a specific instance - try to use that offer ID
            selected_offer_id = int(job.instance_type)
            print(f"Attempting to use user-selected offer ID: {selected_offer_id}")
            job.status_message = f"Checking availability of selected instance {selected_offer_id}..."
            db.commit()
            
            # Get all current offers
            try:
                offers = asyncio.run(vast_client.get_offers(
                    secure_cloud=True,
                    region="global"
                ))
                best_offer = next((offer for offer in offers if offer['id'] == selected_offer_id), None)
                
                if not best_offer:
                    print(f"Selected offer {selected_offer_id} is no longer available, finding similar offer")
                    
                    # Try to find the original offer specs for intelligent fallback
                    original_specs = None
                    try:
                        # Get a broader list to try to find the original offer details
                        all_offers = asyncio.run(vast_client.get_offers(secure_cloud=True))
                        original_specs = next((offer for offer in all_offers if offer['id'] == selected_offer_id), None)
                    except:
                        pass
                    
                    if offers:
                        # Intelligent fallback: match GPU specs as closely as possible
                        if original_specs:
                            original_gpu = original_specs.get('gpu_name', '').lower()
                            original_gpu_count = original_specs.get('num_gpus', 1)
                            original_ram = original_specs.get('cpu_ram', 0)
                            
                            print(f"Original selection: {original_specs.get('gpu_name')} x{original_gpu_count}, {original_ram}GB RAM")
                            
                            # Score each offer based on similarity to original
                            def calculate_similarity_score(offer):
                                score = 0
                                
                                # GPU type match (highest priority)
                                offer_gpu = offer.get('gpu_name', '').lower()
                                if original_gpu in offer_gpu or offer_gpu in original_gpu:
                                    score += 100  # Exact or partial GPU match
                                
                                # GPU count match
                                if offer.get('num_gpus', 1) == original_gpu_count:
                                    score += 50
                                elif abs(offer.get('num_gpus', 1) - original_gpu_count) == 1:
                                    score += 25  # Close GPU count
                                
                                # RAM similarity (within 25% is good)
                                offer_ram = offer.get('cpu_ram', 0)
                                if original_ram > 0:
                                    ram_diff = abs(offer_ram - original_ram) / original_ram
                                    if ram_diff <= 0.25:  # Within 25%
                                        score += 30
                                    elif ram_diff <= 0.5:  # Within 50%
                                        score += 15
                                
                                # Reliability factor
                                score += offer.get('reliability', 0) * 10
                                
                                # Price factor (lower is better, but less important)
                                max_cost = settings_service.max_cost_per_hour
                                if offer.get('dph_total', float('inf')) <= max_cost:
                                    score += 10
                                
                                return score
                            
                            # Find the best matching offer
                            offers_with_scores = [(offer, calculate_similarity_score(offer)) for offer in offers]
                            offers_with_scores.sort(key=lambda x: x[1], reverse=True)
                            
                            best_offer = offers_with_scores[0][0]
                            best_score = offers_with_scores[0][1]
                            
                            print(f"Best match (score {best_score}): {best_offer.get('gpu_name')} x{best_offer.get('num_gpus')}, {best_offer.get('cpu_ram')}GB RAM at ${best_offer.get('dph_total', 0):.3f}/hour")
                        else:
                            # No original specs available, fall back to cheapest within budget
                            max_cost_per_hour = settings_service.max_cost_per_hour
                            budget_offers = [offer for offer in offers if offer.get('dph_total', float('inf')) <= max_cost_per_hour]
                            
                            if budget_offers:
                                best_offer = min(budget_offers, key=lambda x: x.get('dph_total', float('inf')))
                                print(f"Fallback to cheapest available: {best_offer.get('gpu_name')} at ${best_offer.get('dph_total', 0):.3f}/hour")
                            else:
                                # Last resort: cheapest available regardless of budget
                                best_offer = min(offers, key=lambda x: x.get('dph_total', float('inf')))
                                print(f"Emergency fallback (over budget): {best_offer.get('gpu_name')} at ${best_offer.get('dph_total', 0):.3f}/hour")
                    else:
                        raise Exception("No suitable instances available")
                else:
                    print(f"Successfully found user-selected offer {selected_offer_id}")
                
            except Exception as e:
                print(f"Failed to get user-selected offer: {e}")
                # Complete fallback to best available offer
                max_cost_per_hour = settings_service.max_cost_per_hour
                try:
                    offers = asyncio.run(vast_client.get_offers(
                        secure_cloud=True,
                        max_cost_per_hour=max_cost_per_hour,
                        region="global"
                    ))
                    
                    if not offers:
                        raise Exception("No suitable secure cloud instances available")
                    
                    best_offer = min(offers, key=lambda x: x.get('dph_total', float('inf')))
                    print(f"Emergency fallback: Using best available offer {best_offer['id']}")
                except Exception as fallback_error:
                    raise Exception(f"No instances available: {fallback_error}")
                
        else:
            # Fallback: Get available instances (secure cloud only, global region) 
            max_cost_per_hour = settings_service.max_cost_per_hour
            print(f"No specific instance selected, getting global secure cloud offers with max cost: {max_cost_per_hour}")
            offers = asyncio.run(vast_client.get_offers(
                secure_cloud=True,
                max_cost_per_hour=max_cost_per_hour,
                region="global"
            ))
            
            print(f"Found {len(offers)} secure cloud offers")
            if not offers:
                raise Exception("No suitable secure cloud instances available. This may be due to: 1) No instances in budget, 2) Invalid Vast.ai API key, 3) No secure cloud instances available")
            
            # Select best offer (lowest cost per hour)
            best_offer = min(offers, key=lambda x: x.get('dph_total', float('inf')))
        
        # Verify the selected offer meets cost constraints
        cost_per_hour = best_offer.get('dph_total', 0)
        max_total_cost = settings_service.max_total_cost
        print(f"Using offer {best_offer['id']}: {cost_per_hour}/hour")
        
        # Estimate maximum cost based on job hard_end_time or default 24 hours
        # Fix timezone issue by using timezone-aware datetime
        current_time = datetime.now(timezone.utc)
        
        if job.hard_end_time:
            # Ensure hard_end_time is timezone-aware
            if job.hard_end_time.tzinfo is None:
                # If hard_end_time is naive, assume it's UTC
                job.hard_end_time = job.hard_end_time.replace(tzinfo=timezone.utc)
            max_duration_hours = (job.hard_end_time - current_time).total_seconds() / 3600
        else:
            max_duration_hours = 24  # Default 24 hour maximum
        
        estimated_max_cost = cost_per_hour * max_duration_hours
        print(f"Estimated maximum cost: ${estimated_max_cost:.2f} (max allowed: ${max_total_cost})")
        
        if estimated_max_cost > max_total_cost:
            raise Exception(f"Estimated cost ${estimated_max_cost:.2f} exceeds maximum total cost ${max_total_cost}")
        
        # Step 3: Create instance
        job.status_message = f"Creating GPU instance: {best_offer.get('gpu_name', 'Unknown GPU')} (${best_offer.get('dph_total', 0):.3f}/hour)..."
        db.commit()
        
        # Get required disk size from job, default to 20GB
        required_disk = getattr(job, 'required_disk_gb', 20) or 20
        print(f"Creating instance with {required_disk}GB disk space")
        
        instance_result = asyncio.run(vast_client.create_instance(
            offer_id=best_offer['id'],
            image="dizcza/docker-hashcat:cuda",  # Use correct hashcat image
            disk=required_disk,
            label=f"vpk-job-{job.id}"
        ))
        
        instance_id = instance_result.get('new_contract')
        if not instance_id:
            raise Exception("Failed to create instance")
        
        job.instance_id = str(instance_id)
        job.status = JobStatus.RUNNING
        job.status_message = f"Waiting for GPU instance {instance_id} to boot up..."
        db.commit()
        
        # Step 4: Wait for instance to be ready
        ready = asyncio.run(vast_client.wait_for_instance_ready(instance_id, timeout=600))
        if not ready:
            raise Exception("Instance failed to start within timeout")
        
        # Step 4.1: Generate and attach SSH key to the instance
        job.status_message = "Setting up secure connection to GPU instance..."
        db.commit()
        
        logger.info(f"Creating and attaching SSH key to instance {instance_id}...")
        ssh_key_path = None
        try:
            # Generate a new SSH key pair for this instance
            instance_ssh_dir = f"/tmp/ssh_keys_{instance_id}"
            os.makedirs(instance_ssh_dir, exist_ok=True)
            
            ssh_key_path = f"{instance_ssh_dir}/id_rsa"
            ssh_pub_key_path = f"{instance_ssh_dir}/id_rsa.pub"
            
            # Generate SSH key pair
            keygen_result = subprocess.run([
                "ssh-keygen", "-t", "rsa", "-b", "4096", 
                "-f", ssh_key_path, "-N", "", "-q"
            ], capture_output=True, text=True)
            
            if keygen_result.returncode != 0:
                raise Exception(f"SSH key generation failed: {keygen_result.stderr}")
            
            # Set proper permissions
            os.chmod(ssh_key_path, 0o600)
            os.chmod(ssh_pub_key_path, 0o644)
            
            # Read the public key
            with open(ssh_pub_key_path, 'r') as f:
                public_key = f.read().strip()
            
            logger.debug(f"Generated SSH key (first 50 chars): {public_key[:50]}...")
            
            # Attach SSH key to instance with the actual public key string
            logger.debug(f"Attaching SSH key to instance {instance_id} (key length: {len(public_key)})")
            attach_result = subprocess.run([
                "vastai", "attach", "ssh", str(instance_id), public_key, "--api-key", vast_api_key
            ], capture_output=True, text=True)
            
            if attach_result.returncode == 0:
                logger.info("SSH key attached successfully")
            else:
                logger.error(f"SSH key attach failed - stderr: {attach_result.stderr}, stdout: {attach_result.stdout}")
                raise Exception(f"Failed to attach SSH key to instance")
                
        except Exception as e:
            logger.error(f"Failed to create/attach SSH key: {e}")
            raise Exception(f"SSH key setup failed: {e}")
        
        # Step 4.2: Wait for SSH to be ready (crucial - SSH takes time after key attachment)
        wait_time = 30
        logger.info(f"Waiting {wait_time} seconds for SSH key to be properly configured...")
        import time
        time.sleep(wait_time)  # Wait 30 seconds as recommended
        
        # Step 4.5: Test SSH connectivity (2 attempts only)
        logger.info("Testing SSH connectivity...")
        for attempt in range(2):  # Try 2 times max
            logger.debug(f"SSH connectivity test {attempt + 1}/2")
            try:
                test_result = asyncio.run(vast_client.execute_command(instance_id, "echo test", ssh_key_path))
                if test_result.get('returncode') == 0 and 'test' in test_result.get('stdout', ''):
                    logger.info("SSH connectivity successful!")
                    break
                else:
                    # Log only non-zero return codes or missing output
                    if test_result.get('stderr'):
                        logger.warning(f"SSH test stderr: {test_result['stderr']}")
                    if attempt == 0:  # First attempt failed
                        logger.info("Waiting 30 seconds before retry...")
                        time.sleep(30)
                    else:  # Second attempt failed
                        raise Exception("SSH connectivity failed after 2 attempts")
            except Exception as e:
                if attempt == 0:  # First attempt failed
                    logger.warning(f"SSH test error (attempt 1): {e}")
                    logger.info("Waiting 30 seconds before retry...")
                    time.sleep(30)
                else:  # Second attempt failed
                    logger.error(f"SSH test error (attempt 2): {e}")
                    raise Exception("SSH connectivity failed - cancelling job")
        
        # Step 5: Setup instance and transfer files
        job.status_message = "Transferring files and preparing environment..."
        db.commit()
        final_wordlist_path, rules_paths = _setup_instance(vast_client, instance_id, job, db, ssh_key_path)
        
        # Step 6: Execute hashcat with time limit monitoring
        job.status_message = "Starting password cracking process..."
        db.commit()
        _execute_hashcat(vast_client, instance_id, job, db, ssh_key_path, final_wordlist_path, rules_paths)
        
        # Check time limit before retrieving results
        if job.hard_end_time:
            # Ensure hard_end_time is timezone-aware for comparison
            if job.hard_end_time.tzinfo is None:
                job.hard_end_time = job.hard_end_time.replace(tzinfo=timezone.utc)
            if datetime.now(timezone.utc) > job.hard_end_time:
                print(f"Job {job.id} exceeded time limit, stopping execution")
                asyncio.run(vast_client.execute_command(instance_id, "pkill -9 hashcat", ssh_key_path))
                job.status = JobStatus.CANCELLED
                job.error_message = "Job stopped due to hard time limit"
                db.commit()
        
        # Step 7: Retrieve results (but only if job hasn't been cancelled)
        # Refresh job status to check if it was cancelled while running
        db.refresh(job)
        
        if job.status == JobStatus.CANCELLING:
            print(f"Job {job.id} was cancelled during execution, skipping result retrieval (fast retrieval already completed)")
        elif job.status == JobStatus.CANCELLED:
            print(f"Job {job.id} is already cancelled, skipping result retrieval")
        else:
            # Check if instance still exists before attempting retrieval
            try:
                instance_info = asyncio.run(vast_client.show_instance(instance_id))
                if instance_info and instance_info.get('actual_status') in ['running', 'stopped']:
                    job.status_message = "Retrieving results and cleaning up..."
                    db.commit()
                    _retrieve_results(vast_client, instance_id, job, db, ssh_key_path)
                else:
                    print(f"Instance {instance_id} no longer exists or is not accessible, skipping result retrieval")
            except Exception as e:
                print(f"Failed to check instance {instance_id} status: {e}, skipping result retrieval")
        
        # Step 8: Update job status
        job.status = JobStatus.COMPLETED
        job.status_message = "Job completed successfully!"
        job.time_finished = datetime.now(timezone.utc)
        
        # Calculate actual cost
        if job.time_started and job.time_finished:
            # Ensure both datetimes are timezone-aware or both are naive
            if job.time_started.tzinfo is None and job.time_finished.tzinfo is not None:
                job.time_started = job.time_started.replace(tzinfo=job.time_finished.tzinfo)
            elif job.time_started.tzinfo is not None and job.time_finished.tzinfo is None:
                job.time_finished = job.time_finished.replace(tzinfo=job.time_started.tzinfo)
            
            duration_hours = (job.time_finished - job.time_started).total_seconds() / 3600
            job.actual_cost = duration_hours * best_offer.get('dph_total', 0)
        
        db.commit()
        
        return {
            "status": "completed",
            "instance_id": instance_id,
            "duration": str(job.time_finished - job.time_started) if job.time_started else None
        }
        
    except Exception as e:
        # Update job with error
        job.status = JobStatus.FAILED
        job.error_message = str(e)
        job.time_finished = datetime.now(timezone.utc)
        db.commit()
        raise e
        
    finally:
        # Cleanup: Securely clean up instance data, then destroy instance
        if instance_id:
            # Check if job was cancelled (instance might already be destroyed by stop_job)
            db.refresh(job)
            if job.status in [JobStatus.CANCELLING, JobStatus.CANCELLED]:
                print(f"Job {job.id} was cancelled, instance {instance_id} likely already destroyed by stop task")
                # Only try to destroy if instance still exists
                try:
                    instance_info = asyncio.run(vast_client.show_instance(instance_id))
                    if instance_info and instance_info.get('actual_status') != 'stopped':
                        print(f"Instance {instance_id} still exists, destroying it")
                        asyncio.run(vast_client.destroy_instance(instance_id))
                    else:
                        print(f"Instance {instance_id} already destroyed")
                except Exception as e:
                    print(f"Instance {instance_id} check/destruction failed (likely already destroyed): {e}")
            else:
                # Normal cleanup for non-cancelled jobs
                # First, perform secure cleanup of all sensitive data
                try:
                    _secure_cleanup_instance(vast_client, instance_id, ssh_key_path)
                except Exception as secure_cleanup_error:
                    print(f"Secure cleanup failed for instance {instance_id}: {secure_cleanup_error}")
                    # Continue with instance destruction even if secure cleanup fails
                
                # Then destroy the instance
                try:
                    asyncio.run(vast_client.destroy_instance(instance_id))
                except Exception as cleanup_error:
                    print(f"Failed to destroy instance {instance_id}: {cleanup_error}")
            
            # Clean up SSH keys for this instance
            _cleanup_ssh_keys(instance_id)
        
        # Inline creds are used so no need to clean....


def _setup_instance(vast_client: VastAIClient, instance_id: int, job: Job, db: Session, ssh_key_path: str = None):
    """Setup the instance with required files and dependencies"""
    # Initialize settings service if not already initialized
    try:
        settings_service = get_settings_service()
    except RuntimeError:
        from app.services.settings_service import init_settings_service
        init_settings_service()
        settings_service = get_settings_service()
    
    # Create workspace directory first
    try:
        job.status_message = "Setting up workspace on GPU instance..."
        db.commit()
        print("Creating workspace directory...")
        mkdir_result = asyncio.run(vast_client.execute_command(instance_id, "mkdir -p /workspace", ssh_key_path))
        print(f"Workspace creation result: {mkdir_result}")
        
        # Verify workspace was created
        result = asyncio.run(vast_client.execute_command(instance_id, "ls -la /workspace", ssh_key_path))
        print(f"Workspace verification: {result}")
    except Exception as e:
        print(f"Workspace setup failed: {e}")
        raise Exception(f"Failed to create workspace directory: {e}")
    
    # Transfer hash file to instance using secure SSH streaming (POC)
    try:
        # Check if source file exists
        if not os.path.exists(job.hash_file_path):
            raise Exception(f"Source hash file does not exist: {job.hash_file_path}")
        
        job.status_message = "Uploading hash file to GPU instance (secure streaming)..."
        db.commit()
        print(f"Streaming hash file from {job.hash_file_path} to instance via SSH...")
        
        # Get SSH connection details
        ssh_url = asyncio.run(vast_client.get_ssh_url(instance_id))
        logger.debug(f"SSH URL: {ssh_url}")
        
        # Parse SSH URL to get host and port
        import re
        match = re.match(r'ssh://([^@]+)@([^:]+):(\d+)', ssh_url)
        if not match:
            raise Exception(f"Invalid SSH URL format: {ssh_url}")
        
        user, host, port = match.groups()
        
        # Setup secure tmpfs storage using existing /dev/shm (RAM-based, no disk persistence)
        print("Setting up secure tmpfs storage for hash storage...")
        setup_tmpfs_cmd = """
        # Verify /dev/shm tmpfs is available and writable
        if ! mount | grep -q "/dev/shm.*tmpfs"; then
            echo "ERROR: /dev/shm tmpfs not available - cannot proceed without secure memory storage"
            exit 1
        fi
        
        # Create secure directory in existing tmpfs with restricted permissions
        mkdir -p /dev/shm/hashcat_secure
        chmod 700 /dev/shm/hashcat_secure
        
        # Test write access to use this location
        if ! touch /dev/shm/hashcat_secure/test_write 2>/dev/null; then
            echo "ERROR: Cannot write to /dev/shm - permission denied"
            exit 1
        fi
        rm -f /dev/shm/hashcat_secure/test_write
        
        # Create workspace link to tmpfs location  
        ln -sf /dev/shm/hashcat_secure/hashes.txt /workspace/hashes.txt
        
        # Verify setup and show available space
        df -h /dev/shm
        ls -la /workspace/hashes.txt
        echo "Secure tmpfs setup complete using /dev/shm"
        """
        
        setup_result = asyncio.run(vast_client.execute_command(instance_id, setup_tmpfs_cmd, ssh_key_path))
        logger.debug(f"tmpfs setup result: {setup_result}")
        
        if setup_result.get('returncode') != 0:
            error_msg = setup_result.get('stderr', 'Unknown error')
            print(f"CRITICAL: tmpfs setup failed - cannot proceed without secure memory storage")
            print(f"tmpfs error: {error_msg}")
            raise Exception("Critical security requirement failed: tmpfs mount unsuccessful. Cannot store sensitive hash files on disk.")
        
        # Read hash file data
        file_size = os.path.getsize(job.hash_file_path)
        logger.debug(f"Source hash file size: {file_size} bytes")
        
        with open(job.hash_file_path, 'rb') as hash_file:
            hash_data = hash_file.read()
        
        # Stream hash data directly via SSH to secure tmpfs
        # This ensures no persistent disk storage on the remote instance
        target_path = "/dev/shm/hashcat_secure/hashes.txt"
        
        ssh_stream_cmd = [
            "ssh",
            "-i", ssh_key_path,
            "-p", port,
            "-o", "StrictHostKeyChecking=no",
            "-o", "UserKnownHostsFile=/dev/null",
            f"{user}@{host}",
            f"cat > {target_path}"
        ]
        
        logger.debug(f"Streaming hash data via SSH to {target_path}")
        result = subprocess.run(ssh_stream_cmd, input=hash_data, capture_output=True)
        
        if result.returncode != 0:
            # Filter SSH noise from stderr before logging
            stderr_output = result.stderr.decode() if result.stderr else ''
            # Apply similar filtering as in vast_client
            filtered_stderr = '\n'.join([
                line for line in stderr_output.split('\n')
                if line.strip() and not any(pattern in line for pattern in [
                    "Warning: Permanently added",
                    "Welcome to vast.ai",
                    "Have fun!"
                ])
            ])
            if filtered_stderr:
                logger.error(f"SSH stream error: {filtered_stderr}")
            raise Exception(f"Failed to stream hash data: {filtered_stderr or 'Unknown error'}")
        
        # Verify the file was successfully streamed
        logger.debug("Hash streaming completed, verifying...")
        verify_cmd = f"ls -la /workspace/hashes.txt && wc -l /workspace/hashes.txt && echo 'File size:' && stat -c%s /workspace/hashes.txt"
        verify_result = asyncio.run(vast_client.execute_command(instance_id, verify_cmd, ssh_key_path))
        
        if verify_result.get('returncode') != 0:
            logger.error(f"Hash file verification failed: {verify_result.get('stderr', '')}")
            raise Exception("Hash file was not properly transferred via SSH streaming - verification failed")
        else:
            logger.info(f"Successfully streamed and verified hash file to instance (secure: {'tmpfs' if setup_result.get('returncode') == 0 else 'workspace'})")
    
    except Exception as e:
        logger.error(f"Hash file transfer error: {e}")
        raise Exception(f"Failed to transfer hash file: {e}")
        
    # COMMENTED OUT: Old SCP approach
    # # Use SCP to copy the file
    # copy_cmd = [
    #     "scp",
    #     "-i", ssh_key_path,
    #     "-P", port,
    #     "-o", "StrictHostKeyChecking=no",
    #     "-o", "UserKnownHostsFile=/dev/null",
    #     job.hash_file_path,  # local source
    #     f"{user}@{host}:/workspace/hashes.txt"  # remote destination
    # ]
    
    # Download wordlist from S3 if specified
    if job.word_list:
        job.status_message = "Downloading wordlist from cloud storage..."
        db.commit()
        logger.info(f"Downloading wordlist from S3: {job.word_list}")
        aws_access_key = settings_service.get_aws_access_key_id()
        aws_secret_key = settings_service.get_aws_secret_access_key()
        s3_bucket_name = settings_service.s3_bucket_name
        s3_region = settings_service.s3_region
        
        if not aws_access_key or not aws_secret_key or not s3_bucket_name:
            raise Exception("AWS credentials not configured - cannot download wordlist from S3")
            
        try:
            # First check if s5cmd is already installed
            print("Checking if s5cmd is available...")
            check_s5cmd = asyncio.run(vast_client.execute_command(instance_id, "which s5cmd", ssh_key_path))
            
            if check_s5cmd.get('returncode') != 0:
                print("s5cmd not found, installing for optimized S3 transfers...")
                # Update apt and install dependencies including decompression tools
                print("Installing dependencies and decompression tools...")
                deps_cmd = "apt-get update -qq && apt-get install -y -qq curl file p7zip-full unzip gzip bzip2"
                deps_result = asyncio.run(vast_client.execute_command(instance_id, deps_cmd, ssh_key_path))
                if deps_result.get('returncode') != 0:
                    print(f"ERROR: Failed to install dependencies")
                    raise Exception(f"Failed to install curl: {deps_result.get('stderr', '')[:200]}")
                
                # Install s5cmd - high-performance S3 client
                print("Downloading and installing s5cmd...")
                install_cmds = [
                    "cd /tmp",
                    "curl -sL 'https://github.com/peak/s5cmd/releases/download/v2.3.0/s5cmd_2.3.0_Linux-64bit.tar.gz' -o 's5cmd.tar.gz'",
                    "file s5cmd.tar.gz",  # Check file type for debugging
                    "tar -xzf s5cmd.tar.gz",
                    "chmod +x s5cmd",
                    "mv s5cmd /usr/local/bin/"
                ]
                install_cmd = " && ".join(install_cmds)
                install_result = asyncio.run(vast_client.execute_command(instance_id, install_cmd, ssh_key_path))
                
                if install_result.get('returncode') != 0:
                    error_msg = install_result.get('stderr', 'Unknown error')
                    # Filter out SSH connection noise for s5cmd installation
                    lines = error_msg.split('\n')
                    install_errors = []
                    for line in lines:
                        line = line.strip()
                        # Skip SSH connection messages
                        if any(skip_phrase in line for skip_phrase in [
                            'Permanently added', 'Welcome to vast.ai', 'authentication fails',
                            'double check your ssh key', 'Warning:', 'ED25519', 'RSA', 'ECDSA', 'Have fun!'
                        ]):
                            continue
                        # Keep actual installation errors
                        if line and any(error_phrase in line for error_phrase in [
                            'gzip:', 'tar:', 'curl:', 'chmod:', 'mv:', 'not found', 'permission denied',
                            'No such file', 'cannot', 'failed', 'error', 'Error'
                        ]):
                            install_errors.append(line)
                    
                    if install_errors:
                        clean_error = ' | '.join(install_errors)
                        print(f"ERROR: s5cmd installation failed: {clean_error}")
                        raise Exception(f"Failed to install s5cmd: {clean_error}")
                    else:
                        # If no clear errors but command failed, check if s5cmd was actually installed
                        verify_fallback = asyncio.run(vast_client.execute_command(instance_id, "which s5cmd", ssh_key_path))
                        if verify_fallback.get('returncode') == 0:
                            print("s5cmd appears to have installed successfully despite error messages")
                        else:
                            print(f"ERROR: s5cmd installation failed with SSH noise: {error_msg[:200]}")
                            raise Exception(f"Failed to install s5cmd: Installation failed")
                
                # Verify installation
                verify_result = asyncio.run(vast_client.execute_command(instance_id, "s5cmd version", ssh_key_path))
                if verify_result.get('returncode') == 0:
                    print(f"s5cmd installed successfully: {verify_result.get('stdout', '').strip()}")
                else:
                    raise Exception("s5cmd installation verification failed")
            else:
                print("s5cmd is already available on the instance")
            
            # Download specific wordlist file from S3
            print(f"Downloading wordlist file: {job.word_list}")
            s3_path = f"s3://{s3_bucket_name}/{job.word_list}"
            
            # Create s5cmd environment with credentials
            s5cmd_env = f"AWS_ACCESS_KEY_ID='{aws_access_key}' AWS_SECRET_ACCESS_KEY='{aws_secret_key}' AWS_DEFAULT_REGION='{s3_region}'"
            
            # First check if the file exists in S3 using s5cmd
            check_cmd = f"{s5cmd_env} s5cmd ls {s3_path}"
            check_result = asyncio.run(vast_client.execute_command(instance_id, check_cmd, ssh_key_path))
            if check_result.get('returncode') != 0:
                print(f"S3 check failed - stdout: {check_result.get('stdout', '')[:200]}")
                print(f"S3 check failed - stderr: {check_result.get('stderr', '')[:200]}")
                # Try to list the bucket to debug
                list_cmd = f"{s5cmd_env} s5cmd ls s3://{s3_bucket_name}/wordlists/"
                list_result = asyncio.run(vast_client.execute_command(instance_id, list_cmd, ssh_key_path))
                print(f"Wordlist directory contents: {list_result.get('stdout', 'Unable to list')[:500]}")
                raise Exception(f"S3 file not accessible: {job.word_list}")
            
            # Get wordlist file size for progress tracking using s5cmd
            s5cmd_env = f"AWS_ACCESS_KEY_ID='{aws_access_key}' AWS_SECRET_ACCESS_KEY='{aws_secret_key}' AWS_DEFAULT_REGION='{s3_region}'"
            size_cmd = f"{s5cmd_env} s5cmd ls {s3_path}"
            size_result = asyncio.run(vast_client.execute_command(instance_id, size_cmd, ssh_key_path))
            file_size_gb = 0
            if size_result.get('returncode') == 0:
                try:
                    # Parse size from s5cmd output like: "2023/06/01 12:00:00     1234567890  s3://bucket/file.txt"
                    size_output = size_result.get('stdout', '').strip()
                    if size_output:
                        parts = size_output.split()
                        if len(parts) >= 3:
                            file_size_bytes = int(parts[2])
                            file_size_gb = file_size_bytes / (1024 * 1024 * 1024)
                            if file_size_gb >= 1:
                                print(f"Large wordlist detected: {file_size_gb:.1f} GB")
                                job.status_message = f"Downloading large wordlist ({file_size_gb:.1f} GB) with s5cmd - optimized for speed..."
                            else:
                                file_size_mb = file_size_bytes / (1024 * 1024)
                                print(f"Wordlist file size: {file_size_mb:.1f} MB")
                                job.status_message = f"Downloading wordlist ({file_size_mb:.1f} MB) with s5cmd..."
                            db.commit()
                except:
                    pass

            print("Starting high-speed S3 download with s5cmd...")
            # s5cmd automatically optimizes for large files with multipart uploads and parallel transfers
            # It's significantly faster than AWS CLI for large files
            # Download with original filename to preserve compression detection
            wordlist_filename = job.word_list.split('/')[-1]  # Get filename without path
            download_cmd = f"{s5cmd_env} s5cmd cp {s3_path} /workspace/{wordlist_filename}"
            download_result = asyncio.run(vast_client.execute_command(instance_id, download_cmd, ssh_key_path))
            
            if download_result.get('returncode') != 0:
                error_msg = download_result.get('stderr', 'Unknown error')
                lines = error_msg.split('\n')
                aws_errors = []
                for line in lines:
                    line = line.strip()
                    # Skip SSH connection messages and warnings
                    if any(skip_phrase in line for skip_phrase in [
                        'Permanently added', 'Welcome to vast.ai', 'authentication fails',
                        'double check your ssh key', 'Warning:', 'ED25519', 'RSA', 'ECDSA'
                    ]):
                        continue
                    # Keep actual AWS CLI errors
                    if line and any(aws_phrase in line for aws_phrase in [
                        'AccessDenied', 'NoSuchKey', 'NoSuchBucket', 'InvalidRequest',
                        'SignatureDoesNotMatch', 'RequestTimeTooSkewed', 'fatal error',
                        'An error occurred', 'Could not connect', 'Unable to locate credentials'
                    ]):
                        aws_errors.append(line)
                
                # Use AWS Errors if they are there
                if aws_errors:
                    clean_error = ' '.join(aws_errors)
                    if 'AccessDenied' in clean_error:
                        raise Exception("S3 Access Denied - check AWS credentials")
                    elif 'NoSuchKey' in clean_error:
                        raise Exception(f"S3 file not found: {job.word_list}")
                    else:
                        raise Exception(f"S3 download failed: {clean_error[:200]}")
                else:
                    # If no clear AWS errors but command failed, it might be SSH or network issue
                    print(f"S3 download command failed but no clear AWS error found. Full stderr: {error_msg[:500]}")
                    # Let's check if the file actually downloaded despite the error
                    verify_result = asyncio.run(vast_client.execute_command(instance_id, f"ls -la /workspace/{wordlist_filename}", ssh_key_path))
                    if verify_result.get('returncode') == 0:
                        print("File appears to have downloaded successfully despite error messages")
                    else:
                        raise Exception(f"S3 download failed: {error_msg[:200]}")
            
            # Verify the file was downloaded
            verify_result = asyncio.run(vast_client.execute_command(instance_id, f"ls -la /workspace/{wordlist_filename}", ssh_key_path))
            logger.debug(f"Wordlist verification stdout: {verify_result.get('stdout', '').strip()}")
            if verify_result.get('returncode') != 0:
                raise Exception("Wordlist was not properly downloaded - verification failed")
            else:
                print(f"Successfully downloaded and verified wordlist from S3")
                
        except Exception as e:
            print(f"Wordlist download error: {e}")
            raise Exception(f"Critical: Cannot proceed without wordlist - {str(e)}")
    
    # Check if wordlist is compressed and extract if necessary
    final_wordlist_path = None
    if job.word_list:
        try:
            # Detect compression format from filename
            wordlist_filename = job.word_list.split('/')[-1]  # Get filename without path
            compression_format = None
            
            if wordlist_filename.endswith('.7z'):
                compression_format = '7z'
            elif wordlist_filename.endswith('.zip'):
                compression_format = 'zip'
            elif wordlist_filename.endswith('.gz'):
                compression_format = 'gz'
            elif wordlist_filename.endswith('.bz2'):
                compression_format = 'bz2'
            
            if compression_format:
                print(f"Compressed wordlist detected: {compression_format} format")
                job.status_message = f"Extracting compressed wordlist ({compression_format})..."
                db.commit()
                
                # Create extracted filename based on original
                base_name = wordlist_filename
                for ext in ['.7z', '.zip', '.gz', '.bz2']:
                    if base_name.endswith(ext):
                        base_name = base_name[:-len(ext)]
                        break
                
                # Ensure extracted file has .txt extension
                if not base_name.endswith('.txt'):
                    base_name += '.txt'
                
                # Define paths
                input_path = f"/workspace/{wordlist_filename}"
                output_path = f"/workspace/{base_name}"
                final_wordlist_path = output_path
                
                # Get extraction command for the detected format
                if compression_format == '7z':
                    # Extract to a temporary name first, then rename
                    temp_name = f"extracted_wordlist_{compression_format}.txt"
                    extract_cmd = f"cd /workspace && 7z x -y '{wordlist_filename}' && largest_file=$(ls -la *.txt | grep -v '{wordlist_filename}' | sort -k5 -nr | head -1 | awk '{{print $NF}}') && mv \"$largest_file\" '{temp_name}' && mv '{temp_name}' '{base_name}'"
                elif compression_format == 'zip':
                    # Extract to a temporary name first, then rename
                    temp_name = f"extracted_wordlist_{compression_format}.txt"
                    extract_cmd = f"cd /workspace && unzip -o '{wordlist_filename}' && largest_file=$(ls -la *.txt | grep -v '{wordlist_filename}' | sort -k5 -nr | head -1 | awk '{{print $NF}}') && mv \"$largest_file\" '{temp_name}' && mv '{temp_name}' '{base_name}'"
                elif compression_format == 'gz':
                    extract_cmd = f"gunzip -c '{input_path}' > '{output_path}'"
                elif compression_format == 'bz2':
                    extract_cmd = f"bunzip2 -c '{input_path}' > '{output_path}'"
                
                print(f"Extracting wordlist with command: {extract_cmd}")
                extract_result = asyncio.run(vast_client.execute_command(instance_id, extract_cmd, ssh_key_path))
                
                if extract_result.get('returncode') != 0:
                    error_msg = extract_result.get('stderr', 'Unknown extraction error')
                    print(f"Extraction failed: {error_msg}")
                    raise Exception(f"Failed to extract compressed wordlist: {error_msg[:200]}")
                
                # Verify extraction worked
                verify_extract = asyncio.run(vast_client.execute_command(instance_id, f"ls -la '{output_path}'", ssh_key_path))
                if verify_extract.get('returncode') != 0:
                    raise Exception("Wordlist extraction failed - extracted file not found")
                
                print(f"Successfully extracted {compression_format} wordlist to {base_name}")
                job.status_message = "Wordlist extraction completed"
                db.commit()
                
                # Clean up compressed file to save space
                cleanup_cmd = f"rm -f '{input_path}'"
                asyncio.run(vast_client.execute_command(instance_id, cleanup_cmd, ssh_key_path))
                
            else:
                print("Wordlist is not compressed, using original filename")
                final_wordlist_path = f"/workspace/{wordlist_filename}"
                
        except Exception as e:
            print(f"Wordlist processing error: {e}")
            raise Exception(f"Failed to process wordlist: {str(e)}")
    
    # Download rule files if specified
    downloaded_rule_paths = []
    # Get rule files from the relationship
    rule_files_list = [rule.rule_file for rule in job.rule_files] if job.rule_files else []
    if rule_files_list:
        logger.info(f"Downloading {len(rule_files_list)} rule files from S3")
        # Reuse AWS credentials from earlier in function
        if not aws_access_key or not aws_secret_key or not s3_bucket_name:
            aws_access_key = settings_service.get_aws_access_key_id()
            aws_secret_key = settings_service.get_aws_secret_access_key()
            s3_bucket_name = settings_service.s3_bucket_name
            s3_region = settings_service.s3_region
            
            if not aws_access_key or not aws_secret_key or not s3_bucket_name:
                raise Exception("AWS credentials not configured - cannot download rules from S3")
        
        for i, rule_file in enumerate(rule_files_list):
            try:
                # Download each rule file with a unique name
                rule_filename = f"rules_{i+1}.rule"
                rule_path = f"/workspace/{rule_filename}"
                downloaded_rule_paths.append(rule_path)
                
                print(f"Downloading rule file {i+1}/{len(rule_files_list)}: {rule_file}")
                s3_path = f"s3://{s3_bucket_name}/{rule_file}"
                
                # Create s5cmd command with credentials
                s5cmd_env = f"AWS_ACCESS_KEY_ID='{aws_access_key}' AWS_SECRET_ACCESS_KEY='{aws_secret_key}' AWS_DEFAULT_REGION='{s3_region}'"
                download_cmd = f"{s5cmd_env} s5cmd cp {s3_path} {rule_path}"
                download_result = asyncio.run(vast_client.execute_command(instance_id, download_cmd, ssh_key_path))
                
                if download_result.get('returncode') != 0:
                    error_msg = download_result.get('stderr', 'Unknown error')
                    logger.error(f"Rule file {i+1} S3 download failed: {error_msg}")
                    
                    # Filter out SSH connection noise
                    lines = error_msg.split('\n')
                    aws_errors = []
                    for line in lines:
                        line = line.strip()
                        # Skip SSH connection messages and warnings
                        if any(skip_phrase in line for skip_phrase in [
                            'Permanently added', 'Welcome to vast.ai', 'authentication fails',
                            'double check your ssh key', 'Warning:', 'ED25519', 'RSA', 'ECDSA'
                        ]):
                            continue
                        # Keep actual AWS CLI errors
                        if line and any(aws_phrase in line for aws_phrase in [
                            'AccessDenied', 'NoSuchKey', 'NoSuchBucket', 'InvalidRequest',
                            'SignatureDoesNotMatch', 'RequestTimeTooSkewed', 'fatal error',
                            'An error occurred', 'Could not connect', 'Unable to locate credentials'
                        ]):
                            aws_errors.append(line)
                    
                    # Use actual AWS errors
                    if aws_errors:
                        clean_error = ' '.join(aws_errors)
                        raise Exception(f"Critical: Failed to download rule file {rule_file} from S3: {clean_error}")
                    else:
                        # Check if the file actually downloaded despite the error
                        verify_result = asyncio.run(vast_client.execute_command(instance_id, f"ls -la {rule_path}", ssh_key_path))
                        if verify_result.get('returncode') == 0:
                            print(f"Rule file {i+1} appears to have downloaded successfully despite error messages")
                        else:
                            raise Exception(f"Critical: Failed to download rule file {rule_file} from S3: {error_msg[:200]}")
                else:
                    logger.debug(f"Rule file {i+1} S3 download completed successfully")
                
                # Verify the file was downloaded
                verify_result = asyncio.run(vast_client.execute_command(instance_id, f"ls -la {rule_path}", ssh_key_path))
                if verify_result.get('returncode') != 0:
                    raise Exception(f"Rule file {rule_file} was not properly downloaded - verification failed")
                else:
                    print(f"Successfully downloaded and verified rule file {i+1}: {rule_file}")
                    
            except Exception as e:
                print(f"Rule file {i+1} download error: {e}")
                raise Exception(f"Critical: Cannot proceed without rule file {rule_file} - {str(e)}")
    
    # Return the final wordlist path and rule paths for hashcat execution
    return final_wordlist_path, downloaded_rule_paths


def _execute_hashcat(vast_client: VastAIClient, instance_id: int, job: Job, db: Session, ssh_key_path: str = None, wordlist_path: str = None, rules_paths: List[str] = None):
    """Execute hashcat on the instance with real-time monitoring"""
    hashcat_service = HashcatService()
    
    # Build hashcat command with correct paths
    # Use the wordlist_path parameter passed from setup, fallback to old logic if not provided
    if not wordlist_path and job.word_list:
        wordlist_path = "/workspace/wordlist.txt"  # Fallback for compatibility
    
    # Use rules_paths parameter if provided, otherwise fallback to empty list
    if not rules_paths:
        rules_paths = []
    
    # Create a proper job object for the instance context
    from app.models.job import Job as JobModel
    job_for_hashcat = JobModel(
        id=job.id,
        name=job.name,
        hash_type=job.hash_type,
        hash_file_path="/workspace/hashes.txt",  # Instance path
        word_list=job.word_list,
        custom_attack=job.custom_attack,
        hard_end_time=job.hard_end_time
    )
    
    cmd_parts = hashcat_service.build_command(job_for_hashcat, wordlist_path, rules_paths, skip_validation=True)
    
    hashcat_cmd = " ".join(cmd_parts)
    
    # Calculate timeout based on hard_end_time
    timeout_seconds = 7 * 24 * 3600  # 7 days maximum default
    if job.hard_end_time:
        # Ensure hard_end_time is timezone-aware for comparison
        if job.hard_end_time.tzinfo is None:
            job.hard_end_time = job.hard_end_time.replace(tzinfo=timezone.utc)
        remaining_time = (job.hard_end_time - datetime.now(timezone.utc)).total_seconds()
        timeout_seconds = min(timeout_seconds, max(60, remaining_time))
        print(f"Setting hashcat timeout to {timeout_seconds} seconds based on hard_end_time")
    else:
        print(f"No hard_end_time set, using default timeout of {timeout_seconds} seconds")
    
    # Verify files exist before running hashcat
    try:
        print("DEBUG: Verifying required files exist...")
        file_check = asyncio.run(vast_client.execute_command(instance_id, "ls -la /workspace/", ssh_key_path))
        print(f"DEBUG: Workspace contents before hashcat: {file_check}")
        
        # Check specific files
        hash_check = asyncio.run(vast_client.execute_command(instance_id, "ls -la /workspace/hashes.txt", ssh_key_path))
        print(f"DEBUG: Hash file check: {hash_check}")
        
        if job.word_list and wordlist_path:
            wordlist_check = asyncio.run(vast_client.execute_command(instance_id, f"ls -la {wordlist_path}", ssh_key_path))
            print(f"DEBUG: Wordlist file check: {wordlist_check}")
    except Exception as e:
        print(f"DEBUG: File verification failed: {e}")
    
    # Start hashcat execution using SSH
    job.status_message = "Running hashcat password cracking..."
    job.progress = 5
    db.commit()
    
    print(f"Executing hashcat command: {hashcat_cmd}")
    
    # Execute hashcat with real-time monitoring
    _execute_hashcat_with_monitoring(vast_client, instance_id, job, db, ssh_key_path, hashcat_cmd, timeout_seconds)


def _execute_hashcat_with_monitoring(vast_client: VastAIClient, instance_id: int, job: Job, db: Session, ssh_key_path: str, hashcat_cmd: str, timeout_seconds: int):
    """Execute hashcat in background and monitor progress in real-time"""
    
    # Create a wrapper script that properly detaches the process
    wrapper_script = f"""#!/bin/bash
cd /workspace

(
    echo "Starting hashcat execution at $(date)" > hashcat.log
    echo "Command: {hashcat_cmd}" >> hashcat.log
    echo "----------------------------------------" >> hashcat.log
    
    # Run hashcat with timeout and capture all output
    timeout {int(timeout_seconds)} {hashcat_cmd} 2>&1 | tee -a hashcat_output.log
    EXITCODE=${{PIPESTATUS[0]}}
    
    echo "Exit code: $EXITCODE" >> hashcat.log
    echo "Execution finished at $(date)" >> hashcat.log
    
    # Clean up marker
    rm -f /workspace/hashcat.running
) </dev/null >/dev/null 2>&1 &

# Save PID and exit immediately
echo $! > /workspace/hashcat.pid
touch /workspace/hashcat.running

# Exit script immediately
exit 0
"""
    
    # Write the wrapper script
    print("Creating hashcat wrapper script...")
    write_script_cmd = f"cat > /workspace/run_hashcat.sh << 'EOF'\n{wrapper_script}\nEOF"
    script_result = asyncio.run(vast_client.execute_command(instance_id, write_script_cmd, ssh_key_path))
    print(f"DEBUG: Script creation result: {script_result}")
    
    # Make it executable and run it
    print("Starting hashcat in background...")
    start_cmd = "chmod +x /workspace/run_hashcat.sh && /workspace/run_hashcat.sh"
    start_result = asyncio.run(vast_client.execute_command(instance_id, start_cmd, ssh_key_path))
    print(f"DEBUG: Background start result: {start_result}")
    
    if start_result.get('returncode') != 0:
        raise Exception(f"Failed to start hashcat in background: {start_result.get('stderr', 'Unknown error')}")
    
    # Wait a moment for hashcat to start
    time.sleep(3)
    
    # Check what files were created
    print("DEBUG: Checking workspace files after starting hashcat...")
    files_check = asyncio.run(vast_client.execute_command(instance_id, "ls -la /workspace/", ssh_key_path))
    print(f"DEBUG: Workspace files: {files_check}")
    
    # Monitor progress in real-time
    monitoring_start_time = datetime.now(timezone.utc)
    last_log_size = 0
    consecutive_failures = 0
    max_consecutive_failures = 5
    monitoring_loops = 0
    max_monitoring_loops = 600  # 50 minutes max (5 seconds per loop)
    
    print("Starting real-time monitoring...")
    
    time.sleep(2)
    
    while monitoring_loops < max_monitoring_loops:
        monitoring_loops += 1
        print(f"\n--- Monitoring loop {monitoring_loops} ---")
        
        try:
            # Check if exceeded the hard time limit
            if job.hard_end_time:
                if job.hard_end_time.tzinfo is None:
                    job.hard_end_time = job.hard_end_time.replace(tzinfo=timezone.utc)
                if datetime.now(timezone.utc) > job.hard_end_time:
                    print(f"HARD TIME LIMIT EXCEEDED for job {job.id} - Force stopping hashcat")
                    # Kill hashcat process
                    kill_result = asyncio.run(vast_client.execute_command(instance_id, "pkill -9 hashcat || true", ssh_key_path))
                    print(f"Kill result: {kill_result}")
                    job.status = JobStatus.CANCELLED
                    job.error_message = f"Job stopped due to hard time limit exceeded at {datetime.now(timezone.utc)}"
                    job.time_finished = datetime.now(timezone.utc)
                    db.commit()
                    break
            
            # Check if hashcat process is still running
            # First check if PID file exists and get the PID
            pid_check = asyncio.run(vast_client.execute_command(instance_id, "cat /workspace/hashcat.pid 2>/dev/null || echo 'NO_PID'", ssh_key_path))
            print(f"DEBUG: PID check: {pid_check}")
            
            # Then check if process is running
            check_process_cmd = "ps -p $(cat /workspace/hashcat.pid 2>/dev/null) >/dev/null 2>&1 && echo 'RUNNING' || echo 'STOPPED'"
            process_result = asyncio.run(vast_client.execute_command(instance_id, check_process_cmd, ssh_key_path))
            
            print(f"DEBUG: Process check result: {process_result}")
            is_running = "RUNNING" in process_result.get('stdout', '')
            
            # Also check if the marker file still exists
            marker_check = asyncio.run(vast_client.execute_command(instance_id, "test -f /workspace/hashcat.running && echo 'MARKER_EXISTS' || echo 'MARKER_GONE'", ssh_key_path))
            print(f"DEBUG: Marker check: {marker_check}")
            print(f"DEBUG: Process is running: {is_running}")
            
            # Get the latest output from hashcat
            tail_cmd = f"tail -n 50 /workspace/hashcat_output.log 2>/dev/null || echo 'No output yet'"
            tail_result = asyncio.run(vast_client.execute_command(instance_id, tail_cmd, ssh_key_path))
            
            print(f"DEBUG: Tail result returncode: {tail_result.get('returncode')}")
            print(f"DEBUG: Tail stdout length: {len(tail_result.get('stdout', ''))}")
            
            if tail_result.get('returncode') == 0:
                output = tail_result.get('stdout', '')
                
                if output and output != 'No output yet':
                    print(f"DEBUG: Got hashcat output ({len(output)} chars)")
                    print(f"DEBUG: First 200 chars: {output[:200]}")
                    
                    # Parse progress from the latest output
                    _parse_hashcat_progress_realtime(output, job, db)
                    
                    # Reset failure counter on successful read
                    consecutive_failures = 0
                else:
                    print("DEBUG: No hashcat output available yet")
            else:
                consecutive_failures += 1
                print(f"Failed to read hashcat output (attempt {consecutive_failures}/{max_consecutive_failures})")
                print(f"DEBUG: Tail error: {tail_result.get('stderr', 'Unknown error')}")
            
            # If process has stopped, break the monitoring loop
            if not is_running:
                print("Hashcat process has finished")
                
                # Check for output files as additional completion indicator
                completion_check = asyncio.run(vast_client.execute_command(
                    instance_id, 
                    "ls -la /dev/shm/hashcat_secure/cracked.txt /dev/shm/hashcat_secure/hashcat.pot 2>/dev/null | wc -l", 
                    ssh_key_path
                ))
                print(f"DEBUG: Completion file check: {completion_check}")
                
                # Get final output
                final_cmd = "cat /workspace/hashcat_output.log 2>/dev/null || echo 'No final output'"
                final_result = asyncio.run(vast_client.execute_command(instance_id, final_cmd, ssh_key_path))
                if final_result.get('returncode') == 0:
                    final_output = final_result.get('stdout', '')
                    if final_output and final_output != 'No final output':
                        print(f"DEBUG: Final output ({len(final_output)} chars)")
                        _parse_hashcat_progress_realtime(final_output, job, db)
                    else:
                        print("DEBUG: No final output available")
                        # Set completion status
                        job.progress = 100
                        job.status_message = "Password cracking completed"
                        db.commit()
                
                # List all workspace files for debugging
                workspace_files = asyncio.run(vast_client.execute_command(
                    instance_id, 
                    "ls -la /workspace/", 
                    ssh_key_path
                ))
                print(f"DEBUG: Final workspace contents: {workspace_files}")
                
                break
            
            # Stop monitoring if too many consecutive failures
            if consecutive_failures >= max_consecutive_failures:
                print(f"Too many consecutive failures ({consecutive_failures}), stopping monitoring")
                job.error_message = "Lost connection to hashcat process during monitoring"
                job.status = JobStatus.FAILED
                db.commit()
                break
            
            # Wait before next check (5 seconds for responsive updates)
            time.sleep(5)
            
        except Exception as e:
            consecutive_failures += 1
            print(f"Error during monitoring (attempt {consecutive_failures}/{max_consecutive_failures}): {e}")
            
            if consecutive_failures >= max_consecutive_failures:
                print("Too many monitoring errors, stopping")
                job.error_message = f"Monitoring failed: {str(e)}"
                job.status = JobStatus.FAILED
                db.commit()
                break
            
            # Wait before retrying
            time.sleep(10)
    
    # Check if exited due to max loops
    if monitoring_loops >= max_monitoring_loops:
        print(f"Reached maximum monitoring loops ({max_monitoring_loops})")
        job.error_message = "Monitoring timeout - job may still be running"
        # Don't mark as failed, let it complete
    
    # Clean up marker file
    cleanup_cmd = "rm -f /workspace/hashcat.running 2>/dev/null || true"
    asyncio.run(vast_client.execute_command(instance_id, cleanup_cmd, ssh_key_path))
    
    print("Real-time monitoring completed")


def _parse_hashcat_progress_realtime(output: str, job: Job, db: Session):
    """Parse hashcat output for real-time progress updates"""
    try:
        # Look for the latest STATUS line in the output
        status_lines = [line for line in output.split('\n') if line.startswith('STATUS')]
        
        if status_lines:
            latest_status = status_lines[-1]  # Get the most recent status
            parts = latest_status.split('\t')
            
            # Parse different components
            speed = None
            progress_current = None
            progress_total = None
            status_code = None
            
            # Parse status code (position 1)
            if len(parts) > 1 and parts[1].isdigit():
                status_code = int(parts[1])
            
            # Find SPEED section
            if 'SPEED' in parts:
                speed_idx = parts.index('SPEED')
                if speed_idx + 1 < len(parts) and parts[speed_idx + 1].isdigit():
                    speed = int(parts[speed_idx + 1])  # Hashes per second
            
            # Find PROGRESS section
            if 'PROGRESS' in parts:
                progress_idx = parts.index('PROGRESS')
                if progress_idx + 2 < len(parts):
                    try:
                        progress_current = int(parts[progress_idx + 1])
                        progress_total = int(parts[progress_idx + 2])
                    except ValueError:
                        pass
            
            # Calculate progress percentage
            if progress_current is not None and progress_total is not None and progress_total > 0:
                progress_pct = min(95, int((progress_current / progress_total) * 100))
                
                # Calculate estimated time remaining
                eta_msg = ""
                if speed and speed > 0 and progress_current < progress_total:
                    remaining_work = progress_total - progress_current
                    eta_seconds = remaining_work / speed
                    
                    if eta_seconds < 60:
                        eta_msg = f" (ETA: {int(eta_seconds)}s)"
                    elif eta_seconds < 3600:
                        eta_msg = f" (ETA: {int(eta_seconds/60)}m)"
                    else:
                        hours = int(eta_seconds / 3600)
                        minutes = int((eta_seconds % 3600) / 60)
                        eta_msg = f" (ETA: {hours}h {minutes}m)"
                
                # Format speed for display
                speed_msg = ""
                if speed:
                    if speed >= 1000000000:  # Billions
                        speed_msg = f" @ {speed/1000000000:.1f}B H/s"
                    elif speed >= 1000000:  # Millions
                        speed_msg = f" @ {speed/1000000:.1f}M H/s"
                    elif speed >= 1000:  # Thousands
                        speed_msg = f" @ {speed/1000:.1f}K H/s"
                    else:
                        speed_msg = f" @ {speed} H/s"
                
                # Update job progress
                job.progress = progress_pct
                
                # Status code meanings: 1=init, 2=autotune, 3=running, 4=paused, 5=exhausted, 6=cracked, 7=aborted, 8=quit, 9=bypass
                if status_code == 5:  # Exhausted
                    job.status_message = f"Completed: {progress_pct}% - Exhausted all candidates{speed_msg}"
                    job.progress = 100
                elif status_code == 6:  # Cracked
                    job.status_message = f"Completed: {progress_pct}% - All hashes cracked{speed_msg}"
                    job.progress = 100
                elif status_code == 3:  # Running
                    job.status_message = f"Cracking passwords: {progress_pct}% complete{speed_msg}{eta_msg}"
                elif status_code == 2:  # Autotune
                    job.status_message = f"Auto-tuning GPU performance: {progress_pct}%{speed_msg}"
                else:
                    job.status_message = f"Processing: {progress_pct}% complete{speed_msg}{eta_msg}"
                
                db.commit()
                
                print(f"Real-time progress: {progress_current:,}/{progress_total:,} ({progress_pct}%){speed_msg}{eta_msg}")
        
        # Also look for other hashcat phases for more detailed status updates
        if "Counting lines" in output:
            job.progress = max(job.progress, 10)
            job.status_message = "Analyzing hash file and counting entries..."
            db.commit()
            print(f"Updated status: {job.status_message} ({job.progress}%)")
        
        if "Parsed Hashes:" in output:
            job.progress = max(job.progress, 15)
            job.status_message = "Parsing and validating hash format..."
            db.commit()
            print(f"Updated status: {job.status_message} ({job.progress}%)")
        
        if "Removed duplicate hashes" in output:
            job.progress = max(job.progress, 18)
            job.status_message = "Removing duplicate hashes..."
            db.commit()
            print(f"Updated status: {job.status_message} ({job.progress}%)")
        
        if "Sorted salts" in output:
            job.progress = max(job.progress, 20)
            job.status_message = "Sorting and optimizing hash data..."
            db.commit()
            print(f"Updated status: {job.status_message} ({job.progress}%)")
        
        if "Compared hashes with potfile entries" in output:
            job.progress = max(job.progress, 22)
            job.status_message = "Checking for previously cracked hashes..."
            db.commit()
            print(f"Updated status: {job.status_message} ({job.progress}%)")
        
        if "Generated bitmap tables" in output:
            job.progress = max(job.progress, 24)
            job.status_message = "Generating optimization tables..."
            db.commit()
            print(f"Updated status: {job.status_message} ({job.progress}%)")
        
        if "Initializing device kernels" in output or "Initializing backend runtime" in output:
            job.progress = max(job.progress, 25)
            job.status_message = "Initializing GPU compute kernels..."
            db.commit()
            print(f"Updated status: {job.status_message} ({job.progress}%)")
        
        if "Initialized device kernels and memory" in output:
            job.progress = max(job.progress, 30)
            job.status_message = "GPU kernels initialized successfully..."
            db.commit()
            print(f"Updated status: {job.status_message} ({job.progress}%)")
        
        if "Starting self-test" in output:
            job.progress = max(job.progress, 32)
            job.status_message = "Running GPU self-test..."
            db.commit()
            print(f"Updated status: {job.status_message} ({job.progress}%)")
        
        if "Finished self-test" in output:
            job.progress = max(job.progress, 35)
            job.status_message = "GPU self-test completed successfully..."
            db.commit()
            print(f"Updated status: {job.status_message} ({job.progress}%)")
        
        if "Dictionary cache building" in output:
            # Try to extract percentage from cache building
            cache_lines = [line for line in output.split('\n') if 'Dictionary cache building' in line and '%' in line]
            if cache_lines:
                try:
                    # Get the last percentage mentioned
                    for line in reversed(cache_lines):
                        if '(' in line and '%' in line:
                            pct_str = line.split('(')[1].split('%')[0]
                            cache_pct = float(pct_str)
                            progress = 35 + int(cache_pct * 0.15)  # Scale to 35-50% range
                            job.progress = max(job.progress, min(50, progress))
                            job.status_message = f"Building dictionary cache: {cache_pct:.1f}%..."
                            db.commit()
                            print(f"Updated status: {job.status_message} ({job.progress}%)")
                            break
                except:
                    job.progress = max(job.progress, 40)
                    job.status_message = "Building dictionary cache from wordlist..."
                    db.commit()
                    print(f"Updated status: {job.status_message} ({job.progress}%)")
            else:
                job.progress = max(job.progress, 40)
                job.status_message = "Building dictionary cache from wordlist..."
                db.commit()
                print(f"Updated status: {job.status_message} ({job.progress}%)")
        
        if "Dictionary cache built" in output:
            job.progress = max(job.progress, 50)
            job.status_message = "Dictionary cache ready, starting attack..."
            db.commit()
            print(f"Updated status: {job.status_message} ({job.progress}%)")
        
        if "Starting autotune" in output:
            job.progress = max(job.progress, 52)
            job.status_message = "Auto-tuning GPU performance settings..."
            db.commit()
            print(f"Updated status: {job.status_message} ({job.progress}%)")
        
        if "Finished autotune" in output:
            job.progress = max(job.progress, 55)
            job.status_message = "Starting cracking..."
            db.commit()
            print(f"Updated status: {job.status_message} ({job.progress}%)")
        
        # Check if job completed based on various indicators
        if any(indicator in output for indicator in ["Started:", "Stopped:", "Session.........:", "Status..........: Exhausted"]):
            job.progress = 100
            job.status_message = "Password cracking completed!"
            db.commit()
            print(f"Updated status: {job.status_message} ({job.progress}%)")
            
    except Exception as e:
        print(f"Error parsing real-time hashcat progress: {e}")


def _parse_hashcat_progress(stdout: str, job: Job, db: Session):
    """Parse hashcat output for progress information"""
    try:
        # Look for STATUS messages in hashcat output
        # FORMAT: STATUS	6	SPEED	156034648	1000	EXEC_RUNTIME	3.221152	CURKU	0	PROGRESS	2359296	14344384	RECHASH	1	1	RECSALT	1	1	REJECTED	0	UTIL	-1
        if "STATUS" in stdout:
            status_lines = [line for line in stdout.split('\n') if line.startswith('STATUS')]
            if status_lines:
                latest_status = status_lines[-1]  # Get the latest status
                parts = latest_status.split('\t')
                
                # Parse different components
                speed = None
                progress_current = None
                progress_total = None
                exec_runtime = None
                
                # Find SPEED section
                if 'SPEED' in parts:
                    speed_idx = parts.index('SPEED')
                    if speed_idx + 1 < len(parts):
                        speed = int(parts[speed_idx + 1])  # Hashes per second
                
                # Find PROGRESS section
                if 'PROGRESS' in parts:
                    progress_idx = parts.index('PROGRESS')
                    if progress_idx + 2 < len(parts):
                        progress_current = int(parts[progress_idx + 1])
                        progress_total = int(parts[progress_idx + 2])
                
                # Find EXEC_RUNTIME section
                if 'EXEC_RUNTIME' in parts:
                    runtime_idx = parts.index('EXEC_RUNTIME')
                    if runtime_idx + 1 < len(parts):
                        exec_runtime = float(parts[runtime_idx + 1])
                
                # Calculate progress percentage
                if progress_current is not None and progress_total is not None and progress_total > 0:
                    progress_pct = min(95, int((progress_current / progress_total) * 100))
                    
                    # Calculate estimated time remaining
                    eta_msg = ""
                    if speed and speed > 0 and progress_current < progress_total:
                        remaining_work = progress_total - progress_current
                        eta_seconds = remaining_work / speed
                        
                        if eta_seconds < 60:
                            eta_msg = f" (ETA: {int(eta_seconds)}s)"
                        elif eta_seconds < 3600:
                            eta_msg = f" (ETA: {int(eta_seconds/60)}m)"
                        else:
                            hours = int(eta_seconds / 3600)
                            minutes = int((eta_seconds % 3600) / 60)
                            eta_msg = f" (ETA: {hours}h {minutes}m)"
                    
                    # Format speed for display
                    speed_msg = ""
                    if speed:
                        if speed >= 1000000000:  # Billions
                            speed_msg = f" @ {speed/1000000000:.1f}B H/s"
                        elif speed >= 1000000:  # Millions
                            speed_msg = f" @ {speed/1000000:.1f}M H/s"
                        elif speed >= 1000:  # Thousands
                            speed_msg = f" @ {speed/1000:.1f}K H/s"
                        else:
                            speed_msg = f" @ {speed} H/s"
                    
                    job.progress = progress_pct
                    job.status_message = f"Cracking passwords: {progress_pct}% complete{speed_msg}{eta_msg}"
                    db.commit()
                    
                    print(f"Progress update: {progress_current:,}/{progress_total:,} ({progress_pct}%){speed_msg}{eta_msg}")
        
        # Look for completion indicators
        elif "Started:" in stdout and "Stopped:" in stdout:
            job.progress = 100
            job.status_message = "Password cracking completed, processing results..."
            db.commit()
            
        # Look for specific hashcat phases with more detailed messages
        elif "Counting lines" in stdout:
            job.progress = 10
            job.status_message = "Analyzing hash file and counting entries..."
            db.commit()
        elif "Parsing" in stdout and "Hashes:" in stdout:
            job.progress = 15
            job.status_message = "Parsing and validating hash format..."
            db.commit()
        elif "Removing duplicate hashes" in stdout:
            job.progress = 18
            job.status_message = "Removing duplicate hashes..."
            db.commit()
        elif "Initializing device kernels" in stdout:
            job.progress = 25
            job.status_message = "Initializing GPU compute kernels..."
            db.commit()
        elif "Dictionary cache building" in stdout:
            # Check percentage from the cache building line
            cache_lines = [line for line in stdout.split('\n') if 'Dictionary cache building' in line and '%' in line]
            if cache_lines:
                try:
                    pct_str = cache_lines[-1].split('(')[1].split('%')[0]
                    cache_pct = float(pct_str)
                    progress = 30 + int(cache_pct * 0.15)  # Scale to 30-45% range
                    job.progress = min(45, progress)
                    job.status_message = f"Building dictionary cache: {cache_pct:.1f}%..."
                except:
                    job.progress = 35
                    job.status_message = "Building dictionary cache from wordlist..."
            else:
                job.progress = 35
                job.status_message = "Building dictionary cache from wordlist..."
            db.commit()
        elif "Starting autotune" in stdout:
            job.progress = 48
            job.status_message = "Auto-tuning GPU performance settings..."
            db.commit()
        elif "Finished autotune" in stdout:
            job.progress = 50
            job.status_message = "Starting password attack..."
            db.commit()
            
    except Exception as e:
        print(f"Error parsing hashcat progress: {e}")


def _monitor_job_progress(vast_client: VastAIClient, instance_id: int, job: Job, db: Session, ssh_key_path: str = None):
    """Legacy monitor function - now replaced by real-time monitoring"""
    # This function is kept for compatibility but is no longer used
    # Real-time monitoring is now handled in _execute_hashcat_with_monitoring
    pass


def _retrieve_results(vast_client: VastAIClient, instance_id: int, job: Job, db: Session, ssh_key_path: str = None):
    """Retrieve results from the instance"""
    
    # Use vastai copy to download results
    job_dir = f"/app/data/jobs/{job.id}"
    os.makedirs(job_dir, exist_ok=True)
    
    # First, check what files exist on the instance
    print("DEBUG: Checking files on instance...")
    try:
        list_result = asyncio.run(vast_client.execute_command(instance_id, "find /workspace -type f -name '*.pot' -o -name '*.txt' -o -name '*.log' | head -20", ssh_key_path))
        print(f"DEBUG: Found result files: {list_result}")
    except Exception as e:
        print(f"DEBUG: Failed to list files: {e}")
    
    # Download pot file - try multiple potential locations
    pot_file_path = f"{job_dir}/hashcat.pot"
    pot_locations = [
        "/dev/shm/hashcat_secure/hashcat.pot",  # Primary location in tmpfs
        "/dev/shm/hashcat_secure/cracked.txt",  # Output file in tmpfs
        "/workspace/hashcat.pot",                # Fallback workspace location
        "/workspace/cracked.txt",                # Fallback output location
    ]
    
    for pot_location in pot_locations:
        try:
            # First check if the file exists on the instance using SSH
            logger.debug(f"Checking if {pot_location} exists on instance...")
            check_result = asyncio.run(vast_client.execute_command(instance_id, f"test -f {pot_location} && echo 'EXISTS' || echo 'NOT_FOUND'", ssh_key_path))
            
            # Log only the relevant information, not the full result dict
            file_exists = "EXISTS" in check_result.get('stdout', '')
            if check_result.get('stderr'):
                logger.warning(f"SSH stderr while checking file: {check_result['stderr']}")
            
            if not file_exists:
                logger.debug(f"{pot_location} does not exist on instance, skipping")
                continue
                
            logger.info(f"Found pot file at {pot_location}, attempting to copy...")
            
            # Get SSH connection details for SCP
            ssh_url = asyncio.run(vast_client.get_ssh_url(instance_id))
            import re
            match = re.match(r'ssh://([^@]+)@([^:]+):(\d+)', ssh_url)
            if not match:
                raise Exception(f"Invalid SSH URL format: {ssh_url}")
            user, host, port = match.groups()
            
            copy_cmd = [
                "scp",
                "-i", ssh_key_path,
                "-P", port,
                "-o", "StrictHostKeyChecking=no",
                "-o", "UserKnownHostsFile=/dev/null",
                f"{user}@{host}:{pot_location}",
                pot_file_path
            ]
            
            result = subprocess.run(copy_cmd, capture_output=True, text=True)
            print(f"DEBUG: Pot copy from {pot_location} - return code: {result.returncode}")
            print(f"DEBUG: Pot copy stderr: {result.stderr}")
            print(f"DEBUG: Local file exists after copy: {os.path.exists(pot_file_path)}")
            print(f"DEBUG: Local file is file: {os.path.isfile(pot_file_path)}")
            
            # Check file size for debugging
            file_size = os.path.getsize(pot_file_path) if os.path.exists(pot_file_path) else -1
            print(f"DEBUG: Local file size: {file_size} bytes")
            
            if result.returncode == 0 and os.path.isfile(pot_file_path):
                job.pot_file_path = pot_file_path
                if file_size == 0:
                    print(f"Successfully retrieved empty pot file from {pot_location} (no passwords cracked)")
                else:
                    print(f"Successfully retrieved pot file from {pot_location} ({file_size} bytes)")
                break
            elif os.path.exists(pot_file_path):
                print(f"DEBUG: Copy created something but it's not a valid file (size: {file_size})")
                # Clean up if something was created but it's not a proper file
                if os.path.isdir(pot_file_path):
                    import shutil
                    shutil.rmtree(pot_file_path)
                else:
                    os.remove(pot_file_path)
        except Exception as e:
            print(f"Failed to retrieve pot file from {pot_location}: {e}")
    
    # Download log file - capture hashcat output/logs
    log_file_path = f"{job_dir}/job.log"
    log_locations = [
        "/workspace/hashcat_output.log",  # Primary log from real-time monitoring
        "/workspace/hashcat.log",         # Secondary log with metadata
        "/workspace/session.log", 
        "/workspace/output.log"
    ]
    
    # Also try to capture the terminal output from our hashcat execution
    try:
        print("DEBUG: Trying to capture hashcat execution output...")
        terminal_result = asyncio.run(vast_client.execute_command(instance_id, "ls -la /workspace/", ssh_key_path))
        print(f"DEBUG: Workspace contents: {terminal_result}")
        
        for log_location in log_locations:
            try:
                print(f"DEBUG: Trying to copy log from {log_location}")
                
                # Get SSH connection details for SCP
                ssh_url = asyncio.run(vast_client.get_ssh_url(instance_id))
                import re
                match = re.match(r'ssh://([^@]+)@([^:]+):(\d+)', ssh_url)
                if not match:
                    continue  # Skip this log location if SSH URL is invalid
                user, host, port = match.groups()
                
                copy_cmd = [
                    "scp",
                    "-i", ssh_key_path,
                    "-P", port,
                    "-o", "StrictHostKeyChecking=no",
                    "-o", "UserKnownHostsFile=/dev/null",
                    f"{user}@{host}:{log_location}",
                    log_file_path
                ]
                
                result = subprocess.run(copy_cmd, capture_output=True, text=True)
                print(f"DEBUG: Log copy from {log_location} - return code: {result.returncode}")
                
                if result.returncode == 0 and os.path.isfile(log_file_path):
                    job.log_file_path = log_file_path
                    print(f"Successfully retrieved log file from {log_location}")
                    
                    # Debug: Show the contents of the log file
                    try:
                        with open(log_file_path, 'r') as f:
                            log_content = f.read()
                            print(f"DEBUG: Log file contents ({len(log_content)} chars):")
                            print(f"--- BEGIN LOG ---")
                            print(log_content[:2000])  # Show first 2000 chars
                            if len(log_content) > 2000:
                                print(f"... (truncated, total {len(log_content)} chars)")
                            print(f"--- END LOG ---")
                    except Exception as e:
                        print(f"DEBUG: Failed to read log file: {e}")
                    
                    break
                elif os.path.exists(log_file_path):
                    # Clean up if something was created but it's not a proper file
                    if os.path.isdir(log_file_path):
                        import shutil
                        shutil.rmtree(log_file_path)
                    else:
                        os.remove(log_file_path)
            except Exception as e:
                print(f"Failed to retrieve log from {log_location}: {e}")
                
    except Exception as e:
        print(f"Failed to retrieve logs: {e}")
    
    db.commit()


@celery_app.task
def cleanup_old_jobs():
    """Cleanup old job files based on retention policy"""
    db = get_db()
    try:
        # Initialize settings service if not already initialized
        try:
            settings_service = get_settings_service()
        except RuntimeError:
            from app.services.settings_service import init_settings_service
            init_settings_service()
            settings_service = get_settings_service()
            
        retention_days = settings_service.data_retention_days
        cutoff_date = datetime.now(timezone.utc) - timedelta(days=retention_days)
        
        old_jobs = db.query(Job).filter(
            Job.created_at < cutoff_date,
            Job.status.in_([JobStatus.COMPLETED, JobStatus.FAILED, JobStatus.CANCELLED])
        ).all()
        
        for job in old_jobs:
            # Delete job files
            job_dir = f"/app/data/jobs/{job.id}"
            if os.path.exists(job_dir):
                import shutil
                shutil.rmtree(job_dir)
            
            # Delete job record
            db.delete(job)
        
        db.commit()
        return f"Cleaned up {len(old_jobs)} old jobs"
        
    finally:
        db.close()


@celery_app.task
def stop_job(job_id: str):
    """Stop a running job rapidly with result retrieval"""
    db = get_db()
    try:
        # Initialize settings service if not already initialized
        try:
            settings_service = get_settings_service()
        except RuntimeError:
            from app.services.settings_service import init_settings_service
            init_settings_service()
            settings_service = get_settings_service()
        
        job = db.query(Job).filter(Job.id == job_id).first()
        if not job:
            raise Exception(f"Job {job_id} not found")
        
        if job.instance_id and job.status in [JobStatus.RUNNING, JobStatus.INSTANCE_CREATING]:
            vast_client = VastAIClient()
            instance_id = int(job.instance_id)
            ssh_key_path = None
            vast_api_key = settings_service.get_vast_api_key()
            
            # Step 1: Immediately update job status to prevent other operations
            job.status = JobStatus.CANCELLING
            job.time_finished = datetime.now(timezone.utc)
            db.commit()
            
            # Step 1.5: Generate SSH key for stop operations (reuse existing if available)
            try:
                instance_ssh_dir = f"/tmp/ssh_keys_{instance_id}"
                ssh_key_path = f"{instance_ssh_dir}/id_rsa"
                
                # Check if SSH key already exists from the main job execution
                if not os.path.exists(ssh_key_path):
                    print(f"Generating new SSH key for stop operation on instance {instance_id}")
                    os.makedirs(instance_ssh_dir, exist_ok=True)
                    ssh_pub_key_path = f"{instance_ssh_dir}/id_rsa.pub"
                    
                    # Generate SSH key pair
                    keygen_result = subprocess.run([
                        "ssh-keygen", "-t", "rsa", "-b", "4096", 
                        "-f", ssh_key_path, "-N", "", "-q"
                    ], capture_output=True, text=True)
                    
                    if keygen_result.returncode == 0:
                        os.chmod(ssh_key_path, 0o600)
                        os.chmod(ssh_pub_key_path, 0o644)
                        
                        # Read and attach the public key
                        with open(ssh_pub_key_path, 'r') as f:
                            public_key = f.read().strip()
                        
                        # Attach SSH key to instance
                        attach_result = subprocess.run([
                            "vastai", "attach", "ssh", str(instance_id), public_key, "--api-key", vast_api_key
                        ], capture_output=True, text=True)
                        
                        if attach_result.returncode != 0:
                            print(f"Failed to attach stop SSH key: {attach_result.stderr}")
                            ssh_key_path = None  # Fall back to vastai execute
                        else:
                            print(f"Attached SSH key for stop operation")
                            # Brief wait for SSH key to be active
                            time.sleep(5)
                    else:
                        print(f"Failed to generate stop SSH key: {keygen_result.stderr}")
                        ssh_key_path = None
                else:
                    print(f"Reusing existing SSH key for stop operation")
                    
            except Exception as e:
                print(f"SSH key setup for stop failed: {e}")
                ssh_key_path = None  # Fall back to vastai execute
            
            # Step 2: Quickly retrieve any results (with short timeout)
            try:
                _retrieve_results_fast(vast_client, instance_id, job, db, ssh_key_path)
            except Exception as e:
                print(f"Fast result retrieval failed for job {job_id}: {e}")
                # Continue with termination even if result retrieval fails
            
            # Step 3: Force kill hashcat immediately
            try:
                asyncio.run(asyncio.wait_for(
                    vast_client.execute_command(instance_id, "pkill -9 hashcat || true", ssh_key_path),
                    timeout=5.0
                ))
            except Exception as e:
                print(f"Failed to kill hashcat for job {job_id}: {e}")
            
            # Step 3.5: Perform secure cleanup
            try:
                _secure_cleanup_instance(vast_client, instance_id, ssh_key_path)
            except Exception as e:
                print(f"Secure cleanup failed during job stop: {e}")
                # Continue even if cleanup fails
            
            # Step 4: Destroy instance immediately (don't wait)
            try:
                asyncio.run(asyncio.wait_for(
                    vast_client.destroy_instance(instance_id),
                    timeout=10.0
                ))
            except Exception as e:
                print(f"Failed to destroy instance {instance_id} for job {job_id}: {e}")
                # Instance might already be destroyed or unreachable
        
        
        # Step 5: Final status update
        job.status = JobStatus.CANCELLED
        db.commit()
        
        return {"status": "stopped", "job_id": job_id, "instance_destroyed": True}
        
    finally:
        db.close()


def _retrieve_results_fast(vast_client: VastAIClient, instance_id: int, job: Job, db: Session, ssh_key_path: str = None):
    """Fast result retrieval using SCP with 1-minute timeout before proceeding with cleanup"""
    
    job_dir = f"/app/data/jobs/{job.id}"
    os.makedirs(job_dir, exist_ok=True)
    
    if not ssh_key_path:
        print("No SSH key available for fast result retrieval")
        return
    
    # Get SSH connection details
    try:
        ssh_url = asyncio.run(vast_client.get_ssh_url(instance_id))
        import re
        match = re.match(r'ssh://([^@]+)@([^:]+):(\d+)', ssh_url)
        if not match:
            print(f"Invalid SSH URL format: {ssh_url}")
            return
        user, host, port = match.groups()
    except Exception as e:
        print(f"Failed to get SSH connection details: {e}")
        return
    
    # Try to copy pot file from multiple locations (up to 45 seconds total)
    pot_file_path = f"{job_dir}/result.pot"
    pot_locations = [
        "/dev/shm/hashcat_secure/hashcat.pot",  # Primary location in tmpfs
        "/dev/shm/hashcat_secure/cracked.txt",  # Output file in tmpfs
        "/workspace/hashcat.pot",                # Fallback workspace location
        "/workspace/cracked.txt",                # Fallback output location
    ]
    
    pot_retrieved = False
    for pot_location in pot_locations:
        if pot_retrieved:
            break
            
        try:
            # Check if file exists first (5 seconds)
            check_result = asyncio.run(asyncio.wait_for(
                vast_client.execute_command(instance_id, f"test -f {pot_location} && echo 'EXISTS' || echo 'NOT_FOUND'", ssh_key_path),
                timeout=5.0
            ))
            
            if "EXISTS" in check_result.get('stdout', ''):
                print(f"Found pot file at {pot_location}, copying...")
                
                # Use SCP to copy the file (15 seconds per location)
                scp_cmd = [
                    "scp",
                    "-i", ssh_key_path,
                    "-P", port,
                    "-o", "StrictHostKeyChecking=no",
                    "-o", "UserKnownHostsFile=/dev/null",
                    "-o", "ConnectTimeout=10",
                    f"{user}@{host}:{pot_location}",
                    pot_file_path
                ]
                
                result = subprocess.run(scp_cmd, capture_output=True, text=True, timeout=15.0)
                if result.returncode == 0 and os.path.isfile(pot_file_path):
                    job.pot_file_path = pot_file_path
                    file_size = os.path.getsize(pot_file_path)
                    if file_size == 0:
                        print(f"Successfully retrieved empty pot file from {pot_location} (no passwords cracked)")
                    else:
                        print(f"Successfully retrieved pot file from {pot_location} ({file_size} bytes)")
                    pot_retrieved = True
                    break
                else:
                    print(f"SCP failed for {pot_location}: {result.stderr}")
            else:
                print(f"Pot file not found at {pot_location}")
        
        except (subprocess.TimeoutExpired, asyncio.TimeoutError):
            print(f"Timeout while retrieving pot file from {pot_location}")
        except Exception as e:
            print(f"Error retrieving pot file from {pot_location}: {e}")
    
    # Try to copy log file from multiple locations (up to 15 seconds total)
    log_file_path = f"{job_dir}/job.log"
    log_locations = [
        "/workspace/hashcat_output.log",  # Primary log from real-time monitoring
        "/workspace/hashcat.log",         # Secondary log with metadata
    ]
    
    log_retrieved = False
    for log_location in log_locations:
        if log_retrieved:
            break
            
        try:
            # Check if file exists first (3 seconds)
            check_result = asyncio.run(asyncio.wait_for(
                vast_client.execute_command(instance_id, f"test -f {log_location} && echo 'EXISTS' || echo 'NOT_FOUND'", ssh_key_path),
                timeout=3.0
            ))
            
            if "EXISTS" in check_result.get('stdout', ''):
                print(f"Found log file at {log_location}, copying...")
                
                # Use SCP to copy the file (10 seconds per location)
                scp_cmd = [
                    "scp",
                    "-i", ssh_key_path,
                    "-P", port,
                    "-o", "StrictHostKeyChecking=no",
                    "-o", "UserKnownHostsFile=/dev/null",
                    "-o", "ConnectTimeout=7",
                    f"{user}@{host}:{log_location}",
                    log_file_path
                ]
                
                result = subprocess.run(scp_cmd, capture_output=True, text=True, timeout=10.0)
                if result.returncode == 0 and os.path.isfile(log_file_path):
                    job.log_file_path = log_file_path
                    file_size = os.path.getsize(log_file_path)
                    print(f"Successfully retrieved log file from {log_location} ({file_size} bytes)")
                    log_retrieved = True
                    break
                else:
                    print(f"SCP failed for {log_location}: {result.stderr}")
            else:
                print(f"Log file not found at {log_location}")
        
        except (subprocess.TimeoutExpired, asyncio.TimeoutError):
            print(f"Timeout while retrieving log file from {log_location}")
        except Exception as e:
            print(f"Error retrieving log file from {log_location}: {e}")
    
    # Report results
    if pot_retrieved and log_retrieved:
        print(f"Successfully retrieved both pot and log files for job {job.id}")
    elif pot_retrieved:
        print(f"Successfully retrieved pot file but no log file for job {job.id}")
    elif log_retrieved:
        print(f"Successfully retrieved log file but no pot file for job {job.id}")
    else:
        print(f"Failed to retrieve any result files for job {job.id} within 1-minute timeout")
    
    db.commit()