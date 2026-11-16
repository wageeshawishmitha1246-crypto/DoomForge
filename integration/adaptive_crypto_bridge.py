"""Connectivity bridge for the local AdaptiveCryptoSecurity contract.

Set CONTRACT_ADDRESS in the environment before running this module. The ABI is
loaded from the file beside this script, so it always matches the compiled
contract artifact copied into integration/.
"""

from __future__ import annotations

import json
import os
from pathlib import Path

from web3 import Web3


GANACHE_URL = os.getenv("GANACHE_URL", "http://127.0.0.1:8545")
CONTRACT_ADDRESS = os.getenv("CONTRACT_ADDRESS", "")
CONTRACT_ABI_PATH = Path(__file__).with_name("AdaptiveCryptoSecurity_abi.json")

# Details (sizes, timings, audit file) of the most recent High-risk PQ attestation,
# so batch scripts can log them alongside gas usage.
LAST_PQ_ATTESTATION = None


def load_contract() -> tuple[Web3, object]:
    """Connect to Ganache and return the configured contract instance."""
    if not CONTRACT_ADDRESS:
        raise ValueError(
            "CONTRACT_ADDRESS is not set. Use the address printed by the "
            "Hardhat deployment command."
        )
    if not Web3.is_address(CONTRACT_ADDRESS):
        raise ValueError("CONTRACT_ADDRESS must be a valid 0x-prefixed address.")

    with CONTRACT_ABI_PATH.open(encoding="utf-8") as abi_file:
        abi = json.load(abi_file)

    w3 = Web3(Web3.HTTPProvider(GANACHE_URL))
    if not w3.is_connected():
        raise ConnectionError(
            f"Could not connect to Ganache at {GANACHE_URL}. Start `ganache` "
            "and confirm the configured port."
        )

    return w3, w3.eth.contract(
        address=Web3.to_checksum_address(CONTRACT_ADDRESS), abi=abi
    )


def submit_standard_transaction(
    w3: Web3,
    contract,
    sender: str,
    recipient: str,
    risk_level: int,
    data_hash: bytes | None = None,
    value_eth: float = 0.0,
):
    """Submit a Low (0) or Medium (1) risk transaction, signed by the sender.

    Ganache must control `sender`'s key (it signs via eth_sign on the node).
    Medium risk requires a non-zero commitment hash; one is generated if not given.
    """
    if risk_level not in (0, 1):
        raise ValueError("submit_standard_transaction only accepts risk_level 0 (Low) or 1 (Medium)")

    sender = Web3.to_checksum_address(sender)
    recipient = Web3.to_checksum_address(recipient)

    if data_hash is None:
        data_hash = b"\x00" * 32 if risk_level == 0 else w3.keccak(text=f"commitment:{sender}:{recipient}")

    nonce = contract.functions.nonces(sender).call()
    message_hash = w3.solidity_keccak(
        ["address", "address", "bytes32", "uint256", "address"],
        [sender, recipient, data_hash, nonce, contract.address],
    )
    signature = w3.eth.sign(sender, message_hash)

    tx_hash = contract.functions.submitStandardTransaction(
        recipient, data_hash, risk_level, signature, nonce
    ).transact({"from": sender, "value": w3.to_wei(value_eth, "ether")})
    return w3.eth.wait_for_transaction_receipt(tx_hash)


def submit_high_risk_transaction(
    w3: Web3,
    contract,
    sender: str,
    recipient: str,
    attestor: str,
    data_hash: bytes | None = None,
    pq_signature_hash: bytes | None = None,
    value_eth: float = 0.0,
):
    """Submit a High (2) risk transaction, attested by a whitelisted pqAttestor.

    The sender's payload is signed with BOTH CRYSTALS-Dilithium (ML-DSA-44) and
    SPHINCS+ (SLH-DSA-SHA2-128f) off-chain and both signatures are verified
    (see pq_attestor.py). Only if both verify does the attestor sign off; the
    contract then checks that a whitelisted attestor approved this exact
    pq_signature_hash. The contract never verifies PQ cryptography itself,
    because the EVM has no post-quantum precompile.
    """
    global LAST_PQ_ATTESTATION
    sender = Web3.to_checksum_address(sender)
    recipient = Web3.to_checksum_address(recipient)
    attestor = Web3.to_checksum_address(attestor)

    if data_hash is None:
        data_hash = w3.keccak(text=f"payload:{sender}:{recipient}")

    nonce = contract.functions.nonces(sender).call()

    if pq_signature_hash is None:
        # Real post-quantum protection: sign the payload with Dilithium and
        # SPHINCS+, verify both, and derive the 32-byte on-chain summary.
        from pq_attestor import create_attestation  # local import keeps Low/Medium paths dependency-free

        payload_hash = w3.solidity_keccak(
            ["address", "address", "bytes32", "uint256", "address"],
            [sender, recipient, data_hash, nonce, contract.address],
        )
        attestation = create_attestation(sender, bytes(payload_hash))
        pq_signature_hash = attestation.pq_signature_hash
        LAST_PQ_ATTESTATION = attestation

    message_hash = w3.solidity_keccak(
        ["address", "address", "bytes32", "bytes32", "uint256", "address"],
        [sender, recipient, data_hash, pq_signature_hash, nonce, contract.address],
    )
    attestation_sig = w3.eth.sign(attestor, message_hash)

    tx_hash = contract.functions.submitHighRiskTransaction(
        recipient, data_hash, pq_signature_hash, attestation_sig, nonce
    ).transact({"from": sender, "value": w3.to_wei(value_eth, "ether")})
    return w3.eth.wait_for_transaction_receipt(tx_hash)


def process_transaction(
    w3: Web3,
    contract,
    sender: str,
    recipient: str,
    risk_level: int,
    attestor: str | None = None,
    value_eth: float = 0.0,
):
    """Route a transaction to the correct submit function for its risk tier.

    risk_level: 0 = Low, 1 = Medium, 2 = High. High risk requires `attestor`.
    """
    if risk_level in (0, 1):
        return submit_standard_transaction(w3, contract, sender, recipient, risk_level, value_eth=value_eth)
    if risk_level == 2:
        if attestor is None:
            raise ValueError("High risk transactions require an attestor address")
        return submit_high_risk_transaction(w3, contract, sender, recipient, attestor, value_eth=value_eth)
    raise ValueError(f"Unknown risk_level: {risk_level}")


def main() -> None:
    w3, contract = load_contract()
    print(f"Connected to Ganache (chain ID: {w3.eth.chain_id})")
    print(f"Contract: {contract.address}")
    print(f"Version: {contract.functions.VERSION().call()}")
    print(f"Operational: {contract.functions.isOperational().call()}")
    print("[Connection verified]")


if __name__ == "__main__":
    main()
