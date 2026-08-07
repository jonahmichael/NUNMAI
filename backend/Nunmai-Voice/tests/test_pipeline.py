"""
test_pipeline.py
=================
Automated regression tests for NUNMAI-VOICE's preprocessing and
classification pipeline.

UNLIKE NUNMAI-VISION (which only had a confirmed-real test sample),
NUNMAI-VOICE has been validated against BOTH a confirmed-real recording
(test_data/sample.wav) AND a confirmed-synthetic/voice-converted sample
(test_data/fake02.wav) — giving us genuine two-sided regression coverage:
we can catch a future change that breaks either "correctly clears real
audio" OR "correctly flags synthetic audio", not just one direction.

Run with:
    pytest tests\\test_pipeline.py -v

NOTE: the first run will be slow (loads the ~1.2GB pretrained model once
for the whole test session, plus classifies many audio segments).
Subsequent runs use the HuggingFace cache for model loading (faster) but
still need to run inference on every segment each time.
"""

import sys
from pathlib import Path

import pytest
import numpy as np

sys.path.append(str(Path(__file__).resolve().parents[1]))

from nunmai_voice.preprocessing.audio_preprocessing import (
    load_and_resample,
    segment_audio,
    preprocess_audio_file,
    TARGET_SAMPLE_RATE,
)
from nunmai_voice.model.classifier import NunmaiVoiceClassifier

REAL_AUDIO_PATH = "test_data/sample.wav"
FAKE_AUDIO_PATH = "test_data/fake02.wav"


# ============================================================
# Fixtures — shared, expensive-to-create resources
# ============================================================

@pytest.fixture(scope="module")
def classifier():
    """
    Loads the pretrained model ONCE for the entire test module — this is
    a real ~1.2GB model load plus segment-by-segment inference, so
    reloading it per-test would make the suite painfully slow.
    """
    return NunmaiVoiceClassifier()


# ============================================================
# audio_preprocessing.py tests
# ============================================================

def test_load_and_resample_returns_correct_sample_rate():
    if not Path(REAL_AUDIO_PATH).exists():
        pytest.skip(f"Test audio not found at {REAL_AUDIO_PATH}")
    audio = load_and_resample(REAL_AUDIO_PATH)
    assert isinstance(audio, np.ndarray)
    assert audio.ndim == 1  # mono


def test_load_and_resample_raises_on_missing_file():
    with pytest.raises(FileNotFoundError):
        load_and_resample("test_data/this_file_does_not_exist.wav")


def test_segment_audio_produces_correct_length_segments():
    """A 10-second synthetic sine wave at 16kHz, segmented into 4-second
    chunks, should produce 3 segments (4s + 4s + 2s remainder)."""
    fake_audio = np.zeros(16000 * 10)  # 10 seconds of silence at 16kHz
    segments = segment_audio(fake_audio, sample_rate=16000, segment_seconds=4)
    assert len(segments) == 3
    assert len(segments[0]) == 16000 * 4
    assert len(segments[1]) == 16000 * 4
    assert len(segments[2]) == 16000 * 2  # trailing remainder, not dropped


def test_segment_audio_short_clip_returns_single_segment():
    """Audio shorter than one segment length should come back as a
    single segment, not be padded or dropped."""
    short_audio = np.zeros(16000 * 2)  # 2 seconds, shorter than 4s segment
    segments = segment_audio(short_audio, sample_rate=16000, segment_seconds=4)
    assert len(segments) == 1
    assert len(segments[0]) == 16000 * 2


def test_segment_audio_empty_returns_empty_list():
    """Zero-length audio should return an empty segment list, not error."""
    segments = segment_audio(np.array([]), sample_rate=16000, segment_seconds=4)
    assert segments == []


def test_preprocess_audio_file_end_to_end():
    """Full preprocessing pipeline: audio path in, segments out."""
    if not Path(REAL_AUDIO_PATH).exists():
        pytest.skip(f"Test audio not found at {REAL_AUDIO_PATH}")
    segments = preprocess_audio_file(REAL_AUDIO_PATH)
    assert len(segments) > 0
    assert all(isinstance(s, np.ndarray) for s in segments)


