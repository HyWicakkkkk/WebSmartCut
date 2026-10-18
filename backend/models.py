from datetime import datetime
from sqlalchemy import Column, Integer, String, Text, Numeric, DateTime, ForeignKey
from sqlalchemy.orm import relationship
from database import Base


class User(Base):
    __tablename__ = "users"

    user_id = Column(Integer, primary_key=True, index=True, autoincrement=True)
    nama = Column(String(100), nullable=False)
    email = Column(String(100), unique=True, index=True, nullable=False)
    password_hash = Column(String(255), nullable=False)
    account_status = Column(String(20), default="Free", nullable=False)
    sisa_kuota = Column(Integer, default=2, nullable=False)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    clips = relationship("VideoClip", back_populates="owner", cascade="all, delete-orphan")
    transactions = relationship("Transaction", back_populates="user", cascade="all, delete-orphan")


class VideoClip(Base):
    __tablename__ = "video_clips"

    clip_id = Column(Integer, primary_key=True, index=True, autoincrement=True)
    user_id = Column(Integer, ForeignKey("users.user_id"), nullable=False)
    youtube_url = Column(Text, nullable=False)
    video_title = Column(String(255), nullable=False)
    thumbnail_url = Column(Text, nullable=True)
    file_path = Column(String(255), nullable=True)
    transcript_text = Column(Text, nullable=True)
    status_process = Column(String(20), default="Processing", nullable=False)
    segment_timestamp = Column(String(50), default="00:30 - 01:05")
    has_watermark = Column(Integer, default=1)
    has_subtitle = Column(Integer, default=0)
    subtitle_lang = Column(String(10), default="orig")
    created_at = Column(DateTime, default=datetime.utcnow)

    owner = relationship("User", back_populates="clips")
    logs = relationship("ProcessLog", back_populates="clip", cascade="all, delete-orphan")


class Transaction(Base):
    __tablename__ = "transactions"

    transaction_id = Column(Integer, primary_key=True, index=True, autoincrement=True)
    order_id = Column(String(100), unique=True, index=True, nullable=False)
    user_id = Column(Integer, ForeignKey("users.user_id"), nullable=False)
    amount = Column(Numeric(10, 2), nullable=False)
    payment_status = Column(String(20), default="Pending", nullable=False)
    snap_token = Column(String(255), nullable=True)
    payment_type = Column(String(50), default="QRIS")
    created_at = Column(DateTime, default=datetime.utcnow)

    user = relationship("User", back_populates="transactions")


class ProcessLog(Base):
    __tablename__ = "process_logs"

    log_id = Column(Integer, primary_key=True, index=True, autoincrement=True)
    clip_id = Column(Integer, ForeignKey("video_clips.clip_id"), nullable=False)
    process_type = Column(String(50), nullable=False)
    status = Column(String(20), default="Success", nullable=False)
    error_message = Column(Text, nullable=True)
    execution_time_ms = Column(Integer, default=0)
    created_at = Column(DateTime, default=datetime.utcnow)

    clip = relationship("VideoClip", back_populates="logs")


class SystemConfig(Base):
    __tablename__ = "system_configs"

    config_id = Column(Integer, primary_key=True, index=True, autoincrement=True)
    updated_by = Column(Integer, ForeignKey("users.user_id"), nullable=True)
    config_key = Column(String(50), unique=True, nullable=False)
    config_value = Column(Text, nullable=False)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
