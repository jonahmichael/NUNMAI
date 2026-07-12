"""
tests/test_registry.py — exercises crypto, enrollment, verification, and
the API end-to-end. Uses a temp DB file per test session so it never
touches data/registry.db.
"""

import sys
import os
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import pytest
import tempfile

# Point db.py at a throwaway temp file BEFORE importing anything that uses it.
_tmp_dir = tempfile.mkdtemp()
os.environ["NUNMAI_VERIFY_TEST_DB"] = str(Path(_tmp_dir) / "test_registry.db")

import nunmai_verify.db as db
db.DB_PATH = Path(os.environ["NUNMAI_VERIFY_TEST_DB"])

from nunmai_verify import crypto, enrollment, verification, qr_tool
from fastapi.testclient import TestClient


@pytest.fixture(autouse=True, scope="module")
def _init_schema():
    db.init_db()


# ---------- crypto ----------

def test_sign_and_verify_roundtrip():
    priv, pub = crypto.generate_keypair()
    sig = crypto.sign_content(priv, "hello investors")
    assert crypto.verify_signature(pub, "hello investors", sig) is True


def test_verify_fails_on_tampered_content():
    priv, pub = crypto.generate_keypair()
    sig = crypto.sign_content(priv, "original content")
    assert crypto.verify_signature(pub, "tampered content", sig) is False


def test_verify_fails_with_wrong_key():
    priv1, _ = crypto.generate_keypair()
    _, pub2 = crypto.generate_keypair()
    sig = crypto.sign_content(priv1, "some content")
    assert crypto.verify_signature(pub2, "some content", sig) is False


def test_hash_content_is_deterministic():
    assert crypto.hash_content("same text") == crypto.hash_content("same text")
    assert crypto.hash_content("same text") == crypto.hash_content("  same text  ")  # strips whitespace


# ---------- enrollment ----------

def test_enroll_entity_creates_keypair_and_domain():
    result = enrollment.enroll_entity(
        entity_name="Test Exchange",
        entity_type="exchange",
        domains=["testexchange.example"],
    )
    assert result["entity_id"] > 0
    assert "BEGIN PUBLIC KEY" in result["public_key_pem"]

    lookup = verification.verify_domain("testexchange.example")
    assert lookup["verified"] is True
    assert lookup["entity_name"] == "Test Exchange"


def test_unregistered_domain_is_not_verified():
    lookup = verification.verify_domain("totally-unknown-domain.example")
    assert lookup["verified"] is False
    assert lookup["entity_name"] is None


def test_revoked_entity_fails_verification():
    result = enrollment.enroll_entity(
        entity_name="Soon Revoked Broker",
        entity_type="broker",
        domains=["revokeme.example"],
    )
    entity_id = result["entity_id"]

    assert verification.verify_domain("revokeme.example")["verified"] is True

    revoked = enrollment.revoke_entity(entity_id)
    assert revoked is True

    lookup = verification.verify_domain("revokeme.example")
    assert lookup["verified"] is False
    assert lookup["status"] == "revoked"
    assert lookup["entity_name"] == "Soon Revoked Broker"  # identity still surfaced


def test_add_handle_and_verify():
    result = enrollment.enroll_entity(entity_name="Handle Test Co", entity_type="broker")
    enrollment.add_handle(result["entity_id"], "twitter", "@HandleTestCo")

    lookup = verification.verify_handle("twitter", "HandleTestCo")  # @ and case normalized
    assert lookup["verified"] is True
    assert lookup["entity_name"] == "Handle Test Co"


# ---------- signing + token verification ----------

def test_sign_and_verify_signed_content_direct():
    result = enrollment.enroll_entity(entity_name="Signer Co", entity_type="broker")
    entity_id = result["entity_id"]

    signed = verification.create_signed_communication(
        entity_id, content="Your KYC is up to date.", channel="email", subject="KYC status"
    )

    check = verification.verify_signed_content(entity_id, "Your KYC is up to date.", signed["signature_b64"])
    assert check["verified"] is True


