"""Create documented hybrid labels for wallet-level risk-model training.

Labels are a project-scoped approximation, not ground truth:
* known scam-address matches are verified positives;
* unlisted wallets with two or more risk indicators are inferred positives;
* every other wallet is an assumed negative.

The original wallet_features.csv is never overwritten. Train with the generated
wallet_features_labeled.csv file explicitly.
"""

from __future__ import annotations

import argparse
import json
import re
from collections.abc import Iterator
from pathlib import Path

import pandas as pd

from config import PROCESSED_DATA_DIR, RAW_DATA_DIR


ADDRESS_PATTERN = re.compile(r"^0x[a-fA-F0-9]{40}$")
DEFAULT_FEATURES_PATH = PROCESSED_DATA_DIR / "wallet_features.csv"
DEFAULT_OUTPUT_PATH = PROCESSED_DATA_DIR / "wallet_features_labeled.csv"
DEFAULT_KNOWN_SCAMS_PATH = RAW_DATA_DIR / "known_scam_addresses.json"


def iter_strings(value: object) -> Iterator[str]:
    """Yield strings recursively from a JSON value of any supported shape."""
    if isinstance(value, str):
        yield value
    elif isinstance(value, list):
        for item in value:
            yield from iter_strings(item)
    elif isinstance(value, dict):
        for item in value.values():
            yield from iter_strings(item)


def load_known_scam_addresses(path: Path) -> set[str]:
    """Extract Ethereum addresses from a downloaded CryptoScamDB-style JSON file."""
    if not path.exists():
        print(f"Known-scam file not found at {path}; continuing without verified matches.")
        return set()

    with path.open(encoding="utf-8") as source:
        payload = json.load(source)

    addresses = {
        value.lower()
        for value in iter_strings(payload)
        if ADDRESS_PATTERN.fullmatch(value.strip())
    }
    print(f"Loaded {len(addresses):,} Ethereum addresses from {path}")
    return addresses


def percentile_indicator(series: pd.Series, percentile: float = 0.90) -> pd.Series:
    """Mark values at or above the population percentile, ignoring missing data."""
    valid = series.dropna()
    if valid.empty:
        return pd.Series(False, index=series.index)
    return series.ge(valid.quantile(percentile)).fillna(False)


def build_heuristic_indicators(features: pd.DataFrame) -> pd.DataFrame:
    """Return transparent behavioral signals used only for pseudo-labeling.

    The percentile-based signals adapt to small datasets; the failed-transfer
    and contract-interaction rules use fixed, interpretable boundaries.
    """
    required = {
        "sent_failed_ratio",
        "sent_total_value_eth",
        "tx_frequency_per_day",
        "unique_counterparties_sent",
        "contract_interaction_ratio",
    }
    missing = required.difference(features.columns)
    if missing:
        raise ValueError(f"Missing required feature columns: {', '.join(sorted(missing))}")

    return pd.DataFrame(
        {
            "high_failed_transfer_ratio": features["sent_failed_ratio"].ge(0.50),
            "high_value_transfer": percentile_indicator(features["sent_total_value_eth"]),
            "high_transaction_frequency": percentile_indicator(features["tx_frequency_per_day"]),
            "many_unique_counterparties": percentile_indicator(
                features["unique_counterparties_sent"]
            ),
            "high_contract_interaction_ratio": features["contract_interaction_ratio"].ge(0.50),
        },
        index=features.index,
    ).fillna(False)


def label_wallets(features: pd.DataFrame, known_scams: set[str]) -> pd.DataFrame:
    """Add label, source, confidence, and an auditable heuristic explanation."""
    if "wallet_address" not in features.columns:
        raise ValueError("wallet_features.csv must contain a wallet_address column.")

    labeled = features.copy()
    indicators = build_heuristic_indicators(labeled)
    indicator_count = indicators.sum(axis=1)
    known_scam_match = labeled["wallet_address"].str.lower().isin(known_scams)
    heuristic_match = indicator_count.ge(2) & ~known_scam_match

    labeled["label"] = (known_scam_match | heuristic_match).astype(int)
    labeled["label_source"] = "default_negative"
    labeled["label_confidence"] = "assumed"
    labeled.loc[heuristic_match, ["label_source", "label_confidence"]] = [
        "heuristic",
        "inferred",
    ]
    labeled.loc[known_scam_match, ["label_source", "label_confidence"]] = [
        "known_scam",
        "verified",
    ]
    labeled["heuristic_indicator_count"] = indicator_count.astype(int)
    labeled["heuristic_indicators"] = indicators.apply(
        lambda row: ";".join(name for name, triggered in row.items() if triggered), axis=1
    )
    return labeled


def main() -> None:
    parser = argparse.ArgumentParser(description="Generate documented hybrid wallet labels.")
    parser.add_argument("--features-path", type=Path, default=DEFAULT_FEATURES_PATH)
    parser.add_argument("--known-scam-path", type=Path, default=DEFAULT_KNOWN_SCAMS_PATH)
    parser.add_argument("--output-path", type=Path, default=DEFAULT_OUTPUT_PATH)
    args = parser.parse_args()

    features = pd.read_csv(args.features_path)
    known_scams = load_known_scam_addresses(args.known_scam_path)
    labeled = label_wallets(features, known_scams)

    args.output_path.parent.mkdir(parents=True, exist_ok=True)
    labeled.to_csv(args.output_path, index=False)
    print(f"Saved {len(labeled):,} labeled wallets to {args.output_path}")
    print("Label distribution:")
    print(labeled.groupby(["label", "label_source"]).size().to_string())
    print("\nCaution: default-negative labels are assumed, not verified legitimate wallets.")


if __name__ == "__main__":
    main()
