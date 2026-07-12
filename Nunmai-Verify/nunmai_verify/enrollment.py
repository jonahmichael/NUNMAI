"""
enrollment.py — registering entities (SEBI, exchanges, brokers) into the registry.

In a real deployment this would sit behind an admin-only, SEBI-backed
approval workflow. The skeleton exposes it as a plain function + a
POST /enroll endpoint with no auth, which is fine for a hackathon demo
and explicitly NOT fine beyond that.
"""

from nunmai_verify.db import get_conn
from nunmai_verify.crypto import generate_keypair


def enroll_entity(
    entity_name: str,
    entity_type: str,
    registration_number: str | None = None,
    domains: list[str] | None = None,
    phones: list[str] | None = None,
    handles: list[tuple[str, str]] | None = None,  # [(platform, handle), ...]
) -> dict:
    """Register a new entity: generates a fresh keypair and stores any
    domains/phones/handles supplied at enrollment time. Returns the new
    entity's id and PUBLIC key only (private key is never returned to
    the caller in the response, even though the skeleton does persist it
    server-side — see crypto.py's honest-limitation note)."""

    private_pem, public_pem = generate_keypair()

    with get_conn() as conn:
        cur = conn.execute(
            """INSERT INTO entities (entity_name, entity_type, registration_number,
                                      public_key_pem, private_key_pem)
               VALUES (?, ?, ?, ?, ?)""",
            (entity_name, entity_type, registration_number, public_pem, private_pem),
        )
        entity_id = cur.lastrowid

        for domain in (domains or []):
            conn.execute(
                "INSERT OR IGNORE INTO entity_domains (entity_id, domain) VALUES (?, ?)",
                (entity_id, domain.lower().strip()),
            )
        for phone in (phones or []):
            conn.execute(
                "INSERT OR IGNORE INTO entity_phones (entity_id, phone_number) VALUES (?, ?)",
                (entity_id, phone.strip()),
            )
        for platform, handle in (handles or []):
            conn.execute(
                """INSERT OR IGNORE INTO entity_handles (entity_id, platform, handle)
                   VALUES (?, ?, ?)""",
                (entity_id, platform.lower().strip(), handle.lower().lstrip("@").strip()),
            )

    return {"entity_id": entity_id, "entity_name": entity_name, "public_key_pem": public_pem}


def add_domain(entity_id: int, domain: str) -> None:
    with get_conn() as conn:
        conn.execute(
            "INSERT OR IGNORE INTO entity_domains (entity_id, domain) VALUES (?, ?)",
            (entity_id, domain.lower().strip()),
        )


def add_phone(entity_id: int, phone_number: str) -> None:
    with get_conn() as conn:
        conn.execute(
            "INSERT OR IGNORE INTO entity_phones (entity_id, phone_number) VALUES (?, ?)",
            (entity_id, phone_number.strip()),
        )


def add_handle(entity_id: int, platform: str, handle: str) -> None:
    with get_conn() as conn:
        conn.execute(
            "INSERT OR IGNORE INTO entity_handles (entity_id, platform, handle) VALUES (?, ?, ?)",
            (entity_id, platform.lower().strip(), handle.lower().lstrip("@").strip()),
        )


def revoke_entity(entity_id: int) -> bool:
    """Mark an entity revoked (e.g. a broker loses its license). Revoked
    entities fail verification even though their domains/keys stay on file —
    this lets /verify endpoints say "this WAS legitimate, is no longer"
    instead of just "unknown", a materially more useful signal for an investor."""
    with get_conn() as conn:
        cur = conn.execute(
            """UPDATE entities SET status = 'revoked', revoked_at = datetime('now')
               WHERE id = ? AND status = 'active'""",
            (entity_id,),
        )
        return cur.rowcount > 0