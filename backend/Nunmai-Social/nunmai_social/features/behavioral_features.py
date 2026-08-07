"""
behavioral_features.py
========================
RULE-BASED heuristics for detecting bot-like / coordinated-manipulation
behavior on social media posts — NOT a trained ML model.

WHY RULE-BASED, NOT ML: unlike text analysis (reused from Mail) and image
forensics (reused from Vision), there's no clean pretrained-model fit for
"is this account/posting-pattern behaving like a bot or coordinated
campaign." Training a real behavioral classifier would need actual
historical social media account data / API access, which is out of scope
given the project timeline. This module is an honest, clearly-labeled
heuristic layer — same design pattern as NUNMAI-VERIFY's local stub —
standing in for what would eventually be a properly trained model.

INPUT ASSUMPTION: this module expects basic account/post metadata to be
supplied by the caller (account age, post frequency, follower/following
counts, etc.) — it does NOT scrape or fetch this data itself. In a real
deployment, this would come from whatever social platform API the
integration connects to.
"""

import re
from datetime import datetime, timedelta


# Handle patterns common in bot/spam accounts: long strings of digits,
# excessive underscores, or generic "user12345"-style auto-generated names.
SUSPICIOUS_HANDLE_PATTERNS = [
    r"\d{6,}",              # 6+ consecutive digits (e.g. user48213957)
    r"^(user|account)\d+$",  # generic auto-generated username pattern
    r"_{3,}",                # excessive underscores
]

# Bio/profile text patterns commonly seen in scam/bot accounts pushing
# investment schemes.
SUSPICIOUS_BIO_KEYWORDS = {
    "guaranteed returns", "100x", "financial freedom", "dm for signals",
    "crypto expert", "forex signals", "click link in bio", "get rich",
    "passive income guru",
}


def _check_account_age(account_created_date: str | None) -> dict:
    """
    Flags very recently created accounts — a common (though not
    definitive) signal of purpose-built manipulation/bot accounts, since
    genuine long-term investors/commentators typically have older accounts.

    Expects an ISO date string (YYYY-MM-DD) or None if unknown.
    """
    if not account_created_date:
        return {"account_age_days": None, "very_new_account": False}

    try:
        created = datetime.fromisoformat(account_created_date)
        age_days = (datetime.now() - created).days
        return {
            "account_age_days": age_days,
            "very_new_account": age_days < 30,  # less than a month old
        }
    except (ValueError, TypeError):
        return {"account_age_days": None, "very_new_account": False}


def _check_posting_frequency(posts_per_day: float | None) -> dict:
    """
    Flags abnormally high posting frequency — genuine individual
    investors rarely post dozens of times a day; sustained high-volume
    posting is a common coordinated-campaign/bot signal.
    """
    if posts_per_day is None:
        return {"posts_per_day": None, "abnormal_posting_frequency": False}

    return {
        "posts_per_day": posts_per_day,
        "abnormal_posting_frequency": posts_per_day > 20,
    }


def _check_follower_ratio(followers: int | None, following: int | None) -> dict:
    """
    Flags an unusual follower/following ratio. Bot/bought-follower
    accounts often show one of two extreme patterns: following thousands
    while having almost no followers back (spam-follow pattern), or
    implausibly high followers relative to following with very low
    engagement elsewhere (bought-followers pattern — though we can't
    check engagement here, just the ratio).
    """
    if followers is None or following is None or following == 0:
        return {"follower_following_ratio": None, "suspicious_follow_ratio": False}

    ratio = followers / following
    # Following far more accounts than follow back — classic bot pattern.
    suspicious = following > 500 and ratio < 0.05

    return {"follower_following_ratio": round(ratio, 3), "suspicious_follow_ratio": suspicious}


def _check_handle_pattern(handle: str | None) -> dict:
    """Flags auto-generated-looking usernames."""
    if not handle:
        return {"suspicious_handle_pattern": False}

    matches = any(re.search(pattern, handle) for pattern in SUSPICIOUS_HANDLE_PATTERNS)
    return {"suspicious_handle_pattern": matches}


def _check_bio_keywords(bio_text: str | None) -> dict:
    """Flags common scam/pump-and-dump bio language."""
    if not bio_text:
        return {"suspicious_bio_keyword_count": 0}

    bio_lower = bio_text.lower()
    count = sum(1 for kw in SUSPICIOUS_BIO_KEYWORDS if kw in bio_lower)
    return {"suspicious_bio_keyword_count": count}


def extract_behavioral_features(
    handle: str | None = None,
    bio_text: str | None = None,
    account_created_date: str | None = None,
    posts_per_day: float | None = None,
    followers: int | None = None,
    following: int | None = None,
) -> dict:
    """
    MAIN ENTRY POINT. All arguments are optional — pass whatever metadata
    is available for a given account/post; missing fields are handled
    gracefully rather than erroring, since real-world data availability
    varies by platform/integration.
    """
    features = {}
    features.update(_check_account_age(account_created_date))
    features.update(_check_posting_frequency(posts_per_day))
    features.update(_check_follower_ratio(followers, following))
    features.update(_check_handle_pattern(handle))
    features.update(_check_bio_keywords(bio_text))

    # Overall heuristic flag: any TWO or more individual red flags firing
    # together is treated as meaningfully suspicious — a single flag
    # alone is too weak/noisy (e.g. plenty of genuine new users exist),
    # but a cluster of them together is a much stronger signal.
    red_flags = [
        features.get("very_new_account", False),
        features.get("abnormal_posting_frequency", False),
        features.get("suspicious_follow_ratio", False),
        features.get("suspicious_handle_pattern", False),
        features.get("suspicious_bio_keyword_count", 0) > 0,
    ]
    features["behavioral_red_flag_count"] = sum(red_flags)
    features["likely_coordinated_or_bot"] = sum(red_flags) >= 2

    return features


# ------------------------------------------------------------------
# Quick manual test:
#   python nunmai_social\features\behavioral_features.py
# ------------------------------------------------------------------
if __name__ == "__main__":
    suspicious_account = {
        "handle": "crypto_signals_4829173",
        "bio_text": "Guaranteed returns! DM for signals. 100x your portfolio!",
        "account_created_date": (datetime.now() - timedelta(days=5)).strftime("%Y-%m-%d"),
        "posts_per_day": 45,
        "followers": 12,
        "following": 3000,
    }

    genuine_account = {
        "handle": "priya_invests",
        "bio_text": "Long-term investor. Views are my own, not financial advice.",
        "account_created_date": "2019-03-15",
        "posts_per_day": 1.2,
        "followers": 850,
        "following": 400,
    }

    print("Suspicious account:")
    for k, v in extract_behavioral_features(**suspicious_account).items():
        print(f"  {k}: {v}")

    print("\nGenuine account:")
    for k, v in extract_behavioral_features(**genuine_account).items():
        print(f"  {k}: {v}")