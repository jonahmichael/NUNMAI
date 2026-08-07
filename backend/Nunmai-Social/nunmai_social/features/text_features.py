"""
text_features.py
=================
Detects AI-generated / manipulative text WITHOUT relying on bad URLs or
forged headers. Originally built for NUNMAI-MAIL's phishing-email
detection; reused here UNCHANGED for NUNMAI-SOCIAL, since the underlying
signals — LLM vocabulary "tropes," structural monotony (low burstiness),
prompt-leakage artifacts, urgency+action-request combos, and
personalization-vs-ask mismatches — are just as relevant to a
manipulative social media post ("I saw your amazing portfolio gains,
invest in THIS before it's too late!") as they are to a phishing email.

This module is entirely offline/statistical — no pretrained model
download required, no external dependencies beyond the standard library.
"""

import re
import statistics


LLM_TROPE_WORDS = {
    "delve", "crucial", "underscore", "underscores", "seamless", "seamlessly",
    "tapestry", "alignment", "testament", "pivotal", "navigating", "navigate",
    "leverage", "leveraging", "robust", "streamline", "streamlined",
    "holistic", "synergy", "synergies", "paramount", "myriad", "realm",
    "landscape", "foster", "fostering", "elevate", "unlock", "unveil",
    "endeavor", "meticulous", "meticulously", "comprehensive", "innovative",
}

LLM_TROPE_PHRASES = {
    "i hope this email finds you well",
    "in today's fast-paced",
    "in today's rapidly evolving",
    "i deeply value our",
    "at your earliest convenience",
    "please do not hesitate to",
    "i wanted to reach out",
    "i trust this message finds you",
}

PROMPT_LEAKAGE_PATTERNS = [
    r"sure,?\s+here\s+is\s+(an?\s+)?email",
    r"as an ai\b",
    r"i cannot (assist|help) with that",
    r"\[insert (company|name|recipient)[^\]]*\]",
    r"\{\{.*?\}\}",
    r"as a large language model",
    r"i'm sorry,? but i can't",
]

OUT_OF_BAND_EXCUSE_PATTERNS = [
    r"on a plane", r"in-?flight wi-?fi", r"no cellular service",
    r"can'?t (take|answer) calls", r"unable to (verify|confirm) (by|via) phone",
    r"in a meeting all day", r"limited connectivity", r"traveling and",
    r"before we land", r"through this email only",
]

URGENCY_WORDS = {
    "urgent", "immediately", "asap", "right away", "as soon as possible",
    "expire", "expires", "expiring", "expired", "deadline", "final notice",
    "act now", "time-sensitive", "today only",
}
FINANCIAL_ACTION_WORDS = {
    "wire transfer", "wire the funds", "bank details", "account number",
    "routing number", "payment", "invoice", "gift card", "kyc", "verify your account",
    "update your details", "reset your password", "otp", "pin number",
    "process the payment", "authorize", "reimbursement",
}

CAUSAL_CONNECTIVES = {
    "because", "since", "due to", "in order to", "given that", "as a result",
    "the reason for this is", "this is necessary because",
}

PERSONAL_OSINT_WORDS = {
    "linkedin", "your recent post", "congratulations on", "saw that you",
    "your alma mater", "your degree", "your award", "your trip", "your vacation",
    "hiking", "your family", "your hobby", "noticed you", "your profile",
}


def _split_sentences(text: str) -> list[str]:
    protected = re.sub(r"\b(Mr|Mrs|Ms|Dr|Inc|Ltd|e\.g|i\.e)\.", r"\1<DOT>", text)
    raw_sentences = re.split(r"(?<=[.!?])\s+", protected)
    sentences = [s.replace("<DOT>", ".").strip() for s in raw_sentences if s.strip()]
    return sentences


def _burstiness_score(sentences: list[str]) -> float:
    if len(sentences) < 3:
        return 1.0

    lengths = [len(s.split()) for s in sentences]
    mean_len = statistics.mean(lengths)
    if mean_len == 0:
        return 1.0
    stdev_len = statistics.pstdev(lengths)
    return round(stdev_len / mean_len, 3)


def _count_matches(text_lower: str, terms: set[str]) -> int:
    return sum(1 for term in terms if term in text_lower)


def _count_regex_matches(text_lower: str, patterns: list[str]) -> int:
    return sum(1 for pattern in patterns if re.search(pattern, text_lower))


def extract_text_features(email_body: str) -> dict:
    text_lower = email_body.lower()
    sentences = _split_sentences(email_body)
    words = re.findall(r"[a-zA-Z']+", email_body)

    features = {
        "sentence_count": len(sentences),
        "word_count": len(words),
        "burstiness_score": _burstiness_score(sentences),
        "low_burstiness_flag": _burstiness_score(sentences) < 0.35,

        "llm_trope_word_count": _count_matches(text_lower, LLM_TROPE_WORDS),
        "llm_trope_phrase_count": _count_matches(text_lower, LLM_TROPE_PHRASES),

        "prompt_leakage_detected": _count_regex_matches(text_lower, PROMPT_LEAKAGE_PATTERNS) > 0,

        "out_of_band_excuse_count": _count_regex_matches(text_lower, OUT_OF_BAND_EXCUSE_PATTERNS),
        "urgency_word_count": _count_matches(text_lower, URGENCY_WORDS),
        "financial_action_word_count": _count_matches(text_lower, FINANCIAL_ACTION_WORDS),
        "urgency_financial_combo": (
            _count_matches(text_lower, URGENCY_WORDS) > 0
            and _count_matches(text_lower, FINANCIAL_ACTION_WORDS) > 0
        ),

        "causal_connective_count": _count_matches(text_lower, CAUSAL_CONNECTIVES),

        "personal_osint_word_count": _count_matches(text_lower, PERSONAL_OSINT_WORDS),
        "personalization_financial_mismatch": (
            _count_matches(text_lower, PERSONAL_OSINT_WORDS) > 0
            and _count_matches(text_lower, FINANCIAL_ACTION_WORDS) > 0
        ),
    }

    return features


if __name__ == "__main__":
    sample_manipulative_post = (
        "I hope this post finds you well! This is a crucial opportunity, "
        "act now before it expires today. Send your payment details immediately "
        "to secure your allocation. This is urgent and time-sensitive."
    )

    sample_normal_post = (
        "Markets were choppy today. IT stocks did well, banking lagged a bit. "
        "Nothing too dramatic honestly."
    )

    print("Manipulative post sample:")
    for k, v in extract_text_features(sample_manipulative_post).items():
        print(f"  {k}: {v}")

    print("\nNormal post sample:")
    for k, v in extract_text_features(sample_normal_post).items():
        print(f"  {k}: {v}")