"""
main.py
=======
FastAPI serving layer for NUNMAI-VOICE. Accepts an uploaded audio file
and returns a synthetic-voice-detection verdict.

Run with:
    uvicorn nunmai_voice.api.main:app --reload --port 8002

(Port 8002 — Mail runs on 8000, Vision on 8001, keeping each module's
API independently runnable during development. These get unified behind
the Central Orchestration API later, per the architecture diagram.)

Then visit http://127.0.0.1:8002/docs for interactive API documentation.
"""

import sys
import tempfile
import os
from pathlib import Path

from fastapi import FastAPI, HTTPException, UploadFile, File
from pydantic import BaseModel

sys.path.append(str(Path(__file__).resolve().parents[2]))

from nunmai_voice.model.classifier import NunmaiVoiceClassifier

app = FastAPI(
    title="NUNMAI-VOICE API",
    description="AI-driven synthetic voice call detection for securities markets",
    version="0.1.0",
)

print("Starting NUNMAI-VOICE API — loading model...")
classifier = NunmaiVoiceClassifier()
print("Model loaded. API ready.")

ALLOWED_AUDIO_EXTENSIONS = {".wav", ".mp3", ".m4a", ".ogg", ".flac", ".webm"}
MAX_UPLOAD_SIZE_BYTES = 100 * 1024 * 1024  # 100MB — generous for a call recording


class PerSegmentResult(BaseModel):
    fake_probability: float
    label: str


class AudioScanResponse(BaseModel):
    fake_probability: float
    risk_tier: str
    prediction: str
    num_segments_analyzed: int
    per_segment_results: list[PerSegmentResult]


@app.get("/")
def root():
    return {"service": "NUNMAI-VOICE", "status": "running", "docs": "/docs"}


@app.post("/scan-audio", response_model=AudioScanResponse)
async def scan_audio(file: UploadFile = File(...)):
    """
    Main endpoint: upload an audio file, get back a synthetic-voice verdict.
    """
    file_extension = Path(file.filename).suffix.lower()
    if file_extension not in ALLOWED_AUDIO_EXTENSIONS:
        raise HTTPException(
            status_code=400,
            detail=f"Unsupported file type '{file_extension}'. "
                   f"Allowed: {', '.join(ALLOWED_AUDIO_EXTENSIONS)}",
        )

    contents = await file.read()
    if len(contents) > MAX_UPLOAD_SIZE_BYTES:
        raise HTTPException(
            status_code=413,
            detail=f"File too large. Max size: {MAX_UPLOAD_SIZE_BYTES // (1024*1024)}MB",
        )

    tmp_file = tempfile.NamedTemporaryFile(delete=False, suffix=file_extension)
    try:
        tmp_file.write(contents)
        tmp_file.close()

        result = classifier.classify_audio(tmp_file.name)

    except Exception as e:
        raise HTTPException(status_code=400, detail=f"Failed to process audio: {str(e)}")

    finally:
        if os.path.exists(tmp_file.name):
            os.unlink(tmp_file.name)

    if result["risk_tier"] == "NO_AUDIO_DETECTED":
        raise HTTPException(
            status_code=422,
            detail="No usable audio detected in the uploaded file.",
        )

    return result