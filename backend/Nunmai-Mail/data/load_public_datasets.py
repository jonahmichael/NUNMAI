"""
load_public_datasets.py
========================
Loads REAL phishing and legitimate emails from public datasets and merges
them with our synthetic dataset — fixing the "perfect separability" problem
we hit in train.py (see project notes: our fully-synthetic dataset let the
model reach a suspicious 100% accuracy by exploiting deterministic
correlations between class label and injected features; real data breaks
that artificial cleanliness with genuine noise/overlap).

SOURCES USED (see data/README.md for full provenance):
  1. SpamAssassin Public Corpus (easy_ham + hard_ham) — REAL legitimate
     emails with FULL real headers (best quality: no reconstruction needed).
  2. Nazario Phishing Corpus, as distributed via the merged Kaggle
     "Phishing Email Dataset" CSV — REAL phishing (and some legit/control)
     emails. Only partial header info available (sender/subject/date), so
     SPF/DKIM/DMARC are left as "none" (honestly representing "unknown",
     not fabricated as pass/fail).

NOT USED (see notes): email_text.csv — generic spam/ham with no header
info and off-domain content (not phishing-specific). Left as an optional
function below (_load_email_text_csv) if you want to enable it later for
raw volume, but it's not called by main() by default.

OUTPUT:
  data/real_dataset.csv       — real data only, same schema as synthetic
  data/combined_dataset.csv   — real_dataset.csv + synthetic_dataset.csv
                                  merged and shuffled — THIS is what
                                  train.py should be pointed at going
                                  forward (see instructions at the end).

Run with:
    python data\\load_public_datasets.py
"""

import csv
import re
import tarfile
from email import message_from_string, message_from_bytes
from email.utils import parseaddr
from pathlib import Path

import pandas as pd

RAW_PUBLIC_DIR = Path(__file__).parent / "raw_public"
SYNTHETIC_CSV = Path(__file__).parent / "synthetic_dataset.csv"
REAL_OUTPUT_CSV = Path(__file__).parent / "real_dataset.csv"
COMBINED_OUTPUT_CSV = Path(__file__).parent / "combined_dataset.csv"

FIELDNAMES = ["id", "label", "template_id", "category", "subject", "body_text", "raw_email_source", "notes"]


# ============================================================
# SOURCE 1: SpamAssassin Public Corpus (real legit emails, full headers)
# ============================================================

def _extract_body_from_email_message(msg) -> str:
    """
    Pulls plain-text body out of a parsed email.message.Message object,
    handling both simple and multipart emails. Falls back to the raw
    payload as a string if anything goes wrong (old/malformed emails in
    this corpus sometimes have unusual encodings).
    """
    try:
        if msg.is_multipart():
            for part in msg.walk():
                content_type = part.get_content_type()
                if content_type == "text/plain":
                    payload = part.get_payload(decode=True)
                    if payload:
                        return payload.decode("utf-8", errors="replace")
            return ""  # no text/plain part found
        else:
            payload = msg.get_payload(decode=True)
            if payload:
                return payload.decode("utf-8", errors="replace")
            return str(msg.get_payload())
    except Exception:
        return ""


def load_spamassassin_tarball(tarball_path: Path, label: int, source_name: str) -> list[dict]:
    """
    Parses a SpamAssassin public-corpus tarball (one raw email per file)
    into rows matching our dataset schema. Each file's raw content IS
    already a proper raw_email_source (headers + body together) — no
    reconstruction needed, this is genuine real-world data.
    """
    rows = []
    skipped = 0

    if not tarball_path.exists():
        print(f"  WARNING: {tarball_path.name} not found, skipping.")
        return rows

    with tarfile.open(tarball_path, "r:bz2") as tar:
        members = [m for m in tar.getmembers() if m.isfile()]
        for member in members:
            try:
                raw_bytes = tar.extractfile(member).read()
                raw_text = raw_bytes.decode("utf-8", errors="replace")

                msg = message_from_bytes(raw_bytes)
                subject = msg.get("Subject", "(no subject)")
                body_text = _extract_body_from_email_message(msg)

                # Skip emails with essentially no usable body text — these
                # are usually corrupted/empty entries in old corpora and
                # would just add noise.
                if len(body_text.strip()) < 10:
                    skipped += 1
                    continue

                rows.append({
                    "label": label,
                    "template_id": f"real_{source_name}",
                    "category": f"Real: SpamAssassin {source_name.replace('_', ' ').title()}",
                    "subject": subject,
                    "body_text": body_text,
                    "raw_email_source": raw_text,
                    "notes": "Real email from SpamAssassin public corpus, full genuine headers",
                })
            except Exception:
                skipped += 1
                continue

    print(f"  {tarball_path.name}: loaded {len(rows)} rows, skipped {skipped}")
    return rows


