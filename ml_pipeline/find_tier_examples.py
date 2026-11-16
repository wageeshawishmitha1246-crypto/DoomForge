"""Find one example wallet per risk tier (Low/Medium/High) from the trained model's scores.

Reuses split_features_labels from train_model.py rather than re-deriving the
feature-column list, since that function is the single source of truth for
which columns the model was actually trained on.
"""

from __future__ import annotations

import joblib
import pandas as pd

from config import MODELS_DIR, PROCESSED_DATA_DIR
from train_model import split_features_labels

LOW_RISK_THRESHOLD = 0.30
HIGH_RISK_THRESHOLD = 0.70


def main() -> None:
    df = pd.read_csv(PROCESSED_DATA_DIR / "wallet_features_labeled.csv")
    model = joblib.load(MODELS_DIR / "random_forest.joblib")

    X, _ = split_features_labels(df)
    df["risk_score"] = model.predict_proba(X)[:, 1]

    low_example = df[df["risk_score"] < LOW_RISK_THRESHOLD].sort_values("risk_score").head(1)
    medium_pool = df[(df["risk_score"] >= LOW_RISK_THRESHOLD) & (df["risk_score"] < HIGH_RISK_THRESHOLD)]
    medium_example = medium_pool.sample(1, random_state=1) if len(medium_pool) else medium_pool
    high_example = df[df["risk_score"] >= HIGH_RISK_THRESHOLD].sort_values("risk_score", ascending=False).head(1)

    for tier_name, subset in [("LOW", low_example), ("MEDIUM", medium_example), ("HIGH", high_example)]:
        if len(subset) > 0:
            print(f"\n{tier_name} example:")
            print(subset[["wallet_address", "risk_score"]].to_string(index=False))
        else:
            print(f"\n{tier_name}: no wallets found in this range")


if __name__ == "__main__":
    main()
