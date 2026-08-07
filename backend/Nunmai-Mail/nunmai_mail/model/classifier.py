"""
classifier.py
==============
Loads the trained NUNMAI-MAIL model and provides a simple, single-call
interface for scoring ONE email at inference time — this is what the
FastAPI layer (main.py) will call for every incoming request.

WHY THIS FILE EXISTS SEPARATELY FROM train.py:
train.py's job is to build the feature table for THOUSANDS of rows at once
and train/evaluate a model. classifier.py's job is different: given ONE
new email nobody has seen before, build its feature vector in EXACTLY the
same way, feed it through the ALREADY-TRAINED model, and return a
human-readable verdict.

CRITICAL DESIGN POINT: the feature vector for a new email must have the
EXACT SAME COLUMNS, IN THE EXACT SAME ORDER, as what the model was trained
on. This is why train.py saved "feature_columns" alongside the model in
the .joblib file — we reindex every new prediction against that saved
list, filling in 0 for any category that didn't appear in this particular
email.

SENDER VERIFICATION: every prediction also checks the sender's domain
against the NUNMAI-VERIFY local stub (verify.py) — this is the "Sender
Verified? Yes/No" decision branch from the architecture diagram.
"""

import re
import sys
from pathlib import Path
from email import message_from_string
from email.utils import parseaddr

import joblib
import pandas as pd

sys.path.append(str(Path(__file__).resolve().parents[2]))

from nunmai_mail.features.url_features import extract_url_features
from nunmai_mail.features.header_features import extract_header_features
from nunmai_mail.features.text_features import extract_text_features, extract_text_matches
from nunmai_mail.verify import verify_sender_domain

MODEL_PATH = Path(__file__).resolve().parents[2] / "models" / "nunmai_mail_model.joblib"

CATEGORICAL_COLUMNS = ["spf_result", "dkim_result", "dmarc_result"]

RISK_TIER_THRESHOLDS = {
    "SAFE": 0.30,
    "SUSPICIOUS": 0.70,
}

# Feature-name substrings that indicate a POSITIVE/TRUST signal rather
# than a risk signal (e.g. "spf_result_pass" means auth PASSED — that's
# reassuring, not alarming, so it shouldn't be listed as a "risk signal"
# even though it's one of the model's most important features overall).
TRUST_SIGNAL_MARKERS = ["_pass"]


class NunmaiMailClassifier:
    """
    Loads the trained model once (expensive: reads a file from disk) and
    reuses it for many predictions (cheap). Instantiate this ONCE at API
    startup, not per-request.
    """

    def __init__(self, model_path: Path = MODEL_PATH):
        if not model_path.exists():
            raise FileNotFoundError(
                f"Trained model not found at {model_path}. "
                f"Run 'python nunmai_mail\\model\\train.py' first."
            )
        bundle = joblib.load(model_path)
        self.model = bundle["model"]
        self.feature_columns = bundle["feature_columns"]

    def _extract_url_domains(self, body_text: str) -> list[str]:
        """Same helper as train.py — kept identical so feature extraction
        is consistent between training and inference."""
        import tldextract
        url_pattern = re.compile(r'(https?://[^\s<>"\']+|www\.[^\s<>"\']+)')
        urls = url_pattern.findall(body_text)
        domains = []
        for url in urls:
            ext = tldextract.extract(url)
            domains.append(f"{ext.domain}.{ext.suffix}".lower())
        return domains

    def _build_feature_vector(self, body_text: str, raw_email_source: str):
        """
        Runs all three feature extractors on a SINGLE email and returns a
        one-row DataFrame reindexed to match EXACTLY the columns the model
        was trained on, plus the raw (unencoded) feature dicts for display.
        """
        url_domains = self._extract_url_domains(body_text)

        url_feats = extract_url_features(body_text)
        header_feats = extract_header_features(raw_email_source, body_url_domains=url_domains)
        text_feats = extract_text_features(body_text)

        combined = {}
        combined.update({f"url__{k}": v for k, v in url_feats.items()})
        combined.update({f"header__{k}": v for k, v in header_feats.items()})
        combined.update({f"text__{k}": v for k, v in text_feats.items()})

        raw_df = pd.DataFrame([combined])

        bool_cols = raw_df.select_dtypes(include="bool").columns
        raw_df[bool_cols] = raw_df[bool_cols].astype(int)

        categorical_full_names = [f"header__{c}" for c in CATEGORICAL_COLUMNS]
        encoded_df = pd.get_dummies(raw_df, columns=categorical_full_names, dtype=int)

        # Reindex to match the EXACT columns/order the model was trained on.
        final_df = encoded_df.reindex(columns=self.feature_columns, fill_value=0)

        return final_df, {"url": url_feats, "header": header_feats, "text": text_feats}

    def classify_email(self, body_text: str, raw_email_source: str) -> dict:
        """
        MAIN ENTRY POINT. Takes a new email's body text and raw source
        (headers + body), returns a full verdict dictionary.

        Returns:
            {
                ...
                "text_matches": { "urgency": [...], "financial": [...] },
                ...
            }
        """
        feature_df, raw_features = self._build_feature_vector(body_text, raw_email_source)
        text_matches = extract_text_matches(body_text)

        # predict_proba returns [[prob_class_0, prob_class_1]] — we want
        # prob_class_1 (phishing), since label=1 means phishing throughout.
        phishing_probability = float(self.model.predict_proba(feature_df)[0][1])

        if phishing_probability < RISK_TIER_THRESHOLDS["SAFE"]:
            risk_tier = "SAFE"
        elif phishing_probability < RISK_TIER_THRESHOLDS["SUSPICIOUS"]:
            risk_tier = "SUSPICIOUS"
        else:
            risk_tier = "PHISHING"

        prediction = "phishing" if phishing_probability >= 0.5 else "legitimate"

        # --- Explainability: split into RISK signals (features present in
        # THIS email that the model globally weights as important AND that
        # point toward phishing) vs TRUST signals (important features that
        # point toward legitimacy, e.g. auth PASSING). This fixes the
        # earlier issue where "spf_result_pass" was confusingly grouped
        # in with actual risk indicators. ---
        importances = pd.Series(self.model.feature_importances_, index=self.feature_columns)
        this_email_active_flags = feature_df.iloc[0]
        active_important = importances[this_email_active_flags > 0].sort_values(ascending=False)

        def _is_trust_signal(feature_name: str) -> bool:
            return any(marker in feature_name for marker in TRUST_SIGNAL_MARKERS)

        risk_signals = [
            (name, float(this_email_active_flags[name]))
            for name in active_important.index if not _is_trust_signal(name)
        ][:8]
        trust_signals = [
            (name, float(this_email_active_flags[name]))
            for name in active_important.index if _is_trust_signal(name)
        ][:5]

        # --- Sender verification (NUNMAI-VERIFY local stub) ---
        from_header = message_from_string(raw_email_source).get("From", "")
        _, from_addr = parseaddr(from_header)
        sender_verification = verify_sender_domain(from_addr)

        return {
            "phishing_probability": round(phishing_probability, 4),
            "risk_tier": risk_tier,
            "prediction": prediction,
            "top_risk_signals": risk_signals,
            "top_trust_signals": trust_signals,
            "sender_verification": sender_verification,
            "raw_features": raw_features,
            "text_matches": text_matches,
        }


