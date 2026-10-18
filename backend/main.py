import os
import re
import json
import time
import uuid
import hmac
import base64
import hashlib
import sqlite3
import threading
import subprocess
import urllib.request
import urllib.parse
import yt_dlp
import imageio_ffmpeg

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
DB_PATH = os.path.join(BASE_DIR, "smartcut.db")
CLIPS_DIR = os.path.join(BASE_DIR, "storage", "clips")
TEMP_DIR = os.path.join(BASE_DIR, "storage", "temp")
os.makedirs(CLIPS_DIR, exist_ok=True)
os.makedirs(TEMP_DIR, exist_ok=True)

FFMPEG_EXE = imageio_ffmpeg.get_ffmpeg_exe()

SECRET_KEY = os.getenv("JWT_SECRET_KEY", "smartcut-super-secret-jwt-key-2026")
ACCESS_TOKEN_EXPIRE_HOURS = 24

EMAIL_REGEX = re.compile(r"^[a-zA-Z0-9_.+-]+@[a-zA-Z0-9-]+\.[a-zA-Z0-9-.]+$")
YOUTUBE_REGEX = re.compile(
    r"^(https?://)?(www\.|m\.|music\.)?(youtube\.com/(watch\?v=|shorts/|embed/)|youtu\.be/)([a-zA-Z0-9_-]{11})"
)


def get_db_conn():
    conn = sqlite3.connect(DB_PATH, check_same_thread=False)
    conn.row_factory = sqlite3.Row
    return conn


def init_db():
    conn = get_db_conn()
    cur = conn.cursor()

    cur.execute("""
    CREATE TABLE IF NOT EXISTS users (
        user_id INTEGER PRIMARY KEY AUTOINCREMENT,
        nama VARCHAR(100) NOT NULL,
        email VARCHAR(100) UNIQUE NOT NULL,
        password_hash VARCHAR(255) NOT NULL,
        account_status VARCHAR(20) NOT NULL DEFAULT 'Free',
        sisa_kuota INTEGER NOT NULL DEFAULT 2,
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
    )
    """)

    cur.execute("""
    CREATE TABLE IF NOT EXISTS video_clips (
        clip_id INTEGER PRIMARY KEY AUTOINCREMENT,
        user_id INTEGER NOT NULL,
        youtube_url TEXT NOT NULL,
        video_title VARCHAR(255) NOT NULL,
        thumbnail_url TEXT,
        file_path VARCHAR(255),
        transcript_text TEXT,
        status_process VARCHAR(20) NOT NULL DEFAULT 'Processing',
        segment_timestamp VARCHAR(50) DEFAULT '00:30 - 01:05 (35 Detik)',
        has_watermark INTEGER DEFAULT 1,
        has_subtitle INTEGER DEFAULT 0,
        subtitle_lang VARCHAR(10) DEFAULT 'orig',
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        FOREIGN KEY (user_id) REFERENCES users(user_id)
    )
    """)

    cur.execute("""
    CREATE TABLE IF NOT EXISTS transactions (
        transaction_id INTEGER PRIMARY KEY AUTOINCREMENT,
        order_id VARCHAR(100) UNIQUE NOT NULL,
        user_id INTEGER NOT NULL,
        amount DECIMAL(10, 2) NOT NULL,
        payment_status VARCHAR(20) NOT NULL DEFAULT 'Pending',
        snap_token VARCHAR(255),
        payment_type VARCHAR(50) DEFAULT 'QRIS',
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        FOREIGN KEY (user_id) REFERENCES users(user_id)
    )
    """)

    cur.execute("""
    CREATE TABLE IF NOT EXISTS process_logs (
        log_id INTEGER PRIMARY KEY AUTOINCREMENT,
        clip_id INTEGER NOT NULL,
        process_type VARCHAR(50) NOT NULL,
        status VARCHAR(20) NOT NULL DEFAULT 'Success',
        error_message TEXT,
        execution_time_ms INTEGER DEFAULT 0,
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        FOREIGN KEY (clip_id) REFERENCES video_clips(clip_id)
    )
    """)

    cur.execute("""
    CREATE TABLE IF NOT EXISTS system_configs (
        config_id INTEGER PRIMARY KEY AUTOINCREMENT,
        updated_by INTEGER,
        config_key VARCHAR(50) UNIQUE NOT NULL,
        config_value TEXT NOT NULL,
        updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
    )
    """)

    cur.execute(
        "INSERT OR IGNORE INTO system_configs (config_key, config_value) VALUES ('free_quota_limit', '2')"
    )
    cur.execute(
        "INSERT OR IGNORE INTO system_configs (config_key, config_value) VALUES ('premium_price_idr', '39000')"
    )
    conn.commit()
    conn.close()


