"""Risk engine for DoomForge Lab: the thesis Random Forest, unchanged.

Existing wallets are the 99 real Ethereum wallets collected from Etherscan.
Their 17 features come from their real transaction history. A new wallet has
no history, so no features can be computed: it is treated as "Unknown" and
given the Medium tier by platform rule (not a model prediction).
"""

from __future__ import annotations

import random
from functools import lru_cache

import joblib
import pandas as pd

from . import config

FEATURE_GROUPS = {
    "Volume and value": ["sent_tx_count", "recv_tx_count", "total_tx_count", "sent_total_value_eth",
                         "sent_avg_value_eth", "recv_total_value_eth", "recv_avg_value_eth",
                         "sent_received_value_ratio"],
    "Temporal": ["from_avg_time_between_txs_sec", "from_min_time_between_txs_sec", "from_active_days",
                 "tx_frequency_per_day"],
    "Counterparty": ["unique_counterparties_sent", "unique_counterparties_received"],
    "Behaviour": ["sent_failed_ratio", "sent_avg_gas_price", "contract_interaction_ratio"],
}
RULE_FEATURES = {"sent_total_value_eth", "tx_frequency_per_day", "unique_counterparties_sent",
                 "sent_failed_ratio", "contract_interaction_ratio"}


def score_to_tier(score: float) -> int:
    if score < config.LOW_RISK_THRESHOLD:
        return 0
    if score < config.HIGH_RISK_THRESHOLD:
        return 1
    return 2


@lru_cache(maxsize=1)
def model():
    from config import MODELS_DIR  # ml_pipeline/config.py

    return joblib.load(MODELS_DIR / "random_forest.joblib")


@lru_cache(maxsize=1)
def scored_wallets() -> pd.DataFrame:
    """All 99 history wallets with their features, model score and tier."""
    from config import PROCESSED_DATA_DIR
    from train_model import split_features_labels

    df = pd.read_csv(PROCESSED_DATA_DIR / "wallet_features_labeled.csv")
    X, _ = split_features_labels(df)
    df["risk_score"] = model().predict_proba(X)[:, 1]
    df["tier"] = df["risk_score"].apply(score_to_tier)
    df["n_trees"] = len(model().named_steps["clf"].estimators_) if hasattr(model(), "named_steps") else 200
    return df


def pick_wallet(tier: int | None) -> pd.Series:
    """A random history wallet, optionally from one tier (0 Low, 1 Medium, 2 High)."""
    df = scored_wallets()
    pool = df if tier is None else df[df["tier"] == tier]
    if pool.empty:
        pool = df
    return pool.iloc[random.randrange(len(pool))]


def wallet_row(address: str) -> pd.Series | None:
    df = scored_wallets()
    hit = df[df["wallet_address"].str.lower() == address.lower()]
    return None if hit.empty else hit.iloc[0]


def tier_counts() -> dict[int, int]:
    return scored_wallets()["tier"].value_counts().to_dict()


def feature_table(row: pd.Series) -> pd.DataFrame:
    rows = []
    for group, cols in FEATURE_GROUPS.items():
        for col in cols:
            val = row.get(col)
            rows.append({
                "Group": group,
                "Feature": col + (" †" if col in RULE_FEATURES else ""),
                "Value": "missing (filled with training median)" if pd.isna(val) else f"{val:,.4g}",
            })
    return pd.DataFrame(rows)
