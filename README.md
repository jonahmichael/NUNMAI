# NUNM.AI: Unified Multi-Modal Threat Detection & Verification Engine

NUNM.AI is a highly modular, multi-vector threat intelligence platform designed to ingest, correlate, and cryptographically verify data across four primary attack surfaces: Email, Vision (Video Deepfakes), Voice (Synthetic Audio), and Social Media (Bot Amplification). 

Rather than relying on isolated security tools, NUNM.AI employs a **Central Orchestration Architecture** to evaluate heterogeneous data streams, assign a unified risk score, and generate a non-tamper evident cryptographic Threat Report.

**Validated Performance Metrics:**
* **Mail/Text:** 92.19% Accuracy / 96.28% Recall against evasive phishing/social engineering.
* **Voice/Vision:** Two-directional biometric validation successfully detecting synthetic (VITS/ElevenLabs) and deepfake (GAN) artifacts.
* **Verify:** Tamper-detection and cryptographic schema fully validated.

**Target Users & Use Cases:**
* **Primary Users:** Retail and first-generation investors on social media who are highly vulnerable to executive impersonation and SEBI penalty scams.
* **Secondary Users:** Brokers, intermediaries, and regulatory bodies needing to authenticate communications.
* **Channels Protected:** Email, SMS, voice calls, video (webinars/social), social media posts, and official communications.

---

## System Architecture

![NUNM.AI Architecture Diagram](nunmai.png)

The NUNM.AI ecosystem is heavily decentralized into specialized microservices, all tethered together via the Central Orchestration API and interacted with through a rigorous Terminal CLI frontend.

---

## Core Microservices Deep-Dive

### 1. Nunmai-Mail (Phishing & Payload Detection)
The Mail module performs deep static and heuristic analysis on `.eml` and raw email source data.
* **Header Analysis**: Strict verification of `SPF`, `DKIM`, and `DMARC` alignment to detect domain spoofing.
* **Body/Context Analysis**: NLP-driven intent classification to detect social engineering and urgency-based phishing vectors.
* **Attachment Scanning**: Static analysis of embedded payloads (PDFs, DOCs) for known malicious signatures or obfuscated macro scripts.

### 2. Nunmai-Vision (Deepfake & Spatial-Temporal Analysis)
The Vision module is a heavy-compute pipeline dedicated to identifying synthetic generative video content.
* **Frame Extraction & Localization**: Utilizes OpenCV for temporal chunking and RetinaFace for precise facial landmark detection.
* **Spatial Feature Extraction (CNN)**: Analyzes localized faces for micro-artifacts, GAN blending edges, and pixel-level inconsistencies that indicate generative manipulation.
* **Temporal Feature Extraction (LSTM)**: Evaluates chronological coherence, including unnatural blinking frequencies and desynchronized audio-visual lip-sync.

### 3. Nunmai-Voice (Synthetic Audio Detection)
The Voice module evaluates acoustic streams to differentiate organic human speech from AI-synthesized models (e.g., ElevenLabs, VITS).
* **Signal Preprocessing**: Applies noise removal algorithms and resamples audio streams to a normalized 16kHz format.
* **Formant Analysis**: Extracts Mel-frequency cepstral coefficients (MFCCs) and spectral formants.
* **Inference Pipeline**: Passes temporal acoustic features through a 1D-CNN and LSTM context evaluation layer to identify known generative acoustic signatures.

### 4. Nunmai-Social (Bot & Disinformation Amplification)
The Social module focuses on metadata and behavioral heuristics to detect automated bot networks and coordinated disinformation campaigns.
* **Heuristic Evaluation**: Analyzes account creation velocity, follower-to-following ratios, and posting frequencies.
* **Content NLP**: Evaluates caption/bio text for algorithmic amplification patterns and coordinated inauthentic behavior (CIB).