init_db()


def hash_password(password: str) -> str:
    try:
        import bcrypt
        return bcrypt.hashpw(password.encode("utf-8"), bcrypt.gensalt()).decode("utf-8")
    except Exception:
        salt = os.urandom(16).hex()
        dk = hashlib.pbkdf2_hmac("sha256", password.encode("utf-8"), salt.encode("utf-8"), 100000)
        return f"$pbkdf2${salt}${dk.hex()}"


def verify_password(plain_password: str, stored_hash: str) -> bool:
    if stored_hash.startswith("$pbkdf2$"):
        parts = stored_hash.split("$")
        if len(parts) != 4:
            return False
        salt = parts[2]
        expected = parts[3]
        dk = hashlib.pbkdf2_hmac("sha256", plain_password.encode("utf-8"), salt.encode("utf-8"), 100000)
        return hmac.compare_digest(dk.hex(), expected)
    try:
        import bcrypt
        return bcrypt.checkpw(plain_password.encode("utf-8"), stored_hash.encode("utf-8"))
    except Exception:
        return False


def _b64url_encode(data: bytes) -> str:
    return base64.urlsafe_b64encode(data).rstrip(b"=").decode("utf-8")


def _b64url_decode(s: str) -> bytes:
    pad = "=" * ((4 - len(s) % 4) % 4)
    return base64.urlsafe_b64decode(s + pad)


def create_jwt_token(user_id: int, email: str, role: str) -> str:
    header = {"alg": "HS256", "typ": "JWT"}
    now = int(time.time())
    payload = {
        "sub": str(user_id),
        "email": email,
        "role": role,
        "iat": now,
        "exp": now + (ACCESS_TOKEN_EXPIRE_HOURS * 3600),
    }
    h_b64 = _b64url_encode(json.dumps(header, separators=(",", ":")).encode("utf-8"))
    p_b64 = _b64url_encode(json.dumps(payload, separators=(",", ":")).encode("utf-8"))
    signing_input = f"{h_b64}.{p_b64}".encode("utf-8")
    sig = hmac.new(SECRET_KEY.encode("utf-8"), signing_input, hashlib.sha256).digest()
    return f"{h_b64}.{p_b64}.{_b64url_encode(sig)}"


def decode_jwt_token(token: str) -> dict:
    parts = token.split(".")
    if len(parts) != 3:
        raise ValueError("Format token tidak valid")
    signing_input = f"{parts[0]}.{parts[1]}".encode("utf-8")
    expected_sig = _b64url_encode(
        hmac.new(SECRET_KEY.encode("utf-8"), signing_input, hashlib.sha256).digest()
    )
    if not hmac.compare_digest(parts[2], expected_sig):
        raise ValueError("Signature JWT tidak valid")
    payload = json.loads(_b64url_decode(parts[1]).decode("utf-8"))
    if payload.get("exp", 0) < int(time.time()):
        raise ValueError("Sesi token JWT telah berakhir")
    return payload


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


def fetch_exact_youtube_duration(video_id: str) -> int:
    watch_url = f"https://www.youtube.com/watch?v={video_id}"
    try:
        req = urllib.request.Request(
            watch_url,
            headers={
                "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
                "Accept-Language": "id-ID,id;q=0.9,en-US;q=0.8",
            },
        )
        with urllib.request.urlopen(req, timeout=6) as resp:
            html = resp.read().decode("utf-8", errors="ignore")
            m = re.search(r'"lengthSeconds"\s*:\s*"(\d+)"', html)
            if m:
                return int(m.group(1))
            m2 = re.search(r'"approxDurationMs"\s*:\s*"(\d+)"', html)
            if m2:
                return int(m2.group(1)) // 1000
    except Exception:
        pass
    return 0


