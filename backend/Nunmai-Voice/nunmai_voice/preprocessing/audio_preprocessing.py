"""
audio_preprocessing.py
========================
Preprocessing pipeline for NUNMAI-VOICE: loads an audio file, resamples
it to the rate the classifier model expects, and segments it into
fixed-length chunks — matching Step 1 ("Audio Preprocessing: Noise
Removal, Frame Segmentation, Resampling") from the architecture diagram.

RESAMPLING: Wav2Vec2-based models (including our classifier) require
16kHz mono audio. Real-world audio — phone call recordings, WhatsApp
voice notes, etc. — comes in all sorts of sample rates and channel
configs, so this step is not optional; feeding the wrong sample rate
into the model silently produces garbage predictions rather than an
error, which is worth knowing.

SEGMENTATION: rather than feeding an entire (possibly long) call
recording into the model in one shot, we split it into fixed-length
chunks (default 4 seconds) and classify each independently, aggregating
results afterward — same "sample and aggregate" philosophy as
NUNMAI-VISION's frame-by-frame approach, and for the same reason: a
scam call may only be synthetic for PART of its duration (e.g. a
pre-recorded synthetic opening followed by a live human), and averaging
over the whole file could dilute a real detection.

NOISE REMOVAL: we do NOT implement active noise reduction/denoising in
this version — a deliberate scope decision given time constraints. The
pretrained model was trained on relatively clean speech; heavy
background noise could reduce accuracy, which is a known limitation
worth documenting rather than solving here.
"""

import librosa
import numpy as np
from pathlib import Path

TARGET_SAMPLE_RATE = 16000  # required by our Wav2Vec2-based classifier
DEFAULT_SEGMENT_SECONDS = 4  # length of each audio chunk classified independently


def load_and_resample(audio_path: str, target_sr: int = TARGET_SAMPLE_RATE) -> np.ndarray:
    """
    Loads an audio file (any format librosa supports: wav, mp3, m4a, ogg,
    flac, etc.) and resamples it to the target sample rate, converting to
    mono if it's stereo.

    Returns:
        1D numpy array of audio samples (float32, normalized to [-1, 1])
    """
    if not Path(audio_path).exists():
        raise FileNotFoundError(f"Audio file not found: {audio_path}")

    # sr=target_sr tells librosa to resample during loading (more
    # efficient than loading at native rate then resampling separately).
    # mono=True downmixes stereo to a single channel — the classifier
    # doesn't need stereo separation, and it halves the data size.
    audio, _ = librosa.load(audio_path, sr=target_sr, mono=True)
    return audio


def segment_audio(audio: np.ndarray, sample_rate: int = TARGET_SAMPLE_RATE,
                   segment_seconds: int = DEFAULT_SEGMENT_SECONDS) -> list:
    """
    Splits audio into fixed-length segments for independent classification.

    If the audio is shorter than one segment, returns it as a single
    segment (no padding — the classifier can handle variable-length
    input; we just don't want to silently drop very short clips).

    The LAST segment, if shorter than segment_seconds (i.e. audio length
    isn't an exact multiple), is still included as-is rather than
    discarded — a short trailing chunk still carries real signal and
    shouldn't be thrown away.
    """
    segment_samples = segment_seconds * sample_rate
    total_samples = len(audio)

    if total_samples == 0:
        return []

    if total_samples <= segment_samples:
        return [audio]

    segments = []
    for start in range(0, total_samples, segment_samples):
        end = min(start + segment_samples, total_samples)
        segments.append(audio[start:end])

    return segments


def preprocess_audio_file(audio_path: str, segment_seconds: int = DEFAULT_SEGMENT_SECONDS) -> list:
    """
    MAIN ENTRY POINT for preprocessing. Combines loading + resampling +
    segmentation into one call: give it an audio file path, get back a
    list of audio segments (numpy arrays) ready to feed into the classifier.
    """
    audio = load_and_resample(audio_path)
    segments = segment_audio(audio, segment_seconds=segment_seconds)
    return segments


# ------------------------------------------------------------------
# Quick manual test note: needs an actual audio file to test against.
# Once you have a sample .wav/.mp3 (any short voice recording works for
# initial testing — doesn't need to be synthetic), run:
#   python -c "from nunmai_voice.preprocessing.audio_preprocessing import preprocess_audio_file; segs = preprocess_audio_file('path/to/audio.wav'); print(f'{len(segs)} segments, lengths: {[len(s) for s in segs]}')"
# ------------------------------------------------------------------