# ============================================================
# SOURCE 2: Nazario Phishing Corpus (via merged Kaggle CSV)
# ============================================================

def _build_partial_raw_source(sender: str, receiver: str, date: str, subject: str, body: str) -> str:
    """
    Builds a raw_email_source from the PARTIAL real header info available
    in Nazario_5.csv (sender/receiver/date/subject are real; full auth
    headers are not present in this CSV format).

    SPF/DKIM/DMARC are deliberately left as "none" here — this is the
    HONEST representation of "no authentication header data available",
    matching exactly how header_features.py already treats a genuinely
    missing Authentication-Results header. We are NOT fabricating a
    pass/fail verdict we don't actually have.
    """
    sender = str(sender) if pd.notna(sender) else "unknown@unknown.com"
    receiver = str(receiver) if pd.notna(receiver) else "investor@example.com"
    date = str(date) if pd.notna(date) else "Tue, 01 Jan 2024 00:00:00 +0000"
    subject = str(subject) if pd.notna(subject) else "(no subject)"
    body = str(body) if pd.notna(body) else ""

    # receiver field sometimes contains multiple comma-separated addresses
    # (a real distribution list) — just take the first for the To: header.
    first_receiver = receiver.split(",")[0].strip()

    _, sender_addr = parseaddr(sender)
    if not sender_addr:
        sender_addr = "unknown@unknown.com"

    return (
        f"From: {sender}\n"
        f"To: {first_receiver}\n"
        f"Subject: {subject}\n"
        f"Date: {date}\n"
        f"Authentication-Results: mx.example.com; spf=none; dkim=none; dmarc=none\n"
        f"\n"
        f"{body}\n"
    )


def load_nazario_csv(csv_path: Path) -> list[dict]:
    """
    Parses the Nazario_5.csv (merged Kaggle phishing dataset format) into
    rows matching our schema. label is already 0/1 matching our convention
    (confirmed: 1=phishing, 0=legitimate) so no remapping needed.
    """
    if not csv_path.exists():
        print(f"  WARNING: {csv_path.name} not found, skipping.")
        return []

    df = pd.read_csv(csv_path)
    rows = []

    for _, row in df.iterrows():
        body = str(row["body"]) if pd.notna(row["body"]) else ""
        # Skip essentially-empty bodies — not useful training signal.
        if len(body.strip()) < 10:
            continue

        raw_source = _build_partial_raw_source(
            sender=row["sender"], receiver=row["receiver"], date=row["date"],
            subject=row["subject"], body=body,
        )

        label = int(row["label"])
        rows.append({
            "label": label,
            "template_id": "real_nazario" if label == 1 else "real_nazario_control",
            "category": "Real: Nazario Phishing Corpus" if label == 1 else "Real: Nazario Corpus (Legit Control)",
            "subject": str(row["subject"]) if pd.notna(row["subject"]) else "(no subject)",
            "body_text": body,
            "raw_email_source": raw_source,
            "notes": "Real email, partial headers only (sender/subject/date genuine, SPF/DKIM/DMARC unknown -> 'none')",
        })

    print(f"  {csv_path.name}: loaded {len(rows)} rows "
          f"({sum(1 for r in rows if r['label']==1)} phishing, "
          f"{sum(1 for r in rows if r['label']==0)} legit)")
    return rows


# ============================================================
# OPTIONAL / NOT USED BY DEFAULT: generic spam/ham CSV
# ============================================================

def _load_email_text_csv(csv_path: Path, max_rows: int | None = 2000) -> list[dict]:
    """
    NOT called by main() by default — see module docstring for why
    (off-domain content, no header info). Left here in case you want to
    enable it later for raw volume. max_rows caps how many to sample,
    since the full file has 53k+ rows and would dominate the dataset.
    """
    if not csv_path.exists():
        return []
    df = pd.read_csv(csv_path)
    if max_rows:
        df = df.sample(n=min(max_rows, len(df)), random_state=42)

    rows = []
    for _, row in df.iterrows():
        body = str(row["text"]) if pd.notna(row["text"]) else ""
        if len(body.strip()) < 10:
            continue
        label = int(row["label"])
        raw_source = (
            f"From: unknown@unknown.com\nTo: investor@example.com\n"
            f"Subject: (no subject)\n"
            f"Authentication-Results: mx.example.com; spf=none; dkim=none; dmarc=none\n\n{body}\n"
        )
        rows.append({
            "label": label,
            "template_id": "real_generic_spamham",
            "category": "Real: Generic Spam/Ham (off-domain)",
            "subject": "(no subject)",
            "body_text": body,
            "raw_email_source": raw_source,
            "notes": "Generic spam/ham, no real headers, not phishing-specific",
        })
    return rows


