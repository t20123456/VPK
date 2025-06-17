from sqlalchemy import Column, String, Integer, ForeignKey, DateTime, Text, DECIMAL, Enum
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import relationship
import uuid
import enum

from .base import Base, TimestampMixin


class JobStatus(str, enum.Enum):
    READY_TO_START = "ready_to_start"
    QUEUED = "queued"
    INSTANCE_CREATING = "instance_creating"
    RUNNING = "running"
    PAUSED = "paused"
    CANCELLING = "cancelling"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"


class Job(Base, TimestampMixin):
    __tablename__ = "jobs"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    user_id = Column(UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), nullable=False)
    name = Column(String(255), nullable=False)
    hash_type = Column(String(50), nullable=False)
    hash_file_path = Column(String(500))
    word_list = Column(String(500))  # S3 key
    custom_attack = Column(Text)
    rule_list = Column(String(500))  # S3 key
    time_started = Column(DateTime(timezone=True))
    hard_end_time = Column(DateTime(timezone=True))
    time_finished = Column(DateTime(timezone=True))
    status = Column(Enum(JobStatus), default=JobStatus.READY_TO_START, index=True)
    pot_file_path = Column(String(500))
    log_file_path = Column(String(500))
    instance_type = Column(String(100))
    instance_id = Column(String(100))
    estimated_time = Column(Integer)  # seconds
    actual_cost = Column(DECIMAL(10, 4), default=0)
    progress = Column(Integer, default=0)  # percentage 0-100
    error_message = Column(Text)
    status_message = Column(Text)  # Detailed status updates for user
    required_disk_gb = Column(Integer, default=20)  # Required disk space in GB

    user = relationship("User", back_populates="jobs")
    files = relationship("JobFile", back_populates="job", cascade="all, delete-orphan")
    rule_files = relationship("JobRule", back_populates="job", cascade="all, delete-orphan", order_by="JobRule.rule_order")


class JobFile(Base, TimestampMixin):
    __tablename__ = "job_files"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    job_id = Column(UUID(as_uuid=True), ForeignKey("jobs.id", ondelete="CASCADE"), nullable=False, index=True)
    file_type = Column(String(50), nullable=False)
    local_path = Column(String(500))
    s3_key = Column(String(500))
    file_size = Column(Integer)

    job = relationship("Job", back_populates="files")


class JobRule(Base, TimestampMixin):
    __tablename__ = "job_rules"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    job_id = Column(UUID(as_uuid=True), ForeignKey("jobs.id", ondelete="CASCADE"), nullable=False, index=True)
    rule_file = Column(String(500), nullable=False)
    rule_order = Column(Integer, nullable=False, default=0)

    job = relationship("Job", back_populates="rule_files")