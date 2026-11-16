"""Day 3: run a batch of real wallets end-to-end (CSV -> features -> model ->
risk level -> contract call -> on-chain event) and log gas usage per tier.

Samples up to `--per-tier` wallets from each of Low/Medium/High (fewer if a
tier doesn't have enough candidates) using the already-trained model's scores,
then submits each through the deployed contract and records gas used.
"""

from __future__ import annotations

import argparse
import csv
import os
import sys
from pathlib import Path

import joblib

ML_PIPELINE_DIR = Path(__file__).resolve().parents[1] / "ml_pipeline"
sys.path.insert(0, str(ML_PIPELINE_DIR))

from config import MODELS_DIR, PROCESSED_DATA_DIR  # noqa: E402
from train_model import split_features_labels  # noqa: E402

import pandas as pd  # noqa: E402

import adaptive_crypto_bridge as bridge  # noqa: E402
from adaptive_crypto_bridge import load_contract, process_transaction  # noqa: E402
from risk_to_chain import LOW_RISK_THRESHOLD, HIGH_RISK_THRESHOLD, risk_score_to_level  # noqa: E402

TIER_NAMES = {0: "Low", 1: "Medium", 2: "High"}


def pick_batch(per_tier: int, seed: int) -> pd.DataFrame:
    df = pd.read_csv(PROCESSED_DATA_DIR / "wallet_features_labeled.csv")
    model = joblib.load(MODELS_DIR / "random_forest.joblib")

    X, _ = split_features_labels(df)
    df["risk_score"] = model.predict_proba(X)[:, 1]

    low_pool = df[df["risk_score"] < LOW_RISK_THRESHOLD]
    medium_pool = df[(df["risk_score"] >= LOW_RISK_THRESHOLD) & (df["risk_score"] < HIGH_RISK_THRESHOLD)]
    high_pool = df[df["risk_score"] >= HIGH_RISK_THRESHOLD]

    picks = []
    for name, pool in [("Low", low_pool), ("Medium", medium_pool), ("High", high_pool)]:
        n = min(per_tier, len(pool))
        if n < per_tier:
            print(f"Note: only {len(pool)} wallet(s) available for {name} tier (wanted {per_tier}).")
        if n > 0:
            picks.append(pool.sample(n, random_state=seed))

    return pd.concat(picks, ignore_index=True) if picks else df.iloc[0:0]


def main() -> None:
    parser = argparse.ArgumentParser(description="Day 3 batch test: score wallets and submit on-chain.")
    parser.add_argument("--per-tier", type=int, default=3, help="Target wallets per tier (Low/Medium/High).")
    parser.add_argument("--seed", type=int, default=42)
    parser.add_argument("--recipient", default="0x5e8ad2fdba56a7098fd7e680948d1a458d282ae5")
    parser.add_argument("--onchain-sender", default="0xc463ec39975fb1ee40ebe0091282e154533bfda0")
    parser.add_argument("--attestor", default=os.getenv("ATTESTOR_ADDRESS"))
    parser.add_argument("--out", default="day3_gas_log.csv")
    args = parser.parse_args()

    batch = pick_batch(args.per_tier, args.seed)
    print(f"\nSelected {len(batch)} wallets for the batch run.\n")

    w3, contract = load_contract()
    rows = []

    for _, wallet_row in batch.iterrows():
        wallet_address = wallet_row["wallet_address"]
        score = float(wallet_row["risk_score"])
        risk_level = risk_score_to_level(score)
        tier_name = TIER_NAMES[risk_level]

        receipt = process_transaction(
            w3,
            contract,
            args.onchain_sender,
            args.recipient,
            risk_level,
            attestor=args.attestor,
        )

        att = bridge.LAST_PQ_ATTESTATION if risk_level == 2 else None
        bridge.LAST_PQ_ATTESTATION = None
        print(
            f"{wallet_address} | score={score:.3f} | tier={tier_name} | "
            f"status={receipt.status} | gas_used={receipt.gasUsed}"
        )
        rows.append(
            {
                "wallet_address": wallet_address,
                "risk_score": score,
                "tier": tier_name,
                "tx_status": receipt.status,
                "gas_used": receipt.gasUsed,
                "tx_hash": receipt.transactionHash.hex(),
                "pq_sign_ms": round(att.dilithium_sign_ms + att.sphincs_sign_ms, 3) if att else "",
                "pq_verify_ms": round(att.dilithium_verify_ms + att.sphincs_verify_ms, 3) if att else "",
                "pq_audit_file": Path(att.audit_file).name if att else "",
            }
        )

    out_path = Path(args.out)
    with out_path.open("w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=["wallet_address", "risk_score", "tier", "tx_status", "gas_used", "tx_hash", "pq_sign_ms", "pq_verify_ms", "pq_audit_file"])
        writer.writeheader()
        writer.writerows(rows)

    print(f"\nSaved {len(rows)} rows to {out_path.resolve()}")

    if rows:
        by_tier: dict[str, list[int]] = {}
        for row in rows:
            by_tier.setdefault(row["tier"], []).append(row["gas_used"])
        print("\nAverage gas by tier:")
        for tier_name, gas_values in by_tier.items():
            print(f"  {tier_name}: {sum(gas_values) / len(gas_values):.0f} (n={len(gas_values)})")


if __name__ == "__main__":
    main()
