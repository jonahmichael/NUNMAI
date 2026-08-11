@echo off
echo Starting NUNM.AI Backend Services...

cd /d "%~dp0"

start "NUNMAI MAIL" cmd /k "cd Nunmai-Mail && ..\.venv\Scripts\activate.bat && uvicorn nunmai_mail.api.main:app --port 8000"
start "NUNMAI VISION" cmd /k "cd Nunmai-Vision && ..\.venv\Scripts\activate.bat && uvicorn nunmai_vision.api.main:app --port 8001"
start "NUNMAI VOICE" cmd /k "cd Nunmai-Voice && ..\.venv\Scripts\activate.bat && uvicorn nunmai_voice.api.main:app --port 8002"
start "NUNMAI SOCIAL" cmd /k "cd Nunmai-Social && ..\.venv\Scripts\activate.bat && uvicorn nunmai_social.api.main:app --port 8003"
start "NUNMAI GATEWAY" cmd /k ".\.venv\Scripts\activate.bat && python main.py"

echo All services launched in separate windows!
echo API Gateway is running on port 8080.
