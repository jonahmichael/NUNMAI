"""
fusion.py
=========
Combines NUNMAI-SOCIAL's three independent analysis modules — text,
image, and behavioral — into a single unified verdict, matching Step 3
("Score Fusion") from the architecture diagram.

DESIGN NOTE: unlike NUNMAI-MAIL (which trained a real ML ensemble on
labeled data) or NUNMAI-VISION/VOICE (which use a single pretrained
model), NUNMAI-SOCIAL's fusion layer is a WEIGHTED HEURISTIC COMBINATION,
not a trained classifier. This is an honest scope decision: we don't
have a labeled dataset of real social media posts with confirmed
manipulation/bot ground truth to train a proper fusion model against,
given the project timeline. The weights below are reasoned defaults,
not learned from data — worth revisiting with real labeled data later.
"""

import sys
from pathlib import Path

sys.path.append(str(Path(__file__).resolve().parents[2]))

from nunmai_social.features.text_features import extract_text_features
from nunmai_social.features.behavioral_features import extract_behavioral_features
from nunmai_social.model.image_classifier import NunmaiSocialImageClassifier

RISK_TIER_THRESHOLDS = {
    "SAFE": 0.30,
    "SUSPICIOUS": 0.70,
}

# Reasoned (not learned) weights for combining the three signal sources.
# Text and behavioral signals are weighted roughly equally since both are
# reasonably reliable rule-based/heuristic signals; image gets a lower
# weight specifically because it's frequently NOT_APPLICABLE (no face in
# most social posts) and shouldn't drag the score toward zero by default
# when it simply has nothing to say.
WEIGHT_TEXT = 0.4
WEIGHT_IMAGE = 0.3
WEIGHT_BEHAVIORAL = 0.3


class NunmaiSocialAnalyzer:
    """
    Combines text, image, and behavioral analysis into one verdict.
    Loads the image classifier ONCE at construction (expensive model load).
    """

    def __init__(self):
        self.image_classifier = NunmaiSocialImageClassifier()

    def _text_risk_score(self, text_features: dict) -> float:
        """
        Converts text_features.py's raw feature dict into a single 0-1
        risk score, using WEIGHTED signals rather than equal-weighted
        counting. Rationale (found via testing): urgency_financial_combo
        and personalization_financial_mismatch are strong, largely
        standalone red flags on their own — a scam post doesn't need to
        ALSO show LLM trope words or prompt-leakage artifacts to be
        genuinely manipulative. Equal-weighted counting under-scored a
        blatantly manipulative test case (urgency+financial language)
        down to 0.167 just because it didn't also happen to trip four
        unrelated signals.
        """
        weighted_signals = [
            (text_features.get("urgency_financial_combo", False), 0.35),
            (text_features.get("personalization_financial_mismatch", False), 0.35),
            (text_features.get("prompt_leakage_detected", False), 0.15),
            (text_features.get("out_of_band_excuse_count", 0) > 0, 0.10),
            (text_features.get("low_burstiness_flag", False), 0.03),
            (text_features.get("llm_trope_word_count", 0) > 2, 0.02),
        ]
        score = sum(weight for fired, weight in weighted_signals if fired)
        return min(score, 1.0)  # cap at 1.0 in case multiple strong signals stack

    def analyze_post(
        self,
        post_text: str,
        image_path: str | None = None,
        handle: str | None = None,
        bio_text: str | None = None,
        account_created_date: str | None = None,
        posts_per_day: float | None = None,
        followers: int | None = None,
        following: int | None = None,
    ) -> dict:
        """
        MAIN ENTRY POINT. Analyzes a social media post across all three
        dimensions and returns a fused verdict.
        """
        # --- Text analysis ---
        text_features = extract_text_features(post_text)
        text_risk = self._text_risk_score(text_features)

        # --- Image analysis (optional — only if an image is attached) ---
        image_result = None
        image_risk = 0.0
        image_weight_used = 0.0  # only count image toward fusion if applicable
        if image_path:
            image_result = self.image_classifier.classify_image(image_path)
            if image_result["applicable"]:
                image_risk = image_result["fake_probability"]
                image_weight_used = WEIGHT_IMAGE

        # --- Behavioral analysis ---
        behavioral_features = extract_behavioral_features(
            handle=handle, bio_text=bio_text, account_created_date=account_created_date,
            posts_per_day=posts_per_day, followers=followers, following=following,
        )
        behavioral_risk = min(behavioral_features["behavioral_red_flag_count"] / 5, 1.0)

        # --- Weighted fusion ---
        # Renormalize weights if image wasn't applicable, so its absence
        # doesn't just silently drag the score toward zero.
        total_weight = WEIGHT_TEXT + image_weight_used + WEIGHT_BEHAVIORAL
        fused_score = (
            (text_risk * WEIGHT_TEXT)
            + (image_risk * image_weight_used)
            + (behavioral_risk * WEIGHT_BEHAVIORAL)
        ) / total_weight

        if fused_score < RISK_TIER_THRESHOLDS["SAFE"]:
            risk_tier = "SAFE"
        elif fused_score < RISK_TIER_THRESHOLDS["SUSPICIOUS"]:
            risk_tier = "SUSPICIOUS"
        else:
            risk_tier = "MANIPULATIVE"

        return {
            "fused_risk_score": round(fused_score, 4),
            "risk_tier": risk_tier,
            "text_risk_score": round(text_risk, 4),
            "image_risk_score": round(image_risk, 4) if image_path else None,
            "image_applicable": image_result["applicable"] if image_result else None,
            "behavioral_risk_score": round(behavioral_risk, 4),
            "text_features": text_features,
            "behavioral_features": behavioral_features,
        }


# ------------------------------------------------------------------
# Quick manual test:
#   python nunmai_social\model\fusion.py
# ------------------------------------------------------------------
if __name__ == "__main__":
    from datetime import datetime, timedelta

    analyzer = NunmaiSocialAnalyzer()

    print("=" * 60)
    print("TEST: Manipulative post + suspicious account, no image")
    print("=" * 60)
    result = analyzer.analyze_post(
        post_text=(
            "This is a crucial opportunity, act now before it expires today. "
            "Send your payment details immediately to secure your allocation."
        ),
        handle="crypto_signals_4829173",
        bio_text="Guaranteed returns! DM for signals. 100x your portfolio!",
        account_created_date=(datetime.now() - timedelta(days=5)).strftime("%Y-%m-%d"),
        posts_per_day=45,
        followers=12,
        following=3000,
    )
    print(f"Fused risk score: {result['fused_risk_score']}")
    print(f"Risk tier: {result['risk_tier']}")
    print(f"Text risk: {result['text_risk_score']}")
    print(f"Behavioral risk: {result['behavioral_risk_score']}")

    print("\n" + "=" * 60)
    print("TEST: Normal post + genuine account, no image")
    print("=" * 60)
    result = analyzer.analyze_post(
        post_text="Markets were choppy today. IT stocks did well, banking lagged a bit.",
        handle="priya_invests",
        bio_text="Long-term investor. Views are my own, not financial advice.",
        account_created_date="2019-03-15",
        posts_per_day=1.2,
        followers=850,
        following=400,
    )
    print(f"Fused risk score: {result['fused_risk_score']}")
    print(f"Risk tier: {result['risk_tier']}")
    print(f"Text risk: {result['text_risk_score']}")
    print(f"Behavioral risk: {result['behavioral_risk_score']}")