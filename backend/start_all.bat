@echo off
echo Starting NUNM.AI Backend Services...

cd /d "%~dp0"

start "NUNMAI MAIL" cmd /c "..\.venv\Scripts\uvicorn.exe nunmai_mail.api.main:app --port 8000"
start "NUNMAI VISION" cmd /c "..\.venv\Scripts\uvicorn.exe nunmai_vision.api.main:app --port 8001"
start "NUNMAI VOICE" cmd /c "..\.venv\Scripts\uvicorn.exe nunmai_voice.api.main:app --port 8002"
start "NUNMAI SOCIAL" cmd /c "..\.venv\Scripts\uvicorn.exe nunmai_social.api.main:app --port 8003"
start "NUNMAI GATEWAY" cmd /c "..\.venv\Scripts\python.exe main.py"

echo All services launched in separate windows!
echo API Gateway is running on port 8080.
