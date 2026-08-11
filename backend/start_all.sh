#!/bin/bash
echo "Starting NUNM.AI Backend Services in background..."

# Move to backend directory
cd "$(dirname "$0")"

# Activate virtual environment if it exists
if [ -d "./.venv" ]; then
    source ./.venv/bin/activate
fi

# Start each service from its respective directory so Python finds the local modules
(cd Nunmai-Mail && nohup uvicorn nunmai_mail.api.main:app --port 8000 > ../mail.log 2>&1 &)
(cd Nunmai-Vision && nohup uvicorn nunmai_vision.api.main:app --port 8001 > ../vision.log 2>&1 &)
(cd Nunmai-Voice && nohup uvicorn nunmai_voice.api.main:app --port 8002 > ../voice.log 2>&1 &)
(cd Nunmai-Social && nohup uvicorn nunmai_social.api.main:app --port 8003 > ../social.log 2>&1 &)
nohup python main.py > gateway.log 2>&1 &

echo "All services launched! API Gateway is running on port 8080."
echo "Check the .log files for output."
