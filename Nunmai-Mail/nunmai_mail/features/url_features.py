"""
url_features.py
================
Extracts structural/statistical features from URLs found inside an email body.

Why this matters:
Phishing emails almost always contain a malicious link. Even when the *text*
around the link is now AI-generated and perfect (unlike old-school phishing),
the URL itself still tends to carry give-away structural signals — because
attackers still need to point somewhere fake, register cheap/suspicious
domains, and disguise the real destination.

This module doesn't need internet access — it works purely on the string
structure of the URL. (A future upgrade could add live WHOIS/domain-age
lookups and call out to NUNMAI-VERIFY's registry, but that requires network
calls, so we keep this module self-contained for now.)

Reference: this feature category mirrors the "URL data" features found to be
the single most-used data source in phishing detection literature (Catal et
al., 2022 — URL features used in 50% of surveyed studies).
"""

import re
from urllib.parse import urlparse
import tldextract


# Known URL-shortening services — attackers use these to hide the real
# destination domain behind a short, harmless-looking link.
SHORTENER_DOMAINS = {
    "bit.ly", "tinyurl.com", "goo.gl", "t.co", "ow.ly", "is.gd",
    "buff.ly", "rebrand.ly", "cutt.ly", "shorturl.at",
}

# Keywords that scammers commonly stuff into a fake domain/subdomain to
# impersonate legitimate financial entities (e.g. "sebi-verify-login.com").
FINANCIAL_IMPERSONATION_KEYWORDS = {
    "sebi", "nse", "bse", "demat", "kyc", "verify", "secure", "login",
    "account", "update", "broker", "trading", "invest", "refund", "reward",
}

# Legitimate Indian securities-market domains — used as the reference set
# for typosquatting detection. Extend this list with real registered domains
# via NUNMAI-VERIFY once that registry exists.
KNOWN_LEGIT_FINANCIAL_DOMAINS = {
    "sebi.gov.in", "nseindia.com", "bseindia.com", "zerodha.com",
    "groww.in", "upstox.com", "angelone.in", "icicidirect.com",
    "hdfcsec.com", "kotaksecurities.com", "cdslindia.com", "nsdl.co.in",
}


def _levenshtein_distance(a: str, b: str) -> int:
    """
    Classic edit-distance calculation (no external library needed).
    Used to catch typosquatted domains like 'sebi-india.com' vs 'sebi.gov.in'
    or 'zerodhaa.com' vs 'zerodha.com' — one or two characters off from a
    real, known financial domain.
    """
    if len(a) < len(b):
        return _levenshtein_distance(b, a)
    if len(b) == 0:
        return len(a)
    previous_row = range(len(b) + 1)
    for i, ca in enumerate(a):
        current_row = [i + 1]
        for j, cb in enumerate(b):
            insertions = previous_row[j + 1] + 1
            deletions = current_row[j] + 1
            substitutions = previous_row[j] + (ca != cb)
            current_row.append(min(insertions, deletions, substitutions))
        previous_row = current_row
    return previous_row[-1]


def _is_typosquat(domain: str, threshold: int = 2) -> bool:
    """
    Returns True if `domain` appears to be impersonating a known-legit
    financial domain, checking two attacker patterns:

    1. Brand name embedded as a hyphenated segment (e.g. "zerodha-secure.xyz",
       "kyc-sebi-verify.com") — the brand name itself is untouched, but
       stapled next to a suspicious word. Caught via exact-token matching
       after splitting on hyphens.

    2. Single-word close misspelling of the brand itself (e.g. "zerodhaa.com",
       "zerodhq.com") — caught via edit-distance, applied to both the full
       domain base AND each individual hyphen-separated token (so
       "zerodhaa-secure" still catches "zerodhaa" as a near-miss of
       "zerodha" even though the full hyphenated string doesn't match).
    """
    domain_base = domain.split(".")[0]
    tokens = domain_base.split("-")

    for legit in KNOWN_LEGIT_FINANCIAL_DOMAINS:
        legit_base = legit.split(".")[0]

        if domain_base == legit_base:
            continue  # exact match on the real domain — not a typosquat

        # Pattern 1: brand name preserved exactly as one hyphenated segment
        if legit_base in tokens:
            return True

        # Pattern 2: close edit-distance match, checked against the full
        # domain base AND each individual token
        candidates = [domain_base] + tokens
        for candidate in candidates:
            if candidate and candidate != legit_base:
                dist = _levenshtein_distance(candidate, legit_base)
                if 0 < dist <= threshold:
                    return True

    return False

