"""
mail_integration_example.py — NOT part of the Verify service itself.

Shows how nunmai_mail/verify.py's stub could be swapped for a real call
to this service, once Verify is running (e.g. on port 8004). Copy this
into Nunmai-Mail's verify.py when you're ready to retire the hardcoded
VERIFIED_ENTITY_REGISTRY dict — the return shape is unchanged, so nothing
else in Mail needs to change.

    # nunmai_mail/verify.py (updated)
    import requests

    VERIFY_SERVICE_URL = "http://localhost:8004"

    def verify_sender_domain(domain: str) -> dict:
        try:
            resp = requests.get(f"{VERIFY_SERVICE_URL}/verify/domain/{domain}", timeout=2)
            resp.raise_for_status()
            data = resp.json()
            return {
                "verified": data["verified"],
                "entity_name": data.get("entity_name"),
                "domain_checked": data["domain_checked"],
            }
        except requests.RequestException:
            # Verify service unreachable -> fail closed, same as "not found"
            return {"verified": False, "entity_name": None, "domain_checked": domain}
"""