def test_verify_signed_content_fails_for_wrong_entity():
    a = enrollment.enroll_entity(entity_name="Entity A", entity_type="broker")
    b = enrollment.enroll_entity(entity_name="Entity B", entity_type="broker")

    signed = verification.create_signed_communication(a["entity_id"], content="A's message")
    # claim it came from B instead
    check = verification.verify_signed_content(b["entity_id"], "A's message", signed["signature_b64"])
    assert check["verified"] is False


def test_lookup_by_token_and_content_check():
    result = enrollment.enroll_entity(entity_name="Token Test Co", entity_type="exchange")
    signed = verification.create_signed_communication(
        result["entity_id"], content="Circular: trading halted for XYZ.", channel="sms"
    )
    token = signed["verification_token"]

    meta = verification.lookup_by_token(token)
    assert meta is not None
    assert meta["entity_name"] == "Token Test Co"
    assert meta["currently_valid"] is True

    content_check = verification.verify_token_against_content(token, "Circular: trading halted for XYZ.")
    assert content_check["verified"] is True

    tampered_check = verification.verify_token_against_content(token, "Circular: trading halted for ABC.")
    assert tampered_check["verified"] is False
    assert tampered_check["reason"] == "content_tampered"


def test_unknown_token_returns_none():
    assert verification.lookup_by_token("not-a-real-token") is None


# ---------- QR ----------

def test_qr_png_bytes_are_valid_png():
    png = qr_tool.generate_qr_png_bytes("some-token-123")
    assert png[:8] == b"\x89PNG\r\n\x1a\n"  # PNG magic bytes


# ---------- API end-to-end ----------

@pytest.fixture
def client():
    from nunmai_verify.api.main import app
    return TestClient(app)


def test_api_enroll_and_verify_domain(client):
    resp = client.post("/enroll", json={
        "entity_name": "API Test Broker",
        "entity_type": "broker",
        "domains": ["apitestbroker.example"],
    })
    assert resp.status_code == 200
    entity_id = resp.json()["entity_id"]

    resp2 = client.get("/verify/domain/apitestbroker.example")
    assert resp2.status_code == 200
    assert resp2.json()["verified"] is True
    assert resp2.json()["entity_name"] == "API Test Broker"

    resp3 = client.get("/verify/domain/nonexistent-domain.example")
    assert resp3.json()["verified"] is False


def test_api_sign_and_token_lookup(client):
    enroll_resp = client.post("/enroll", json={"entity_name": "API Signer", "entity_type": "regulator"})
    entity_id = enroll_resp.json()["entity_id"]

    sign_resp = client.post("/sign", json={
        "entity_id": entity_id,
        "content": "Official notice from API Signer.",
        "channel": "email",
    })
    assert sign_resp.status_code == 200
    token = sign_resp.json()["verification_token"]

    lookup_resp = client.get(f"/verify/token/{token}")
    assert lookup_resp.status_code == 200
    assert lookup_resp.json()["entity_name"] == "API Signer"

    check_resp = client.post(f"/verify/token/{token}/check", json={"content": "Official notice from API Signer."})
    assert check_resp.json()["verified"] is True


def test_api_revoke_flow(client):
    enroll_resp = client.post("/enroll", json={
        "entity_name": "API Revoke Test",
        "entity_type": "broker",
        "domains": ["apirevoketest.example"],
    })
    entity_id = enroll_resp.json()["entity_id"]

    revoke_resp = client.post(f"/entities/{entity_id}/revoke")
    assert revoke_resp.status_code == 200

    verify_resp = client.get("/verify/domain/apirevoketest.example")
    assert verify_resp.json()["verified"] is False


def test_api_qr_endpoint_returns_png(client):
    enroll_resp = client.post("/enroll", json={"entity_name": "QR Test Co", "entity_type": "broker"})
    entity_id = enroll_resp.json()["entity_id"]
    sign_resp = client.post("/sign", json={"entity_id": entity_id, "content": "QR test content"})
    token = sign_resp.json()["verification_token"]

    qr_resp = client.get(f"/qr/{token}")
    assert qr_resp.status_code == 200
    assert qr_resp.headers["content-type"] == "image/png"