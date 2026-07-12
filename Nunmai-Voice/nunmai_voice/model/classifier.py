"""
classifier.py
==============
Wraps a PRETRAINED deepfake voice classifier (Wav2Vec2-XLSR-based, from
HuggingFace) for use in the NUNMAI-VOICE pipeline.

WHY A PRETRAINED MODEL: same reasoning as NUNMAI-VISION — training a
real CNN-LSTM voice spoofing detector from scratch requires large labeled
datasets (ASVspoof, WaveFake) and substantial training time. Given the
project timeline, we use an existing pretrained model
(Gustking/wav2vec2-large-xlsr-deepfake-audio-classification) instead.

MODEL CHOICE NOTE: Wav2Vec2-XLSR is pretrained across 53 languages,
which matters for a securities-market context where calls may happen in
Hindi, Tamil, or other Indian languages alongside English — a
language-specific model would be a real limitation here.

AGGREGATION: we use MEDIAN across audio segments, not MAX — applying the
lesson learned directly from NUNMAI-VISION's debugging cycle, where MAX
aggregation proved too fragile (a single noisy/outlier frame could flip
an entire video's verdict). The same risk applies here: a brief loud
noise, a cough, or an audio-encoding artifact in one 4-second segment
could produce a spurious high "fake" score. Median requires more than
half of the analyzed segments to genuinely look synthetic before the
overall verdict flips — much more robust to single-segment noise while
still catching audio that's synthetic throughout most of its duration.
"""

import sys
import statistics
from pathlib import Path

import torch
import numpy as np
from transformers import AutoModelForAudioClassification, AutoFeatureExtractor

sys.path.append(str(Path(__file__).resolve().parents[2]))

from nunmai_voice.preprocessing.audio_preprocessing import preprocess_audio_file, TARGET_SAMPLE_RATE

MODEL_NAME = "Gustking/wav2vec2-large-xlsr-deepfake-audio-classification"

RISK_TIER_THRESHOLDS = {
    "SAFE": 0.30,
    "SUSPICIOUS": 0.70,
}


class NunmaiVoiceClassifier:
    """
    Loads the pretrained Wav2Vec2 deepfake-voice classifier ONCE
    (expensive — downloads/loads model weights) and reuses it for many
    predictions. Instantiate this ONCE at API startup, not per-request.
    """

    def __init__(self, model_name: str = MODEL_NAME):
        print(f"Loading pretrained model '{model_name}' (first run downloads weights, may take a while)...")
        self.feature_extractor = AutoFeatureExtractor.from_pretrained(model_name)
        self.model = AutoModelForAudioClassification.from_pretrained(model_name)
        self.model.eval()  # inference mode, not training mode
        self.id2label = self.model.config.id2label
        print("Model loaded. Labels:", self.id2label)

    def _classify_single_segment(self, audio_segment: np.ndarray) -> dict:
        """
        Classifies ONE audio segment (numpy array, 16kHz mono) as
        real/fake.

        Returns: {"fake_probability": float, "label": str}
        """
        inputs = self.feature_extractor(
            audio_segment, sampling_rate=TARGET_SAMPLE_RATE, return_tensors="pt"
        )
        with torch.no_grad():
            outputs = self.model(**inputs)
            probs = torch.nn.functional.softmax(outputs.logits, dim=1).squeeze().tolist()

        # Handle the edge case where squeeze() collapses a single-value
        # tensor into a plain float rather than a list (can happen with
        # certain model configs) — normalize to a list either way.
        if isinstance(probs, float):
            probs = [1 - probs, probs]

        label_probs = {self.id2label[i]: probs[i] for i in range(len(probs))}

        # Label names vary by model checkpoint conventions — check
        # several common variants rather than hardcoding one exact string.
        fake_probability = None
        for key in ("fake", "Fake", "spoof", "Spoof", "FAKE", "1"):
            if key in label_probs:
                fake_probability = label_probs[key]
                break
        if fake_probability is None:
            # Fallback: assume index 1 is "fake" if no matching label
            # name was found — flagged clearly so this doesn't fail silently.
            fake_probability = probs[1] if len(probs) > 1 else probs[0]

        predicted_label = max(label_probs, key=label_probs.get)

        return {"fake_probability": float(fake_probability), "label": predicted_label}

    def classify_audio(self, audio_path: str) -> dict:
        """
        MAIN ENTRY POINT. Takes an audio file path, segments it,
        classifies each segment, and aggregates into a single verdict
        using MEDIAN (see module docstring for why).

        Returns:
            {
                "fake_probability": float (0-1, aggregated),
                "risk_tier": "SAFE" | "SUSPICIOUS" | "SYNTHETIC",
                "prediction": "synthetic" | "authentic",
                "num_segments_analyzed": int,
                "per_segment_results": [ {"fake_probability": float, "label": str}, ... ],
            }
        """
        segments = preprocess_audio_file(audio_path)

        if not segments:
            return {
                "fake_probability": 0.0,
                "risk_tier": "NO_AUDIO_DETECTED",
                "prediction": "unable_to_assess",
                "num_segments_analyzed": 0,
                "per_segment_results": [],
            }

        per_segment_results = [self._classify_single_segment(seg) for seg in segments]
        fake_probabilities = [r["fake_probability"] for r in per_segment_results]

        aggregated_fake_probability = statistics.median(fake_probabilities)

        if aggregated_fake_probability < RISK_TIER_THRESHOLDS["SAFE"]:
            risk_tier = "SAFE"
        elif aggregated_fake_probability < RISK_TIER_THRESHOLDS["SUSPICIOUS"]:
            risk_tier = "SUSPICIOUS"
        else:
            risk_tier = "SYNTHETIC"

        prediction = "synthetic" if aggregated_fake_probability >= 0.5 else "authentic"

        return {
            "fake_probability": round(aggregated_fake_probability, 4),
            "risk_tier": risk_tier,
            "prediction": prediction,
            "num_segments_analyzed": len(segments),
            "per_segment_results": per_segment_results,
        }


# ------------------------------------------------------------------
# Quick manual test — run this file directly against your test audio:
#   python nunmai_voice\model\classifier.py
# ------------------------------------------------------------------
if __name__ == "__main__":
    clf = NunmaiVoiceClassifier()

    test_audio_path = "test_data/fake02.wav"
    print(f"\nAnalyzing: {test_audio_path}")
    result = clf.classify_audio(test_audio_path)

    print(f"\nPrediction: {result['prediction']}")
    print(f"Fake probability (median): {result['fake_probability']}")
    print(f"Risk tier: {result['risk_tier']}")
    print(f"Segments analyzed: {result['num_segments_analyzed']}")
    print("\nPer-segment breakdown (first 10):")
    for i, seg_result in enumerate(result["per_segment_results"][:10]):
        print(f"  Segment {i+1}: {seg_result}")