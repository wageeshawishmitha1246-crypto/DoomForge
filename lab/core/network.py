"""Real Ethereum mainnet network signals from the Etherscan API (v2, chain 1).

The collector stores a sample every COLLECT_EVERY_SECONDS. The dashboard only
shows samples older than NETWORK_DELAY_SECONDS (one hour by default), so the
platform shows the network as it was an hour ago, never live, never invented.
"""

from __future__ import annotations

import time

import requests

from . import config, store


class EtherscanError(RuntimeError):
    pass


def _get(params: dict) -> dict | list | str:
    if not config.ETHERSCAN_API_KEY:
        raise EtherscanError("ETHERSCAN_API_KEY is not set in lab/.env")
    q = {"chainid": "1", "apikey": config.ETHERSCAN_API_KEY, **params}
    r = requests.get(config.ETHERSCAN_URL, params=q, timeout=20)
    r.raise_for_status()
    body = r.json()
    if "result" not in body:
        raise EtherscanError(str(body))
    if body.get("status") == "0" and body.get("message") != "OK":
        raise EtherscanError(str(body.get("result")))
    return body["result"]


def _hex(v) -> int:
    return int(v, 16) if isinstance(v, str) else int(v)


def fetch_sample() -> dict:
    """Take one real sample of the Ethereum mainnet (3 Etherscan calls)."""
    oracle = _get({"module": "gastracker", "action": "gasoracle"})
    time.sleep(0.25)
    block = _get({"module": "proxy", "action": "eth_getBlockByNumber", "tag": "latest", "boolean": "false"})
    time.sleep(0.25)
    number = _hex(block["number"])
    prev = _get({"module": "proxy", "action": "eth_getBlockByNumber", "tag": hex(number - 1), "boolean": "false"})
    gas_used, gas_limit = _hex(block["gasUsed"]), _hex(block["gasLimit"])
    return {
        "ts": int(time.time()),
        "block_number": number,
        "block_time_s": float(_hex(block["timestamp"]) - _hex(prev["timestamp"])),
        "tx_count": len(block.get("transactions", [])),
        "gas_used_ratio": gas_used / gas_limit if gas_limit else None,
        "base_fee_gwei": _hex(block.get("baseFeePerGas", "0x0")) / 1e9,
        "safe_gwei": float(oracle["SafeGasPrice"]),
        "propose_gwei": float(oracle["ProposeGasPrice"]),
        "fast_gwei": float(oracle["FastGasPrice"]),
    }


def collect_forever() -> None:
    print(f"Collecting Ethereum mainnet samples every {config.COLLECT_EVERY_SECONDS}s into {config.DB_PATH}")
    while True:
        try:
            s = fetch_sample()
            store.save_network_sample(s)
            print(f"[{time.strftime('%H:%M:%S')}] block {s['block_number']}: {s['tx_count']} txs, "
                  f"{s['gas_used_ratio']:.0%} full, base fee {s['base_fee_gwei']:.3f} gwei")
        except Exception as exc:  # noqa: BLE001
            print(f"[{time.strftime('%H:%M:%S')}] sample failed: {exc}")
        time.sleep(config.COLLECT_EVERY_SECONDS)


def delayed_samples(window_hours: float = 6):
    """Samples from [now - delay - window, now - delay]."""
    until = int(time.time()) - config.NETWORK_DELAY_SECONDS
    since = until - int(window_hours * 3600)
    return store.network_samples(until, since)
