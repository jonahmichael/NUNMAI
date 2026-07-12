"""
classifier.py
==============
Wraps a PRETRAINED deepfake-detection model (SigLIP2-based, from
HuggingFace) for use in the NUNMAI-VISION pipeline.

WHY A PRETRAINED MODEL RATHER THAN TRAINING FROM SCRATCH: training a
real CNN-LSTM deepfake detector from zero requires large video datasets
(FaceForensics++, DFDC — many GB, hours of download) and substantial
training time (hours to days). Given the project timeline, we use an
existing, actively-maintained pretrained image classifier instead
(prithivMLmods/Deepfake-Detect-Siglip2, a 2025 SigLIP2-based model) and
apply it per-frame, aggregating results across a video. This is an
honest simplification: it captures the SPATIAL half of the architecture
diagram's "CNN Spatial Features" step, but does NOT include the
diagram's LSTM Temporal Features step (blinking/lip-sync/motion analysis
across time) — that would require training our own temporal model.

MODEL CHOICE NOTE: we deliberately avoided the older, more-cited
dima806/deepfake_vs_real_image_detection model, since its own model card
explicitly warns it's ~3 years stale against newer generation techniques
(known "concept drift"). Deepfake-Detect-Siglip2 is a more recent (2025)
alternative.
"""

import sys
from pathlib import Path
from collections import Counter
import statistics
import torch
from PIL import Image
from transformers import AutoImageProcessor, SiglipForImageClassification
import numpy as np
import cv2

sys.path.append(str(Path(__file__).resolve().parents[2]))

from nunmai_vision.preprocessing.frame_extraction import extract_face_crops_from_video

MODEL_NAME = "prithivMLmods/Deepfake-Detect-Siglip2"

# Risk tier thresholds for the aggregated video-level verdict — same
# pattern as NUNMAI-MAIL's classifier.py, for consistency across modules.
RISK_TIER_THRESHOLDS = {
    "SAFE": 0.30,
    "SUSPICIOUS": 0.70,
}


