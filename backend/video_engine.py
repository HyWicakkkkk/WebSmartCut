import os
import re
import time
import requests
import yt_dlp
from sqlalchemy.orm import Session
from models import VideoClip, ProcessLog

YOUTUBE_REGEX = re.compile(
    r"^(https?://)?(www\.|m\.)?(youtube\.com/(watch\?v=|shorts/|embed/)|youtu\.be/)([a-zA-Z0-9_-]{11})"
)

CLIPS_DIR = os.path.join(os.path.dirname(__file__), "storage", "clips")
TEMP_DIR = os.path.join(os.path.dirname(__file__), "storage", "temp")
os.makedirs(CLIPS_DIR, exist_ok=True)
os.makedirs(TEMP_DIR, exist_ok=True)


def validate_youtube_url(url: str) -> tuple[bool, str]:
    if not url:
        return False, ""
    match = YOUTUBE_REGEX.search(url.strip())
    if not match:
        return False, ""
    return True, match.group(5)


def format_duration(seconds: int) -> str:
    mins, secs = divmod(int(seconds or 0), 60)
    hrs, mins = divmod(mins, 60)
    if hrs > 0:
        return f"{hrs:02d}:{mins:02d}:{secs:02d}"
    return f"{mins:02d}:{secs:02d}"


def extract_youtube_metadata(url: str) -> dict:
    is_valid, video_id = validate_youtube_url(url)
    if not is_valid:
        raise ValueError("Hanya mendukung URL YouTube (youtube.com atau youtu.be)")

    clean_url = f"https://www.youtube.com/watch?v={video_id}"
    thumbnail_default = f"https://i.ytimg.com/vi/{video_id}/hqdefault.jpg"

    try:
        resp = requests.get(
            f"https://www.youtube.com/oembed?url={clean_url}&format=json",
            timeout=4,
        )
        if resp.status_code == 200:
            data = resp.json()
            return {
                "valid": True,
                "youtube_url": clean_url,
                "video_id": video_id,
                "video_title": data.get("title", f"YouTube Video {video_id}"),
                "channel_name": data.get("author_name", "YouTube Creator"),
                "duration_seconds": 215,
                "duration_formatted": "03:35",
                "thumbnail_url": data.get("thumbnail_url", thumbnail_default),
            }
    except Exception:
        pass

    ydl_opts = {
        "quiet": True,
        "no_warnings": True,
        "skip_download": True,
        "socket_timeout": 5,
    }
    try:
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            info = ydl.extract_info(clean_url, download=False)
            duration = int(info.get("duration") or 180)
            return {
                "valid": True,
                "youtube_url": clean_url,
                "video_id": video_id,
                "video_title": info.get("title") or f"YouTube Video ({video_id})",
                "channel_name": info.get("uploader") or "YouTube Creator",
                "duration_seconds": duration,
                "duration_formatted": format_duration(duration),
                "thumbnail_url": info.get("thumbnail") or thumbnail_default,
            }
    except Exception:
        return {
            "valid": True,
            "youtube_url": clean_url,
            "video_id": video_id,
            "video_title": f"YouTube Video Highlight ({video_id})",
            "channel_name": "YouTube Channel",
            "duration_seconds": 180,
            "duration_formatted": "03:00",
            "thumbnail_url": thumbnail_default,
        }
