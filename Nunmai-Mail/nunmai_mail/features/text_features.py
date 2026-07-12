"""
text_features.py
=================
Detects AI-generated / hyper-personalized phishing text WITHOUT relying on
bad URLs or forged headers — because in the worst case (a genuinely
compromised legitimate account, i.e. AI-enabled Business Email Compromise),
neither of those exist. SPF/DKIM/DMARC all pass. The domain is real. The
only thing left to inspect is the WRITING ITSELF.

This module is entirely offline/statistical — no pretrained model download
required. It operationalizes four categories of signal:

  1. AI linguistic fingerprints (LLM vocabulary "tropes", low burstiness/
     structural monotony — AI sentences tend to be suspiciously uniform in
     length compared to real human writing, which is "bursty")
  2. Prompt-leakage / automation artifacts (a sloppy attacker's script left
     raw LLM output artifacts in the email, e.g. "Sure, here is an email...")
  3. Pretext/ask patterns (out-of-band excuses, over-justification, urgency +
     financial-action combos — the actual "ask" an attacker needs to make)
  4. Uncanny-valley personalization mismatch (personal/OSINT-flavoured
     language sitting right next to a financial/credential request — a
     forced transition that real colleagues rarely make)

NOTE: This does NOT attempt full academic "perplexity" (which needs a
trained language model to score word-by-word probability). Instead we use a
proxy: sentence-length burstiness + trope-vocabulary density, which is what
the reference material actually points to as the practical, human-detectable
signal. A TODO hook is included at the bottom for swapping in a real
pretrained AI-text-detector model later without changing the calling code.
"""

import re
import statistics


# --- 1. LLM "trope" vocabulary -------------------------------------------
# Words/phrases that models like GPT/Claude/Gemini disproportionately favor
# compared to typical human business-email writing. Individually meaningless,
# but density of these across a short email is a real signal.
LLM_TROPE_WORDS = {
    "delve", "crucial", "underscore", "underscores", "seamless", "seamlessly",
    "tapestry", "alignment", "testament", "pivotal", "navigating", "navigate",
    "leverage", "leveraging", "robust", "streamline", "streamlined",
    "holistic", "synergy", "synergies", "paramount", "myriad", "realm",
    "landscape", "foster", "fostering", "elevate", "unlock", "unveil",
    "endeavor", "meticulous", "meticulously", "comprehensive", "innovative",
}

# Full-phrase LLM tropes (checked as substrings since they're multi-word).
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

# --- 2. Prompt-leakage / automation artifacts -----------------------------
# Signs a lazy attacker automated the email generation and didn't scrub the
# raw LLM output before sending.
PROMPT_LEAKAGE_PATTERNS = [
    r"sure,?\s+here\s+is\s+(an?\s+)?email",
    r"as an ai\b",
    r"i cannot (assist|help) with that",
    r"\[insert (company|name|recipient)[^\]]*\]",
    r"\{\{.*?\}\}",              # unfilled template placeholders like {{name}}
    r"as a large language model",
    r"i'm sorry,? but i can't",
]

# --- 3. Out-of-band excuse patterns ---------------------------------------
# The classic "why you can't verify this the normal way" pretext used to
# pressure the victim into acting without calling/confirming.
OUT_OF_BAND_EXCUSE_PATTERNS = [
    r"on a plane", r"in-?flight wi-?fi", r"no cellular service",
    r"can'?t (take|answer) calls", r"unable to (verify|confirm) (by|via) phone",
    r"in a meeting all day", r"limited connectivity", r"traveling and",
    r"before we land", r"through this email only",
]

# --- 4. Urgency + financial-action combo ----------------------------------
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

# --- 5. Causal/justification connectives -----------------------------------
# Over-justification: real people asking for routine things just ask.
# LLMs tend to over-explain WHY, using connectives like these.
CAUSAL_CONNECTIVES = {
    "because", "since", "due to", "in order to", "given that", "as a result",
    "the reason for this is", "this is necessary because",
}

# --- 6. Personal/OSINT-flavoured language ----------------------------------
# Words that suggest the email is referencing personal (scraped) details
# rather than a normal transactional business relationship.
PERSONAL_OSINT_WORDS = {
    "linkedin", "your recent post", "congratulations on", "saw that you",
    "your alma mater", "your degree", "your award", "your trip", "your vacation",
    "hiking", "your family", "your hobby", "noticed you", "your profile",
}


def _split_sentences(text: str) -> list[str]:
    """
    Very lightweight sentence splitter (no NLTK/spacy dependency needed).
    Splits on '.', '!', '?' followed by whitespace, while trying not to
    split on common abbreviations. Good enough for feature purposes — we
    don't need perfect linguistic accuracy, just consistent measurement.
    """
    # Protect common abbreviations from being treated as sentence-enders.
    protected = re.sub(r"\b(Mr|Mrs|Ms|Dr|Inc|Ltd|e\.g|i\.e)\.", r"\1<DOT>", text)
    raw_sentences = re.split(r"(?<=[.!?])\s+", protected)
    sentences = [s.replace("<DOT>", ".").strip() for s in raw_sentences if s.strip()]
    return sentences