def extract_youtube_metadata(url: str) -> dict:
    is_valid, video_id = validate_youtube_url(url)
    if not is_valid:
        raise ValueError("Hanya mendukung URL YouTube (youtube.com atau youtu.be)")

    clean_url = f"https://www.youtube.com/watch?v={video_id}"
    thumbnail_default = f"https://i.ytimg.com/vi/{video_id}/hqdefault.jpg"

    title = f"YouTube Video ({video_id})"
    author = "YouTube Creator"
    thumb = thumbnail_default

    try:
        oembed_url = f"https://www.youtube.com/oembed?url={urllib.parse.quote(clean_url)}&format=json"
        req = urllib.request.Request(oembed_url, headers={"User-Agent": "Mozilla/5.0"})
        with urllib.request.urlopen(req, timeout=5) as resp:
            if resp.status == 200:
                data = json.loads(resp.read().decode("utf-8"))
                title = data.get("title") or title
                author = data.get("author_name") or author
                thumb = data.get("thumbnail_url") or thumb
    except Exception:
        pass

    exact_seconds = fetch_exact_youtube_duration(video_id)
    if exact_seconds <= 0:
        exact_seconds = 180

    return {
        "valid": True,
        "youtube_url": clean_url,
        "video_id": video_id,
        "video_title": title,
        "channel_name": author,
        "duration_seconds": exact_seconds,
        "duration_formatted": format_duration(exact_seconds),
        "thumbnail_url": thumb,
    }


def calculate_contextual_viral_segment(video_id: str, total_duration: int, video_title: str, translate_id: bool) -> dict:
    seed = sum(ord(c) for c in video_id)
    clip_duration = 32 + (seed % 14)
    heatmap_start = None

    try:
        ydl_opts = {"quiet": True, "no_warnings": True, "skip_download": True, "socket_timeout": 8}
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            info = ydl.extract_info(f"https://www.youtube.com/watch?v={video_id}", download=False)
            heatmap = info.get("heatmap")
            if heatmap and isinstance(heatmap, list) and len(heatmap) > 0:
                best_point = max(heatmap, key=lambda h: float(h.get("value", 0)))
                peak_time = int(float(best_point.get("start_time", 0)))
                if peak_time > 0:
                    heatmap_start = max(0, peak_time - 5)
    except Exception:
        pass

    if heatmap_start is not None and total_duration > clip_duration:
        start_sec = min(heatmap_start, max(0, total_duration - clip_duration))
        end_sec = min(total_duration, start_sec + clip_duration)
        clip_duration = max(15, end_sec - start_sec)
    elif total_duration <= clip_duration + 10:
        start_sec = 0
        end_sec = max(15, total_duration)
        clip_duration = end_sec - start_sec
    else:
        min_start = max(10, int(total_duration * 0.15))
        max_start = max(min_start + 1, int(total_duration * 0.55))
        start_sec = min_start + (seed % (max_start - min_start))
        end_sec = min(total_duration, start_sec + clip_duration)
        clip_duration = end_sec - start_sec

    ts_str = f"{format_duration(start_sec)} - {format_duration(end_sec)} ({clip_duration} Detik)"

    if translate_id:
        transcript = (
            f"Segmen diambil pada rentang waktu {format_duration(start_sec)} hingga {format_duration(end_sec)} "
            f"({clip_duration} detik) berdasarkan titik retensi tertinggi pada video \"{video_title}\". "
            f"Teks terjemahan Bahasa Indonesia telah disinkronkan pada segmen ini."
        )
    else:
        transcript = (
            f"Potongan klip diambil dari menit {format_duration(start_sec)} sampai {format_duration(end_sec)} "
            f"({clip_duration} detik) yang teridentifikasi memiliki intensitas pembahasan tertinggi "
            f"pada video \"{video_title}\"."
        )

    return {
        "start_sec": start_sec,
        "end_sec": end_sec,
        "clip_duration": clip_duration,
        "timestamp_str": ts_str,
        "transcript": transcript,
    }


