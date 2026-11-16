"""Negative (security) tests for AdaptiveCryptoSecurity on a local chain.

Each case must be REJECTED by the contract or by the off-chain PQ attestor.
Requires CONTRACT_ADDRESS and ATTESTOR_ADDRESS (whitelisted) in the environment
and a running Ganache with unlocked accounts.

Run:  python test_contract_security.py
"""

from __future__ import annotations

import os

from web3 import Web3

import pq_attestor as pq
from adaptive_crypto_bridge import load_contract

ATTESTOR = Web3.to_checksum_address(os.environ["ATTESTOR_ADDRESS"])


def expect_revert(name: str, fn) -> bool:
    try:
        fn()
    except Exception as exc:  # contract revert or PQ failure
        reason = str(exc).split("\n")[0][:90]
        print(f"  [PASS] {name}\n         rejected: {reason}")
        return True
    print(f"  [FAIL] {name} (was accepted)")
    return False


def main() -> None:
    w3, c = load_contract()
    acc = w3.eth.accounts
    sender, recipient, outsider = acc[6], acc[7], acc[8]
    ok = True
    print("Security tests")

    def std_args(risk, data_hash, nonce=None, signer=None):
        n = c.functions.nonces(sender).call() if nonce is None else nonce
        msg = w3.solidity_keccak(["address", "address", "bytes32", "uint256", "address"],
                                 [sender, recipient, data_hash, n, c.address])
        sig = w3.eth.sign(signer or sender, msg)
        return recipient, data_hash, risk, sig, n

    # 1. Medium tier without a commitment hash
    ok &= expect_revert("Medium-risk transaction without commitment hash",
        lambda: c.functions.submitStandardTransaction(*std_args(1, b"\x00" * 32)).transact({"from": sender}))

    # 2. High tier sent through the standard (ECDSA-only) path
    ok &= expect_revert("High-risk transaction via the standard ECDSA path",
        lambda: c.functions.submitStandardTransaction(*std_args(2, w3.keccak(text="x"))).transact({"from": sender}))

    # 3. Signature made by a different key (stolen-transaction scenario)
    ok &= expect_revert("ECDSA signature from a different account",
        lambda: c.functions.submitStandardTransaction(*std_args(0, b"\x00" * 32, signer=outsider)).transact({"from": sender}))

    # 4. Replay: reuse an already-consumed nonce
    args = std_args(0, b"\x00" * 32)
    w3.eth.wait_for_transaction_receipt(c.functions.submitStandardTransaction(*args).transact({"from": sender}))
    ok &= expect_revert("Replay of an already-used nonce",
        lambda: c.functions.submitStandardTransaction(*args).transact({"from": sender}))

    # 5. High tier attested by a NON-whitelisted attestor
    def high(attestor):
        n = c.functions.nonces(sender).call()
        data_hash = w3.keccak(text="high")
        payload = w3.solidity_keccak(["address", "address", "bytes32", "uint256", "address"],
                                     [sender, recipient, data_hash, n, c.address])
        att = pq.create_attestation(sender, bytes(payload))
        msg = w3.solidity_keccak(["address", "address", "bytes32", "bytes32", "uint256", "address"],
                                 [sender, recipient, data_hash, att.pq_signature_hash, n, c.address])
        sig = w3.eth.sign(attestor, msg)
        return c.functions.submitHighRiskTransaction(recipient, data_hash, att.pq_signature_hash, sig, n).transact({"from": sender})
    ok &= expect_revert("High-risk transaction approved by a non-whitelisted attestor", lambda: high(outsider))

    # 6. Tampered post-quantum signature is refused before reaching the chain
    def tampered():
        keys = pq.load_or_create_keys(sender)
        payload = os.urandom(32)
        sd, ss, _, _ = pq.sign_payload(keys, payload)
        pq.verify_and_attest(payload, keys.dilithium_pk, keys.sphincs_pk, sd, bytes([ss[0] ^ 1]) + ss[1:])
    ok &= expect_revert("Tampered SPHINCS+ signature (refused off-chain)", tampered)

    # 7. Positive control: correctly attested High-risk transaction is accepted
    r = w3.eth.wait_for_transaction_receipt(high(ATTESTOR))
    print(f"  [{'PASS' if r.status == 1 else 'FAIL'}] Correctly attested High-risk transaction accepted (gas {r.gasUsed})")
    ok &= r.status == 1

    print("\nALL SECURITY TESTS PASSED" if ok else "\nSOME SECURITY TESTS FAILED")
    raise SystemExit(0 if ok else 1)


if __name__ == "__main__":
    main()
