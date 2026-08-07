# NUNMAI-MAIL - Synthetic Dataset

## What this is

`synthetic_dataset.csv` is a labeled dataset of phishing and legitimate
securities-market emails, used to train the NUNMAI-MAIL classifier.

**Important:** This dataset is entirely synthetic. Real hyper-personalized
LLM-phishing corpora barely exist publicly (the threat is too new), and
public phishing datasets (PhishTank, Nazario) predate the LLM era and don't
capture this attack style. So we generate our own — with red flags
deliberately injected in a controlled, labeled way — modeled on:

- Traditional phishing indicators (URL structure, header authentication
  failures) from established literature
- AI-enabled Business Email Compromise (BEC) patterns: hyper-personalization,
  out-of-band excuses, LLM vocabulary "tropes," burstiness — see the design
  reference used to build `text_features.py`

This is a **starting point, not a finished dataset**. Swap in real labeled
data later (e.g. from a live NUNMAI-VERIFY deployment or partner
organization) without changing anything downstream — `train.py` only cares
about the CSV schema below, not where the rows came from.

## How it's built

1. A small set of **seed templates** (~25-30 phishing, ~25-30 legitimate)
   are hand-written / LLM-drafted inside `generate_synthetic_data.py`,
   covering distinct attack subtypes (KYC-expiry scams, BEC wire-transfer
   requests, fake dividend/refund notices, impersonated-executive requests,
   genuine broker statements, real KYC reminders, etc.)
2. Each template is expanded into many rows by randomizing:
   - Victim/sender names, amounts, dates
   - Sender domain (real-looking spoofed domain vs. free-mail vs. legit domain)
   - SPF/DKIM/DMARC pass/fail combinations
   - Presence/absence of typosquatting, shorteners, IP-based links
3. Output is written to `synthetic_dataset.csv`.

Regenerate the dataset anytime with:
```powershell
python data\generate_synthetic_data.py
```

## Schema

| Column             | Type | Description                                                                 |
|---------------------|------|-------------------------------------------------------------------------------|
| `id`                | int  | Unique row identifier                                                        |
| `label`             | int  | `1` = phishing, `0` = legitimate                                             |
| `template_id`       | str  | Seed template this row was generated from (e.g. `phish_kyc_expiry`)          |
| `category`          | str  | Human-readable category (e.g. `"KYC Verification Scam"`, `"BEC Wire Transfer"`) |
| `subject`           | str  | Email subject line                                                           |
| `body_text`         | str  | Plain body text only — feeds `extract_url_features()` and `extract_text_features()` |
| `raw_email_source`  | str  | Full header block + blank line + body, `.eml`-style — feeds `extract_header_features()` |
| `notes`             | str  | QA notes on injected red flags (for humans only, not used by the model)      |

## Dataset size targets

| Tier               | Rows (both classes) | Use case                          |
|---------------------|----------------------|-------------------------------------|
| Minimum viable demo | ~1,000 (500/500)     | Fast working prototype              |
| Recommended         | ~4,000 (2,000/2,000) | Solid generalization, defensible    |
| Literature-matching | ~10,000+ (5,000/5,000) | Matches scale of published studies |

This project targets the **Recommended** tier by default.

## A note on class balance

The dataset is generated **balanced (50/50 phishing/legitimate)** on
purpose, even though real-world email traffic is heavily skewed toward
legitimate mail. This is standard practice in phishing-detection literature
(see Mughaid et al., 2022) — training on a balanced set avoids the model
lazily learning to always predict "legitimate," and produces more reliable
precision/recall estimates. If deployed on real, imbalanced traffic later,
the model's *decision threshold* (not the training data) should be
recalibrated.

## Known limitations

- Synthetic data cannot capture every real-world phishing variation —
  treat this as a way to bootstrap and validate the feature pipeline, not
  as ground truth
- Template authors (human or LLM-assisted) have inherent writing biases;
  the model may partially learn "our phrasing" rather than the fully
  general pattern — mitigated by keeping template *categories* diverse,
  not just quantity high
- No real header/routing data (e.g. genuine Received-chain hops from real
  mail servers) — all header fields are synthetically composed