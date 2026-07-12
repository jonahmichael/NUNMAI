# Nunmai-Vision

NUNMAI-VISION's pipeline (frame extraction → face detection → pretrained SigLIP2 classification → median aggregation) has been validated against real, non-deepfake footage — correctly and consistently classifying it as authentic across repeated runs. Its ability to correctly flag genuine deepfakes has not yet been empirically tested against a confirmed-fake sample, due to the size/access constraints of standard deepfake benchmark datasets (FaceForensics++, DFDC) within the project timeline. The architecture and model choice are sound (a 2025 SigLIP2 deepfake classifier, purpose-built for this exact task), but this specific claim remains architecturally justified rather than empirically confirmed.

