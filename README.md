# Web SmartCut

Nama: Muhammad Rizky Wicaksono  
NIM: 11241062  

## Deskripsi Proyek
Web SmartCut adalah aplikasi web pemotong video YouTube otomatis menjadi klip pendek berformat vertikal 9:16 (MP4).

## Tech Stack
- Frontend: React (Vite), Tailwind CSS
- Backend: Python (Uvicorn ASGI, SQLAlchemy, SQLite)
- Autentikasi: Bcrypt & JWT
- Pemrosesan Video: yt-dlp & FFmpeg

## Cara Menjalankan

### Backend
```powershell
cd backend
python -m venv .venv
.\.venv\Scripts\pip install -r requirements.txt
.\.venv\Scripts\uvicorn main:app --reload --port 8000
```

### Frontend
```powershell
cd frontend
npm install
npm run dev
```
