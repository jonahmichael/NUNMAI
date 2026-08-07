"""
test_features.py
=================
Automated regression tests for NUNMAI-MAIL's feature extraction modules.

WHY THIS EXISTS: we've hand-verified each module's output at every step
of building this (checking printed dictionaries after every change). This
file turns those manual checks into permanent, automated ones — so if you
edit url_features.py, header_features.py, or text_features.py again before
the pitch (or after), running `pytest` instantly tells you whether you
broke something that used to work correctly.

This is intentionally NOT exhaustive (a full production test suite would
cover many more edge cases) — given time constraints, this covers the
core "does each module correctly distinguish an obvious phishing example
from an obvious legitimate example" cases we already validated by hand,
plus a few specific edge cases worth locking in.

Run with:
    pytest tests\\test_features.py -v
"""

import sys
from pathlib import Path

import pytest

sys.path.append(str(Path(__file__).resolve().parents[1]))

from nunmai_mail.features.url_features import extract_url_features
from nunmai_mail.features.header_features import extract_header_features
from nunmai_mail.features.text_features import extract_text_features
from nunmai_mail.verify import verify_sender_domain


# ============================================================
# url_features.py tests
# ============================================================

def test_url_features_detects_suspicious_tld():
    body = "Verify here: http://sebi-kyc-verify.xyz/secure/update"
    features = extract_url_features(body)
    assert features["suspicious_tld"] is True


def test_url_features_detects_ip_address_link():
    body = "Login here: http://192.168.1.1/login"
    features = extract_url_features(body)
    assert features["is_ip_address"] is True


def test_url_features_detects_shortener():
    body = "Click here: http://bit.ly/abc123"
    features = extract_url_features(body)
    assert features["is_shortened"] is True


def test_url_features_clean_legit_url():
    body = "View your statement: https://www.zerodha.com/console/statements"
    features = extract_url_features(body)
    assert features["suspicious_tld"] is False
    assert features["is_ip_address"] is False
    assert features["is_shortened"] is False
    assert features["has_https"] is True


def test_url_features_no_urls_returns_neutral_defaults():
    body = "This email has no links at all."
    features = extract_url_features(body)
    assert features["num_urls"] == 0
    assert features["is_ip_address"] is False


def test_url_features_detects_typosquat():
    body = "Verify at http://zerodhaa-secure.xyz/login"
    features = extract_url_features(body)
    assert features["is_typosquat"] is True


# ============================================================
# header_features.py tests
# ============================================================

PHISHING_HEADERS = """From: "SEBI Compliance Team" <alerts.sebi.kyc@gmail.com>
To: investor@example.com
Reply-To: sebi-support-desk@gmail.com
Return-Path: <bounce@compromised-server.ru>
Subject: URGENT: Your SEBI KYC Verification Has Expired
Message-ID: <123456789@localhost>
X-Mailer: PHPMailer 6.5
Authentication-Results: mx.google.com; spf=fail; dkim=none; dmarc=fail

Dear Investor, your SEBI KYC has expired...
"""

LEGIT_HEADERS = """From: "Zerodha Support" <support@zerodha.com>
To: investor@example.com
Reply-To: support@zerodha.com
Return-Path: <bounce@zerodha.com>
Subject: Your Quarterly Statement is Ready
Message-ID: <a1b2c3d4e5@mail.zerodha.com>
X-Mailer: Zerodha Mailer 2.0
Authentication-Results: mx.google.com; spf=pass; dkim=pass; dmarc=pass

Your quarterly statement is now available in Console.
"""


def test_header_features_detects_auth_failure():
    features = extract_header_features(PHISHING_HEADERS)
    assert features["spf_result"] == "fail"
    assert features["dkim_result"] == "none"
    assert features["dmarc_result"] == "fail"
    assert features["auth_all_failed"] is True


def test_header_features_detects_auth_pass():
    features = extract_header_features(LEGIT_HEADERS)
    assert features["spf_result"] == "pass"
    assert features["dkim_result"] == "pass"
    assert features["dmarc_result"] == "pass"
    assert features["auth_all_failed"] is False


def test_header_features_detects_display_name_impersonation():
    features = extract_header_features(PHISHING_HEADERS)
    assert features["display_name_impersonation"] is True
    assert features["sender_uses_free_email"] is True


def test_header_features_clean_sender_not_impersonating():
    features = extract_header_features(LEGIT_HEADERS)
    assert features["display_name_impersonation"] is False


def test_header_features_detects_message_id_mismatch():
    features = extract_header_features(PHISHING_HEADERS)
    assert features["message_id_domain_mismatch"] is True


def test_header_features_matching_message_id():
    features = extract_header_features(LEGIT_HEADERS)
    assert features["message_id_domain_mismatch"] is False


def test_header_features_detects_suspicious_mailer():
    features = extract_header_features(PHISHING_HEADERS)
    assert features["suspicious_mailer"] is True


def test_header_features_no_attachments_returns_zero():
    features = extract_header_features(LEGIT_HEADERS)
    assert features["num_attachments"] == 0
    assert features["has_dangerous_attachment"] is False


# ============================================================
# text_features.py tests
# ============================================================

def test_text_features_detects_llm_tropes():
    body = "I hope this email finds you well. This is crucial to underscore our seamless process."
    features = extract_text_features(body)
    assert features["llm_trope_word_count"] > 0
    assert features["llm_trope_phrase_count"] > 0


def test_text_features_detects_out_of_band_excuse():
    body = "I'm currently on a plane without cellular service, but the in-flight wifi is letting this through."
    features = extract_text_features(body)
    assert features["out_of_band_excuse_count"] > 0


def test_text_features_detects_urgency_financial_combo():
    body = "This is urgent, please process the wire transfer immediately before it expires."
    features = extract_text_features(body)
    assert features["urgency_financial_combo"] is True


def test_text_features_detects_personalization_mismatch():
    body = "I saw your LinkedIn post about your hiking trip, congratulations. We need to process a wire transfer today."
    features = extract_text_features(body)
    assert features["personalization_financial_mismatch"] is True


def test_text_features_clean_human_text_low_signal():
    body = "Approved. Send it. Also loop in Priya on the numbers when you get a sec. Thx."
    features = extract_text_features(body)
    assert features["llm_trope_word_count"] == 0
    assert features["out_of_band_excuse_count"] == 0
    assert features["personalization_financial_mismatch"] is False


def test_text_features_detects_prompt_leakage():
    body = "Sure, here is an email drafted to convince the recipient to act urgently."
    features = extract_text_features(body)
    assert features["prompt_leakage_detected"] is True


# ============================================================
# verify.py tests
# ============================================================

def test_verify_recognizes_legit_domain():
    result = verify_sender_domain("support@zerodha.com")
    assert result["verified"] is True
    assert result["entity_name"] == "Zerodha"


def test_verify_rejects_typosquat_domain():
    result = verify_sender_domain("compliance@sebi-verify.xyz")
    assert result["verified"] is False
    assert result["entity_name"] is None


def test_verify_rejects_free_email():
    result = verify_sender_domain("alerts.sebi.kyc@gmail.com")
    assert result["verified"] is False


def test_verify_handles_malformed_address():
    result = verify_sender_domain("not-an-email-address")
    assert result["verified"] is False
    assert result["domain_checked"] == ""