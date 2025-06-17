from sqlalchemy import Column, String, Integer, Boolean, DECIMAL, JSON
from sqlalchemy.dialects.postgresql import UUID
import uuid

from .base import Base, TimestampMixin


class InstanceType(Base, TimestampMixin):
    __tablename__ = "instance_types"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    vast_id = Column(String(100), unique=True, nullable=False)
    name = Column(String(255), nullable=False)
    gpu_type = Column(String(100), nullable=False)
    gpu_count = Column(Integer, nullable=False)
    cpu_count = Column(Integer, nullable=False)
    ram_gb = Column(DECIMAL(10, 2), nullable=False)
    cost_per_hour = Column(DECIMAL(10, 4), nullable=False)
    benchmark_data = Column(JSON)
    is_available = Column(Boolean, default=True)