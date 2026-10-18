from pydantic import BaseModel, Field
from typing import Optional, List
from datetime import datetime


class UserRegisterRequest(BaseModel):
    nama: str = Field(..., min_length=2, max_length=100)
    email: str
    password: str = Field(..., min_length=8)


class UserLoginRequest(BaseModel):
    email: str
    password: str


class UserResponse(BaseModel):
    user_id: int
    nama: str
    email: str
    account_status: str
    sisa_kuota: int
    created_at: datetime

    class Config:
        from_attributes = True


class AuthResponse(BaseModel):
    message: str
    access_token: str
    token_type: str = "bearer"
    expires_in_hours: int = 24
    user: UserResponse


class YouTubeValidateRequest(BaseModel):
    youtube_url: str


class YouTubeMetadataResponse(BaseModel):
    valid: bool
    youtube_url: str
    video_id: str
    video_title: str
    channel_name: str
    duration_seconds: int
    duration_formatted: str
    thumbnail_url: str


class CreateClipRequest(BaseModel):
    youtube_url: str
    add_subtitle: bool = False
    translate_id: bool = False


class ProcessLogResponse(BaseModel):
    log_id: int
    clip_id: int
    process_type: str
    status: str
    error_message: Optional[str] = None
    execution_time_ms: int
    created_at: datetime

    class Config:
        from_attributes = True


class VideoClipResponse(BaseModel):
    clip_id: int
    user_id: int
    youtube_url: str
    video_title: str
    thumbnail_url: Optional[str] = None
    file_path: Optional[str] = None
    download_url: Optional[str] = None
    transcript_text: Optional[str] = None
    status_process: str
    segment_timestamp: Optional[str] = None
    has_watermark: int
    has_subtitle: int
    subtitle_lang: str
    created_at: datetime
    logs: List[ProcessLogResponse] = []

    class Config:
        from_attributes = True
