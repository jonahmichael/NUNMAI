"""
verify.py
=========
Lightweight LOCAL STUB for the NUNMAI-VERIFY authentic-communication
registry. The full system design (see architecture diagram) has
NUNMAI-VERIFY as a separate service: entity enrollment, cryptographic
signing, a live lookup API across domains/phones/emails/social
handles/voice/face. That doesn't exist yet — it's a whole separate
module, out of scope to build fully here.

This stub hardcodes a small list of known-legitimate SEBI/exchange/broker
domains, giving every other module a real "Sender/Source Verified?
Yes/No" decision (matching the architecture diagram) without needing the
full registry service built.

WHEN THE REAL NUNMAI-VERIFY SERVICE EXISTS: replace the internal dict
lookup in verify_sender_domain() with an HTTP call to its Verification
API. No calling code changes needed elsewhere — every caller just keeps
getting the same dict shape back.
"""

import tldextract

# Local stand-in for what would eventually be a live, cryptographically
# signed registry maintained by NUNMAI-VERIFY. Same entity list used for
# typosquat-detection in url_features.py — kept as a separate copy here
# so this module can run fully standalone (see url_features.py's own
# note on this same design tradeoff).
VERIFIED_ENTITY_REGISTRY = {
    "sebi.gov.in": "SEBI",
    "nseindia.com": "NSE",
    "bseindia.com": "BSE",
    "zerodha.com": "Zerodha",
    "groww.in": "Groww",
    "upstox.com": "Upstox",
    "angelone.in": "Angel One",
    "icicidirect.com": "ICICI Direct",
    "hdfcsec.com": "HDFC Securities",
    "kotaksecurities.com": "Kotak Securities",
    "cdslindia.com": "CDSL",
    "nsdl.co.in": "NSDL",
}


def verify_sender_domain(from_address: str) -> dict:
    """
    Checks a sender's email domain against the local verified-entity
    registry stub. This is the "Sender Verified?" decision branch from
    the architecture diagram, implemented as a local lookup rather than
    a live registry call.

    Args:
        from_address: the sender's email address (e.g. "support@zerodha.com")

    Returns:
        {
            "verified": bool,           # True if domain matches a known entity
            "entity_name": str | None,  # e.g. "Zerodha", or None if unverified
            "domain_checked": str,      # the registrable domain we looked up
        }
    """
    if not from_address or "@" not in from_address:
        return {"verified": False, "entity_name": None, "domain_checked": ""}

    raw_domain = from_address.split("@")[-1].strip().lower()
    ext = tldextract.extract(raw_domain)
    domain = f"{ext.domain}.{ext.suffix}".lower()

    entity_name = VERIFIED_ENTITY_REGISTRY.get(domain)
    return {
        "verified": entity_name is not None,
        "entity_name": entity_name,
        "domain_checked": domain,
    }


# ------------------------------------------------------------------
# Quick manual test — run this file directly to sanity-check output:
#   python nunmai_mail/verify.py
# ------------------------------------------------------------------
if __name__ == "__main__":
    test_cases = [
        "support@zerodha.com",           # genuine, should verify
        "compliance@sebi-verify.xyz",     # typosquat, should NOT verify
        "alerts.sebi.kyc@gmail.com",      # free email, should NOT verify
        "invalid-address",                # malformed, should NOT verify
    ]
    for addr in test_cases:
        result = verify_sender_domain(addr)
        print(f"{addr:35s} -> {result}")