def _has_homograph_chars(url: str) -> bool:
    """
    Detects mixed-script / non-ASCII characters in a URL — a classic sign of
    homograph spoofing (e.g. Cyrillic 'а' swapped for Latin 'a').
    Legitimate financial URLs are almost always pure ASCII.
    """
    try:
        url.encode("ascii")
        return False
    except UnicodeEncodeError:
        return True

def _find_urls(text: str) -> list[str]:
    """Pull every URL-looking substring out of raw email text."""
    # Simple but effective regex: matches http(s):// or www. prefixed strings.
    url_pattern = re.compile(r'(https?://[^\s<>"\']+|www\.[^\s<>"\']+)')
    return url_pattern.findall(text)


def _analyze_single_url(url: str) -> dict:
    """Compute structural features for one URL."""
    # tldextract cleanly separates subdomain / domain / suffix (e.g. .com)
    # even for tricky cases like "login.secure.paytm.phish.co.in"
    ext = tldextract.extract(url)
    parsed = urlparse(url if "://" in url else "http://" + url)

    full_domain = f"{ext.domain}.{ext.suffix}".lower()
    subdomain = ext.subdomain.lower()
    path = parsed.path or ""

    features = {
        # Raw length — phishing URLs tend to be longer (extra params/tokens
        # to make them look "official" or to evade simple blacklists).
        "url_length": len(url),

        # Structural character counts — legitimate bank/broker URLs are
        # usually clean; phishing URLs often stuff in dots/hyphens/@ symbols.
        "num_dots": url.count("."),
        "num_hyphens": url.count("-"),
        "num_at_symbols": url.count("@"),
        "num_digits": sum(c.isdigit() for c in url),

        # Depth of subdomain nesting — e.g. "secure.login.sebi.fake.com"
        # has 2 subdomain levels before the real (fake) domain.
        "subdomain_level": len(subdomain.split(".")) if subdomain else 0,

        # Path depth — number of "/" segments after the domain.
        "path_level": path.count("/"),

        # Is this an IP address instead of a domain name? (e.g. http://192.168.1.1/login)
        # Legitimate financial institutions never send raw-IP links.
        "is_ip_address": bool(re.match(r"^\d{1,3}(\.\d{1,3}){3}$", ext.domain)),

        # Does it use HTTPS? Lack of HTTPS is a weak-but-real signal.
        "has_https": url.lower().startswith("https://"),

        # Is this a known URL-shortening service? These are used to hide
        # the real destination and are disproportionately used in phishing.
        "is_shortened": full_domain in SHORTENER_DOMAINS,

        # Does the domain/subdomain contain financial-impersonation keywords?
        # e.g. "sebi-kyc-verify.xyz" scores high here even though it has
        # nothing to do with the real SEBI domain.
        "impersonation_keyword_count": sum(
            1 for kw in FINANCIAL_IMPERSONATION_KEYWORDS
            if kw in subdomain or kw in ext.domain.lower()
        ),

        # Suspicious/free TLDs disproportionately used in phishing campaigns
        # (cheap or free to register, hard to trace).
        "suspicious_tld": ext.suffix.lower() in {
            "xyz", "top", "club", "info", "online", "site", "tk", "ml", "ga"
        },
        
        # --- Additional lexical/semantic features (per updated reference) ---

        # @ symbol trick: everything before '@' is ignored by browsers, so
        # "https://sebi.gov.in@malicious.com" actually goes to malicious.com.
        "has_at_symbol_trick": "@" in url,

        # Double slash in the path (not the http:// prefix) — signals
        # possible open-redirect abuse on a trusted domain.
        "has_double_slash_in_path": "//" in path,

        # Is a victim's email address embedded in the URL as a parameter?
        # Strong signal of a PERSONALIZED phishing kit (pre-filling a fake
        # login page) — highly relevant to the "hyper-personalized" threat
        # this whole module exists to catch.
        "has_email_in_url": bool(
            re.search(r"[A-Za-z0-9._%+-]+%40[A-Za-z0-9.-]+", url)  # %40 = encoded @
            or re.search(r"email=[^&]*%40", url)
            or re.search(r"[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}", path)
        ),

        # Excessive percent-encoding — attackers hex-encode characters to
        # dodge simple keyword-based spam filters.
        "num_percent_encoded_chars": url.count("%"),

        # Typosquatting check against known legitimate financial domains.
        "is_typosquat": _is_typosquat(full_domain),

        # Homograph/mixed-script spoofing check.
        "has_homograph_chars": _has_homograph_chars(url),
    }
    return features


