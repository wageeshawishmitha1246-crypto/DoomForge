"""Preprocessing utilities for Ethereum transaction data.

This module loads raw CSV files produced by data_collection.py and
performs basic cleaning:
- normalize column names
- keep a consistent set of important fields
- convert types (numeric, timestamps)
- handle missing fields safely

The cleaned output is saved to data/processed/processed_transactions.csv
and is used as input to feature_engineering.py.
"""

from __future__ import annotations

from pathlib import Path
from typing import List

import numpy as np
import pandas as pd

from config import PROCESSED_DATA_DIR, RAW_DATA_DIR


IMPORTANT_COLUMNS: List[str] = [
    "hash",
    "from",
    "to",
    "value",
    "gas",
    "gasprice",
    "gasUsed",  # present for some endpoints
    "timeStamp",
    "isError",
    "methodId",
    "functionName",
    "blockNumber",
    "contractAddress",  # useful for contract interactions
    "input",  # raw input data, can be parsed later
    "queried_address",  # added in data_collection.py
]


def _load_if_exists(path: Path) -> pd.DataFrame:
    """Load a CSV if it exists, otherwise return an empty DataFrame."""

    if not path.exists():
        return pd.DataFrame()
    return pd.read_csv(path)


def load_raw_transactions() -> pd.DataFrame:
    """Load all available raw transaction CSVs and concatenate them.

    Returns an empty DataFrame if nothing is found.
    """

    paths = [
        RAW_DATA_DIR / "normal_transactions.csv",
        RAW_DATA_DIR / "internal_transactions.csv",
        RAW_DATA_DIR / "erc20_transfers.csv",
    ]

    frames = []
    for p in paths:
        df = _load_if_exists(p)
        if not df.empty:
            frames.append(df)

    if not frames:
        return pd.DataFrame()

    combined = pd.concat(frames, ignore_index=True, sort=False)
    return combined


def clean_transactions(df: pd.DataFrame) -> pd.DataFrame:
    """Clean and normalize raw transaction data.

    - Standardizes column names to lower-case.
    - Ensures all IMPORTANT_COLUMNS exist (creates missing ones with NaN).
    - Converts numeric fields to numeric dtypes.
    - Parses timestamps to datetime and keeps both raw and parsed versions.
    """

    if df.empty:
        return df

    # Normalize column names
    df = df.copy()
    df.columns = [c.lower() for c in df.columns]

    # Ensure all important columns exist
    for col in IMPORTANT_COLUMNS:
        col_lower = col.lower()
        if col_lower not in df.columns:
            df[col_lower] = np.nan

    # Keep only the important columns for now
    df = df[[c.lower() for c in IMPORTANT_COLUMNS]]

    # Type conversions
    for col in ["value", "gas", "gasprice", "gasused"]:
        if col in df.columns:
            df[col] = pd.to_numeric(df[col], errors="coerce")

    for col in ["blocknumber", "timestamp"]:
        # Some endpoints use "timeStamp"; we normalized it to lowercase.
        if col == "timestamp":
            src = "timestamp"
        else:
            src = col
        if src in df.columns:
            df[src] = pd.to_numeric(df[src], errors="coerce")

    # isError is "0" or "1" for many endpoints
    if "iserror" in df.columns:
        df["iserror"] = pd.to_numeric(df["iserror"], errors="coerce").fillna(0).astype(int)

    # Parse timestamps to a real datetime column; keep the raw numeric seconds as well.
    if "timestamp" in df.columns:
        df["timestamp"] = pd.to_numeric(df["timestamp"], errors="coerce")
        df["timestamp_dt"] = pd.to_datetime(df["timestamp"], unit="s", errors="coerce")

    # Convert value from Wei to ETH for convenience
    if "value" in df.columns:
        df["value_eth"] = df["value"] / 1e18

    return df


def save_clean_transactions(df: pd.DataFrame) -> Path:
    """Save the cleaned transactions to the processed data directory."""

    PROCESSED_DATA_DIR.mkdir(parents=True, exist_ok=True)
    out_path = PROCESSED_DATA_DIR / "processed_transactions.csv"
    df.to_csv(out_path, index=False)
    return out_path


def main() -> None:
    """Run the preprocessing pipeline end-to-end."""

    print("Loading raw transactions from data/raw/...")
    raw_df = load_raw_transactions()

    if raw_df.empty:
        print("No raw transactions found. Run data_collection.py first.")
        return

    print(f"Loaded {len(raw_df):,} raw records. Cleaning...")
    clean_df = clean_transactions(raw_df)
    out_path = save_clean_transactions(clean_df)
    print(f"Saved cleaned transactions to {out_path}")


if __name__ == "__main__":
    main()