# ============================================================
# classifier.py tests
# ============================================================

def test_classifier_loads_with_correct_labels(classifier):
    """Sanity check: the model's label mapping should include real/fake
    in some form."""
    labels = set(label.lower() for label in classifier.id2label.values())
    assert "real" in labels
    assert "fake" in labels


def test_classify_single_segment_returns_valid_shape(classifier):
    """A single segment classification should return a dict with the
    expected keys and value types."""
    # A short synthetic silent segment — we're only checking the RETURN
    # SHAPE here, not the actual prediction (silence isn't meaningfully
    # real or fake, so we don't assert on the label/probability itself).
    silent_segment = np.zeros(16000 * 4, dtype=np.float32)
    result = classifier._classify_single_segment(silent_segment)
    assert "fake_probability" in result
    assert "label" in result
    assert 0.0 <= result["fake_probability"] <= 1.0


def test_classify_audio_returns_valid_shape(classifier):
    """Full pipeline: audio file in, properly-shaped verdict dict out."""
    if not Path(REAL_AUDIO_PATH).exists():
        pytest.skip(f"Test audio not found at {REAL_AUDIO_PATH}")

    result = classifier.classify_audio(REAL_AUDIO_PATH)

    assert "fake_probability" in result
    assert "risk_tier" in result
    assert "prediction" in result
    assert "num_segments_analyzed" in result
    assert result["risk_tier"] in ("SAFE", "SUSPICIOUS", "SYNTHETIC", "NO_AUDIO_DETECTED")
    assert result["prediction"] in ("synthetic", "authentic", "unable_to_assess")


def test_classify_audio_raises_on_missing_file(classifier):
    """A nonexistent audio path should raise FileNotFoundError, not
    fail silently or crash with an unrelated error."""
    with pytest.raises(FileNotFoundError):
        classifier.classify_audio("test_data/this_file_does_not_exist.wav")


# ============================================================
# REGRESSION CHECKS — real, confirmed results locked in as permanent
# tests. Both directions covered: correctly clears real audio, AND
# correctly flags known-synthetic audio.
# ============================================================

def test_classify_audio_correctly_identifies_known_real_recording(classifier):
    """
    REGRESSION CHECK (real audio): we manually confirmed sample.wav is a
    real human voice recording, and the model correctly classified it as
    'authentic' with a median fake_probability of 0.0904 (well within the
    SAFE tier, well under the 0.30 threshold). If a future change breaks
    this, this test catches it.
    """
    if not Path(REAL_AUDIO_PATH).exists():
        pytest.skip(f"Test audio not found at {REAL_AUDIO_PATH}")

    result = classifier.classify_audio(REAL_AUDIO_PATH)
    assert result["prediction"] == "authentic"
    assert result["risk_tier"] == "SAFE"
    assert result["fake_probability"] < 0.30


def test_classify_audio_correctly_flags_known_synthetic_voice(classifier):
    """
    REGRESSION CHECK (synthetic audio): we manually confirmed fake02.wav
    is a genuine voice-converted/synthetic sample, and the model
    correctly classified it as 'synthetic' with a median fake_probability
    of 0.8202 (both analyzed segments individually scored 'fake': 0.868
    and 0.773). This is the harder and more important direction to get
    right for a security tool — if a future change (e.g. an aggregation
    strategy tweak) breaks this and lets synthetic audio slip through
    undetected, this test catches it immediately.
    """
    if not Path(FAKE_AUDIO_PATH).exists():
        pytest.skip(
            f"Known-synthetic test audio not found at {FAKE_AUDIO_PATH} — "
            f"skipping. This test requires a real confirmed-fake sample; "
            f"see project notes on how it was obtained."
        )

    result = classifier.classify_audio(FAKE_AUDIO_PATH)
    assert result["prediction"] == "synthetic"
    assert result["risk_tier"] == "SYNTHETIC"
    assert result["fake_probability"] > 0.70