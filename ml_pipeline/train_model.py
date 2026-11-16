"""Train baseline ML models for Ethereum transaction/wallet risk.

This script trains simple baseline models (Logistic Regression and
Random Forest) on wallet-level features produced by
feature_engineering.py.

Important:
- The script expects a binary label column named "label" in the
  wallet_features.csv file.
- If labels are not yet available, it will explain how to add them and
  exit gracefully.

Later, you can plug in real fraud labels from external datasets and
reuse this script without changing the overall structure.
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path
from typing import List, Tuple

import joblib
import numpy as np
import pandas as pd
from sklearn.ensemble import RandomForestClassifier
from sklearn.impute import SimpleImputer
from sklearn.linear_model import LogisticRegression
from sklearn.model_selection import train_test_split
from sklearn.pipeline import Pipeline
from sklearn.preprocessing import StandardScaler

from config import MODELS_DIR, PROCESSED_DATA_DIR
from evaluate import compute_classification_metrics, pretty_print_metrics


def load_features(path: Path) -> pd.DataFrame:
    """Load wallet-level features from CSV."""

    if not path.exists():
        raise FileNotFoundError(
            f"Wallet feature file not found at {path}. Run feature_engineering.py first."
        )
    return pd.read_csv(path)


def split_features_labels(df: pd.DataFrame) -> Tuple[pd.DataFrame, pd.Series]:
    """Split a DataFrame into feature matrix X and label vector y.

    The function assumes the label column is named "label" and that all
    other columns are features. If the label column does not exist,
    an informative exception is raised.
    """

    if "label" not in df.columns:
        raise KeyError(
            "No 'label' column found in wallet_features.csv. "
            "Add a binary label column (0 = non-risky, 1 = risky) before training."
        )

    y = df["label"].astype(int)
    # Label provenance is retained in the CSV for auditability, but must never
    # be used as a model feature. In particular, heuristic_indicator_count
    # directly encodes how the pseudo-label was assigned.
    label_metadata_columns = {
        "label",
        "label_source",
        "label_confidence",
        "heuristic_indicator_count",
        "heuristic_indicators",
    }
    X = df.drop(columns=label_metadata_columns.intersection(df.columns))

    # Keep numeric columns for this baseline to avoid failures caused by
    # string identifiers such as wallet_address.
    X = X.select_dtypes(include=["number"]).copy()
    if X.empty:
        raise ValueError(
            "No numeric feature columns found after removing 'label'. "
            "Ensure wallet_features.csv contains engineered numeric features."
        )
    return X, y


def build_models(random_state: int = 42) -> List[Tuple[str, object]]:
    """Construct baseline models with reasonable default hyperparameters."""

    log_reg_pipeline = Pipeline(
        steps=[
            ("imputer", SimpleImputer(strategy="median")),
            ("scaler", StandardScaler()),
            (
                "clf",
                LogisticRegression(
                    max_iter=1000,
                    class_weight="balanced",
                    n_jobs=None,
                ),
            ),
        ]
    )

    rf = Pipeline(
        steps=[
            ("imputer", SimpleImputer(strategy="median")),
            (
                "clf",
                RandomForestClassifier(
                    n_estimators=200,
                    random_state=random_state,
                    n_jobs=-1,
                    class_weight="balanced",
                ),
            ),
        ]
    )

    return [
        ("logistic_regression", log_reg_pipeline),
        ("random_forest", rf),
    ]


def train_and_evaluate_models(
    X: pd.DataFrame,
    y: pd.Series,
    test_size: float = 0.2,
    random_state: int = 42,
) -> None:
    """Train baseline models and print evaluation metrics."""

    # Only drop rows missing a label; missing feature values are handled by
    # each pipeline's SimpleImputer, so dropping on X here would discard rows
    # unnecessarily given how sparse some engineered features are.
    labeled_mask = y.notna()
    X = X.loc[labeled_mask]
    y = y.loc[labeled_mask].astype(int)

    if y.nunique() < 2:
        raise ValueError(
            "Label column contains only one class. Add both risky and non-risky "
            "examples before training."
        )

    X_train, X_test, y_train, y_test = train_test_split(
        X,
        y,
        test_size=test_size,
        random_state=random_state,
        stratify=y,
    )

    models = build_models(random_state=random_state)

    MODELS_DIR.mkdir(parents=True, exist_ok=True)

    for name, model in models:
        print(f"\nTraining {name}...")
        model.fit(X_train, y_train)

        y_pred = model.predict(X_test)
        # Some models expose predict_proba, others might not; handle both.
        if hasattr(model, "predict_proba"):
            y_proba = model.predict_proba(X_test)[:, 1]
        else:
            y_proba = None

        metrics = compute_classification_metrics(y_test, y_pred, y_proba)
        pretty_print_metrics(f"Evaluation for {name}", metrics)

        model_path = MODELS_DIR / f"{name}.joblib"
        joblib.dump(model, model_path)
        print(f"Saved trained model to {model_path}")


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Train baseline risk models on wallet-level features.",
    )
    parser.add_argument(
        "--features-path",
        type=str,
        default=str(PROCESSED_DATA_DIR / "wallet_features.csv"),
        help="Path to the wallet_features.csv file.",
    )
    parser.add_argument(
        "--test-size",
        type=float,
        default=0.2,
        help="Fraction of data to use as test set (0-1).",
    )

    args = parser.parse_args()

    try:
        features_df = load_features(Path(args.features_path))
        X, y = split_features_labels(features_df)
        train_and_evaluate_models(X, y, test_size=args.test_size)
    except Exception as exc:  # noqa: BLE001
        print(f"Error during training: {exc}")
        print(
            "If you do not yet have labels, add a 'label' column to "
            "wallet_features.csv (0 = non-risky, 1 = risky) before rerunning."
        )
        sys.exit(1)


if __name__ == "__main__":
    main()
