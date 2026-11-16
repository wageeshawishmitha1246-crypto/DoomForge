"""Data collection from the Etherscan API v2.

This module downloads Ethereum transaction data for one or more wallet
addresses using the Etherscan API and stores the results as CSV files
under data/raw/.

It focuses on:
- normal transactions by address
- internal transactions (optional)
- ERC-20 token transfers (optional)

The goal is to provide a clean, reusable interface for later phases of
this research project.
"""

from __future__ import annotations

import argparse
import sys
import time
from pathlib import Path
from typing import Dict, Iterable, List, Tuple

import pandas as pd
import requests
from requests import Response

from config import (
    ETHERSCAN_CHAIN_ID,
    ETHERSCAN_BASE_URL,
    RAW_DATA_DIR,
    REQUEST_MAX_RETRIES,
    REQUESTS_PER_SECOND,
    REQUEST_TIMEOUT,
    get_etherscan_api_key,
)


def rate_limit_sleep() -> None:
    """Sleep briefly to respect Etherscan rate limits.

    For the free tier, Etherscan allows only a small number of requests
    per second. We use a simple sleep-based throttle to stay safe.
    """

    delay = 1.0 / max(REQUESTS_PER_SECOND, 1)
    time.sleep(delay)


def make_etherscan_request(params: Dict[str, str]) -> Dict:
    """Perform a single Etherscan API request with basic error handling.

    Parameters
    ----------
    params:
        Query parameters for the request. The API key is added here.

    Returns
    -------
    dict
        Parsed JSON response. If something goes wrong, an exception is
        raised with a readable message.
    """

    api_key = get_etherscan_api_key()
    full_params = {
        **params,
        "apikey": api_key,
        "chainid": str(ETHERSCAN_CHAIN_ID),
    }

    last_error: Exception | None = None

    for attempt in range(1, REQUEST_MAX_RETRIES + 1):
        try:
            response: Response = requests.get(
                ETHERSCAN_BASE_URL, params=full_params, timeout=REQUEST_TIMEOUT
            )
        except requests.RequestException as exc:  # Network / connection issues
            last_error = exc
            rate_limit_sleep()
            continue

        if response.status_code != 200:
            last_error = RuntimeError(
                f"Etherscan returned HTTP {response.status_code}: {response.text[:200]}"
            )
            rate_limit_sleep()
            continue

        try:
            data = response.json()
        except ValueError as exc:  # JSON decode error
            last_error = RuntimeError(
                f"Failed to decode Etherscan JSON response: {response.text[:200]}"
            )
            rate_limit_sleep()
            continue

        # Standard Etherscan structure: {"status": "1"|"0", "message": str, "result": ...}
        status = data.get("status")
        message = str(data.get("message", ""))
        result = data.get("result")

        if status == "1":
            return data

        # status == "0" can mean "No transactions found" OR an error such as rate limiting
        if "No transactions found" in message:
            return data

        # Retry common transient cases: explicit rate limit, temporary errors.
        rate_limit_markers = ["rate limit", "max rate", "busy", "timeout", "temporar"]
        combined = f"{message} {result}".lower()
        if any(marker in combined for marker in rate_limit_markers):
            last_error = RuntimeError(
                f"Transient Etherscan API error (attempt {attempt}): status={status}, message={message}"
            )
            rate_limit_sleep()
            continue

        raise RuntimeError(f"Etherscan API error: status={status}, message={message}")

    if last_error is None:
        raise RuntimeError("Etherscan request failed after retries for an unknown reason.")
    raise RuntimeError(f"Etherscan request failed after retries: {last_error}")


def fetch_transactions_for_address(
    address: str,
    tx_type: str = "normal",
    start_block: int = 0,
    end_block: int = 99999999,
    sort: str = "asc",
    page_size: int = 10_000,
) -> List[Dict]:
    """Fetch all transactions of a given type for a single address.

    Parameters
    ----------
    address:
        Ethereum address (string starting with "0x...").
    tx_type:
        One of "normal", "internal", or "erc20".
    start_block, end_block:
        Block range for the query.
    sort:
        "asc" or "desc" ordering by block number.
    page_size:
        Max records per page (Etherscan limit is typically up to 10,000).

    Returns
    -------
    list of dict
        All transactions returned by Etherscan for this address and type.
    """

    if tx_type not in {"normal", "internal", "erc20"}:
        raise ValueError("tx_type must be one of 'normal', 'internal', or 'erc20'")

    action_map = {
        "normal": "txlist",
        "internal": "txlistinternal",
        "erc20": "tokentx",
    }

    module = "account"
    action = action_map[tx_type]

    all_results: List[Dict] = []
    page = 1

    while True:
        params = {
            "module": module,
            "action": action,
            "address": address,
            "startblock": str(start_block),
            "endblock": str(end_block),
            "page": str(page),
            "offset": str(page_size),
            "sort": sort,
        }

        rate_limit_sleep()
        data = make_etherscan_request(params)
        result = data.get("result", [])

        # If no transactions are returned, we are done for this address/type.
        if not isinstance(result, list) or len(result) == 0:
            break

        all_results.extend(result)

        # If we received fewer than page_size items, then we reached the end.
        if len(result) < page_size:
            break

        page += 1

    return all_results