# ============================================================
# MAIN: load, combine, write outputs
# ============================================================

def _write_csv(rows: list[dict], path: Path):
    """Assigns sequential IDs and writes a list of row-dicts to a CSV
    matching our standard schema."""
    for i, row in enumerate(rows, start=1):
        row["id"] = i
    with open(path, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=FIELDNAMES)
        writer.writeheader()
        writer.writerows(rows)

def _balance_classes(combined_df: pd.DataFrame, random_state: int = 42) -> pd.DataFrame:
    """
    Downsamples the majority class to match the minority class count,
    restoring 50/50 balance. We downsample rather than upsample the
    minority class because upsampling (duplicating rows) would let the
    model overfit to repeated exact rows, whereas downsampling just means
    "use less of the class we have plenty of" — a cleaner fix with no
    duplication risk.

    The downsampling is random (not "first N rows"), so we don't
    accidentally lose diversity by only keeping e.g. all-SpamAssassin
    and no synthetic legit rows.
    """
    label_counts = combined_df["label"].value_counts()
    minority_count = label_counts.min()

    balanced_parts = []
    for label_value in label_counts.index:
        subset = combined_df[combined_df["label"] == label_value]
        sampled = subset.sample(n=minority_count, random_state=random_state)
        balanced_parts.append(sampled)

    balanced_df = pd.concat(balanced_parts, ignore_index=True)
    return balanced_df

def main():
    print("Loading real public datasets...")
    print()

    print("SpamAssassin (legit, label=0):")
    real_rows = []
    real_rows += load_spamassassin_tarball(
        RAW_PUBLIC_DIR / "20021010_easy_ham.tar.bz2", label=0, source_name="easy_ham"
    )
    real_rows += load_spamassassin_tarball(
        RAW_PUBLIC_DIR / "20021010_hard_ham.tar.bz2", label=0, source_name="hard_ham"
    )

    print("\nNazario (phishing + legit control):")
    real_rows += load_nazario_csv(RAW_PUBLIC_DIR / "Nazario_5.csv")

    # Shuffle so the real_dataset.csv isn't grouped by source.
    import random
    random.seed(42)
    random.shuffle(real_rows)

    _write_csv(real_rows, REAL_OUTPUT_CSV)
    num_phish = sum(1 for r in real_rows if r["label"] == 1)
    num_legit = sum(1 for r in real_rows if r["label"] == 0)
    print(f"\nWrote {len(real_rows)} real rows to {REAL_OUTPUT_CSV.name}")
    print(f"  Phishing: {num_phish}  |  Legitimate: {num_legit}")

    # --- Merge with synthetic dataset into the final combined training file ---
    if not SYNTHETIC_CSV.exists():
        print(f"\nWARNING: {SYNTHETIC_CSV.name} not found — run generate_synthetic_data.py first "
              f"if you want a combined dataset. Skipping merge.")
        return

    synthetic_df = pd.read_csv(SYNTHETIC_CSV)
    real_df = pd.read_csv(REAL_OUTPUT_CSV)

    combined_df = pd.concat([synthetic_df, real_df], ignore_index=True)

    pre_balance_phish = (combined_df["label"] == 1).sum()
    pre_balance_legit = (combined_df["label"] == 0).sum()
    print(f"\nBefore balancing: {pre_balance_phish} phishing, {pre_balance_legit} legitimate")

    combined_df = _balance_classes(combined_df)
    combined_df = combined_df.sample(frac=1, random_state=42).reset_index(drop=True)  # shuffle
    combined_df["id"] = range(1, len(combined_df) + 1)  # renumber IDs sequentially

    combined_df.to_csv(COMBINED_OUTPUT_CSV, index=False)

    total_phish = (combined_df["label"] == 1).sum()
    total_legit = (combined_df["label"] == 0).sum()
    print(f"\nWrote {len(combined_df)} BALANCED combined rows to {COMBINED_OUTPUT_CSV.name}")
    print(f"  Phishing: {total_phish}  |  Legitimate: {total_legit}")
    print(f"  (synthetic: {len(synthetic_df)} + real: {len(real_df)}, downsampled to balance)")


if __name__ == "__main__":
    main()