def _burstiness_score(sentences: list[str]) -> float:
    """
    Burstiness = coefficient of variation (stdev / mean) of sentence lengths
    (measured in words).

    Human writing is "bursty": a mix of long rambling sentences and short
    punchy ones ("Approved. Send it." next to a three-line paragraph).
    AI writing tends to be structurally monotonous — sentences cluster
    around a similar length. LOW burstiness (low CV) is the AI-like signal.

    Returns a value >= 0. Roughly: below ~0.3 is suspiciously uniform;
    human business email is typically 0.4-0.8+.
    """
    if len(sentences) < 3:
        return 1.0  # not enough sentences to measure meaningfully; assume neutral/human-like

    lengths = [len(s.split()) for s in sentences]
    mean_len = statistics.mean(lengths)
    if mean_len == 0:
        return 1.0
    stdev_len = statistics.pstdev(lengths)
    return round(stdev_len / mean_len, 3)


def _count_matches(text_lower: str, terms: set[str]) -> int:
    """Count how many distinct terms from a set appear in the text (case-insensitive)."""
    return sum(1 for term in terms if term in text_lower)


def _count_regex_matches(text_lower: str, patterns: list[str]) -> int:
    """Count how many distinct regex patterns match somewhere in the text."""
    return sum(1 for pattern in patterns if re.search(pattern, text_lower))


def extract_text_features(email_body: str) -> dict:
    """
    Main entry point: takes the raw email BODY text (not headers) and
    returns a dictionary of text-based AI-generation / social-engineering
    features.
    """
    text_lower = email_body.lower()
    sentences = _split_sentences(email_body)
    words = re.findall(r"[a-zA-Z']+", email_body)

    features = {
        # --- Structural / AI fingerprint signals ---
        "sentence_count": len(sentences),
        "word_count": len(words),
        "burstiness_score": _burstiness_score(sentences),
        "low_burstiness_flag": _burstiness_score(sentences) < 0.35,

        # --- Vocabulary trope density ---
        "llm_trope_word_count": _count_matches(text_lower, LLM_TROPE_WORDS),
        "llm_trope_phrase_count": _count_matches(text_lower, LLM_TROPE_PHRASES),

        # --- Prompt leakage / automation artifacts (very high-confidence signal) ---
        "prompt_leakage_detected": _count_regex_matches(text_lower, PROMPT_LEAKAGE_PATTERNS) > 0,

        # --- Pretext / social-engineering ask patterns ---
        "out_of_band_excuse_count": _count_regex_matches(text_lower, OUT_OF_BAND_EXCUSE_PATTERNS),
        "urgency_word_count": _count_matches(text_lower, URGENCY_WORDS),
        "financial_action_word_count": _count_matches(text_lower, FINANCIAL_ACTION_WORDS),
        "urgency_financial_combo": (
            _count_matches(text_lower, URGENCY_WORDS) > 0
            and _count_matches(text_lower, FINANCIAL_ACTION_WORDS) > 0
        ),

        # --- Over-justification ---
        "causal_connective_count": _count_matches(text_lower, CAUSAL_CONNECTIVES),

        # --- Uncanny-valley personalization mismatch ---
        "personal_osint_word_count": _count_matches(text_lower, PERSONAL_OSINT_WORDS),
        # The real "tell": personal/OSINT language AND a financial ask in the
        # SAME short email — real colleagues don't pivot from your hiking
        # trip to a wire transfer in three sentences.
        "personalization_financial_mismatch": (
            _count_matches(text_lower, PERSONAL_OSINT_WORDS) > 0
            and _count_matches(text_lower, FINANCIAL_ACTION_WORDS) > 0
        ),
    }

    return features


# ------------------------------------------------------------------
# TODO (future upgrade hook):
# If you later want a pretrained AI-text classifier (e.g. a fine-tuned
# RoBERTa detector) instead of / in addition to these heuristics, add a
# function here like:
#
#   def ai_generation_probability_ml(email_body: str) -> float:
#       # load model once at module level, run inference, return 0-1 score
#       ...
#
# and merge its output into extract_text_features()'s returned dict as
# an additional key (e.g. "ml_ai_probability"). No other module needs to
# change — train.py and classifier.py just pick up whatever keys exist.
# ------------------------------------------------------------------


# ------------------------------------------------------------------
# Quick manual test — run this file directly to sanity-check output:
#   python nunmai_mail/features/text_features.py
# ------------------------------------------------------------------
if __name__ == "__main__":
    sample_ai_phishing = (
        "I hope this email finds you well. I saw your fantastic LinkedIn post "
        "about your hiking trip in the Alps, congratulations on reaching the summit. "
        "Speaking of scaling new heights, I wanted to reach out because we need to "
        "urgently process a wire transfer to a new vendor before the deadline today. "
        "This is crucial as it will underscore our commitment to a seamless "
        "onboarding process. Unfortunately I am currently on a plane without "
        "cellular service, but the in-flight wifi is letting this email through. "
        "Please handle this payment before we land. I deeply value our synergy."
    )

    sample_human_legit = (
        "Hey, saw the invoice from the printer vendor. Approved. Send it. "
        "Also can you loop in Priya on the Q3 numbers when you get a sec? Thx."
    )

    print("AI-generated phishing sample:")
    for k, v in extract_text_features(sample_ai_phishing).items():
        print(f"  {k}: {v}")

    print("\nHuman-written legit sample:")
    for k, v in extract_text_features(sample_human_legit).items():
        print(f"  {k}: {v}")