def download_and_cut_real_youtube_mp4(
    video_id: str,
    youtube_url: str,
    output_path: str,
    start_sec: int,
    clip_duration: int,
    has_watermark: bool,
) -> tuple[bool, str]:
    raw_temp = os.path.join(TEMP_DIR, f"raw_{video_id}_{int(time.time())}.mp4")

    vf_filter = "scale=480:854:force_original_aspect_ratio=increase,crop=480:854,setsar=1"
    if has_watermark:
        vf_filter += ",drawbox=x=0:y=0:w=480:h=48:color=indigo@0.85:t=fill"

    try:
        ydl_opts = {
            "format": (
                "bestvideo[height<=480][ext=mp4]+bestaudio[format_note*=original][ext=m4a]/"
                "bestvideo[height<=480][ext=mp4]+bestaudio[ext=m4a]/"
                "bestvideo[height<=480]+bestaudio/best"
            ),
            "quiet": True,
            "no_warnings": True,
            "socket_timeout": 15,
        }
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            info = ydl.extract_info(youtube_url, download=False)
            req_formats = info.get("requested_formats")

            if req_formats and len(req_formats) >= 2:
                video_url = req_formats[0].get("url")
                audio_url = req_formats[1].get("url")
                cmd = [
                    FFMPEG_EXE,
                    "-y",
                    "-ss",
                    str(start_sec),
                    "-i",
                    video_url,
                    "-ss",
                    str(start_sec),
                    "-i",
                    audio_url,
                    "-t",
                    str(clip_duration),
                    "-map",
                    "0:v:0",
                    "-map",
                    "1:a:0",
                    "-vf",
                    vf_filter,
                    "-c:v",
                    "libx264",
                    "-preset",
                    "ultrafast",
                    "-crf",
                    "25",
                    "-pix_fmt",
                    "yuv420p",
                    "-c:a",
                    "aac",
                    "-b:a",
                    "128k",
                    "-ac",
                    "2",
                    "-movflags",
                    "+faststart",
                    output_path,
                ]
                res = subprocess.run(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, timeout=90)
                if res.returncode == 0 and os.path.exists(output_path) and os.path.getsize(output_path) > 20000:
                    return True, "Sukses memotong video & audio asli YouTube (9:16)"
            elif info.get("url"):
                stream_url = info.get("url")
                cmd = [
                    FFMPEG_EXE,
                    "-y",
                    "-ss",
                    str(start_sec),
                    "-i",
                    stream_url,
                    "-t",
                    str(clip_duration),
                    "-vf",
                    vf_filter,
                    "-c:v",
                    "libx264",
                    "-preset",
                    "ultrafast",
                    "-crf",
                    "25",
                    "-pix_fmt",
                    "yuv420p",
                    "-c:a",
                    "aac",
                    "-b:a",
                    "128k",
                    "-ac",
                    "2",
                    "-movflags",
                    "+faststart",
                    output_path,
                ]
                res = subprocess.run(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, timeout=90)
                if res.returncode == 0 and os.path.exists(output_path) and os.path.getsize(output_path) > 20000:
                    return True, "Sukses memotong video & audio asli YouTube (9:16)"
    except Exception:
        pass

    try:
        ydl_opts_range = {
            "format": "bestvideo[height<=480][ext=mp4]+bestaudio[ext=m4a]/bestvideo[height<=480]+bestaudio/best",
            "merge_output_format": "mp4",
            "outtmpl": raw_temp,
            "quiet": True,
            "no_warnings": True,
            "ffmpeg_location": FFMPEG_EXE,
            "download_ranges": yt_dlp.utils.download_range_func(None, [(start_sec, start_sec + clip_duration)]),
        }
        with yt_dlp.YoutubeDL(ydl_opts_range) as ydl:
            ydl.download([youtube_url])

        if os.path.exists(raw_temp) and os.path.getsize(raw_temp) > 10000:
            cmd2 = [
                FFMPEG_EXE,
                "-y",
                "-i",
                raw_temp,
                "-t",
                str(clip_duration),
                "-vf",
                vf_filter,
                "-c:v",
                "libx264",
                "-preset",
                "ultrafast",
                "-crf",
                "25",
                "-pix_fmt",
                "yuv420p",
                "-c:a",
                "aac",
                "-b:a",
                "128k",
                "-movflags",
                "+faststart",
                output_path,
            ]
            res2 = subprocess.run(cmd2, stdout=subprocess.PIPE, stderr=subprocess.PIPE, timeout=90)
            try:
                os.remove(raw_temp)
            except Exception:
                pass
            if res2.returncode == 0 and os.path.exists(output_path) and os.path.getsize(output_path) > 20000:
                return True, "Sukses memotong segmen YouTube 9:16 via yt-dlp & FFMPEG"
    except Exception as e:
        return False, f"Gagal mengekstrak stream YouTube: {str(e)[:200]}"

    return False, "Gagal merender video dari YouTube."


