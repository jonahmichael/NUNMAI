"""
header_features.py
===================
Extracts features from EMAIL HEADERS — the metadata around an email that
users never see but that carries strong signals of impersonation.

Why this matters for the "hyper-personalized LLM phishing" threat specifically:
Once the *body text* of a phishing email is polished enough to fool a human,
headers become one of the few remaining reliable signals — attackers can
perfect the words, but faking SPF/DKIM/DMARC authentication, a clean Received
chain, and a matching Message-ID domain is much harder.

This module works on RAW email source text (headers + body, like a .eml file,
or what Gmail's "Show original" gives you) using Python's built-in `email`
module — no external dependency needed for parsing.

NOTE ON SCOPE: Some features from the reference material need live network
lookups we deliberately skip here to keep this module offline/self-contained:
  - Originating-IP geolocation (needs a GeoIP database or API call)
  - Live domain-age / WHOIS checks
These are stubbed as TODO hooks for a future NUNMAI-VERIFY integration,
which will have proper network access and a maintained IP/geo dataset.

ATTACHMENT ANALYSIS: we enumerate MIME attachment filenames/extensions
only — we NEVER open, execute, or deep-scan attachment content. This stays
within the project's safe, fully-offline scope while still catching common
malware-delivery patterns (dangerous extensions, macro-enabled Office docs,
double-extension tricks like "invoice.pdf.exe").
"""

import re
from email import message_from_string
from email.utils import parseaddr, getaddresses

import tldextract


# Free/public email providers. Legitimate regulators and brokers NEVER send
# official communication from a free personal-email domain.
FREE_EMAIL_PROVIDERS = {
    "gmail.com", "yahoo.com", "outlook.com", "hotmail.com", "rediffmail.com",
    "protonmail.com", "aol.com", "icloud.com", "mail.com", "yandex.com",
}

# Keywords in a DISPLAY NAME that suggest impersonation of an official/
# regulatory body — e.g. Display name = "SEBI Compliance Team" but the
# actual address is some unrelated free-mail account.
OFFICIAL_ENTITY_KEYWORDS = {
    "sebi", "nse", "bse", "rbi", "compliance", "kyc", "regulator",
    "official", "support", "security", "broker", "exchange",
}

# X-Mailer / User-Agent strings that are red flags when they claim to be an
# automated alert from a bank/broker/regulator — these tools are common in
# phishing kits and bulk-mail scripts, not corporate mail infrastructure.
SUSPICIOUS_MAILER_SIGNATURES = {
    "phpmailer", "python-smtplib", "swiftmailer", "sendgrid-bulk",
    "outlook express", "mail::sender",
}

# --- Attachment-related constants (module-level, defined once) ---

# Extensions that are almost never legitimately emailed to investors —
# executable/script types commonly used for malware delivery.
DANGEROUS_ATTACHMENT_EXTENSIONS = {
    "exe", "scr", "js", "vbs", "bat", "cmd", "jar", "msi", "ps1", "com", "pif",
}

# Macro-enabled Office formats — a classic malware-delivery vector
# (malicious VBA macros), distinct from their safe non-macro counterparts.
MACRO_ENABLED_EXTENSIONS = {"docm", "xlsm", "pptm"}

# Common legitimate document extensions — used to detect "double extension"
# tricks like "invoice.pdf.exe" (looks like a PDF, is actually an EXE).
COMMON_DOCUMENT_EXTENSIONS = {"pdf", "doc", "docx", "xls", "xlsx", "jpg", "png", "txt"}

# Filename keywords commonly used to socially engineer a victim into
# opening a malicious attachment.
ATTACHMENT_SOCIAL_KEYWORDS = {
    "invoice", "urgent", "statement", "receipt", "kyc", "payment",
    "refund", "document", "important", "verify",
}


def _domain_of(email_address: str) -> str:
    """Extract just the registrable domain (e.g. 'gmail.com') from an address."""
    if not email_address or "@" not in email_address:
        return ""
    raw_domain = email_address.split("@")[-1].strip().lower()
    ext = tldextract.extract(raw_domain)
    return f"{ext.domain}.{ext.suffix}".lower()


def _parse_auth_results(auth_results_header: str) -> dict:
    """
    Parses an 'Authentication-Results' header (the modern combined header
    most mail servers now use instead of separate SPF/DKIM/DMARC headers)
    into pass/fail/none for each of the three protocols.

    Example real header:
      Authentication-Results: mx.google.com;
        spf=fail (google.com: domain of x@y.com does not designate...) smtp.mailfrom=x@y.com;
        dkim=fail header.i=@y.com;
        dmarc=fail (p=REJECT sp=REJECT dis=NONE) header.from=y.com
    """
    text = (auth_results_header or "").lower()

    def _extract_result(protocol: str) -> str:
        match = re.search(rf"{protocol}=(\w+)", text)
        return match.group(1) if match else "none"

    return {
        "spf": _extract_result("spf"),
        "dkim": _extract_result("dkim"),
        "dmarc": _extract_result("dmarc"),
    }


