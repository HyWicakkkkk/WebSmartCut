@echo off
start cmd /k "cd /d "%~dp0backend" && .\.venv\Scripts\uvicorn main:app --reload --port 8000"
start cmd /k "cd /d "%~dp0frontend" && npm run dev"
