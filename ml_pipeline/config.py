"""Configuration utilities for the Ethereum risk detection pipeline.

This module centralizes paths and environment-dependent settings so they can
be reused across the project.
"""

from __future__ import annotations

import os
from pathlib import Path

# Base directories
PROJECT_ROOT = Path(__file__).resolve().parent
DATA_DIR = PROJECT_ROOT / "data"
RAW_DATA_DIR = DATA_DIR / "raw"
PROCESSED_DATA_DIR = DATA_DIR / "processed"
MODELS_DIR = PROJECT_ROOT / "models"

# Ensure data/model directories exist when this module is imported
RAW_DATA_DIR.mkdir(parents=True, exist_ok=True)
PROCESSED_DATA_DIR.mkdir(parents=True, exist_ok=True)
MODELS_DIR.mkdir(parents=True, exist_ok=True)

# Etherscan API configuration
# Etherscan v2 endpoint uses /v2/api and supports a chain id parameter.
ETHERSCAN_BASE_URL = "https://api.etherscan.io/v2/api"
ETHERSCAN_CHAIN_ID = os.getenv("ETHERSCAN_CHAIN_ID", "1")


def get_etherscan_api_key() -> str:
    """Return the Etherscan API key from the environment.

    The key must be set in the ETHERSCAN_API_KEY environment variable.
    This function raises a ValueError with a clear message if the
    variable is missing, so calling scripts can fail fast.
    """

    api_key = os.getenv("ETHERSCAN_API_KEY")
    if not api_key:
        raise ValueError(
            "ETHERSCAN_API_KEY is not set. Please export your Etherscan API key "
            "as an environment variable before running the pipeline."
        )
    return api_key


# Simple rate-limit control (free tier is low, be conservative)
# You can adjust this later if you upgrade your Etherscan plan.
REQUESTS_PER_SECOND = 4
REQUEST_TIMEOUT = 10  # seconds
REQUEST_MAX_RETRIES = 3
