"""Score a wallet's risk from its full transaction history and submit the
result on-chain via AdaptiveCryptoSecurity.

Unlike a per-transaction score, this scores one wallet using every
transaction it has ever sent or received, since that's what the trained
model's features (tx_frequency_per_day, unique_counterparties_sent, etc.)
are computed from.
"""

from __future__ import annotations

import argparse
import os
import sys
from pathlib import Path

import joblib

ML_PIPELINE_DIR = Path(__file__).resolve().parents[1] / "ml_pipeline"
sys.path.insert(0, str(ML_PIPELINE_DIR))

from config import MODELS_DIR  # noqa: E402
from feature_engineering import build_wallet_level_features, load_clean_transactions  # noqa: E402

from adaptive_crypto_bridge import load_contract, process_transaction  # noqa: E402

LOW_RISK_THRESHOLD = 0.30
HIGH_RISK_THRESHOLD = 0.70


def score_wallet(wallet_address: str, model_name: str = "random_forest") -> float:
    """Compute a risk score in [0, 1] for one wallet from its full transaction history.

    build_wallet_level_features groups by "from"/"to" internally, so it must run
    on every transaction, not a pre-filtered subset, or the received-side and
    counterparty stats for this wallet will be missing.
    """
    tx_df = load_clean_transactions()
    wallet_features = build_wallet_level_features(tx_df)

    row = wallet_features.loc[wallet_features["wallet_address"].str.lower() == wallet_address.lower()]
    if row.empty:
        raise ValueError(f"No transaction history found for wallet {wallet_address}")

    model = joblib.load(MODELS_DIR / f"{model_name}.joblib")
    X = row.select_dtypes(include=["number"])
    return float(model.predict_proba(X)[0, 1])


def risk_score_to_level(score: float) -> int:
    """Map a risk score to RiskLevel: 0 = Low, 1 = Medium, 2 = High."""
    if score < LOW_RISK_THRESHOLD:
        return 0
    if score < HIGH_RISK_THRESHOLD:
        return 1
    return 2


def main() -> None:
    parser = argparse.ArgumentParser(description="Score a wallet and submit the result on-chain.")
    parser.add_argument("wallet_address", help="Wallet to score (must appear in the transaction history).")
    parser.add_argument("recipient", help="Recipient address for the on-chain transaction.")
    parser.add_argument("--model", default="random_forest", choices=["random_forest", "logistic_regression"])
    parser.add_argument("--attestor", default=os.getenv("ATTESTOR_ADDRESS"), help="Required if risk resolves to High.")
    parser.add_argument("--value-eth", type=float, default=0.0)
    parser.add_argument(
        "--onchain-sender",
        default=None,
        help=(
            "Address that actually signs and submits the on-chain transaction. "
            "Defaults to wallet_address, but that only works if the node controls "
            "its private key (true for local Ganache accounts, not for real "
            "historical wallet addresses pulled from Etherscan). Pass one of "
            "Ganache's own accounts here to demo the on-chain path for a wallet "
            "whose history you're scoring but whose key you don't hold."
        ),
    )
    args = parser.parse_args()

    score = score_wallet(args.wallet_address, args.model)
    risk_level = risk_score_to_level(score)
    tier_name = {0: "Low", 1: "Medium", 2: "High"}[risk_level]
    print(f"Wallet {args.wallet_address}: risk_score={score:.3f} -> {tier_name} (risk_level={risk_level})")

    onchain_sender = args.onchain_sender or args.wallet_address

    w3, contract = load_contract()
    receipt = process_transaction(
        w3,
        contract,
        onchain_sender,
        args.recipient,
        risk_level,
        attestor=args.attestor,
        value_eth=args.value_eth,
    )
    print(f"On-chain tx status: {receipt.status} | Tier: {tier_name} | Gas used: {receipt.gasUsed}")
    for log in contract.events.RiskAssessed().process_receipt(receipt):
        print(" ", log["args"])


if __name__ == "__main__":
    main()