# ------------------------------------------------------------------
# Quick manual test — run this file directly to sanity-check output:
#   python nunmai_mail\model\classifier.py
# ------------------------------------------------------------------
if __name__ == "__main__":
    clf = NunmaiMailClassifier()

    test_phishing_body = (
        "Dear Investor,\n\nYour SEBI KYC has expired. Verify immediately or your "
        "account will be suspended: http://sebi-kyc-verify.xyz/secure/update?id=8827\n\n"
        "This is urgent, act now to avoid permanent suspension."
    )
    test_phishing_raw = (
        'From: "SEBI Compliance" <compliance@sebi-verify.xyz>\n'
        "To: investor@example.com\n"
        "Subject: URGENT: KYC Verification Expired\n"
        "Authentication-Results: mx.example.com; spf=fail; dkim=none; dmarc=fail\n\n"
        + test_phishing_body
    )

    test_legit_body = (
        "Dear Investor,\n\nYour quarterly statement is now available. "
        "View it here: https://www.zerodha.com/console/statements\n\nRegards, Zerodha Support"
    )
    test_legit_raw = (
        'From: "Zerodha Support" <support@zerodha.com>\n'
        "To: investor@example.com\n"
        "Subject: Your Quarterly Statement\n"
        "Authentication-Results: mx.example.com; spf=pass; dkim=pass; dmarc=pass\n\n"
        + test_legit_body
    )

    print("=" * 60)
    print("TEST 1: Phishing email")
    print("=" * 60)
    result = clf.classify_email(test_phishing_body, test_phishing_raw)
    print(f"Prediction: {result['prediction']}")
    print(f"Phishing probability: {result['phishing_probability']}")
    print(f"Risk tier: {result['risk_tier']}")
    print("Top risk signals:")
    for name, value in result["top_risk_signals"]:
        print(f"  {name} = {value}")
    print("Top trust signals:")
    for name, value in result["top_trust_signals"]:
        print(f"  {name} = {value}")
    print("Sender verification:", result["sender_verification"])

    print("\n" + "=" * 60)
    print("TEST 2: Legitimate email")
    print("=" * 60)
    result = clf.classify_email(test_legit_body, test_legit_raw)
    print(f"Prediction: {result['prediction']}")
    print(f"Phishing probability: {result['phishing_probability']}")
    print(f"Risk tier: {result['risk_tier']}")
    print("Top risk signals:")
    for name, value in result["top_risk_signals"]:
        print(f"  {name} = {value}")
    print("Top trust signals:")
    for name, value in result["top_trust_signals"]:
        print(f"  {name} = {value}")
    print("Sender verification:", result["sender_verification"])