def collect_for_addresses(
    addresses: Iterable[str],
    include_internal: bool = False,
    include_erc20: bool = False,
) -> Tuple[Path, Path | None, Path | None]:
    """Collect transactions for multiple addresses and save to CSV files.

    Parameters
    ----------
    addresses:
        Iterable of Ethereum wallet addresses.
    include_internal:
        If True, also fetch internal transactions.
    include_erc20:
        If True, also fetch ERC-20 token transfer events.

    Returns
    -------
    tuple of Paths
        Paths to the raw CSV files for (normal, internal, erc20). Some of
        these can be None if their corresponding type was not requested.
    """

    addresses = [addr.strip() for addr in addresses if addr.strip()]
    if not addresses:
        raise ValueError("No wallet addresses were provided.")

    RAW_DATA_DIR.mkdir(parents=True, exist_ok=True)

    def _collect_type(tx_type: str) -> List[Dict]:
        """Collect one transaction type for all addresses with progress prints."""

        print(f"\nCollecting {tx_type} transactions...")
        all_rows: List[Dict] = []

        for idx, addr in enumerate(addresses, start=1):
            print(f"  [{idx}/{len(addresses)}] Address: {addr}")
            try:
                txs = fetch_transactions_for_address(addr, tx_type=tx_type)
            except Exception as exc:  # noqa: BLE001 — friendly error surface
                print(f"    Error fetching {tx_type} for {addr}: {exc}")
                continue

            # Attach the queried wallet address explicitly for clarity
            for row in txs:
                row.setdefault("queried_address", addr)
            all_rows.extend(txs)

        return all_rows

    normal_rows = _collect_type("normal")
    normal_path = RAW_DATA_DIR / "normal_transactions.csv"
    if normal_rows:
        pd.DataFrame(normal_rows).to_csv(normal_path, index=False)
        print(f"Saved {len(normal_rows)} normal transactions to {normal_path}")
    else:
        print("No normal transactions were collected.")

    internal_path: Path | None = None
    erc20_path: Path | None = None

    if include_internal:
        internal_rows = _collect_type("internal")
        internal_path = RAW_DATA_DIR / "internal_transactions.csv"
        if internal_rows:
            pd.DataFrame(internal_rows).to_csv(internal_path, index=False)
            print(f"Saved {len(internal_rows)} internal transactions to {internal_path}")
        else:
            print("No internal transactions were collected.")

    if include_erc20:
        erc20_rows = _collect_type("erc20")
        erc20_path = RAW_DATA_DIR / "erc20_transfers.csv"
        if erc20_rows:
            pd.DataFrame(erc20_rows).to_csv(erc20_path, index=False)
            print(f"Saved {len(erc20_rows)} ERC-20 transfers to {erc20_path}")
        else:
            print("No ERC-20 transfers were collected.")

    return normal_path, internal_path, erc20_path


def read_addresses_file(path: Path) -> List[str]:
    """Read a simple text file with one Ethereum address per line."""

    if not path.exists():
        raise FileNotFoundError(
            f"Addresses file not found: {path}. Create it with one address per line."
        )

    lines = path.read_text(encoding="utf-8").splitlines()
    addresses = [line.strip() for line in lines if line.strip()]
    return addresses


def main() -> None:
    """Command-line entrypoint for data collection.

    Example usage:

    python data_collection.py \
        --addresses-file data/wallet_addresses.txt \
        --include-internal \
        --include-erc20
    """

    parser = argparse.ArgumentParser(
        description="Collect Ethereum transactions from the Etherscan API v2.",
    )
    parser.add_argument(
        "--addresses-file",
        type=str,
        default="data/wallet_addresses.txt",
        help="Path to a text file with one wallet address per line.",
    )
    parser.add_argument(
        "--include-internal",
        action="store_true",
        help="Also collect internal transactions.",
    )
    parser.add_argument(
        "--include-erc20",
        action="store_true",
        help="Also collect ERC-20 token transfers.",
    )

    args = parser.parse_args()

    try:
        addresses = read_addresses_file(Path(args.addresses_file))
        collect_for_addresses(
            addresses,
            include_internal=args.include_internal,
            include_erc20=args.include_erc20,
        )
    except Exception as exc:  # noqa: BLE001
        print(f"Error during data collection: {exc}")
        sys.exit(1)


if __name__ == "__main__":
    main()
