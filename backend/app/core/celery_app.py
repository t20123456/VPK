from celery import Celery
from celery.signals import worker_process_init
from app.core.config import settings

celery_app = Celery(
    "vpk",
    broker=settings.REDIS_URL,
    backend=settings.REDIS_URL,
    include=["app.tasks.job_tasks"]
)

@worker_process_init.connect
def worker_process_init_handler(**kwargs):
    """Initialize settings service when worker process starts"""
    from app.services.settings_service import init_settings_service
    try:
        init_settings_service()
        print("Settings service initialized in Celery worker process")
    except Exception as e:
        print(f"Failed to initialize settings service in Celery worker: {e}")

# Celery configuration, default time outs are overwritten by user selections on hard time outs. These are defaults. 
celery_app.conf.update(
    task_serializer="json",
    accept_content=["json"],
    result_serializer="json",
    timezone="UTC",
    enable_utc=True,
    task_track_started=True,
    task_time_limit=30 * 60,  # 30 minutes
    task_soft_time_limit=25 * 60,  # 25 minutes
    worker_prefetch_multiplier=1,
    worker_max_tasks_per_child=1000,
)