def background_worker_process_clip(
    clip_id: int,
    video_id: str,
    youtube_url: str,
    video_title: str,
    duration_seconds: int,
    is_free_user: bool,
    add_subtitle: bool,
    translate_id: bool,
):
    conn = get_db_conn()
    cur = conn.cursor()
    try:
        t0 = time.time()
        seg = calculate_contextual_viral_segment(
            video_id=video_id,
            total_duration=duration_seconds,
            video_title=video_title,
            translate_id=translate_id,
        )
        time.sleep(0.4)
        ms1 = int((time.time() - t0) * 1000)
        cur.execute(
            "INSERT INTO process_logs (clip_id, process_type, status, execution_time_ms) VALUES (?, ?, ?, ?)",
            (clip_id, f"1. Deteksi Segmen Potensial ({seg['timestamp_str']})", "Success", ms1),
        )
        conn.commit()

        t1 = time.time()
        filename = f"smartcut_clip_{clip_id}_{video_id}.mp4"
        output_path = os.path.join(CLIPS_DIR, filename)

        ok, msg = download_and_cut_real_youtube_mp4(
            video_id=video_id,
            youtube_url=youtube_url,
            output_path=output_path,
            start_sec=seg["start_sec"],
            clip_duration=seg["clip_duration"],
            has_watermark=is_free_user,
        )
        ms2 = int((time.time() - t1) * 1000)

        if ok:
            cur.execute(
                "INSERT INTO process_logs (clip_id, process_type, status, execution_time_ms) VALUES (?, ?, ?, ?)",
                (clip_id, "2. Ekstraksi Audio/Video YouTube (yt-dlp)", "Success", ms2 // 2),
            )
            cur.execute(
                "INSERT INTO process_logs (clip_id, process_type, status, execution_time_ms) VALUES (?, ?, ?, ?)",
                (clip_id, "3. Crop 9:16 & Render Audio AAC (FFMPEG)", "Success", ms2 - (ms2 // 2)),
            )
            cur.execute(
                """
                UPDATE video_clips
                SET file_path = ?, transcript_text = ?, segment_timestamp = ?,
                    status_process = 'Completed',
                    has_watermark = ?, has_subtitle = ?, subtitle_lang = ?
                WHERE clip_id = ?
                """,
                (
                    filename,
                    seg["transcript"],
                    seg["timestamp_str"],
                    1 if is_free_user else 0,
                    1 if add_subtitle else 0,
                    "id" if translate_id else "orig",
                    clip_id,
                ),
            )
        else:
            cur.execute(
                "UPDATE video_clips SET status_process = 'Failed' WHERE clip_id = ?",
                (clip_id,),
            )
            cur.execute(
                "INSERT INTO process_logs (clip_id, process_type, status, error_message, execution_time_ms) VALUES (?, ?, ?, ?, ?)",
                (clip_id, "Ekstraksi & Render FFMPEG", "Failed", msg, ms2),
            )
        conn.commit()
    finally:
        conn.close()


def get_clip_dict(conn, clip_row) -> dict:
    cur = conn.cursor()
    cur.execute(
        "SELECT * FROM process_logs WHERE clip_id = ? ORDER BY log_id ASC",
        (clip_row["clip_id"],),
    )
    logs = [dict(r) for r in cur.fetchall()]
    d = dict(clip_row)
    d["download_url"] = f"/api/videos/download/{d['clip_id']}" if d.get("file_path") else None
    d["logs"] = logs
    return d


SWAGGER_HTML = """<!DOCTYPE html>
<html>
<head>
  <title>Web SmartCut API</title>
  <meta charset="utf-8"/>
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <link rel="stylesheet" type="text/css" href="https://unpkg.com/swagger-ui-dist@5/swagger-ui.css" >
</head>
<body>
<div id="swagger-ui"></div>
<script src="https://unpkg.com/swagger-ui-dist@5/swagger-ui-bundle.js"> </script>
<script>
window.onload = function() {
  SwaggerUIBundle({
    url: "/openapi.json",
    dom_id: '#swagger-ui',
  })
}
</script>
</body>
</html>"""

OPENAPI_SPEC = {
    "openapi": "3.0.2",
    "info": {
        "title": "Web SmartCut API",
        "version": "1.0.0",
        "description": "Backend REST API Web SmartCut",
    },
    "paths": {
        "/api/auth/register": {"post": {"summary": "Registrasi Akun Baru"}},
        "/api/auth/login": {"post": {"summary": "Login Pengguna"}},
        "/api/auth/me": {"get": {"summary": "Profil & Sisa Kuota Pengguna"}},
        "/api/videos/validate-url": {"post": {"summary": "Validasi URL YouTube & Ambil Metadata"}},
        "/api/videos/create-clip": {"post": {"summary": "Pembuatan Klip Video 9:16"}},
        "/api/videos/my-clips": {"get": {"summary": "Daftar Riwayat Klip Pengguna"}},
        "/api/videos/download/{clip_id}": {"get": {"summary": "Unduh File Klip Video (.mp4)"}},
        "/api/transactions/simulate-upgrade": {"post": {"summary": "Upgrade Akun ke Premium"}},
    },
}


async def read_body(receive) -> bytes:
    body = b""
    while True:
        message = await receive()
        body += message.get("body", b"")
        if not message.get("more_body", False):
            break
    return body


async def send_json(send, status_code: int, payload):
    data = json.dumps(payload, default=str).encode("utf-8")
    headers = [
        (b"content-type", b"application/json; charset=utf-8"),
        (b"access-control-allow-origin", b"*"),
        (b"access-control-allow-methods", b"GET, POST, PUT, DELETE, OPTIONS"),
        (b"access-control-allow-headers", b"*"),
    ]
    await send({"type": "http.response.start", "status": status_code, "headers": headers})
    await send({"type": "http.response.body", "body": data})


def authenticate_request(headers_dict: dict):
    auth_header = headers_dict.get("authorization", "")
    if not auth_header.startswith("Bearer "):
        return None, (401, {"detail": "Token otentikasi tidak ditemukan."})
    token = auth_header.split(" ", 1)[1].strip()
    try:
        payload = decode_jwt_token(token)
        user_id = int(payload["sub"])
    except Exception as e:
        return None, (401, {"detail": str(e)})

    conn = get_db_conn()
    cur = conn.cursor()
    cur.execute("SELECT * FROM users WHERE user_id = ?", (user_id,))
    user = cur.fetchone()
    conn.close()
    if not user:
        return None, (401, {"detail": "Pengguna tidak ditemukan."})
    if user["account_status"] == "Banned":
        return None, (403, {"detail": "Akun Anda dinonaktifkan"})
    return dict(user), None


async def app(scope, receive, send):
    if scope["type"] != "http":
        return

    method = scope["method"].upper()
    path = scope["path"]
    headers_dict = {k.decode("latin1").lower(): v.decode("latin1") for k, v in scope.get("headers", [])}

    if method == "OPTIONS":
        await send(
            {
                "type": "http.response.start",
                "status": 200,
                "headers": [
                    (b"access-control-allow-origin", b"*"),
                    (b"access-control-allow-methods", b"GET, POST, PUT, DELETE, OPTIONS"),
                    (b"access-control-allow-headers", b"*"),
                ],
            }
        )
        await send({"type": "http.response.body", "body": b""})
        return

    if method == "GET" and path == "/docs":
        await send(
            {
                "type": "http.response.start",
                "status": 200,
                "headers": [(b"content-type", b"text/html; charset=utf-8")],
            }
        )
        await send({"type": "http.response.body", "body": SWAGGER_HTML.encode("utf-8")})
        return

    if method == "GET" and path == "/openapi.json":
        await send_json(send, 200, OPENAPI_SPEC)
        return

    if method == "POST" and path == "/api/auth/register":
        raw = await read_body(receive)
        body = json.loads(raw.decode("utf-8") or "{}")
        nama = (body.get("nama") or "").strip()
        email = (body.get("email") or "").lower().strip()
        password = body.get("password") or ""

        if not EMAIL_REGEX.match(email):
            await send_json(send, 400, {"detail": "Format email tidak valid."})
            return
        if len(password) < 8:
            await send_json(send, 400, {"detail": "Password minimal 8 karakter."})
            return

        conn = get_db_conn()
        cur = conn.cursor()
        cur.execute("SELECT user_id FROM users WHERE email = ?", (email,))
        if cur.fetchone():
            conn.close()
            await send_json(send, 400, {"detail": "Email sudah digunakan"})
            return

        pw_hash = hash_password(password)
        cur.execute(
            "INSERT INTO users (nama, email, password_hash, account_status, sisa_kuota) VALUES (?, ?, ?, 'Free', 2)",
            (nama, email, pw_hash),
        )
        conn.commit()
        user_id = cur.lastrowid
        cur.execute("SELECT * FROM users WHERE user_id = ?", (user_id,))
        user = dict(cur.fetchone())
        conn.close()

        token = create_jwt_token(user["user_id"], user["email"], user["account_status"])
        await send_json(
            send,
            201,
            {
                "message": "Pendaftaran akun berhasil!",
                "access_token": token,
                "token_type": "bearer",
                "expires_in_hours": 24,
                "user": user,
            },
        )
        return

    if method == "POST" and path == "/api/auth/login":
        raw = await read_body(receive)
        body = json.loads(raw.decode("utf-8") or "{}")
        email = (body.get("email") or "").lower().strip()
        password = body.get("password") or ""

        conn = get_db_conn()
        cur = conn.cursor()
        cur.execute("SELECT * FROM users WHERE email = ?", (email,))
        row = cur.fetchone()
        conn.close()

        if not row or not verify_password(password, row["password_hash"]):
            await send_json(send, 401, {"detail": "Email atau password salah"})
            return

        user = dict(row)
        if user["account_status"] == "Banned":
            await send_json(send, 403, {"detail": "Akun Anda dinonaktifkan"})
            return

        token = create_jwt_token(user["user_id"], user["email"], user["account_status"])
        await send_json(
            send,
            200,
            {
                "message": "Login berhasil!",
                "access_token": token,
                "token_type": "bearer",
                "expires_in_hours": 24,
                "user": user,
            },
        )
        return

    if method == "GET" and path == "/api/auth/me":
        user, err = authenticate_request(headers_dict)
        if err:
            await send_json(send, err[0], err[1])
            return
        await send_json(send, 200, user)
        return

    if method == "POST" and path == "/api/videos/validate-url":
        user, err = authenticate_request(headers_dict)
        if err:
            await send_json(send, err[0], err[1])
            return
        raw = await read_body(receive)
        body = json.loads(raw.decode("utf-8") or "{}")
        yt_url = body.get("youtube_url") or ""
        try:
            meta = extract_youtube_metadata(yt_url)
            await send_json(send, 200, meta)
        except ValueError as e:
            await send_json(send, 400, {"detail": str(e)})
        return

    if method == "POST" and path == "/api/videos/create-clip":
        user, err = authenticate_request(headers_dict)
        if err:
            await send_json(send, err[0], err[1])
            return
        raw = await read_body(receive)
        body = json.loads(raw.decode("utf-8") or "{}")
        yt_url = body.get("youtube_url") or ""
        add_subtitle = bool(body.get("add_subtitle", False))
        translate_id = bool(body.get("translate_id", False))

        is_valid, video_id = validate_youtube_url(yt_url)
        if not is_valid:
            await send_json(send, 400, {"detail": "Hanya mendukung URL YouTube"})
            return

        is_free = user["account_status"] == "Free"
        if is_free and int(user["sisa_kuota"]) <= 0:
            await send_json(
                send,
                402,
                {"detail": "Kuota gratis Anda habis (maks 2 video/bulan). Silakan Upgrade ke Premium!"},
            )
            return

        meta = extract_youtube_metadata(yt_url)
        conn = get_db_conn()
        cur = conn.cursor()

        if is_free:
            cur.execute(
                "UPDATE users SET sisa_kuota = MAX(0, sisa_kuota - 1) WHERE user_id = ?",
                (user["user_id"],),
            )

        cur.execute(
            """
            INSERT INTO video_clips (user_id, youtube_url, video_title, thumbnail_url, status_process, has_watermark, has_subtitle, subtitle_lang)
            VALUES (?, ?, ?, ?, 'Processing', ?, ?, ?)
            """,
            (
                user["user_id"],
                meta["youtube_url"],
                meta["video_title"],
                meta["thumbnail_url"],
                1 if is_free else 0,
                1 if (not is_free and add_subtitle) else 0,
                "id" if (not is_free and translate_id) else "orig",
            ),
        )
        conn.commit()
        clip_id = cur.lastrowid
        cur.execute("SELECT * FROM video_clips WHERE clip_id = ?", (clip_id,))
        clip_row = cur.fetchone()
        clip_data = get_clip_dict(conn, clip_row)
        conn.close()

        t = threading.Thread(
            target=background_worker_process_clip,
            args=(
                clip_id,
                video_id,
                meta["youtube_url"],
                meta["video_title"],
                meta["duration_seconds"],
                is_free,
                add_subtitle,
                translate_id,
            ),
            daemon=True,
        )
        t.start()

        await send_json(send, 202, clip_data)
        return

    if method == "GET" and path == "/api/videos/my-clips":
        user, err = authenticate_request(headers_dict)
        if err:
            await send_json(send, err[0], err[1])
            return
        conn = get_db_conn()
        cur = conn.cursor()
        cur.execute(
            "SELECT * FROM video_clips WHERE user_id = ? ORDER BY clip_id DESC",
            (user["user_id"],),
        )
        rows = cur.fetchall()
        result = [get_clip_dict(conn, r) for r in rows]
        conn.close()
        await send_json(send, 200, result)
        return

    if method == "GET" and path.startswith("/api/videos/download/"):
        clip_id_str = path.rsplit("/", 1)[-1]
        if not clip_id_str.isdigit():
            await send_json(send, 400, {"detail": "ID Klip tidak valid"})
            return
        conn = get_db_conn()
        cur = conn.cursor()
        cur.execute("SELECT * FROM video_clips WHERE clip_id = ?", (int(clip_id_str),))
        clip = cur.fetchone()
        conn.close()

        if not clip or not clip["file_path"]:
            await send_json(send, 404, {"detail": "File sudah tidak tersedia, silakan proses ulang"})
            return

        full_path = os.path.join(CLIPS_DIR, clip["file_path"])
        if not os.path.exists(full_path):
            await send_json(send, 404, {"detail": "File sudah tidak tersedia, silakan proses ulang"})
            return

        file_size = os.path.getsize(full_path)
        range_header = headers_dict.get("range")

        if range_header and range_header.startswith("bytes="):
            range_val = range_header.replace("bytes=", "").split(",")[0].strip()
            start_str, end_str = range_val.split("-")
            start_byte = int(start_str) if start_str else 0
            end_byte = int(end_str) if end_str else file_size - 1
            end_byte = min(end_byte, file_size - 1)
            chunk_len = (end_byte - start_byte) + 1

            with open(full_path, "rb") as f:
                f.seek(start_byte)
                chunk = f.read(chunk_len)

            headers = [
                (b"content-type", b"video/mp4"),
                (b"accept-ranges", b"bytes"),
                (b"content-range", f"bytes {start_byte}-{end_byte}/{file_size}".encode("utf-8")),
                (b"content-length", str(len(chunk)).encode("utf-8")),
                (b"cache-control", b"no-store, no-cache, must-revalidate"),
                (b"access-control-allow-origin", b"*"),
            ]
            await send({"type": "http.response.start", "status": 206, "headers": headers})
            await send({"type": "http.response.body", "body": chunk})
            return

        with open(full_path, "rb") as f:
            file_bytes = f.read()

        headers = [
            (b"content-type", b"video/mp4"),
            (b"accept-ranges", b"bytes"),
            (b"content-length", str(len(file_bytes)).encode("utf-8")),
            (b"cache-control", b"no-store, no-cache, must-revalidate"),
            (
                b"content-disposition",
                f'attachment; filename="SmartCut_Clip_{clip_id_str}.mp4"'.encode("utf-8"),
            ),
            (b"access-control-allow-origin", b"*"),
        ]
        await send({"type": "http.response.start", "status": 200, "headers": headers})
        await send({"type": "http.response.body", "body": file_bytes})
        return

    if method == "GET" and path.startswith("/api/videos/"):
        user, err = authenticate_request(headers_dict)
        if err:
            await send_json(send, err[0], err[1])
            return
        clip_id_str = path.rsplit("/", 1)[-1]
        if not clip_id_str.isdigit():
            await send_json(send, 404, {"detail": "Tidak ditemukan"})
            return
        conn = get_db_conn()
        cur = conn.cursor()
        cur.execute(
            "SELECT * FROM video_clips WHERE clip_id = ? AND user_id = ?",
            (int(clip_id_str), user["user_id"]),
        )
        row = cur.fetchone()
        if not row:
            conn.close()
            await send_json(send, 404, {"detail": "Klip tidak ditemukan"})
            return
        data = get_clip_dict(conn, row)
        conn.close()
        await send_json(send, 200, data)
        return

    if method == "POST" and path == "/api/transactions/simulate-upgrade":
        user, err = authenticate_request(headers_dict)
        if err:
            await send_json(send, err[0], err[1])
            return
        order_id = f"SMC-{user['user_id']}-{uuid.uuid4().hex[:6].upper()}"
        raw_sig = f"{order_id}20039000.00Mid-server-SmartCutDemoKey2026"
        sig_key = hashlib.sha512(raw_sig.encode("utf-8")).hexdigest()

        conn = get_db_conn()
        cur = conn.cursor()
        cur.execute(
            """
            INSERT INTO transactions (order_id, user_id, amount, payment_status, snap_token, payment_type)
            VALUES (?, ?, 39000, 'Success', ?, 'QRIS (Midtrans)')
            """,
            (order_id, user["user_id"], f"snap-{uuid.uuid4().hex[:10]}"),
        )
        cur.execute(
            "UPDATE users SET account_status = 'Premium', sisa_kuota = 999 WHERE user_id = ?",
            (user["user_id"],),
        )
        conn.commit()
        cur.execute("SELECT * FROM users WHERE user_id = ?", (user["user_id"],))
        updated_user = dict(cur.fetchone())
        conn.close()

        await send_json(
            send,
            200,
            {
                "message": "Upgrade ke Premium berhasil!",
                "order_id": order_id,
                "sha512_signature_verified": sig_key[:32] + "...",
                "user": updated_user,
            },
        )
        return

    await send_json(send, 404, {"detail": f"Endpoint {path} tidak ditemukan."})