def _parse_received_spf(received_spf_header: str) -> str:
    """Fallback parser for the older standalone 'Received-SPF' header."""
    if not received_spf_header:
        return "none"
    text = received_spf_header.lower().strip()
    for result in ("pass", "fail", "softfail", "neutral", "none"):
        if text.startswith(result):
            return result
    return "none"


def _get_received_chain(msg) -> list[str]:
    """
    Returns all 'Received' headers in order (there's one per hop the email
    took). The email module returns them newest-first by default; we keep
    that order since the FIRST one (top) is the most recent hop and the
    LAST one is the original sending server — useful for chain-length and
    basic anomaly checks.
    """
    return msg.get_all("Received", [])


def _check_message_id_domain(message_id: str, sender_domain: str) -> bool:
    """
    Checks whether the Message-ID's domain matches the sender's domain.
    Legitimate mail servers generate Message-IDs like:
      <a1b2c3d4@mail.zerodha.com>
    A mismatch (or a garbage/localhost ID) is a phishing-script fingerprint.
    Returns True if there's a MISMATCH (i.e. this is a bad sign).
    """
    if not message_id:
        return True  # missing entirely — treat as suspicious
    match = re.search(r"@([\w.\-]+)>?$", message_id.strip())
    if not match:
        return True  # malformed ID — can't even parse a domain out of it
    msg_id_domain = match.group(1).lower()
    if "localhost" in msg_id_domain or msg_id_domain == "":
        return True
    # Allow partial match (e.g. mail.zerodha.com contains zerodha.com)
    return sender_domain not in msg_id_domain


def _extract_attachment_features(msg) -> dict:
    """
    Enumerates MIME attachment parts (filenames/extensions only — content
    is never opened, executed, or deep-scanned) and flags common
    malware-delivery patterns:
      - Dangerous executable/script extensions (.exe, .js, .vbs, etc.)
      - Macro-enabled Office documents (.docm, .xlsm, .pptm)
      - "Double extension" tricks (invoice.pdf.exe — looks like a PDF,
        is actually an executable)
      - Social-engineering filename keywords (invoice, urgent, kyc, etc.)
    """
    filenames = [part.get_filename() for part in msg.walk() if part.get_filename()]

    has_dangerous = False
    has_macro = False
    has_double_ext = False
    keyword_count = 0

    for fname in filenames:
        fname_lower = fname.lower()
        parts = fname_lower.split(".")

        if len(parts) >= 2:
            ext = parts[-1]
            if ext in DANGEROUS_ATTACHMENT_EXTENSIONS:
                has_dangerous = True
            if ext in MACRO_ENABLED_EXTENSIONS:
                has_macro = True

        if len(parts) >= 3:
            # e.g. "invoice.pdf.exe" -> second_ext="pdf", ext="exe"
            second_ext = parts[-2]
            if second_ext in COMMON_DOCUMENT_EXTENSIONS and parts[-1] in DANGEROUS_ATTACHMENT_EXTENSIONS:
                has_double_ext = True

        keyword_count += sum(1 for kw in ATTACHMENT_SOCIAL_KEYWORDS if kw in fname_lower)

    return {
        "num_attachments": len(filenames),
        "has_dangerous_attachment": has_dangerous,
        "has_macro_attachment": has_macro,
        "has_double_extension_attachment": has_double_ext,
        "attachment_social_keyword_count": keyword_count,
    }


