"""
crypto.py — real PKI primitives, not statistical scoring.

RSA-2048 keypairs, PSS padding, SHA-256 digest. This is what actually
makes Verify different in kind from Mail/Vision/Voice/Social: those
modules output a probability; this module outputs a boolean that
follows from math, not a trained model.

*** HONEST LIMITATION ***
Private keys are generated here and stored in the same SQLite file as
everything else (see db.py: entities.private_key_pem). That is a
hackathon-demo shortcut ONLY. A real deployment must never let the
verification service hold entities' private keys at all — signing should
happen on the entity's own side (or in an HSM/KMS the registry doesn't
have raw access to), and this service should only ever store and check
PUBLIC keys. The skeleton keeps private keys here purely so the demo can
show "SEBI signs a circular -> anyone can verify it" end-to-end without
standing up separate signer infrastructure for each seeded entity.
"""

from cryptography.hazmat.primitives.asymmetric import rsa, padding
from cryptography.hazmat.primitives import hashes, serialization
from cryptography.exceptions import InvalidSignature
import base64
import hashlib


def generate_keypair() -> tuple[str, str]:
    """Generate a new RSA-2048 keypair. Returns (private_pem, public_pem) as strings."""
    private_key = rsa.generate_private_key(public_exponent=65537, key_size=2048)
    public_key = private_key.public_key()

    private_pem = private_key.private_bytes(
        encoding=serialization.Encoding.PEM,
        format=serialization.PrivateFormat.PKCS8,
        encryption_algorithm=serialization.NoEncryption(),
    ).decode("utf-8")

    public_pem = public_key.public_bytes(
        encoding=serialization.Encoding.PEM,
        format=serialization.PublicFormat.SubjectPublicKeyInfo,
    ).decode("utf-8")

    return private_pem, public_pem


def hash_content(content: str) -> str:
    """SHA-256 hex digest of canonicalized content. Used both as the thing
    we sign and as the compact fingerprint shown in QR/lookup responses."""
    canonical = content.strip().encode("utf-8")
    return hashlib.sha256(canonical).hexdigest()


def sign_content(private_pem: str, content: str) -> str:
    """Sign content with an entity's private key. Returns base64 signature."""
    private_key = serialization.load_pem_private_key(private_pem.encode("utf-8"), password=None)
    digest = hash_content(content).encode("utf-8")
    signature = private_key.sign(
        digest,
        padding.PSS(mgf=padding.MGF1(hashes.SHA256()), salt_length=padding.PSS.MAX_LENGTH),
        hashes.SHA256(),
    )
    return base64.b64encode(signature).decode("utf-8")


def verify_signature(public_pem: str, content: str, signature_b64: str) -> bool:
    """Verify a signature against content and an entity's public key.
    Returns True/False — never raises for a bad signature (only for
    malformed inputs, which callers should treat as verification failure too)."""
    try:
        public_key = serialization.load_pem_public_key(public_pem.encode("utf-8"))
        digest = hash_content(content).encode("utf-8")
        signature = base64.b64decode(signature_b64)
        public_key.verify(
            signature,
            digest,
            padding.PSS(mgf=padding.MGF1(hashes.SHA256()), salt_length=padding.PSS.MAX_LENGTH),
            hashes.SHA256(),
        )
        return True
    except (InvalidSignature, ValueError, TypeError):
        return False