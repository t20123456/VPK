from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
from typing import List
from uuid import UUID

from app.core.database import get_db
from app.core.security import get_password_hash
from app.models.user import User as UserModel, UserRole
from app.schemas.user import User, UserCreate, UserUpdate, AdminUserCreate
from app.api.deps import get_current_admin_user, get_current_user

router = APIRouter()


@router.post("/register", response_model=User)
async def register(
    user_data: UserCreate,
    db: Session = Depends(get_db)
):
    # Check if user already exists
    existing_user = db.query(UserModel).filter(UserModel.email == user_data.email).first()
    if existing_user:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Email already registered"
        )
    
    # Create new user (always disabled by default, admin role not allowed)
    db_user = UserModel(
        email=user_data.email,
        password_hash=get_password_hash(user_data.password),
        role=UserRole.USER,  # Force user role only
        is_active=False  # Always create as disabled
    )
    db.add(db_user)
    db.commit()
    db.refresh(db_user)
    
    return db_user


@router.get("/", response_model=List[User])
async def list_users(
    skip: int = 0,
    limit: int = 100,
    current_user: UserModel = Depends(get_current_admin_user),
    db: Session = Depends(get_db)
):
    users = db.query(UserModel).offset(skip).limit(limit).all()
    return users


@router.get("/{user_id}", response_model=User)
async def get_user(
    user_id: UUID,
    current_user: UserModel = Depends(get_current_admin_user),
    db: Session = Depends(get_db)
):
    user = db.query(UserModel).filter(UserModel.id == user_id).first()
    if not user:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="User not found"
        )
    return user


@router.patch("/{user_id}", response_model=User)
async def update_user(
    user_id: UUID,
    user_update: UserUpdate,
    current_user: UserModel = Depends(get_current_admin_user),
    db: Session = Depends(get_db)
):
    user = db.query(UserModel).filter(UserModel.id == user_id).first()
    if not user:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="User not found"
        )
    
    update_data = user_update.dict(exclude_unset=True)
    if "password" in update_data:
        update_data["password_hash"] = get_password_hash(update_data.pop("password"))
    
    for field, value in update_data.items():
        setattr(user, field, value)
    
    db.commit()
    db.refresh(user)
    return user


@router.post("/", response_model=User)
async def create_user(
    user_data: AdminUserCreate,
    current_admin: UserModel = Depends(get_current_admin_user),
    db: Session = Depends(get_db)
):
    """Create a new user (admin only)"""
    # Check if user already exists
    existing_user = db.query(UserModel).filter(UserModel.email == user_data.email).first()
    if existing_user:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Email already registered"
        )
    
    # Create new user with specified role and active status
    db_user = UserModel(
        email=user_data.email,
        password_hash=get_password_hash(user_data.password),
        role=user_data.role,
        is_active=user_data.is_active
    )
    db.add(db_user)
    db.commit()
    db.refresh(db_user)
    
    return db_user


@router.delete("/{user_id}")
async def delete_user(
    user_id: UUID,
    current_user: UserModel = Depends(get_current_admin_user),
    db: Session = Depends(get_db)
):
    user = db.query(UserModel).filter(UserModel.id == user_id).first()
    if not user:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="User not found"
        )
    
    db.delete(user)
    db.commit()
    return {"detail": "User deleted successfully"}