class NunmaiVisionClassifier:
    """
    Loads the pretrained SigLIP2 deepfake classifier ONCE (expensive —
    downloads/loads model weights) and reuses it for many predictions.
    Instantiate this ONCE at API startup, not per-request.
    """

    def __init__(self, model_name: str = MODEL_NAME):
        print(f"Loading pretrained model '{model_name}' (first run downloads weights, may take a while)...")
        self.processor = AutoImageProcessor.from_pretrained(model_name)
        self.model = SiglipForImageClassification.from_pretrained(model_name)
        self.model.eval()  # inference mode, not training mode
        self.id2label = self.model.config.id2label
        print("Model loaded. Labels:", self.id2label)

    def _classify_single_face(self, face_crop_bgr) -> dict:
        """
        Classifies ONE face crop (OpenCV BGR numpy array) as real/fake.

        Returns: {"fake_probability": float, "label": str}
        """
        # Convert OpenCV's BGR format to RGB (PIL/transformers expect RGB)
        face_rgb = cv2.cvtColor(face_crop_bgr, cv2.COLOR_BGR2RGB)
        pil_image = Image.fromarray(face_rgb)

        inputs = self.processor(images=pil_image, return_tensors="pt")
        with torch.no_grad():
            outputs = self.model(**inputs)
            probs = torch.nn.functional.softmax(outputs.logits, dim=1).squeeze().tolist()

        # id2label maps {0: "Fake", 1: "Real"} per this model's config —
        # we look up dynamically rather than hardcoding the index, in
        # case a different model with a different label order is swapped
        # in later.
        label_probs = {self.id2label[i]: probs[i] for i in range(len(probs))}
        fake_probability = label_probs.get("Fake", label_probs.get("fake", 0.0))
        predicted_label = max(label_probs, key=label_probs.get)

        return {"fake_probability": float(fake_probability), "label": predicted_label}

    def classify_video(self, video_path: str, sample_every_n_frames: int = 15) -> dict:
        """
        MAIN ENTRY POINT. Takes a video file path, extracts face crops,
        classifies each one, and aggregates into a single video-level
        verdict.

        AGGREGATION STRATEGY: we average the TOP-3 highest fake-probability
        scores across all analyzed faces (not a pure max, not a pure
        average). Rationale: a pure MAX was found in testing to be too
        fragile — a single noisy or oddly-decoded frame could flip an
        otherwise-clean video's verdict entirely on its own. Averaging
        the top few scores keeps the intent of "flag videos that look
        fake in multiple frames, not diluted by many easy ones" while
        requiring more than one outlier before the verdict flips.

        Returns:
            {
                "fake_probability": float (0-1, the aggregated video-level score),
                "risk_tier": "SAFE" | "SUSPICIOUS" | "PHISHING"-equivalent i.e. "DEEPFAKE",
                "prediction": "deepfake" | "authentic",
                "num_faces_analyzed": int,
                "num_frames_sampled": int,
                "per_face_results": [ {"fake_probability": float, "label": str}, ... ],
            }
        """
        face_crops = extract_face_crops_from_video(video_path, sample_every_n_frames)

        if not face_crops:
            # No faces detected at all — can't make a deepfake determination.
            # This is an important honest edge case: a video with no visible
            # face (e.g. screen recording, landscape footage) simply isn't
            # something this module can assess.
            return {
                "fake_probability": 0.0,
                "risk_tier": "NO_FACE_DETECTED",
                "prediction": "unable_to_assess",
                "num_faces_analyzed": 0,
                "num_frames_sampled": 0,
                "per_face_results": [],
            }

        per_face_results = [self._classify_single_face(crop) for crop in face_crops]
        fake_probabilities = [r["fake_probability"] for r in per_face_results]

        # AGGREGATION: MEDIAN of all per-face fake-probability scores.
        #
        # History: we started with MAX (too fragile — one noisy/badly-
        # cropped frame could flip the whole video's verdict), then tried
        # averaging the top-3 (better, but a single strong outlier could
        # still drag the average across a risk-tier threshold — observed
        # directly in testing: one oddly-cropped frame scored 0.999995
        # "fake" while 14 other frames scored near-zero, and top-3
        # averaging still produced a false SUSPICIOUS result).
        #
        # MEDIAN solves this properly: with more than a couple of faces
        # analyzed, a single outlier crop cannot move the median at all
        # (more than half the values would need to be high for the
        # median itself to shift). This correctly ignores one-off
        # detector noise while still catching genuine deepfakes, where
        # manipulation artifacts typically appear across MANY frames,
        # not just one — a real deepfake would still push the median up.
        #
        # A proper temporal model (LSTM layer, deferred per project
        # scope — see architecture diagram) would handle frame-to-frame
        # consistency even more rigorously than this statistical
        # aggregation can.
        aggregated_fake_probability = statistics.median(fake_probabilities)

        if aggregated_fake_probability < RISK_TIER_THRESHOLDS["SAFE"]:
            risk_tier = "SAFE"
        elif aggregated_fake_probability < RISK_TIER_THRESHOLDS["SUSPICIOUS"]:
            risk_tier = "SUSPICIOUS"
        else:
            risk_tier = "DEEPFAKE"

        prediction = "deepfake" if aggregated_fake_probability >= 0.5 else "authentic"

        return {
            "fake_probability": round(aggregated_fake_probability, 4),
            "risk_tier": risk_tier,
            "prediction": prediction,
            "num_faces_analyzed": len(face_crops),
            "num_frames_sampled": len(face_crops),  # each crop came from one sampled frame
            "per_face_results": per_face_results,
        }


# ------------------------------------------------------------------
# Quick manual test — run this file directly against your test video:
#   python nunmai_vision\model\classifier.py
# ------------------------------------------------------------------
if __name__ == "__main__":
    clf = NunmaiVisionClassifier()

    test_video_path = "test_data/sample.mp4"
    print(f"\nAnalyzing: {test_video_path}")
    result = clf.classify_video(test_video_path)

    print(f"\nPrediction: {result['prediction']}")
    print(f"Fake probability: {result['fake_probability']}")
    print(f"Risk tier: {result['risk_tier']}")
    print(f"Faces analyzed: {result['num_faces_analyzed']}")
    print("\nPer-face breakdown (first 5):")
    for i, face_result in enumerate(result["per_face_results"][:5]):
        print(f"  Face {i+1}: {face_result}")