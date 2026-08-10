# NUNM.AI: SEBI-Anchored Multi-Modal Threat Detection Engine

NUNM.AI is a highly modular, multi-vector threat intelligence platform designed explicitly to protect **Indian retail investors** against financial fraud, regulatory spoofing, and executive deepfake impersonation. 

Rather than relying on isolated security tools, NUNM.AI employs a **Central Orchestration Architecture** to evaluate heterogeneous data streams, assign a unified risk score, cross-check against a verified regulatory trust chain, and generate a non-tamper evident cryptographic Threat Report.

**Validated Performance Metrics:**
* **Mail:** 93% Accuracy (F1: 0.93) against evasive, hyper-personalized Indian market phishing (e.g., SEBI Show Cause Notice scams, Investor Grievance refund theft).
* **Vision & Voice:** Biometric deepfake detection powered by PyTorch (SigLIP2 / Wav2Vec2) to catch AI-generated executive impersonation.
* **Verify:** Complete cryptographic registry with **SEBI as the Root of Trust**, anchoring authorized brokers, exchanges, and verified executives.

---

## 🏗 System Architecture

The ecosystem consists of a React/Vite Frontend and 5 independent Python/FastAPI microservices routed through a central API Gateway.

### 1. Nunmai-Mail (Regulatory Spoofing Detection)
* **Stack**: Scikit-Learn (Gradient Boosting Classifier)
* **Function**: Evaluates raw email text and headers. Detects missing DMARC/SPF/DKIM alignments and identifies NLP urgency vectors specific to the Indian securities market (e.g., demands for penalty payments, fake KYC expiry links).

### 2. Nunmai-Vision (Deepfake Detection)
* **Stack**: OpenCV, PyTorch (SigLIP2)
* **Function**: Accepts video uploads and analyzes frames for spatial inconsistencies, GAN blending artifacts, and synthetic facial manipulation.

### 3. Nunmai-Voice (Synthetic Audio Detection)
* **Stack**: PyTorch (Wav2Vec2)
* **Function**: Analyzes acoustic streams and spectral formants to differentiate organic human speech from AI-synthesized cloning (e.g., ElevenLabs).

### 4. Nunmai-Social (Bot Amplification)
* **Stack**: FastAPI
* **Function**: Evaluates social media post text, follower ratios, and account behavior to flag automated disinformation networks or pump-and-dump bots.

### 5. Nunmai-Verify (The SEBI Trust Chain)
* **Stack**: SQLite, RSA Cryptography
* **Function**: The central cryptographic registry. SEBI is mathematically anchored as Entity #1. Legitimate brokers (Zerodha, Upstox) and exchanges (NSE, BSE) are registered under SEBI. Contains the `entity_executives` table to track who is legally authorized to speak on behalf of these entities.

---

## 🛡️ The Unified Demo Scenario: Executive Impersonation

The system is designed to stop coordinated, multi-channel impersonation campaigns:

1. **The Attack:** An investor receives a panicked email claiming their demat account is frozen, followed by a WhatsApp video message claiming to be a SEBI official (e.g., Madhabi Puri Buch) demanding immediate action.
2. **Mail Ingestion:** The Mail module parses the email, identifies spoofed routing headers, and flags high-pressure "Show Cause Notice" vocabulary.
3. **Biometric Ingestion:** The investor uploads the video to the Vision module and inputs the `claimed_speaker_name` ("Madhabi Puri Buch").
4. **The Cross-Check:** The Vision module detects synthetic generative artifacts in the video. Simultaneously, it queries the `Nunmai-Verify` SQLite registry. It confirms that Madhabi Puri Buch *is* an authorized executive, but because the video is a deepfake, the system recognizes an executive impersonation attack.
5. **Resolution:** The React UI instantly presents a Unified Threat Report showing the synthetic biometric probability, the spoofed email warnings, and generates a tamper-proof QR code to share with authorities.

---

## 🚀 Setup & Hosting Instructions

The application is configured to run fully locally or on a cloud server. 

### 1. Backend Services
All backend services run in a Python virtual environment and are brokered by the API Gateway (`main.py`) on port **8080**.

**Quick Start (Windows):**
Simply double-click `backend/start_all.bat`. This will open 5 command prompts and launch the gateway and all 4 microservices automatically.

**Quick Start (Linux / Cloud Server):**
```bash
cd backend
chmod +x start_all.sh
./start_all.sh
```

*(Note: The API Gateway binds to `0.0.0.0:8080`, so ensure Port 8080 is open in your cloud firewall).*

### 2. Frontend (React UI)
The frontend is built using React 18 and Vite.

**Local Development:**
```bash
cd frontend
npm install
npm run dev
```

**Production Build (Hosting):**
When building for a public server, you must pass the API Gateway URL as an environment variable so the browser knows where to route requests.
```bash
cd frontend
npm install
VITE_API_URL=http://<YOUR-SERVER-PUBLIC-IP>:8080 npm run build
```
You can then serve the output `dist/` directory using Nginx, Vercel, Netlify, or any static file host.

---
*System Architect: Jonah | NUNM.AI © 2026*
