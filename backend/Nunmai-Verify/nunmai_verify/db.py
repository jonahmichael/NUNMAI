"""
db.py — SQLite schema + connection helper for the entity registry.

SQLite is a deliberate hackathon-scope choice, same rationale as Mail's
verify.py stub: no live infra needed, easy to seed/demo. A real deployment
would need a proper RDBMS with row-level auditing and, critically, keys
kept OUT of this database entirely (see crypto.py docstring).
"""

import sqlite3
from pathlib import Path
from contextlib import contextmanager

DB_PATH = Path(__file__).resolve().parent.parent / "data" / "registry.db"

SCHEMA = """
CREATE TABLE IF NOT EXISTS entities (
    id                      INTEGER PRIMARY KEY AUTOINCREMENT,
    entity_name             TEXT NOT NULL,
    entity_type             TEXT NOT NULL CHECK (entity_type IN
                             ('regulator', 'exchange', 'broker', 'other')),
    registration_number     TEXT,
    public_key_pem          TEXT NOT NULL,
    private_key_pem         TEXT NOT NULL,
    status                  TEXT NOT NULL DEFAULT 'active'
                             CHECK (status IN ('active', 'revoked')),
    created_at              TEXT NOT NULL DEFAULT (datetime('now')),
    revoked_at              TEXT
);

CREATE TABLE IF NOT EXISTS entity_domains (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    entity_id   INTEGER NOT NULL REFERENCES entities(id),
    domain      TEXT NOT NULL UNIQUE,
    added_at    TEXT NOT NULL DEFAULT (datetime('now'))
);

CREATE TABLE IF NOT EXISTS entity_phones (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    entity_id       INTEGER NOT NULL REFERENCES entities(id),
    phone_number    TEXT NOT NULL UNIQUE,
    added_at        TEXT NOT NULL DEFAULT (datetime('now'))
);

CREATE TABLE IF NOT EXISTS entity_handles (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    entity_id   INTEGER NOT NULL REFERENCES entities(id),
    platform    TEXT NOT NULL,
    handle      TEXT NOT NULL,
    added_at    TEXT NOT NULL DEFAULT (datetime('now')),
    UNIQUE(platform, handle)
);

-- Every communication an entity signs gets logged here. This is what
-- powers /verify/token/{token} and the investor-facing QR lookup.
CREATE TABLE IF NOT EXISTS signed_communications (
    id                  INTEGER PRIMARY KEY AUTOINCREMENT,
    entity_id           INTEGER NOT NULL REFERENCES entities(id),
    content_hash        TEXT NOT NULL,
    signature_b64       TEXT NOT NULL,
    verification_token  TEXT NOT NULL UNIQUE,
    channel             TEXT,
    subject             TEXT,
    created_at          TEXT NOT NULL DEFAULT (datetime('now'))
);

CREATE INDEX IF NOT EXISTS idx_domains_domain ON entity_domains(domain);
CREATE INDEX IF NOT EXISTS idx_handles_lookup ON entity_handles(platform, handle);
CREATE INDEX IF NOT EXISTS idx_phones_number ON entity_phones(phone_number);
CREATE INDEX IF NOT EXISTS idx_token ON signed_communications(verification_token);
"""


def init_db():
    DB_PATH.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(DB_PATH)
    try:
        conn.executescript(SCHEMA)
        conn.commit()
    finally:
        conn.close()


@contextmanager
def get_conn():
    DB_PATH.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    try:
        yield conn
        conn.commit()
    finally:
        conn.close()