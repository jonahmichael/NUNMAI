"""
main.py
=======
FastAPI serving layer for NUNMAI-MAIL. Wraps the trained classifier in a
single HTTP endpoint so other systems (a frontend, the future Central
Orchestration API, or a simple demo UI) can POST an email and get back a
phishing verdict.

Run with:
    uvicorn nunmai_mail.api.main:app --reload

Then visit http://127.0.0.1:8000/docs for interactive API documentation
(FastAPI auto-generates this — useful for demoing without building a
separate frontend).
"""

import sys
from pathlib import Path

from fastapi import FastAPI, HTTPException
from pydantic import BaseModel, Field

sys.path.append(str(Path(__file__).resolve().parents[2]))

from nunmai_mail.model.classifier import NunmaiMailClassifier

app = FastAPI(
    title="NUNMAI-MAIL API",
    description="AI-driven phishing email detection for securities markets",
    version="0.1.0",
)

# Load the trained model ONCE at API startup, not per-request — loading
# from disk on every call would be slow and pointless since the model
# doesn't change between requests.
classifier = NunmaiMailClassifier()


class EmailScanRequest(BaseModel):
    """
    What the API expects in a POST request body.

    body_text: the plain email body (used for URL + text feature extraction)
    raw_email_source: the FULL raw email — headers + blank line + body,
        exactly like a .eml file or Gmail's "Show Original" view (used
        for header feature extraction). If you only have the body and no
        headers, you can still pass a minimal header block (see the
        classifier.py test cases for the minimal shape needed).
    """
    body_text: str = Field(..., description="Plain email body text")
    raw_email_source: str = Field(..., description="Full raw email: headers + blank line + body")


class RiskSignal(BaseModel):
    feature: str
    value: float


class SenderVerification(BaseModel):
    verified: bool
    entity_name: str | None
    domain_checked: str


class EmailScanResponse(BaseModel):
    phishing_probability: float
    risk_tier: str
    prediction: str
    top_risk_signals: list[RiskSignal]
    top_trust_signals: list[RiskSignal]
    sender_verification: SenderVerification
    text_matches: dict[str, list[str]]


@app.get("/")
def root():
    """Basic health-check / landing endpoint."""
    return {
        "service": "NUNMAI-MAIL",
        "status": "running",
        "docs": "/docs",
    }


@app.post("/scan-email", response_model=EmailScanResponse)
def scan_email(request: EmailScanRequest):
    """
    Main endpoint: submit an email, get back a phishing verdict.

    Example request body:
    {
      "body_text": "Dear Investor, your SEBI KYC has expired...",
      "raw_email_source": "From: ...\\nSubject: ...\\n\\nDear Investor..."
    }
    """
    try:
        result = classifier.classify_email(
            body_text=request.body_text,
            raw_email_source=request.raw_email_source,
        )
    except Exception as e:
        # Catch-all: malformed email source, unexpected parsing failure,
        # etc. Returns a clean 400 rather than a raw stack trace to the
        # client.
        raise HTTPException(status_code=400, detail=f"Failed to process email: {str(e)}")

    return {
        "phishing_probability": result["phishing_probability"],
        "risk_tier": result["risk_tier"],
        "prediction": result["prediction"],
        "top_risk_signals": [
            {"feature": name, "value": value} for name, value in result["top_risk_signals"]
        ],
        "top_trust_signals": [
            {"feature": name, "value": value} for name, value in result["top_trust_signals"]
        ],
        "sender_verification": result["sender_verification"],
        "text_matches": result.get("text_matches", {}),
    }