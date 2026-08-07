"""
NUNMAI-VERIFY
=============
Authentic-communication registry for the NUNMAI platform.

Unlike Mail/Vision/Voice/Social (statistical risk-scoring), Verify is a
cryptographic source-of-truth: entities enroll once, get an RSA keypair,
and every subsequent communication can be signed and later checked against
the registry. There is no "probability" here — a signature either matches
a registered entity's public key or it doesn't.

This is a hackathon-scope skeleton. See README.md "Honest limitations"
section before treating any part of this as production-ready.
"""

__version__ = "0.1.0"