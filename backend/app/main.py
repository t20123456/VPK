from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from contextlib import asynccontextmanager
import os

try:
    from collections.abc import Callable
    import collections
    if not hasattr(collections, 'Callable'):
        collections.Callable = Callable
except ImportError:
    pass

from app.core.config import settings
from app.api.v1.api import api_router
from app.core.database import engine
from app.models import base


@asynccontextmanager
async def lifespan(app: FastAPI):
    # Startup
    print("Starting up...")
    # Create initial admin user if it doesn't exist
    from app.utils.init_db import init_db
    init_db()
    
    # Initialize settings service
    from app.services.settings_service import init_settings_service
    init_settings_service()
    print("Settings service initialized")
    
    yield
    # Shutdown
    print("Shutting down...")


app = FastAPI(
    title=settings.PROJECT_NAME,
    description="Vast Password Kracker API",
    version=settings.VERSION,
    lifespan=lifespan
)

# Configure CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.BACKEND_CORS_ORIGINS,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Include API router
app.include_router(api_router, prefix=settings.API_V1_STR)


@app.get("/")
async def root():
    return {"message": "VPK API is running", "version": settings.VERSION}


@app.get("/health")
async def health_check():
    return {"status": "healthy"}