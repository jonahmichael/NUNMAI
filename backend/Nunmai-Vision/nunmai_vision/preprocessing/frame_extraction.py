"""
frame_extraction.py
====================
Preprocessing pipeline for NUNMAI-VISION: takes a video file, extracts a
sample of frames, and detects faces within each frame — matching Step 1
("Video Preprocessing: Frame Extraction, Face Detection") from the
architecture diagram.

FACE DETECTION CHOICE: we use OpenCV's built-in Haar Cascade classifier
rather than a heavier library like MTCNN or mediapipe. This is a
deliberate simplicity tradeoff given time constraints — Haar Cascade
ships bundled with opencv-python (zero extra downloads), is fast on CPU,
and is "good enough" for a working demo. It's less accurate than
MTCNN/mediapipe on difficult angles/lighting — worth upgrading later if
this becomes a priority, but not now.

WHY WE SAMPLE FRAMES RATHER THAN PROCESS EVERY FRAME: a typical video has
24-30 frames per second. Running a full deep-learning classifier on every
single frame of even a short clip would be slow and mostly redundant
(consecutive frames barely differ). We sample at a fixed interval instead
(configurable via `sample_every_n_frames`).
"""

import cv2
import torch
from pathlib import Path
from facenet_pytorch import MTCNN

# Initialize MTCNN for robust face detection (replaces buggy OpenCV CascadeClassifier)
device = torch.device('cuda' if torch.cuda.is_available() else 'cpu')
# keep_all=True means it detects all faces in the frame, not just the largest one
_mtcnn = MTCNN(keep_all=True, device=device)


def extract_frames(video_path: str, sample_every_n_frames: int = 15) -> list:
    """
    Reads a video file and returns a list of sampled frames as numpy
    arrays (OpenCV's native format, BGR color order).
    """
    if not Path(video_path).exists():
        raise FileNotFoundError(f"Video file not found: {video_path}")

    cap = cv2.VideoCapture(video_path)
    if not cap.isOpened():
        raise ValueError(f"Could not open video file: {video_path}")

    frames = []
    frame_index = 0

    while True:
        ret, frame = cap.read()
        if not ret:
            break  # end of video
        if frame_index % sample_every_n_frames == 0:
            frames.append(frame)
        frame_index += 1

    cap.release()
    return frames


def detect_faces_in_frame(frame) -> list:
    """
    Runs MTCNN face detection on a single frame.

    Returns:
        List of (x, y, width, height) bounding boxes, one per detected face.
        Empty list if no faces found.
    """
    # OpenCV loads frames in BGR. MTCNN expects RGB.
    rgb_frame = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
    
    # boxes are returned as [x1, y1, x2, y2] by MTCNN
    boxes, probs = _mtcnn.detect(rgb_frame)
    
    if boxes is None:
        return []
        
    formatted_boxes = []
    for box in boxes:
        x1, y1, x2, y2 = box
        # Convert [x1, y1, x2, y2] to [x, y, width, height]
        w = x2 - x1
        h = y2 - y1
        formatted_boxes.append((int(x1), int(y1), int(w), int(h)))
        
    return formatted_boxes


def crop_face(frame, bounding_box, padding_ratio: float = 0.2):
    """
    Crops a face out of a frame given a bounding box, with a bit of
    padding around it (deepfake artifacts often show up at the EDGES of
    a swapped face, e.g. blending seams — so a tight crop with no margin
    can actually cut off useful signal).

    Args:
        frame: the full frame (numpy array)
        bounding_box: (x, y, width, height) from detect_faces_in_frame
        padding_ratio: fraction of the face size to pad on each side
    """
    x, y, w, h = bounding_box
    pad_x = int(w * padding_ratio)
    pad_y = int(h * padding_ratio)

    frame_h, frame_w = frame.shape[:2]
    x1 = max(0, x - pad_x)
    y1 = max(0, y - pad_y)
    x2 = min(frame_w, x + w + pad_x)
    y2 = min(frame_h, y + h + pad_y)

    return frame[y1:y2, x1:x2]


def extract_face_crops_from_video(video_path: str, sample_every_n_frames: int = 15) -> list:
    """
    MAIN ENTRY POINT for preprocessing. Combines frame extraction + face
    detection + cropping into one call: give it a video path, get back a
    list of cropped face images (numpy arrays, BGR) ready to feed into
    the classifier.

    If a sampled frame contains multiple faces, ALL of them are included
    (a video call scam might have multiple people in frame) — each face
    crop is treated as an independent classification target, and results
    get aggregated later in classifier.py.
    """
    frames = extract_frames(video_path, sample_every_n_frames)
    face_crops = []

    for frame in frames:
        boxes = detect_faces_in_frame(frame)
        for box in boxes:
            crop = crop_face(frame, box)
            if crop.size > 0:  # guard against degenerate/empty crops
                face_crops.append(crop)

    return face_crops


# ------------------------------------------------------------------
# Quick manual test note: this file needs an actual video file to test
# against, which we don't have yet. Once you have a sample .mp4 (even a
# short clip of any face-containing video for testing), run:
#   python -c "from nunmai_vision.preprocessing.frame_extraction import extract_face_crops_from_video; print(len(extract_face_crops_from_video('path/to/video.mp4')))"
# ------------------------------------------------------------------