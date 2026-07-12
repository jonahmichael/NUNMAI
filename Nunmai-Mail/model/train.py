"""
train.py
========
Trains the NUNMAI-MAIL phishing classifier.

PIPELINE:
  1. Load data/synthetic_dataset.csv
  2. Run every row through all three feature extractors:
       url_features.extract_url_features(body_text)
       header_features.extract_header_features(raw_email_source, url_domains)
       text_features.extract_text_features(body_text)
     ...and flatten the three resulting dicts into ONE feature row.
  3. One-hot encode the categorical header fields (spf_result/dkim_result/
     dmarc_result are strings like "pass"/"fail", not numbers).
  4. Split 80/20 (train/test), stratified so both classes stay balanced
     in each split.
  5. Run 5-fold cross-validation ON THE TRAINING SET ONLY — this gives a
     more robust accuracy estimate than a single split, because it trains
     and validates 5 times on different slices and averages the result,
     rather than trusting one lucky/unlucky split.
  6. Train the FINAL model on the full training set.
  7. Evaluate ONCE on the held-out test set (data the model has never
     seen in any form) — this is the number that actually matters.
  8. Print feature importances — which signals the model actually learned
     to rely on. This is our explainability layer: a security analyst can
     see WHY an email was flagged, not just that it was.
  9. Save the trained model + the exact feature-column order to
     models/nunmai_mail_model.joblib — classifier.py will load this file
     for inference.

Run with:
    python nunmai_mail\\model\\train.py
"""

import sys
import re
from pathlib import Path

import pandas as pd
import joblib
from sklearn.model_selection import train_test_split, cross_val_score
from sklearn.ensemble import GradientBoostingClassifier
from sklearn.metrics import (
    accuracy_score, precision_score, recall_score, f1_score, confusion_matrix,
    classification_report,
)

# Allow running this file directly (python nunmai_mail\model\train.py) by
# adding the project root to the import path, since it's not installed as
# a proper package yet.
# Allow running this file directly (python nunmai_mail\model\train.py) by
# adding the project root to the import path, since it's not installed as
# a proper package yet.
sys.path.append(str(Path(__file__).resolve().parents[2]))

from nunmai_mail.features.url_features import extract_url_features
from nunmai_mail.features.header_features import extract_header_features
from nunmai_mail.features.text_features import extract_text_features


DATA_PATH = Path(__file__).resolve().parents[2] / "data" / "combined_dataset.csv"
MODEL_OUTPUT_PATH = Path(__file__).resolve().parents[2] / "models" / "nunmai_mail_model.joblib"

# Columns from header_features.py that come back as STRINGS ("pass", "fail",
# "none", "softfail", "neutral") rather than numbers/booleans. These need
# one-hot encoding before a model can use them — GradientBoostingClassifier
# (like all sklearn models) only accepts numeric input.
CATEGORICAL_COLUMNS = ["spf_result", "dkim_result", "dmarc_result"]


def _extract_url_domains(body_text: str) -> list[str]:
    """
    Lightweight helper: pulls just the registrable domains out of any URLs
    in the body text. Used to feed header_features.py's sender-vs-URL
    cross-check (extract_header_features's `body_url_domains` argument).

    This intentionally duplicates a small amount of URL-finding logic
    rather than importing url_features.py's private _find_urls()/
    _analyze_single_url() helpers, to keep each feature module's internals
    independent and not create fragile cross-module private-function
    dependencies.
    """
    import tldextract
    url_pattern = re.compile(r'(https?://[^\s<>"\']+|www\.[^\s<>"\']+)')
    urls = url_pattern.findall(body_text)
    domains = []
    for url in urls:
        ext = tldextract.extract(url)
        domains.append(f"{ext.domain}.{ext.suffix}".lower())
    return domains


def build_feature_table(df: pd.DataFrame) -> pd.DataFrame:
    """
    Runs every row in the raw dataset through all three feature extractors
    and returns a single flat DataFrame: one row per email, one column per
    feature, ready for model training. The 'label' column is preserved.
    """
    feature_rows = []

    for _, row in df.iterrows():
        body = row["body_text"]
        raw_source = row["raw_email_source"]

        url_domains = _extract_url_domains(body)

        url_feats = extract_url_features(body)
        header_feats = extract_header_features(raw_source, body_url_domains=url_domains)
        text_feats = extract_text_features(body)

        # Merge all three feature dicts into one row. Prefixing keys by
        # source module avoids any accidental name collisions and makes
        # the final feature-importance printout easier to read (you can
        # instantly tell "this signal came from the URL analyzer" etc.)
        combined = {}
        combined.update({f"url__{k}": v for k, v in url_feats.items()})
        combined.update({f"header__{k}": v for k, v in header_feats.items()})
        combined.update({f"text__{k}": v for k, v in text_feats.items()})
        combined["label"] = row["label"]

        feature_rows.append(combined)

    feature_df = pd.DataFrame(feature_rows)

    # Convert boolean columns (True/False) to 0/1 integers — sklearn models
    # want numeric input, and this is a clean lossless conversion.
    bool_cols = feature_df.select_dtypes(include="bool").columns
    feature_df[bool_cols] = feature_df[bool_cols].astype(int)

    return feature_df


