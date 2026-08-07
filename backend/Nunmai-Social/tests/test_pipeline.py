"""
tests/test_pipeline.py
=======================
Test suite for NUNMAI-SOCIAL: fusion logic + FastAPI endpoint.

Mirrors the testing approach used across Mail/Vision/Voice: unit tests
on the core logic, plus API-level tests via FastAPI's TestClient.

The image classifier is mocked throughout — it wraps a pretrained
SigLIP2 model (same one Vision uses), which is expensive to load and
already covered by Vision's own test suite. These tests exist to
validate SOCIAL's fusion/API layer, not re-validate the underlying
model.

Run with:
    pytest nunmai_social/tests/test_pipeline.py -v
"""

import sys
from pathlib import Path
from datetime import datetime, timedelta
from unittest.mock import patch, MagicMock

import pytest
from fastapi.testclient import TestClient

sys.path.append(str(Path(__file__).resolve().parents[2]))


# ---------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------

@pytest.fixture
def mock_image_classifier():
    """
    Patches NunmaiSocialImageClassifier so no real model load/inference
    happens during these tests. Patched at the point of use (fusion.py's
    import), not at its definition, per standard mocking practice.
    """
    with patch("nunmai_social.model.fusion.NunmaiSocialImageClassifier") as mock_cls:
        mock_instance = MagicMock()
        mock_cls.return_value = mock_instance
        yield mock_instance


@pytest.fixture
def analyzer(mock_image_classifier):
    from nunmai_social.model.fusion import NunmaiSocialAnalyzer
    return NunmaiSocialAnalyzer()


@pytest.fixture
def client(mock_image_classifier):
    """
    TestClient for main.py. Patches the image classifier BEFORE main.py
    is imported, since main.py instantiates NunmaiSocialAnalyzer (which
    loads the image classifier) at module load time.
    """
    with patch("nunmai_social.model.fusion.NunmaiSocialImageClassifier") as mock_cls:
        mock_cls.return_value = MagicMock()
        from nunmai_social.api.main import app
        yield TestClient(app)


# ---------------------------------------------------------------------
# Fusion logic — text risk scoring
# ---------------------------------------------------------------------

class TestTextRiskScore:

    def test_urgency_financial_combo_alone_scores_meaningfully(self, analyzer):
        """
        Regression test for the exact bug documented in fusion.py's
        docstring: a strong standalone signal (urgency + financial combo)
        should NOT be diluted down near-zero just because it doesn't also
        trip four unrelated signals. This was previously 0.167 under
        equal-weighted counting; weighted scoring should put it well
        above the SAFE threshold (0.30) on its own.
        """
        features = {
            "urgency_financial_combo": True,
            "personalization_financial_mismatch": False,
            "prompt_leakage_detected": False,
            "out_of_band_excuse_count": 0,
            "low_burstiness_flag": False,
            "llm_trope_word_count": 0,
        }
        score = analyzer._text_risk_score(features)
        assert score == pytest.approx(0.35)
        assert score >= 0.30  # clears SAFE threshold on this signal alone

    def test_no_signals_scores_zero(self, analyzer):
        features = {
            "urgency_financial_combo": False,
            "personalization_financial_mismatch": False,
            "prompt_leakage_detected": False,
            "out_of_band_excuse_count": 0,
            "low_burstiness_flag": False,
            "llm_trope_word_count": 0,
        }
        assert analyzer._text_risk_score(features) == 0.0

    def test_all_signals_capped_at_one(self, analyzer):
        """Stacking every signal should cap at 1.0, not overflow past it."""
        features = {
            "urgency_financial_combo": True,
            "personalization_financial_mismatch": True,
            "prompt_leakage_detected": True,
            "out_of_band_excuse_count": 3,
            "low_burstiness_flag": True,
            "llm_trope_word_count": 5,
        }
        score = analyzer._text_risk_score(features)
        assert score == 1.0

    def test_missing_keys_default_safely(self, analyzer):
        """An empty/partial feature dict shouldn't raise — .get() defaults apply."""
        score = analyzer._text_risk_score({})
        assert score == 0.0


# ---------------------------------------------------------------------
# Fusion logic — full analyze_post, no image
# ---------------------------------------------------------------------

