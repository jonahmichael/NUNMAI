"""
verification.py — the real implementation of what Mail's verify.py
currently fakes with a hardcoded VERIFIED_ENTITY_REGISTRY dict.

Returns the same {"verified": bool, "entity_name": str|None,
"domain_checked": str} shape Mail already expects, plus extra fields, so
Mail (and Social) can eventually call this service instead of their local
stub without changing their calling code.
"""

import secrets
from nunmai_verify.db import get_conn
from nunmai_verify.crypto import sign_content, verify_signature, hash_content


def verify_domain(domain: str) -> dict:
    domain = domain.lower().strip()
    with get_conn() as conn:
        row = conn.execute(
            """SELECT e.* FROM entities e
               JOIN entity_domains d ON d.entity_id = e.id
               WHERE d.domain = ?""",
            (domain,),
        ).fetchone()

    if row is None:
        return {"verified": False, "entity_name": None, "domain_checked": domain}

    return {
        "verified": row["status"] == "active",
        "entity_name": row["entity_name"],
        "domain_checked": domain,
        "status": row["status"],
        "entity_id": row["id"],
    }


def verify_handle(platform: str, handle: str) -> dict:
    platform = platform.lower().strip()
    handle = handle.lower().lstrip("@").strip()
    with get_conn() as conn:
        row = conn.execute(
            """SELECT e.* FROM entities e
               JOIN entity_handles h ON h.entity_id = e.id
               WHERE h.platform = ? AND h.handle = ?""",
            (platform, handle),
        ).fetchone()

    if row is None:
        return {"verified": False, "entity_name": None, "handle_checked": handle, "platform": platform}

    return {
        "verified": row["status"] == "active",
        "entity_name": row["entity_name"],
        "handle_checked": handle,
        "platform": platform,
        "status": row["status"],
        "entity_id": row["id"],
    }


def verify_phone(phone_number: str) -> dict:
    phone_number = phone_number.strip()
    with get_conn() as conn:
        row = conn.execute(
            """SELECT e.* FROM entities e
               JOIN entity_phones p ON p.entity_id = e.id
               WHERE p.phone_number = ?""",
            (phone_number,),
        ).fetchone()

    if row is None:
        return {"verified": False, "entity_name": None, "phone_checked": phone_number}

    return {
        "verified": row["status"] == "active",
        "entity_name": row["entity_name"],
        "phone_checked": phone_number,
        "status": row["status"],
        "entity_id": row["id"],
    }


def create_signed_communication(
    entity_id: int, content: str, channel: str | None = None, subject: str | None = None
) -> dict:
    """An entity (e.g. SEBI) signs a piece of outgoing content — a circular,
    an email body, an SMS. Returns a verification_token that can be embedded
    as a QR code or a short link in the communication itself, so a recipient
    can independently confirm it really came from who it claims to."""
    with get_conn() as conn:
        entity = conn.execute(
            "SELECT * FROM entities WHERE id = ? AND status = 'active'", (entity_id,)
        ).fetchone()
        if entity is None:
            raise ValueError(f"No active entity with id {entity_id}")

        signature_b64 = sign_content(entity["private_key_pem"], content)
        content_hash = hash_content(content)
        token = secrets.token_urlsafe(12)

        conn.execute(
            """INSERT INTO signed_communications
               (entity_id, content_hash, signature_b64, verification_token, channel, subject)
               VALUES (?, ?, ?, ?, ?, ?)""",
            (entity_id, content_hash, signature_b64, token, channel, subject),
        )

    return {
        "verification_token": token,
        "content_hash": content_hash,
        "signature_b64": signature_b64,
        "entity_id": entity_id,
        "entity_name": entity["entity_name"],
    }


def verify_signed_content(entity_id: int, content: str, signature_b64: str) -> dict:
    """Direct signature check: given raw content + a signature someone
    claims came from entity_id, is that true? Used when a recipient has
    the signature but not a verification_token (e.g. it was attached to
    a forwarded email rather than looked up via QR)."""
    with get_conn() as conn:
        entity = conn.execute("SELECT * FROM entities WHERE id = ?", (entity_id,)).fetchone()

    if entity is None:
        return {"verified": False, "reason": "unknown_entity"}

    if entity["status"] != "active":
        return {"verified": False, "reason": "entity_revoked", "entity_name": entity["entity_name"]}

    valid = verify_signature(entity["public_key_pem"], content, signature_b64)
    return {
        "verified": valid,
        "reason": None if valid else "signature_mismatch",
        "entity_name": entity["entity_name"],
        "entity_id": entity["id"],
    }


def lookup_by_token(token: str) -> dict | None:
    """The QR-code / short-link lookup path: recipient scans a code, hits
    GET /verify/token/{token}, gets back entity identity + the recorded
    content hash. NOTE: this only proves "an entity signed *something*
    under this token, and here's whether that entity is still active" —
    it can't independently confirm the message the recipient is holding
    matches, since the registry deliberately never stores raw content
    (only its hash), for the same reason password stores never keep
    plaintext. Use verify_token_against_content() below to check a
    specific piece of content against a token."""
    with get_conn() as conn:
        row = conn.execute(
            """SELECT sc.*, e.entity_name, e.entity_type, e.status, e.public_key_pem
               FROM signed_communications sc
               JOIN entities e ON e.id = sc.entity_id
               WHERE sc.verification_token = ?""",
            (token,),
        ).fetchone()

    if row is None:
        return None

    return {
        "verification_token": token,
        "entity_name": row["entity_name"],
        "entity_type": row["entity_type"],
        "entity_status": row["status"],
        "content_hash": row["content_hash"],
        "channel": row["channel"],
        "subject": row["subject"],
        "signed_at": row["created_at"],
        "currently_valid": row["status"] == "active",
    }


def verify_token_against_content(token: str, content: str) -> dict:
    """Given a token (from a scanned QR/link) AND the actual content the
    recipient received, do three checks at once: (1) does the token exist,
    (2) does content's hash match what was signed, (3) does the stored
    signature verify against the entity's public key. This is the
    strongest verification path — it catches both impersonation (token
    doesn't exist / wrong entity) and tampering (content was altered after
    signing, so the hash won't match even if the token is real)."""
    with get_conn() as conn:
        row = conn.execute(
            """SELECT sc.*, e.entity_name, e.status, e.public_key_pem
               FROM signed_communications sc
               JOIN entities e ON e.id = sc.entity_id
               WHERE sc.verification_token = ?""",
            (token,),
        ).fetchone()

    if row is None:
        return {"verified": False, "reason": "unknown_token"}

    if row["status"] != "active":
        return {"verified": False, "reason": "entity_revoked", "entity_name": row["entity_name"]}

    if hash_content(content) != row["content_hash"]:
        return {"verified": False, "reason": "content_tampered", "entity_name": row["entity_name"]}

    signature_ok = verify_signature(row["public_key_pem"], content, row["signature_b64"])
    return {
        "verified": signature_ok,
        "reason": None if signature_ok else "signature_mismatch",
        "entity_name": row["entity_name"],
    }