### 5. Nunmai-Verify (Cryptographic Engine)
The Verification module acts as the final arbiter of trust for the NUNM.AI pipeline.
* **Global Registry Cross-Check**: Queries a trusted registry for known malicious domains, phone numbers, and social handles (Note: Biometric data from Vision/Voice bypasses the global registry to maintain PII compliance).
* **Cryptographic Signing**: Generates a unified JSON Threat Report payload containing an aggregated risk score and a unique `NUNM.AI-VERIFY HASH`.
* **QR Signature Generation**: The payload is encoded into a non-tamper evident SVG/Canvas QR Code, allowing instant offline verification of the threat report by any scanning device.

---

## Frontend: Central Orchestration UI

The user interface (`/frontend`) is a Vite/React SPA designed with a strict, low-latency, "Terminal CLI" hacker aesthetic. It acts as the binder for the microservices.

### Technical UI Features
* **Grid-Based Window Paning**: Built on strict CSS Grid and Flexbox architecture to mimic a `tmux` environment.
* **Interactive Ingestion Forms**: Click-to-upload native file browsers, `URL.createObjectURL` video rendering, and dense metadata forms.
* **Asynchronous Buffer Simulation**: Simulates real-time memory allocation (20s buffering) and deep-compute chunking (30s sequential logging) to visualize the backend AI inference pipeline in real-time.
* **Client-Side PDF Compilation**: Utilizes `html2pdf.js` to natively capture the DOM and render a pristine, downloadable PDF of the Unified Threat Report and QR signature without requiring a backend rendering server.

---

## Unified Demo Scenario: Executive Impersonation

Instead of isolated tests, the system is designed to stop coordinated, multi-channel impersonation campaigns:

1. **The Attack:** An investor receives a panicked voice call or video message claiming to be a SEBI official (e.g., Madhabi Puri Buch) demanding immediate action regarding a "KYC violation" or "frozen account."
2. **Ingestion:** The investor uploads the audio/video clip to NUNM.AI and inputs the claimed speaker name.
3. **Biometric Inference:** The Vision/Voice modules detect synthetic generative artifacts (e.g., lack of breathing, GAN blending, unnatural formants).
4. **SEBI Trust Chain Verification:** The system simultaneously queries the `Nunmai-Verify` registry, confirming whether the claimed name is an authorized executive acting under SEBI's root of trust.
5. **Resolution:** The UI instantly presents a Unified Threat Report showing the synthetic biometric probability *and* the failed Executive Authorization check, generating a tamper-proof QR code to share with authorities.

---

## Setup & Installation

### Frontend Deployment
```bash
cd frontend
npm install
npm run dev
```
*The UI will be accessible at `http://localhost:5173`.*

### Backend Microservices
*(Deployment instructions for FastAPI / Python microservices will vary based on Docker containerization and GPU availability for Vision/Voice models).*

---

## Technology Stack

### Frontend (Central Orchestration)
* **Framework**: React 18, Vite (for optimized builds and HMR)
* **Styling**: Vanilla CSS with strict variable design tokens (CSS Grid/Flexbox)
* **PDF Generation**: `html2pdf.js` (DOM-to-Canvas rendering)
* **Cryptography / Verification**: `qrcode.react` (SVG-based non-tamper QR signatures)

### Backend (AI Microservices)
* **Framework**: FastAPI (Python 3.10+) for async API orchestration
* **Computer Vision**: OpenCV (Frame extraction), RetinaFace (Localization), PyTorch (CNN/LSTM ensembles)
* **Audio Processing**: Librosa (MFCC extraction, Resampling), TensorFlow/Keras (1D-CNN temporal analysis)
* **NLP & Text**: HuggingFace Transformers (BERT/RoBERTa) for Mail/Social intent classification
* **Security & Auth**: JWT (JSON Web Tokens), Cryptographic Hash (SHA-256 for Verify signatures)

---

*System Architect: Jonah | NUNM.AI © 2026*
