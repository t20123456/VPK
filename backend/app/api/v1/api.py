from fastapi import APIRouter
from app.api.v1 import auth, users, jobs, storage, events, vast, settings

api_router = APIRouter()

api_router.include_router(auth.router, prefix="/auth", tags=["auth"])
api_router.include_router(users.router, prefix="/users", tags=["users"])
api_router.include_router(jobs.router, prefix="/jobs", tags=["jobs"])
api_router.include_router(storage.router, prefix="/storage", tags=["storage"])
api_router.include_router(events.router, prefix="/events", tags=["events"])
api_router.include_router(vast.router, prefix="/vast", tags=["vast"])
api_router.include_router(settings.router, prefix="/settings", tags=["settings"])