"""
image_classifier.py
=====================
Wraps the SAME pretrained deepfake/AI-face classifier used in
NUNMAI-VISION (prithivMLmods/Deepfake-Detect-Siglip2) for single-image
classification in NUNMAI-SOCIAL.

IMPORTANT SCOPE LIMITATION (discovered via testing): this model is a
FACE-FORGERY detector — it was trained to distinguish real human faces
from AI-swapped/generated faces, NOT to judge "is this image AI-generated"
in general. Feeding it an image with no face (a graphic, poster,
screenshot, chart) produces a confidently-WRONG result, since the model
has no "not applicable" output — it forces everything through its
real-face/fake-face decision boundary regardless of actual content.
Confirmed directly: a plain graphic/poster image scored 99.995% "Fake"
despite containing no face at all.

FIX: we gate classification behind a face-detection check (same OpenCV
Haar Cascade approach as NUNMAI-VISION). If no face is detected, we
return NOT_APPLICABLE rather than forcing a spurious verdict. This is an
honest, important limitation: this module can assess face-based image
manipulation (a fake image of a company CEO/CIO), but NOT general
AI-generated graphics, charts, or screenshots — that would require a
different, general-purpose AI-image detector, which is out of scope
given the project timeline.
"""

import cv2
from PIL import Image
import numpy as np
import torch
from transformers import AutoImageProcessor, SiglipForImageClassification

MODEL_NAME = "prithivMLmods/Deepfake-Detect-Siglip2"

_FACE_CASCADE_PATH = cv2.data.haarcascades + "haarcascade_frontalface_default.xml"
_face_detector = cv2.CascadeClassifier(_FACE_CASCADE_PATH)


def _contains_face(image_path: str) -> bool:
    """
    Quick gate check: does this image contain a detectable face at all?
    Uses the same Haar Cascade detector as NUNMAI-VISION for consistency.
    """
    img = cv2.imread(image_path)
    if img is None:
        return False  # unreadable image file
    gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
    faces = _face_detector.detectMultiScale(gray, scaleFactor=1.1, minNeighbors=5, minSize=(60, 60))
    return len(faces) > 0


class NunmaiSocialImageClassifier:
    """
    Loads the pretrained SigLIP2 classifier ONCE and reuses it for many
    single-image predictions. Instantiate once at API startup.
    """

    def __init__(self, model_name: str = MODEL_NAME):
        print(f"Loading pretrained model '{model_name}' (first run downloads weights)...")
        self.processor = AutoImageProcessor.from_pretrained(model_name)
        self.model = SiglipForImageClassification.from_pretrained(model_name)
        self.model.eval()
        self.id2label = self.model.config.id2label
        print("Model loaded. Labels:", self.id2label)

    def classify_image(self, image_path: str) -> dict:
        """
        Classifies a single image file as authentic/AI-generated FACE
        content — ONLY if a face is detected first. If no face is found,
        returns NOT_APPLICABLE rather than a forced, meaningless verdict.

        Returns:
            {"fake_probability": float, "label": str, "applicable": bool}
        """
        if not _contains_face(image_path):
            return {
                "fake_probability": 0.0,
                "label": "NOT_APPLICABLE",
                "applicable": False,
            }

        pil_image = Image.open(image_path).convert("RGB")

        inputs = self.processor(images=pil_image, return_tensors="pt")
        with torch.no_grad():
            outputs = self.model(**inputs)
            probs = torch.nn.functional.softmax(outputs.logits, dim=1).squeeze().tolist()

        label_probs = {self.id2label[i]: probs[i] for i in range(len(probs))}
        fake_probability = label_probs.get("Fake", label_probs.get("fake", 0.0))
        predicted_label = max(label_probs, key=label_probs.get)

        return {"fake_probability": float(fake_probability), "label": predicted_label, "applicable": True}


# ------------------------------------------------------------------
# Quick manual test:
#   python nunmai_social\model\image_classifier.py
# ------------------------------------------------------------------
if __name__ == "__main__":
    clf = NunmaiSocialImageClassifier()

    test_images = ["test_data/aihuman.png"]  # add a face-containing image path here too, if you have one

    for path in test_images:
        print(f"\nAnalyzing: {path}")
        result = clf.classify_image(path)
        print(f"Applicable: {result['applicable']}")
        print(f"Label: {result['label']}")
        print(f"Fake probability: {result['fake_probability']}")