def extract_url_features(email_body: str) -> dict:
    """
    Main entry point: takes the raw email body text and returns an
    aggregated dictionary of URL-based features.

    If an email contains multiple URLs, we take the MAX/OR across them
    for boolean/count features (i.e. if ANY link in the email is suspicious,
    the email as a whole is flagged) — this matches how a real attacker only
    needs ONE malicious link to succeed.
    """
    urls = _find_urls(email_body)

    # Base case: no URLs found at all. Note this is not automatically "safe" —
    # some phishing relies on phone numbers or reply-to tricks instead — but
    # for pure URL-features, we return a neutral/zeroed feature set.
    if not urls:
        return {
            "num_urls": 0,
            "url_length": 0,
            "num_dots": 0,
            "num_hyphens": 0,
            "num_at_symbols": 0,
            "num_digits": 0,
            "subdomain_level": 0,
            "path_level": 0,
            "is_ip_address": False,
            "has_https": True,   # neutral default, no link to be insecure
            "is_shortened": False,
            "impersonation_keyword_count": 0,
            "suspicious_tld": False,
            "num_percent_encoded_chars": 0,
            "has_at_symbol_trick": False,
            "has_double_slash_in_path": False,
            "has_email_in_url": False,
            "is_typosquat": False,
            "has_homograph_chars": False,
        }

    per_url_features = [_analyze_single_url(u) for u in urls]

    # Aggregate across all URLs found in the email.
    aggregated = {"num_urls": len(urls)}
    numeric_keys = [
        "url_length", "num_dots", "num_hyphens", "num_at_symbols",
        "num_digits", "subdomain_level", "path_level",
        "impersonation_keyword_count",
        "num_percent_encoded_chars",          # <-- new
    ]
    boolean_keys = [
        "is_ip_address", "is_shortened", "suspicious_tld",
        "has_at_symbol_trick", "has_double_slash_in_path",  # <-- new
        "has_email_in_url", "is_typosquat", "has_homograph_chars",  # <-- new
    ]

    for key in numeric_keys:
        # Use MAX so the single worst/most suspicious URL drives the score.
        aggregated[key] = max(f[key] for f in per_url_features)

    for key in boolean_keys:
        # OR across all URLs — one bad link is enough to flag.
        aggregated[key] = any(f[key] for f in per_url_features)

    # has_https: flag if ANY link lacks HTTPS (worst case).
    aggregated["has_https"] = all(f["has_https"] for f in per_url_features)

    return aggregated


# ------------------------------------------------------------------
# Quick manual test — run this file directly to sanity-check output:
#   python nunmai_mail/features/url_features.py
# ------------------------------------------------------------------
if __name__ == "__main__":
    sample_phishing = (
        "Dear Investor, your SEBI KYC has expired. "
        "Verify now: http://sebi-kyc-verify-login.xyz/secure/update?id=8827"
    )
    sample_legit = (
        "Your quarterly statement is available at "
        "https://www.zerodha.com/console/statements"
    )
    print("Phishing sample:", extract_url_features(sample_phishing))
    print("Legit sample:   ", extract_url_features(sample_legit))