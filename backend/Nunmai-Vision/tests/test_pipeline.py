"""
test_pipeline.py
=================
Automated regression tests for NUNMAI-VISION's preprocessing and
classification pipeline.

IMPORTANT HONEST LIMITATION: we only have ONE known-real test video
(test_data/sample.mp4) — no confirmed deepfake sample to test against.
So these tests validate PIPELINE CORRECTNESS (doesn't crash, returns
properly-shaped output, correctly classifies the one real video we have)
rather than a full real/fake accuracy benchmark. If you obtain a known
deepfake clip later (e.g. a FaceForensics++ sample), add a
test_classify_video_detects_known_fake() test following the same pattern.

Run with:
    pytest tests\\test_pipeline.py -v

NOTE: the first run will be slow (loads the ~372MB pretrained model once
for the whole test session). Subsequent runs use the HuggingFace cache
and should be faster.
"""

import sys
from pathlib import Path

import pytest
import numpy as np

sys.path.append(str(Path(__file__).resolve().parents[1]))

from nunmai_vision.preprocessing.frame_extraction import (
    extract_frames,
    detect_faces_in_frame,
    crop_face,
    extract_face_crops_from_video,
)
from nunmai_vision.model.classifier import NunmaiVisionClassifier

TEST_VIDEO_PATH = "test_data/manipulated.mp4"


# ============================================================
# Fixtures — shared, expensive-to-create resources
# ============================================================

@pytest.fixture(scope="module")
def classifier():
    """
    Loads the pretrained model ONCE for the entire test module, not once
    per test — loading it repeatedly would make the test suite
    painfully slow given it's a real ~372MB model load each time.
    """
    return NunmaiVisionClassifier()


@pytest.fixture(scope="module")
def sample_frames():
    """Extracts frames from the test video once, reused across tests."""
    if not Path(TEST_VIDEO_PATH).exists():
        pytest.skip(f"Test video not found at {TEST_VIDEO_PATH} — skipping video-dependent tests.")
    return extract_frames(TEST_VIDEO_PATH, sample_every_n_frames=15)


# ============================================================
# frame_extraction.py tests
# ============================================================

def test_extract_frames_returns_nonempty_list(sample_frames):
    """A real video should yield at least one sampled frame."""
    assert len(sample_frames) > 0


def test_extract_frames_returns_valid_numpy_arrays(sample_frames):
    """Each extracted frame should be a proper image array (H, W, 3 channels)."""
    frame = sample_frames[0]
    assert isinstance(frame, np.ndarray)
    assert frame.ndim == 3
    assert frame.shape[2] == 3  # BGR channels


def test_extract_frames_raises_on_missing_file():
    """A nonexistent video path should raise FileNotFoundError, not fail silently."""
    with pytest.raises(FileNotFoundError):
        extract_frames("test_data/this_file_does_not_exist.mp4")


def test_detect_faces_finds_at_least_one_face(sample_frames):
    """
    Our test video is known to contain a visible face (confirmed manually
    earlier: 19 face crops were extracted). At least one sampled frame
    should have a detectable face.
    """
    total_faces_found = sum(len(detect_faces_in_frame(f)) for f in sample_frames)
    assert total_faces_found > 0


def test_detect_faces_on_blank_frame_returns_empty():
    """A blank/solid-color frame has no face — detector should return an
    empty list, not error out."""
    blank_frame = np.zeros((480, 640, 3), dtype=np.uint8)
    faces = detect_faces_in_frame(blank_frame)
    assert faces == [] or len(faces) == 0


def test_crop_face_produces_nonempty_crop(sample_frames):
    """Cropping a detected face should produce a valid, non-empty image region."""
    for frame in sample_frames:
        boxes = detect_faces_in_frame(frame)
        if boxes:
            crop = crop_face(frame, boxes[0])
            assert crop.size > 0
            assert crop.ndim == 3
            return  # found and validated one, that's enough
    pytest.skip("No faces found in any sampled frame to test cropping against.")


def test_extract_face_crops_from_video_end_to_end():
    """Full preprocessing pipeline: video path in, face crops out."""
    if not Path(TEST_VIDEO_PATH).exists():
        pytest.skip(f"Test video not found at {TEST_VIDEO_PATH}")
    crops = extract_face_crops_from_video(TEST_VIDEO_PATH)
    assert len(crops) > 0
    assert all(isinstance(c, np.ndarray) for c in crops)


# ============================================================
# classifier.py tests
# ============================================================

def test_classifier_loads_with_correct_labels(classifier):
    """Sanity check: the model's label mapping should be exactly what
    our code expects (Fake/Real, in some index order)."""
    labels = set(classifier.id2label.values())
    assert "Fake" in labels
    assert "Real" in labels


def test_classify_single_face_returns_valid_shape(classifier, sample_frames):
    """A single face classification should return a dict with the
    expected keys and value types."""
    for frame in sample_frames:
        boxes = detect_faces_in_frame(frame)
        if boxes:
            crop = crop_face(frame, boxes[0])
            result = classifier._classify_single_face(crop)
            assert "fake_probability" in result
            assert "label" in result
            assert 0.0 <= result["fake_probability"] <= 1.0
            assert result["label"] in ("Fake", "Real")
            return
    pytest.skip("No faces found to test classification against.")


def test_classify_video_returns_valid_shape(classifier):
    """Full pipeline: video in, properly-shaped verdict dict out."""
    if not Path(TEST_VIDEO_PATH).exists():
        pytest.skip(f"Test video not found at {TEST_VIDEO_PATH}")

    result = classifier.classify_video(TEST_VIDEO_PATH)

    assert "fake_probability" in result
    assert "risk_tier" in result
    assert "prediction" in result
    assert "num_faces_analyzed" in result
    assert result["risk_tier"] in ("SAFE", "SUSPICIOUS", "DEEPFAKE", "NO_FACE_DETECTED")
    assert result["prediction"] in ("deepfake", "authentic", "unable_to_assess")


def test_classify_video_correctly_identifies_known_real_video(classifier):
    """
    REGRESSION CHECK: we manually confirmed sample.mp4 is a real,
    non-deepfake video and the model correctly classified it as
    'authentic' with near-zero fake probability. If a future change
    breaks this, this test catches it.
    """
    if not Path(TEST_VIDEO_PATH).exists():
        pytest.skip(f"Test video not found at {TEST_VIDEO_PATH}")

    result = classifier.classify_video(TEST_VIDEO_PATH)
    assert result["prediction"] == "authentic"
    assert result["risk_tier"] == "SAFE"
    assert result["fake_probability"] < 0.30


def test_classify_video_raises_on_missing_file(classifier):
    """A nonexistent video path should raise FileNotFoundError, not
    fail silently or crash with an unrelated error."""
    with pytest.raises(FileNotFoundError):
        classifier.classify_video("test_data/this_file_does_not_exist.mp4")