"""
seed_known_entities.py — seeds known-public real entities.

Mirrors what Mail's verify.py currently hardcodes as
VERIFIED_ENTITY_REGISTRY, but as real registry rows with real generated
keypairs instead of a static dict. This is the "technical skeleton
seeded with known-public real entities" scope — NOT a claim that these
organizations have actually enrolled or endorsed this system.
Run once: `python -m nunmai_verify.seed_known_entities`.
"""

from nunmai_verify.db import init_db, get_conn
from nunmai_verify.enrollment import enroll_entity

KNOWN_ENTITIES = [
    {
        "entity_name": "Securities and Exchange Board of India (SEBI)",
        "entity_type": "regulator",
        "registration_number": None,
        "domains": ["sebi.gov.in"],
        "handles": [("twitter", "SEBI_India")],
        "executives": ["Madhabi Puri Buch", "Ananth Narayan G", "Ashwani Bhatia"],
    },
    {
        "entity_name": "National Stock Exchange of India (NSE)",
        "entity_type": "exchange",
        "registration_number": None,
        "domains": ["nseindia.com"],
        "handles": [("twitter", "NSEIndia")],
        "executives": ["Ashishkumar Chauhan"],
    },
    {
        "entity_name": "BSE Limited",
        "entity_type": "exchange",
        "registration_number": None,
        "domains": ["bseindia.com"],
        "handles": [("twitter", "BSEIndia")],
    },
    {
        "entity_name": "Zerodha Broking Ltd",
        "entity_type": "broker",
        "registration_number": "INZ000031633",
        "domains": ["zerodha.com"],
        "handles": [("twitter", "zerodhaonline")],
    },
    {
        "entity_name": "Groww (Billionbrains Garage Ventures)",
        "entity_type": "broker",
        "registration_number": "INZ000208032",
        "domains": ["groww.in"],
        "handles": [("twitter", "_groww")],
    },
    {
        "entity_name": "Upstox (RKSV Securities)",
        "entity_type": "broker",
        "registration_number": "INZ000185536",
        "domains": ["upstox.com"],
        "handles": [("twitter", "Upstox")],
    },
    {
        "entity_name": "ICICI Securities (ICICI Direct)",
        "entity_type": "broker",
        "registration_number": "INZ000183631",
        "domains": ["icicidirect.com"],
        "handles": [("twitter", "ICICIdirect")],
    },
    {
        "entity_name": "HDFC Securities",
        "entity_type": "broker",
        "registration_number": "INZ000186937",
        "domains": ["hdfcsec.com"],
        "handles": [("twitter", "HDFCSec")],
    },
]


def seed():
    init_db()
    created = []
    
    # Track SEBI's ID to use as the trust root for others
    sebi_id = None
    
    with get_conn() as conn:
        existing_domains = {r["domain"] for r in conn.execute("SELECT domain FROM entity_domains")}

    for entity in KNOWN_ENTITIES:
        if any(d in existing_domains for d in entity["domains"]):
            print(f"skip (already seeded): {entity['entity_name']}")
            # If SEBI was already seeded, we still need its ID for the others
            if entity["entity_name"] == "Securities and Exchange Board of India (SEBI)":
                with get_conn() as conn:
                    row = conn.execute("SELECT id FROM entities WHERE entity_name = ?", (entity["entity_name"],)).fetchone()
                    if row:
                        sebi_id = row["id"]
            continue
            
        is_sebi = entity["entity_name"] == "Securities and Exchange Board of India (SEBI)"
        auth_id = None if is_sebi else sebi_id
        
        result = enroll_entity(
            entity_name=entity["entity_name"],
            entity_type=entity["entity_type"],
            registration_number=entity["registration_number"],
            domains=entity["domains"],
            handles=entity.get("handles"),
            executives=entity.get("executives"),
            authorized_by_id=auth_id,
        )
        
        if is_sebi:
            sebi_id = result["entity_id"]
            
        created.append(result)
        print(f"seeded: {entity['entity_name']} -> entity_id={result['entity_id']} (auth_by={auth_id})")

    print(f"\n{len(created)} entities newly seeded.")
    return created


if __name__ == "__main__":
    seed()