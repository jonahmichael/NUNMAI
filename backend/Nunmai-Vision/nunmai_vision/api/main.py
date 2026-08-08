"""
main.py
=======
FastAPI serving layer for NUNMAI-VISION. Accepts an uploaded video file
and returns a deepfake-detection verdict.

DIFFERENCE FROM NUNMAI-MAIL'S API: Mail's API took JSON text in the
request body (an email is just text). Vision needs to accept an actual
uploaded FILE (a video), which FastAPI handles via UploadFile — the
video gets saved to a temporary file on disk (our classifier pipeline
works on file paths, via OpenCV's VideoCapture), processed, then cleaned
up.

Run with:
    uvicorn nunmai_vision.api.main:app --reload --port 8001

(Using port 8001 rather than the default 8000, since NUNMAI-MAIL's API
may already be running on 8000 — each module's API can run independently
and later be unified behind the Central Orchestration API from the
architecture diagram.)

Then visit http://127.0.0.1:8001/docs for interactive API documentation.
"""

import sys
import tempfile
import os
import sqlite3
from pathlib import Path

from fastapi import FastAPI, HTTPException, UploadFile, File, Form
from pydantic import BaseModel

sys.path.append(str(Path(__file__).resolve().parents[2]))

from nunmai_vision.model.classifier import NunmaiVisionClassifier

app = FastAPI(
    title="NUNMAI-VISION API",
    description="AI-driven deepfake video detection for securities markets (CEOs, CIOs, market experts)",
    version="0.1.0",
)

# Load the pretrained model ONCE at API startup — this is a real ~372MB
# model load, so we do NOT want this happening per-request.
print("Starting NUNMAI-VISION API — loading model...")
classifier = NunmaiVisionClassifier()
print("Model loaded. API ready.")

# Video formats we accept — matches what OpenCV's VideoCapture can
# reliably read on most systems.
ALLOWED_VIDEO_EXTENSIONS = {".mp4", ".avi", ".mov", ".mkv", ".webm"}

# Simple safety cap: reject absurdly large uploads rather than letting
# someone hang the API processing a multi-GB file. 200MB is generous for
# a short clip; adjust if real use cases need longer videos.
MAX_UPLOAD_SIZE_BYTES = 200 * 1024 * 1024  # 200MB


class PerFaceResult(BaseModel):
    fake_probability: float
    label: str


class VideoScanResponse(BaseModel):
    fake_probability: float
    risk_tier: str
    prediction: str
    num_faces_analyzed: int
    num_frames_sampled: int
    per_face_results: list[PerFaceResult]
    executive_verification: dict | None = None


@app.get("/")
def root():
    """Basic health-check / landing endpoint."""
    return {
        "service": "NUNMAI-VISION",
        "status": "running",
        "docs": "/docs",
    }


@app.post("/scan-video", response_model=VideoScanResponse)
async def scan_video(
    file: UploadFile = File(...),
    claimed_speaker_name: str | None = Form(None)
):
    """
    Main endpoint: upload a video file, get back a deepfake verdict.

    Accepts multipart/form-data with a single file field. In Swagger UI
    (/docs), this renders as a file-picker widget.
    """
    # --- Validate file extension ---
    file_extension = Path(file.filename).suffix.lower()
    if file_extension not in ALLOWED_VIDEO_EXTENSIONS:
        raise HTTPException(
            status_code=400,
            detail=f"Unsupported file type '{file_extension}'. "
                   f"Allowed: {', '.join(ALLOWED_VIDEO_EXTENSIONS)}",
        )

    # --- Read upload into memory, enforce size cap ---
    contents = await file.read()
    if len(contents) > MAX_UPLOAD_SIZE_BYTES:
        raise HTTPException(
            status_code=413,
            detail=f"File too large. Max size: {MAX_UPLOAD_SIZE_BYTES // (1024*1024)}MB",
        )

    # --- Save to a temporary file on disk ---
    # Our classifier pipeline (via OpenCV's VideoCapture) works on file
    # PATHS, not in-memory bytes, so we write the upload to a temp file,
    # process it, then clean up regardless of success or failure.
    tmp_file = tempfile.NamedTemporaryFile(delete=False, suffix=file_extension)
    try:
        tmp_file.write(contents)
        tmp_file.close()

        result = classifier.classify_video(tmp_file.name)

    except Exception as e:
        raise HTTPException(status_code=400, detail=f"Failed to process video: {str(e)}")

    finally:
        # Always clean up the temp file, even if processing failed —
        # otherwise every failed upload leaves orphaned files on disk.
        if os.path.exists(tmp_file.name):
            os.unlink(tmp_file.name)

    if result["risk_tier"] == "NO_FACE_DETECTED":
        raise HTTPException(
            status_code=422,
            detail="No face detected in the uploaded video — unable to assess for deepfake indicators.",
        )

    # Cross-check claimed speaker against Verify DB
    executive_verification = None
    if claimed_speaker_name:
        db_path = Path(__file__).resolve().parents[3] / "Nunmai-Verify" / "data" / "registry.db"
        if db_path.exists():
            conn = sqlite3.connect(db_path)
            conn.row_factory = sqlite3.Row
            row = conn.execute(
                "SELECT e.entity_name FROM entity_executives ex JOIN entities e ON ex.entity_id = e.id WHERE ex.executive_name = ?",
                (claimed_speaker_name.strip(),)
            ).fetchone()
            conn.close()
            
            if row:
                executive_verification = {
                    "authorized": True,
                    "status": f"PASSED (Authorized under {row['entity_name']})"
                }
            else:
                executive_verification = {
                    "authorized": False,
                    "status": "FAILED (Not an authorized executive)"
                }
    
    result["executive_verification"] = executive_verification

    return result