class TestAnalyzePostNoImage:

    def test_manipulative_post_flags_high_risk(self, analyzer):
        """The exact 'suspicious crypto account' scenario from fusion.py's
        own manual test — should NOT land in SAFE."""
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
        assert result["risk_tier"] in ("SUSPICIOUS", "MANIPULATIVE")
        assert result["fused_risk_score"] > 0.30

    def test_normal_post_flags_safe(self, analyzer):
        result = analyzer.analyze_post(
            post_text="Markets were choppy today. IT stocks did well, banking lagged a bit.",
            handle="priya_invests",
            bio_text="Long-term investor. Views are my own, not financial advice.",
            account_created_date="2019-03-15",
            posts_per_day=1.2,
            followers=850,
            following=400,
        )
        assert result["risk_tier"] == "SAFE"

    def test_no_image_fields_are_none(self, analyzer):
        """When no image is submitted, image_risk_score/image_applicable
        should be None, not 0.0/False — distinguishes 'not analyzed' from
        'analyzed and found safe'."""
        result = analyzer.analyze_post(post_text="Just a normal update.")
        assert result["image_risk_score"] is None
        assert result["image_applicable"] is None

    def test_fusion_ignores_image_weight_when_absent(self, analyzer):
        """With no image, total_weight should renormalize to just
        text+behavioral — i.e. fused_score shouldn't be silently
        depressed by a phantom image_weight of 0 in the numerator only."""
        result = analyzer.analyze_post(
            post_text=(
                "This is a crucial opportunity, act now before it expires today. "
                "Send your payment details immediately."
            ),
        )
        # text_risk alone (urgency_financial_combo fires) = 0.35, behavioral = 0
        # renormalized over (WEIGHT_TEXT + WEIGHT_BEHAVIORAL) = 0.7
        expected = (0.35 * 0.4) / 0.7
        assert result["fused_risk_score"] == pytest.approx(expected, abs=0.01)


# ---------------------------------------------------------------------
# Fusion logic — with image (mocked classifier)
# ---------------------------------------------------------------------

class TestAnalyzePostWithImage:

    def test_applicable_fake_image_raises_risk(self, analyzer, mock_image_classifier):
        mock_image_classifier.classify_image.return_value = {
            "applicable": True,
            "fake_probability": 0.95,
        }
        result = analyzer.analyze_post(
            post_text="Neutral market commentary here.",
            image_path="/fake/path/to/image.jpg",
        )
        assert result["image_applicable"] is True
        assert result["image_risk_score"] == pytest.approx(0.95)
        assert result["fused_risk_score"] > 0.0

    def test_not_applicable_image_does_not_drag_score_to_zero(self, analyzer, mock_image_classifier):
        """
        Regression test for the exact bug documented in the codebase:
        a NOT_APPLICABLE image (no face detected) should be excluded
        from fusion entirely via renormalization, not silently pull the
        score toward 0 as if it were confirmed 'safe'.
        """
        mock_image_classifier.classify_image.return_value = {
            "applicable": False,
            "fake_probability": 0.0,
        }
        manipulative_text = (
            "This is a crucial opportunity, act now before it expires today. "
            "Send your payment details immediately."
        )
        with_image = analyzer.analyze_post(post_text=manipulative_text, image_path="/fake/graphic.jpg")
        without_image = analyzer.analyze_post(post_text=manipulative_text)

        # Same underlying signal, image just not applicable either way —
        # fused scores should match (image weight properly excluded, not
        # counted as 0.0 fake_probability against full weight).
        assert with_image["fused_risk_score"] == pytest.approx(without_image["fused_risk_score"])
        assert with_image["image_applicable"] is False

    def test_image_path_provided_but_classifier_returns_none_applicable_key_missing(self, analyzer, mock_image_classifier):
        """Defensive: classifier result missing expected keys shouldn't crash analyze_post silently mid-fusion."""
        mock_image_classifier.classify_image.return_value = {"applicable": False}
        result = analyzer.analyze_post(post_text="Some post.", image_path="/fake/image.jpg")
        assert result["image_applicable"] is False


