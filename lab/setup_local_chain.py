"""Set up the free local Ethereum test network for DoomForge Lab (no real or Sepolia ETH needed).

1. Start the chain first, in its own window:   start_chain.bat
2. Then run this once:                         python setup_local_chain.py

It deploys a fresh AdaptiveCryptoSecurity contract to the local chain, approves the
post-quantum attestor, creates a funded faucet wallet for top-ups, and writes the
values into lab/.env. Your old .env is kept as .env.sepolia.backup.
Everything is real: real transactions, real blocks, the real contract. Only the
network is private (on your laptop) instead of public.
"""

from __future__ import annotations

import json
import shutil
import sys
from pathlib import Path

from eth_account import Account
from web3 import Web3

LAB = Path(__file__).resolve().parent
ENV = LAB / ".env"
HARDHAT_ARTIFACT = LAB.parent / "blockchain" / "artifacts" / "contracts" / "AdaptiveCryptoSecurity.sol" / "AdaptiveCryptoSecurity.json"
FALLBACK_BUILD = LAB / "contract_build.json"
RPC = "http://127.0.0.1:8545"
FAUCET_FUNDING_ETH = 50_000


def read_env() -> dict:
    vals = {}
    if ENV.exists():
        for line in ENV.read_text(encoding="utf-8").splitlines():
            if "=" in line and not line.lstrip().startswith("#"):
                k, v = line.split("=", 1)
                vals[k.strip()] = v.split("#", 1)[0].strip()
    return vals


def write_env(updates: dict) -> None:
    lines = ENV.read_text(encoding="utf-8").splitlines() if ENV.exists() else []
    done = set()
    out = []
    for line in lines:
        key = line.split("=", 1)[0].strip() if "=" in line and not line.lstrip().startswith("#") else None
        if key in updates:
            out.append(f"{key}={updates[key]}")
            done.add(key)
        else:
            out.append(line)
    for k, v in updates.items():
        if k not in done:
            out.append(f"{k}={v}")
    ENV.write_text("\n".join(out) + "\n", encoding="utf-8")


def send(w3, acct, tx):
    tx.update({"chainId": w3.eth.chain_id, "nonce": w3.eth.get_transaction_count(acct.address, "pending")})
    if "maxFeePerGas" not in tx:
        tx["gasPrice"] = w3.eth.gas_price
    if "gas" not in tx:
        tx["gas"] = int(w3.eth.estimate_gas(tx) * 1.2)
    signed = acct.sign_transaction(tx)
    raw = getattr(signed, "raw_transaction", None) or signed.rawTransaction
    return w3.eth.wait_for_transaction_receipt(w3.eth.send_raw_transaction(raw), timeout=120)


def main() -> None:
    w3 = Web3(Web3.HTTPProvider(RPC))
    if not w3.is_connected():
        sys.exit("The local chain is not running. Start it first with start_chain.bat, then run this again.")
    print(f"Connected to the local chain (chain id {w3.eth.chain_id}, block {w3.eth.block_number}).")

    if ENV.exists() and "127.0.0.1" not in read_env().get("RPC_URL", ""):
        shutil.copy(ENV, LAB / ".env.sepolia.backup")
        print("Saved your Sepolia settings as lab/.env.sepolia.backup")
    old = read_env()

    # Contract code: Hardhat's own build if present, else the build shipped with the lab.
    build_path = HARDHAT_ARTIFACT if HARDHAT_ARTIFACT.exists() else FALLBACK_BUILD
    build = json.loads(build_path.read_text(encoding="utf-8"))
    print(f"Using contract build: {build_path.relative_to(LAB.parent)}")

    # Faucet wallet: a new key, funded from the chain's pre-funded account.
    faucet = Account.create()
    bank = w3.eth.accounts[0]
    h = w3.eth.send_transaction({"from": bank, "to": faucet.address, "value": w3.to_wei(FAUCET_FUNDING_ETH, "ether")})
    w3.eth.wait_for_transaction_receipt(h, timeout=120)
    print(f"Faucet wallet {faucet.address} funded with {FAUCET_FUNDING_ETH:,} test ETH.")

    # Attestor: keep the key you already made (python make_attestor_key.py), or make one.
    att_key = old.get("ATTESTOR_PRIVATE_KEY", "")
    if not att_key.startswith("0x") or len(att_key) != 66:
        att_key = "0x" + bytes(Account.create().key).hex()
    attestor = Account.from_key(att_key)

    # Deploy, then approve the attestor (the faucet wallet is the contract owner).
    contract = w3.eth.contract(abi=build["abi"], bytecode=build["bytecode"])
    r = send(w3, faucet, contract.constructor().build_transaction({"from": faucet.address}))
    address = r.contractAddress
    print(f"AdaptiveCryptoSecurity deployed to: {address}  (gas {r.gasUsed:,})")
    inst = w3.eth.contract(address=address, abi=build["abi"])
    send(w3, faucet, inst.functions.setPQAttestor(attestor.address, True).build_transaction({"from": faucet.address}))
    ok = inst.functions.pqAttestors(attestor.address).call()
    print(f"Registered PQ attestor: {attestor.address} -> approved = {ok}")

    write_env({
        "RPC_URL": RPC,
        "CONTRACT_ADDRESS": address,
        "ATTESTOR_PRIVATE_KEY": att_key,
        "FAUCET_PRIVATE_KEY": "0x" + bytes(faucet.key).hex(),
        "NETWORK_NAME": "DoomForge Testnet (local Ethereum)",
        "EXPLORER_URL": "",
        "TOPUP_ETH": "1",
        "MAX_TOPUPS_PER_ACCOUNT": "5",
    })
    print("\nlab/.env updated. Your ACCESS_CODE and ETHERSCAN_API_KEY were kept.")
    print("Next: python collector.py  and  streamlit run app.py")


if __name__ == "__main__":
    main()
