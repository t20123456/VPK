from sqlalchemy.orm import Session
from app.core.database import SessionLocal
from app.core.config import settings
from app.core.security import get_password_hash
from app.models.user import User, UserRole
from app.models.system_setting import SystemSetting


def init_db() -> None:
    db = SessionLocal()
    try:
        # Create admin user if it doesn't exist
        admin_user = db.query(User).filter(User.email == settings.ADMIN_EMAIL).first()
        if not admin_user:
            try:
                admin_user = User(
                    email=settings.ADMIN_EMAIL,
                    password_hash=get_password_hash(settings.ADMIN_PASSWORD),
                    role=UserRole.ADMIN,
                    is_active=True
                )
                db.add(admin_user)
                db.commit()
                print(f"Admin user created: {settings.ADMIN_EMAIL}")
            except Exception as user_error:
                db.rollback()
                print(f"Admin user likely already exists: {settings.ADMIN_EMAIL}")
        else:
            print(f"Admin user already exists: {settings.ADMIN_EMAIL}")
        
        # Initialize system settings
        default_settings = {
            "max_cost_per_hour": str(settings.MAX_COST_PER_HOUR),
            "max_total_cost": str(settings.MAX_TOTAL_COST),
            "max_upload_size_mb": str(settings.MAX_UPLOAD_SIZE_MB),
            "max_hash_file_size_mb": str(settings.MAX_HASH_FILE_SIZE_MB),
            "data_retention_days": str(settings.DATA_RETENTION_DAYS),
            "default_job_timeout_hours": "168"
        }
        
        for key, value in default_settings.items():
            setting = db.query(SystemSetting).filter(SystemSetting.key == key).first()
            if not setting:
                setting = SystemSetting(
                    key=key,
                    value=value,
                    description=f"Default value for {key.replace('_', ' ')}"
                )
                db.add(setting)
        
        db.commit()
        print("System settings initialized")
        
    except Exception as e:
        print(f"Error initializing database: {e}")
        db.rollback()
    finally:
        db.close()