"""
main.py
=======
FastAPI serving layer for NUNMAI-SOCIAL. Accepts post text plus optional
image and account metadata, returns a fused manipulation-risk verdict.

Run with:
    uvicorn nunmai_social.api.main:app --reload --port 8003

(Mail=8000, Vision=8001, Voice=8002, Social=8003 — each module runs
independently during development, later unified behind the Central
Orchestration API per the architecture diagram.)
"""

import sys
import tempfile
import os
from pathlib import Path
from typing import Optional

from fastapi import FastAPI, HTTPException, UploadFile, File, Form
from pydantic import BaseModel

sys.path.append(str(Path(__file__).resolve().parents[2]))

from nunmai_social.model.fusion import NunmaiSocialAnalyzer

app = FastAPI(
    title="NUNMAI-SOCIAL API",
    description="AI-driven detection of manipulative social media content targeting retail investors",
    version="0.1.0",
)

print("Starting NUNMAI-SOCIAL API — loading model...")
analyzer = NunmaiSocialAnalyzer()
print("Model loaded. API ready.")

ALLOWED_IMAGE_EXTENSIONS = {".jpg", ".jpeg", ".png", ".webp"}
MAX_UPLOAD_SIZE_BYTES = 20 * 1024 * 1024  # 20MB — generous for a social post image


class PostScanResponse(BaseModel):
    fused_risk_score: float
    risk_tier: str
    text_risk_score: float
    image_risk_score: Optional[float]
    image_applicable: Optional[bool]
    behavioral_risk_score: float


@app.get("/")
def root():
    return {"service": "NUNMAI-SOCIAL", "status": "running", "docs": "/docs"}


@app.post("/scan-post", response_model=PostScanResponse)
async def scan_post(
    post_text: str = Form(...),
    handle: Optional[str] = Form(None),
    bio_text: Optional[str] = Form(None),
    account_created_date: Optional[str] = Form(None),
    posts_per_day: Optional[float] = Form(None),
    followers: Optional[int] = Form(None),
    following: Optional[int] = Form(None),
    image: Optional[UploadFile] = File(None),
):
    """
    Main endpoint: submit post text + optional account metadata + optional
    image, get back a fused manipulation-risk verdict.

    Uses Form fields (not JSON body) because this endpoint optionally
    accepts a file upload alongside text fields — FastAPI requires
    multipart/form-data for that combination, same as Vision/Voice's
    file-upload endpoints but with extra text fields alongside.
    """
    tmp_image_path = None
    try:
        if image is not None:
            file_extension = Path(image.filename).suffix.lower()
            if file_extension not in ALLOWED_IMAGE_EXTENSIONS:
                raise HTTPException(
                    status_code=400,
                    detail=f"Unsupported image type '{file_extension}'. "
                           f"Allowed: {', '.join(ALLOWED_IMAGE_EXTENSIONS)}",
                )
            contents = await image.read()
            if len(contents) > MAX_UPLOAD_SIZE_BYTES:
                raise HTTPException(status_code=413, detail="Image too large.")

            tmp_file = tempfile.NamedTemporaryFile(delete=False, suffix=file_extension)
            tmp_file.write(contents)
            tmp_file.close()
            tmp_image_path = tmp_file.name

        result = analyzer.analyze_post(
            post_text=post_text,
            image_path=tmp_image_path,
            handle=handle,
            bio_text=bio_text,
            account_created_date=account_created_date,
            posts_per_day=posts_per_day,
            followers=followers,
            following=following,
        )

    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"Failed to process post: {str(e)}")

    finally:
        if tmp_image_path and os.path.exists(tmp_image_path):
            os.unlink(tmp_image_path)

    return result