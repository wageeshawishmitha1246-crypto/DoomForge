"""Settings for DoomForge Lab, read from lab/.env (see .env.example)."""

from __future__ import annotations

import os
import sys
from pathlib import Path

from dotenv import load_dotenv

LAB_DIR = Path(__file__).resolve().parents[1]
REPO_DIR = LAB_DIR.parent
INTEGRATION_DIR = REPO_DIR / "integration"
ML_PIPELINE_DIR = REPO_DIR / "ml_pipeline"

load_dotenv(LAB_DIR / ".env")

# Make the existing project code importable (risk model, PQ attestor).
for p in (INTEGRATION_DIR, ML_PIPELINE_DIR):
    if str(p) not in sys.path:
        sys.path.insert(0, str(p))

# --- blockchain -------------------------------------------------------------
RPC_URL = os.getenv("RPC_URL", "http://127.0.0.1:8545")
CONTRACT_ADDRESS = os.getenv("CONTRACT_ADDRESS", "")
ATTESTOR_PRIVATE_KEY = os.getenv("ATTESTOR_PRIVATE_KEY", "")
FAUCET_PRIVATE_KEY = os.getenv("FAUCET_PRIVATE_KEY", "")
NETWORK_NAME = os.getenv("NETWORK_NAME", "Sepolia")
EXPLORER_URL = os.getenv("EXPLORER_URL", "https://sepolia.etherscan.io").rstrip("/")
TOPUP_ETH = float(os.getenv("TOPUP_ETH", "0.01"))
ACCESS_CODE = os.getenv("ACCESS_CODE", "")  # if set, needed to create a wallet
MAX_TOPUPS_PER_ACCOUNT = int(os.getenv("MAX_TOPUPS_PER_ACCOUNT", "3"))
TX_TIMEOUT_SECONDS = int(os.getenv("TX_TIMEOUT_SECONDS", "180"))

# --- risk tiers (same as the thesis) ----------------------------------------
LOW_RISK_THRESHOLD = 0.30
HIGH_RISK_THRESHOLD = 0.70
NEW_WALLET_TIER = 1  # no history -> "Unknown", treated as Medium

# --- network data (Ethereum mainnet, from Etherscan) ------------------------
ETHERSCAN_API_KEY = os.getenv("ETHERSCAN_API_KEY", "")
ETHERSCAN_URL = "https://api.etherscan.io/v2/api"
NETWORK_DELAY_SECONDS = int(os.getenv("NETWORK_DELAY_SECONDS", "3600"))
COLLECT_EVERY_SECONDS = int(os.getenv("COLLECT_EVERY_SECONDS", "60"))

DB_PATH = Path(os.getenv("LAB_DB_PATH", str(LAB_DIR / "lab.db")))

TIER_NAMES = {0: "Low", 1: "Medium", 2: "High"}
SCHEME_NAMES = {0: "Standard ECDSA", 1: "ECDSA + commitment hash", 2: "Dilithium + SPHINCS+ (attested)"}