def extract_header_features(raw_email_source: str, body_url_domains: list[str] | None = None) -> dict:
    """
    Main entry point. Takes the RAW email source (full headers + body as one
    string — e.g. from a .eml file or "Show Original" in Gmail) and returns
    a dictionary of header-based features.

    Optional `body_url_domains`: a list of domains extracted from links in
    the email body (from url_features.py). If provided, we cross-check
    whether the claimed sender's domain matches where the links actually
    point — one of the strongest phishing signals there is.
    """
    msg = message_from_string(raw_email_source)

    # --- 1. Parse core address headers ---
    from_name, from_addr = parseaddr(msg.get("From", ""))
    from_domain = _domain_of(from_addr)

    reply_to_name, reply_to_addr = parseaddr(msg.get("Reply-To", ""))
    reply_to_domain = _domain_of(reply_to_addr)

    _, return_path_addr = parseaddr(msg.get("Return-Path", ""))
    return_path_domain = _domain_of(return_path_addr)

    sender_name, sender_addr = parseaddr(msg.get("Sender", ""))
    sender_header_domain = _domain_of(sender_addr)

    # --- 2. Authentication results (SPF / DKIM / DMARC) ---
    auth_results = _parse_auth_results(msg.get("Authentication-Results", ""))
    # Fall back to the older standalone Received-SPF header if the modern
    # combined header isn't present.
    if auth_results["spf"] == "none":
        auth_results["spf"] = _parse_received_spf(msg.get("Received-SPF", ""))

    # --- 3. Received chain (routing) ---
    received_chain = _get_received_chain(msg)

    # --- 4. Message-ID check ---
    message_id_mismatch = _check_message_id_domain(msg.get("Message-ID", ""), from_domain)

    # --- 5. X-Mailer / suspicious sending software ---
    x_mailer = (msg.get("X-Mailer", "") or msg.get("User-Agent", "")).lower()
    suspicious_mailer = any(sig in x_mailer for sig in SUSPICIOUS_MAILER_SIGNATURES)

    # Presence of a script-originating header — common when mail is blasted
    # from a compromised web server/CMS rather than real mail infrastructure.
    has_script_originating_header = any(
        h.lower().startswith("x-php") or h.lower().startswith("x-originating-script")
        for h in msg.keys()
    )

    # --- 6. Display-name impersonation check ---
    display_name_claims_official = any(
        kw in from_name.lower() for kw in OFFICIAL_ENTITY_KEYWORDS
    )
    sender_uses_free_email = from_domain in FREE_EMAIL_PROVIDERS

    # An email is impersonating an official body if the DISPLAY NAME sounds
    # official/regulatory BUT the actual sending domain is a free provider.
    # This is the "SEBI Compliance Team <randomguy@gmail.com>" pattern.
    display_name_impersonation = display_name_claims_official and sender_uses_free_email

    # --- 7. Cross-check sender domain against body URL domains (if given) ---
    sender_url_mismatch = False
    if body_url_domains:
        # Flag if NONE of the links in the body point to the claimed sender's
        # own domain — e.g. "From: support@sebi.gov.in" but every link goes
        # to a completely unrelated domain.
        sender_url_mismatch = from_domain not in [d.lower() for d in body_url_domains]

    # --- 8. Assemble final feature dictionary ---
    features = {
        # Authentication (the "Big Three") — most reliable signals available
        "spf_result": auth_results["spf"],
        "dkim_result": auth_results["dkim"],
        "dmarc_result": auth_results["dmarc"],
        "auth_all_failed": all(
            auth_results[p] in ("fail", "softfail", "none")
            for p in ("spf", "dkim", "dmarc")
        ),

        # Identity/address mismatches
        "from_returnpath_mismatch": bool(return_path_addr) and from_domain != return_path_domain,
        "from_replyto_mismatch": bool(reply_to_addr) and from_domain != reply_to_domain,
        "reply_to_is_free_email": reply_to_domain in FREE_EMAIL_PROVIDERS,
        "sender_header_mismatch": bool(sender_addr) and from_domain != sender_header_domain,

        # Sender identity red flags
        "sender_uses_free_email": sender_uses_free_email,
        "display_name_impersonation": display_name_impersonation,

        # Cross-reference with body content (only meaningful if URLs were passed in)
        "sender_url_domain_mismatch": sender_url_mismatch,

        # Routing/chain features (geo-IP lookup deliberately deferred — see module docstring)
        "received_chain_length": len(received_chain),
        "received_chain_missing": len(received_chain) == 0,  # no hops at all = highly unusual

        # Structural/software fingerprints
        "message_id_domain_mismatch": message_id_mismatch,
        "suspicious_mailer": suspicious_mailer,
        "has_script_originating_header": has_script_originating_header,

        # TODO (NUNMAI-VERIFY integration, needs network access):
        #   - originating_ip_geo_mismatch: bool
        #   - domain_age_days: int
    }

    # --- 9. Attachment analysis ---
    features.update(_extract_attachment_features(msg))

    return features


# ------------------------------------------------------------------
# Quick manual test — run this file directly to sanity-check output:
#   python nunmai_mail/features/header_features.py
# ------------------------------------------------------------------
if __name__ == "__main__":
    # A crude but realistic fake phishing email source, with headers you'd
    # actually see in a "Show Original" view.
    sample_phishing_source = """From: "SEBI Compliance Team" <alerts.sebi.kyc@gmail.com>
To: investor@example.com
Reply-To: sebi-support-desk@gmail.com
Return-Path: <bounce@compromised-server.ru>
Sender: <bulk-mailer@compromised-server.ru>
Subject: URGENT: Your SEBI KYC Verification Has Expired
Message-ID: <123456789@localhost>
X-Mailer: PHPMailer 6.5
Authentication-Results: mx.google.com; spf=fail smtp.mailfrom=alerts.sebi.kyc@gmail.com; dkim=none; dmarc=fail
Date: Tue, 08 Jul 2026 10:00:00 +0000

Dear Investor, your SEBI KYC has expired...
"""

    sample_legit_source = """From: "Zerodha Support" <support@zerodha.com>
To: investor@example.com
Reply-To: support@zerodha.com
Return-Path: <bounce@zerodha.com>
Subject: Your Quarterly Statement is Ready
Message-ID: <a1b2c3d4e5@mail.zerodha.com>
X-Mailer: Zerodha Mailer 2.0
Authentication-Results: mx.google.com; spf=pass smtp.mailfrom=support@zerodha.com; dkim=pass header.i=@zerodha.com; dmarc=pass
Date: Tue, 08 Jul 2026 10:00:00 +0000

Your quarterly statement is now available in Console.
"""

    print("Phishing sample:")
    for k, v in extract_header_features(sample_phishing_source).items():
        print(f"  {k}: {v}")

    print("\nLegit sample:")
    for k, v in extract_header_features(sample_legit_source).items():
        print(f"  {k}: {v}")