"""
api/main.py — FastAPI app for NUNMAI-VERIFY.

Endpoint groups:
  - enrollment (POST /enroll, /entities/{id}/domains|phones|handles, /entities/{id}/revoke)
  - lookup     (GET  /verify/domain|handle|phone/...)
  - signing    (POST /sign)
  - token/QR   (GET  /verify/token/{token}, POST /verify/token/{token}/check, GET /qr/{token})

No auth on /enroll or /sign in this skeleton — both are exactly the kind
of thing a real deployment must lock down hard (enrollment behind SEBI-
backed approval, signing restricted to the entity's own authenticated
system). Left open here so the demo can be driven end-to-end from Swagger.
"""

from fastapi import FastAPI, HTTPException
from fastapi.responses import StreamingResponse
from pydantic import BaseModel
import io

from nunmai_verify.db import init_db
from nunmai_verify import enrollment, verification, qr_tool

app = FastAPI(title="NUNMAI-VERIFY", version="0.1.0")
@app.get("/")
def root():
    return {
        "service": "NUNMAI-VERIFY",
        "status": "running",
        "version": "0.1.0",
        "docs": "/docs",
        "endpoints": {
            "enroll": "POST /enroll",
            "verify_domain": "GET /verify/domain/{domain}",
            "verify_handle": "GET /verify/handle/{platform}/{handle}",
            "verify_phone": "GET /verify/phone/{phone}",
            "sign": "POST /sign",
            "verify_token": "GET /verify/token/{token}",
            "verify_token_content": "POST /verify/token/{token}/check",
            "qr_code": "GET /qr/{token}",
        },
    }

@app.on_event("startup")
def _startup():
    init_db()


# ---------- schemas ----------

class EnrollRequest(BaseModel):
    entity_name: str
    entity_type: str  # regulator | exchange | broker | other
    registration_number: str | None = None
    domains: list[str] = []
    phones: list[str] = []
    handles: list[list[str]] = []  # [["twitter", "SEBI_India"], ...]


class AddDomainRequest(BaseModel):
    domain: str


class AddPhoneRequest(BaseModel):
    phone_number: str


class AddHandleRequest(BaseModel):
    platform: str
    handle: str


class SignRequest(BaseModel):
    entity_id: int
    content: str
    channel: str | None = None
    subject: str | None = None


class VerifySignatureRequest(BaseModel):
    entity_id: int
    content: str
    signature_b64: str


class VerifyTokenContentRequest(BaseModel):
    content: str


# ---------- enrollment ----------

@app.post("/enroll")
def enroll(req: EnrollRequest):
    handles = [(h[0], h[1]) for h in req.handles]
    result = enrollment.enroll_entity(
        entity_name=req.entity_name,
        entity_type=req.entity_type,
        registration_number=req.registration_number,
        domains=req.domains,
        phones=req.phones,
        handles=handles,
    )
    return result


@app.post("/entities/{entity_id}/domains")
def add_domain(entity_id: int, req: AddDomainRequest):
    enrollment.add_domain(entity_id, req.domain)
    return {"entity_id": entity_id, "domain_added": req.domain}


@app.post("/entities/{entity_id}/phones")
def add_phone(entity_id: int, req: AddPhoneRequest):
    enrollment.add_phone(entity_id, req.phone_number)
    return {"entity_id": entity_id, "phone_added": req.phone_number}


@app.post("/entities/{entity_id}/handles")
def add_handle(entity_id: int, req: AddHandleRequest):
    enrollment.add_handle(entity_id, req.platform, req.handle)
    return {"entity_id": entity_id, "handle_added": f"{req.platform}:{req.handle}"}


@app.post("/entities/{entity_id}/revoke")
def revoke(entity_id: int):
    ok = enrollment.revoke_entity(entity_id)
    if not ok:
        raise HTTPException(status_code=404, detail="entity not found or already revoked")
    return {"entity_id": entity_id, "status": "revoked"}


# ---------- lookup ----------

@app.get("/verify/domain/{domain}")
def verify_domain(domain: str):
    return verification.verify_domain(domain)


@app.get("/verify/handle/{platform}/{handle}")
def verify_handle(platform: str, handle: str):
    return verification.verify_handle(platform, handle)


@app.get("/verify/phone/{phone}")
def verify_phone(phone: str):
    return verification.verify_phone(phone)


# ---------- signing ----------

@app.post("/sign")
def sign(req: SignRequest):
    try:
        result = verification.create_signed_communication(
            entity_id=req.entity_id, content=req.content, channel=req.channel, subject=req.subject
        )
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))
    result["qr_url"] = qr_tool.build_verification_url(result["verification_token"])
    return result


@app.post("/verify-signature")
def verify_signature_endpoint(req: VerifySignatureRequest):
    return verification.verify_signed_content(req.entity_id, req.content, req.signature_b64)


# ---------- token / QR lookup ----------

@app.get("/verify/token/{token}")
def verify_token(token: str):
    result = verification.lookup_by_token(token)
    if result is None:
        raise HTTPException(status_code=404, detail="unknown verification token")
    return result


@app.post("/verify/token/{token}/check")
def verify_token_content(token: str, req: VerifyTokenContentRequest):
    return verification.verify_token_against_content(token, req.content)


@app.get("/qr/{token}")
def get_qr(token: str):
    png_bytes = qr_tool.generate_qr_png_bytes(token)
    return StreamingResponse(io.BytesIO(png_bytes), media_type="image/png")