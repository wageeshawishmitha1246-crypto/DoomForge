"""Feature engineering for Ethereum transaction risk modeling.

This module takes cleaned transaction data and builds simple
transaction-level and wallet-level behavioral features, such as:
- transaction value in ETH
- gas price and gas used statistics
- transaction frequency per wallet
- time gaps between transactions
- number of unique counterparties
- sent/received value ratio
- failed transaction ratio
- average transaction value
- (placeholder) contract interaction ratio

The output is a wallet-level feature table saved under
data/processed/wallet_features.csv.
"""

from __future__ import annotations

from pathlib import Path
from typing import Tuple

import numpy as np
import pandas as pd

from config import PROCESSED_DATA_DIR


def load_clean_transactions() -> pd.DataFrame:
    """Load cleaned transactions produced by preprocessing.py."""

    path = PROCESSED_DATA_DIR / "processed_transactions.csv"
    if not path.exists():
        raise FileNotFoundError(
            f"Processed transactions not found at {path}. Run preprocessing.py first."
        )
    return pd.read_csv(path, parse_dates=["timestamp_dt"])


def build_transaction_level_features(df: pd.DataFrame) -> pd.DataFrame:
    """Return the same DataFrame; this function is a placeholder.

    For now, the basic transaction-level fields (value_eth, gas, gasprice,
    iserror, timestamp_dt, from, to, etc.) are already enough for a
    baseline. More complex per-transaction features can be added later.
    """

    return df


def _wallet_time_features(df: pd.DataFrame, address_col: str) -> pd.DataFrame:
    """Compute time-based statistics for wallets based on a given column.

    Parameters
    ----------
    df:
        Cleaned transaction DataFrame.
    address_col:
        Column name to treat as the wallet identifier ("from" or "to").
    """

    # Drop rows without a valid timestamp
    ts_df = df.dropna(subset=["timestamp_dt"]).copy()
    ts_df = ts_df.sort_values("timestamp_dt")

    groups = ts_df.groupby(address_col)

    records = []
    for wallet, g in groups:
        times = g["timestamp_dt"].sort_values()
        if len(times) > 1:
            deltas = times.diff().dropna().dt.total_seconds()
            avg_gap = float(deltas.mean())
            min_gap = float(deltas.min())
        else:
            avg_gap = np.nan
            min_gap = np.nan

        first = times.min()
        last = times.max()
        active_seconds = max((last - first).total_seconds(), 1.0)
        active_days = active_seconds / (24 * 3600)

        records.append(
            {
                "wallet_address": wallet,
                f"{address_col}_avg_time_between_txs_sec": avg_gap,
                f"{address_col}_min_time_between_txs_sec": min_gap,
                f"{address_col}_active_days": active_days,
            }
        )

    return pd.DataFrame.from_records(records)


def build_wallet_level_features(df: pd.DataFrame) -> pd.DataFrame:
    """Aggregate transaction data into wallet-level behavioral features."""

    if df.empty:
        return pd.DataFrame()

    df = df.copy()

    # Basic group-bys for sent and received sides
    sent = (
        df.groupby("from")
        .agg(
            sent_tx_count=("hash", "count"),
            sent_total_value_eth=("value_eth", "sum"),
            sent_avg_value_eth=("value_eth", "mean"),
            sent_failed_ratio=("iserror", "mean"),
            sent_avg_gas_price=("gasprice", "mean"),
        )
        .rename_axis("wallet_address")
    )

    received = (
        df.groupby("to")
        .agg(
            recv_tx_count=("hash", "count"),
            recv_total_value_eth=("value_eth", "sum"),
            recv_avg_value_eth=("value_eth", "mean"),
        )
        .rename_axis("wallet_address")
    )

    # Unique counterparties for each wallet
    # For senders: unique "to" addresses, for receivers: unique "from" addresses.
    unique_cp_from = (
        df.dropna(subset=["from", "to"])
        .groupby("from")["to"]
        .nunique()
        .rename("unique_counterparties_sent")
    )
    unique_cp_to = (
        df.dropna(subset=["from", "to"])
        .groupby("to")["from"]
        .nunique()
        .rename("unique_counterparties_received")
    )

    # Merge everything on wallet_address
    wallet = sent.join(received, how="outer")
    wallet = wallet.join(unique_cp_from, how="left")
    wallet = wallet.join(unique_cp_to, how="left")

    wallet["sent_tx_count"] = wallet["sent_tx_count"].fillna(0)
    wallet["recv_tx_count"] = wallet["recv_tx_count"].fillna(0)

    wallet["total_tx_count"] = wallet["sent_tx_count"] + wallet["recv_tx_count"]

    # Sent/received value ratio
    wallet["sent_received_value_ratio"] = wallet["sent_total_value_eth"] / (
        wallet["recv_total_value_eth"].replace({0: np.nan})
    )

    # Failed transaction ratio (only really meaningful for senders)
    wallet["sent_failed_ratio"] = wallet["sent_failed_ratio"].fillna(0.0)

    # Approximate transaction frequency using active days from the "from" side
    time_features_from = _wallet_time_features(df, address_col="from")
    wallet = wallet.join(time_features_from.set_index("wallet_address"), how="left")

    wallet["tx_frequency_per_day"] = wallet["total_tx_count"] / (
        wallet["from_active_days"].replace({0: np.nan})
    )

    # Placeholder contract interaction ratio.
    # In this baseline, we simply flag transactions where contractAddress is
    # non-null as contract interactions. Later, you can refine this using
    # full contract metadata or bytecode analysis.
    if "contractaddress" in df.columns:
        df["is_contract_interaction"] = df["contractaddress"].notna() & (df["contractaddress"] != "")
    else:
        df["is_contract_interaction"] = False

    contract_ratio = (
        df.groupby("from")["is_contract_interaction"]
        .mean()
        .rename("contract_interaction_ratio")
    )
    wallet = wallet.join(contract_ratio, how="left")

    wallet.reset_index(inplace=True)

    return wallet


def save_wallet_features(df: pd.DataFrame) -> Path:
    """Save wallet-level features to the processed directory."""

    PROCESSED_DATA_DIR.mkdir(parents=True, exist_ok=True)
    out_path = PROCESSED_DATA_DIR / "wallet_features.csv"
    df.to_csv(out_path, index=False)
    return out_path


def run_feature_engineering() -> Tuple[Path, pd.DataFrame]:
    """End-to-end feature engineering entrypoint."""

    tx_df = load_clean_transactions()
    tx_df = build_transaction_level_features(tx_df)
    wallet_df = build_wallet_level_features(tx_df)

    if wallet_df.empty:
        raise RuntimeError("No wallet-level features were generated.")

    out_path = save_wallet_features(wallet_df)
    return out_path, wallet_df


def main() -> None:
    print("Loading cleaned transactions and building features...")
    try:
        out_path, wallet_df = run_feature_engineering()
    except Exception as exc:  # noqa: BLE001
        print(f"Error during feature engineering: {exc}")
        return

    print(f"Built wallet-level features for {len(wallet_df):,} wallets.")
    print(f"Saved wallet features to {out_path}")


if __name__ == "__main__":
    main()