# ---------------------------------------------------------------------
# Risk tier boundaries
# ---------------------------------------------------------------------

class TestRiskTierThresholds:

    @pytest.mark.parametrize("score,expected_tier", [
        (0.0, "SAFE"),
        (0.29, "SAFE"),
        (0.30, "SUSPICIOUS"),   # boundary: SAFE threshold is exclusive upper bound
        (0.69, "SUSPICIOUS"),
        (0.70, "MANIPULATIVE"),  # boundary: SUSPICIOUS threshold is exclusive upper bound
        (1.0, "MANIPULATIVE"),
    ])
    def test_tier_boundaries(self, analyzer, score, expected_tier):
        from nunmai_social.model.fusion import RISK_TIER_THRESHOLDS
        if score < RISK_TIER_THRESHOLDS["SAFE"]:
            tier = "SAFE"
        elif score < RISK_TIER_THRESHOLDS["SUSPICIOUS"]:
            tier = "SUSPICIOUS"
        else:
            tier = "MANIPULATIVE"
        assert tier == expected_tier


# ---------------------------------------------------------------------
# API layer — /scan-post
# ---------------------------------------------------------------------

class TestScanPostEndpoint:

    def test_root_endpoint(self, client):
        response = client.get("/")
        assert response.status_code == 200
        assert response.json()["service"] == "NUNMAI-SOCIAL"

    def test_scan_post_text_only(self, client):
        response = client.post(
            "/scan-post",
            data={"post_text": "Markets were flat today."},
        )
        assert response.status_code == 200
        body = response.json()
        assert "fused_risk_score" in body
        assert "risk_tier" in body
        assert body["image_risk_score"] is None
        assert body["image_applicable"] is None

    def test_scan_post_missing_required_field_returns_422(self, client):
        """post_text is a required Form field — omitting it should fail
        FastAPI's own validation before reaching the analyzer."""
        response = client.post("/scan-post", data={"handle": "someone"})
        assert response.status_code == 422

    def test_scan_post_rejects_disallowed_file_extension(self, client):
        response = client.post(
            "/scan-post",
            data={"post_text": "Check this out"},
            files={"image": ("malicious.exe", b"not an image", "application/octet-stream")},
        )
        assert response.status_code == 400
        assert "Unsupported image type" in response.json()["detail"]

    def test_scan_post_rejects_oversized_image(self, client):
        oversized = b"0" * (20 * 1024 * 1024 + 1)  # 1 byte over MAX_UPLOAD_SIZE_BYTES
        response = client.post(
            "/scan-post",
            data={"post_text": "Check this image"},
            files={"image": ("big.jpg", oversized, "image/jpeg")},
        )
        assert response.status_code == 413

    def test_scan_post_accepts_valid_image(self, client, mock_image_classifier):
        mock_image_classifier.classify_image.return_value = {
            "applicable": True,
            "fake_probability": 0.4,
        }
        response = client.post(
            "/scan-post",
            data={"post_text": "Check this image"},
            files={"image": ("photo.jpg", b"\xff\xd8\xff\xe0fakejpegbytes", "image/jpeg")},
        )
        assert response.status_code == 200
        assert response.json()["image_applicable"] is True

    def test_scan_post_with_full_account_metadata(self, client):
        response = client.post(
            "/scan-post",
            data={
                "post_text": "Guaranteed 100x returns, DM now!",
                "handle": "scam_account_9182",
                "bio_text": "Guaranteed returns!",
                "account_created_date": "2026-07-01",
                "posts_per_day": "50",
                "followers": "3",
                "following": "5000",
            },
        )
        assert response.status_code == 200
        body = response.json()
        assert body["behavioral_risk_score"] is not None

    def test_scan_post_analyzer_exception_returns_400(self, client, analyzer_patch=None):
        """If analyze_post raises unexpectedly, the API should surface a
        400 with a clear message rather than a raw 500 traceback."""
        with patch("nunmai_social.api.main.analyzer.analyze_post", side_effect=ValueError("boom")):
            response = client.post("/scan-post", data={"post_text": "test"})
            assert response.status_code == 400
            assert "Failed to process post" in response.json()["detail"]


if __name__ == "__main__":
    pytest.main([__file__, "-v"])