def encode_categoricals(feature_df: pd.DataFrame) -> pd.DataFrame:
    """
    One-hot encodes the string-valued header authentication columns
    (header__spf_result, header__dkim_result, header__dmarc_result).

    Done on the FULL dataset before the train/test split — this is safe
    (not data leakage) because we're only fixing the *vocabulary* of
    possible categories (pass/fail/none/softfail/neutral), not learning
    anything about the labels. The model itself never sees the test
    labels during training regardless.
    """
    categorical_full_names = [f"header__{c}" for c in CATEGORICAL_COLUMNS]
    encoded_df = pd.get_dummies(feature_df, columns=categorical_full_names, dtype=int)
    return encoded_df


def train_and_evaluate():
    print("=" * 60)
    print("NUNMAI-MAIL — Model Training")
    print("=" * 60)

    # --- 1. Load raw dataset ---
    if not DATA_PATH.exists():
        raise FileNotFoundError(
            f"Dataset not found at {DATA_PATH}. "
            f"Run 'python data\\generate_synthetic_data.py' first."
        )
    df = pd.read_csv(DATA_PATH)
    print(f"\nLoaded {len(df)} rows from {DATA_PATH.name}")
    print(f"  Phishing (label=1): {(df['label'] == 1).sum()}")
    print(f"  Legitimate (label=0): {(df['label'] == 0).sum()}")

    # --- 2. Build feature table (runs all 3 extractors on every row) ---
    print("\nExtracting features from all rows (this may take a moment)...")
    feature_df = build_feature_table(df)
    feature_df = encode_categoricals(feature_df)
    print(f"Feature extraction complete: {feature_df.shape[1] - 1} features per email")

    # --- 3. Split features (X) from label (y) ---
    X = feature_df.drop(columns=["label"])
    y = feature_df["label"]

    # --- 4. 80/20 stratified train/test split ---
    # stratify=y ensures both the train and test sets keep the same
    # phishing/legit ratio as the full dataset (important since a random
    # split could otherwise accidentally put more of one class in test).
    X_train, X_test, y_train, y_test = train_test_split(
        X, y, test_size=0.2, random_state=42, stratify=y
    )
    print(f"\nTrain set: {len(X_train)} rows | Test set: {len(X_test)} rows")

    # --- 5. 5-fold cross-validation on the TRAINING set only ---
    # This gives a more robust accuracy estimate than trusting a single
    # split: the training data is split into 5 chunks, the model is
    # trained on 4 and validated on the 5th, five times over (each chunk
    # gets a turn as the validation set), and we average the results.
    print("\nRunning 5-fold cross-validation on training set...")
    cv_model = GradientBoostingClassifier(random_state=42)
    cv_scores = cross_val_score(cv_model, X_train, y_train, cv=5, scoring="accuracy")
    print(f"  Cross-validation accuracy per fold: {[round(s, 4) for s in cv_scores]}")
    print(f"  Mean CV accuracy: {cv_scores.mean():.4f}  (+/- {cv_scores.std():.4f})")

    # --- 6. Train the FINAL model on the full training set ---
    print("\nTraining final model on full training set...")
    model = GradientBoostingClassifier(
        n_estimators=200,       # number of boosting stages (trees)
        learning_rate=0.1,      # shrinks each tree's contribution — lower = more conservative
        max_depth=3,            # shallow trees, standard for boosting — prevents overfitting
        random_state=42,
    )
    model.fit(X_train, y_train)

    # --- 7. Evaluate ONCE on the held-out test set ---
    print("\n" + "=" * 60)
    print("HELD-OUT TEST SET RESULTS (data the model never saw)")
    print("=" * 60)
    y_pred = model.predict(X_test)

    accuracy = accuracy_score(y_test, y_pred)
    precision = precision_score(y_test, y_pred)
    recall = recall_score(y_test, y_pred)
    f1 = f1_score(y_test, y_pred)

    print(f"Accuracy:  {accuracy:.4f}")
    print(f"Precision: {precision:.4f}  (of emails flagged phishing, how many really were)")
    print(f"Recall:    {recall:.4f}  (of actual phishing emails, how many we caught)")
    print(f"F1-Score:  {f1:.4f}  (balance of precision and recall)")

    print("\nConfusion Matrix:")
    cm = confusion_matrix(y_test, y_pred)
    print(f"                 Predicted Legit   Predicted Phish")
    print(f"  Actual Legit   {cm[0][0]:>15}   {cm[0][1]:>15}")
    print(f"  Actual Phish   {cm[1][0]:>15}   {cm[1][1]:>15}")

    print("\nFull classification report:")
    print(classification_report(y_test, y_pred, target_names=["Legitimate", "Phishing"]))

    # --- 8. Feature importances — the explainability layer ---
    print("=" * 60)
    print("TOP 15 MOST IMPORTANT FEATURES")
    print("(what the model actually learned to rely on)")
    print("=" * 60)
    importances = pd.Series(model.feature_importances_, index=X.columns)
    top_features = importances.sort_values(ascending=False).head(15)
    for feature_name, importance in top_features.items():
        print(f"  {importance:.4f}  {feature_name}")

    # --- 9. Save model + feature column order for inference ---
    MODEL_OUTPUT_PATH.parent.mkdir(parents=True, exist_ok=True)
    joblib.dump(
        {
            "model": model,
            "feature_columns": list(X.columns),  # exact order the model expects at inference
        },
        MODEL_OUTPUT_PATH,
    )
    print(f"\nModel saved to: {MODEL_OUTPUT_PATH}")
    print("=" * 60)


if __name__ == "__main__":
    train_and_evaluate()