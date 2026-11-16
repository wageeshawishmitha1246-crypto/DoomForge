"""Blockchain layer for DoomForge Lab.

Every transaction is signed locally with a private key (eth_account), so the
same code runs on Sepolia (a public testnet) and on Ganache. This replaces the
Ganache-only `w3.eth.sign` / unlocked-account calls in integration/.
"""

from __future__ import annotations

import json
import time
from dataclasses import dataclass, field

from eth_account import Account
from eth_account.messages import encode_defunct
from web3 import Web3
from web3.exceptions import ContractLogicError
from web3.logs import DISCARD

from . import config

ZERO32 = b"\x00" * 32


@dataclass
class Step:
    title: str
    detail: str
    data: dict = field(default_factory=dict)


@dataclass
class SendResult:
    ok: bool
    mode: str
    tier: int | None
    scheme: str
    tx_hash: str | None
    gas_used: int | None
    block: int | None
    steps: list[Step]
    error: str | None = None
    tx_id: str | None = None
    seconds: float = 0.0


def reason(exc: Exception) -> str:
    """Short revert reason from a web3 error (Ganache and Sepolia word it differently)."""
    text = str(getattr(exc, "message", None) or exc)
    for marker in ("execution reverted: ", "revert "):
        if marker in text:
            return text.split(marker, 1)[1].split("'")[0].split('"')[0].strip()
    return text


def _raw(signed) -> bytes:
    return getattr(signed, "raw_transaction", None) or signed.rawTransaction


def _short(b: bytes | str, n: int = 10) -> str:
    h = b if isinstance(b, str) else "0x" + bytes(b).hex()
    return h if len(h) <= 2 * n + 3 else f"{h[:n + 2]}…{h[-n:]}"


class Chain:
    def __init__(self) -> None:
        self.w3 = Web3(Web3.HTTPProvider(config.RPC_URL, request_kwargs={"timeout": 60}))
        if not self.w3.is_connected():
            raise ConnectionError(f"Cannot reach the blockchain RPC at {config.RPC_URL}")
        if not config.CONTRACT_ADDRESS:
            raise ValueError("CONTRACT_ADDRESS is not set in lab/.env")
        abi = json.loads((config.INTEGRATION_DIR / "AdaptiveCryptoSecurity_abi.json").read_text(encoding="utf-8"))
        self.contract = self.w3.eth.contract(address=Web3.to_checksum_address(config.CONTRACT_ADDRESS), abi=abi)
        self.chain_id = self.w3.eth.chain_id
        self.attestor = Account.from_key(config.ATTESTOR_PRIVATE_KEY) if config.ATTESTOR_PRIVATE_KEY else None
        self.faucet = Account.from_key(config.FAUCET_PRIVATE_KEY) if config.FAUCET_PRIVATE_KEY else None

    # ------------------------------------------------------------ helpers
    # With no public explorer (the local DoomForge Testnet), links open the built-in explorer page.
    def tx_link(self, tx_hash: str) -> str:
        return f"{config.EXPLORER_URL}/tx/{tx_hash}" if config.EXPLORER_URL else f"/explorer?tx={tx_hash}"

    def address_link(self, address: str) -> str:
        return f"{config.EXPLORER_URL}/address/{address}" if config.EXPLORER_URL else f"/explorer?address={address}"

    # --------------------------------------------- built-in block explorer
    def latest_blocks(self, n: int = 12) -> list[dict]:
        top = self.w3.eth.block_number
        out = []
        for num in range(top, max(-1, top - n), -1):
            b = self.w3.eth.get_block(num)
            out.append({"number": num, "time": b.timestamp, "txs": len(b.transactions),
                        "gas_used": b.gasUsed, "hash": "0x" + bytes(b.hash).hex()})
        return out

    def recent_transactions(self, blocks: int = 300, address: str | None = None, limit: int = 25) -> list[dict]:
        """Transactions in the most recent blocks, newest first, optionally only those touching one address."""
        top = self.w3.eth.block_number
        want = address.lower() if address else None
        out = []
        for num in range(top, max(-1, top - blocks), -1):
            b = self.w3.eth.get_block(num, full_transactions=True)
            for tx in reversed(b.transactions):
                frm, to = tx["from"], tx.get("to") or tx.get("creates") or ""
                if want and want not in (frm.lower(), (to or "").lower()):
                    continue
                out.append({"hash": "0x" + bytes(tx["hash"]).hex(), "block": num, "time": b.timestamp,
                            "from": frm, "to": to or "(contract creation)",
                            "value_eth": float(self.w3.from_wei(tx["value"], "ether")),
                            "kind": self.describe_call(tx)})
                if len(out) >= limit:
                    return out
        return out

    def describe_call(self, tx) -> str:
        to = tx.get("to")
        if to is None:
            return "Contract deployment"
        if to.lower() != self.contract.address.lower():
            return "ETH transfer" if not tx.get("input") or bytes(tx["input"]) in (b"", b"0x") else "Contract call"
        try:
            fn, _ = self.contract.decode_function_input(tx["input"])
            return {"submitStandardTransaction": "DoomForge: Low/Medium",
                    "submitHighRiskTransaction": "DoomForge: High (post-quantum)",
                    "setPQAttestor": "Approve attestor"}.get(fn.fn_name, fn.fn_name)
        except Exception:  # noqa: BLE001
            return "DoomForge contract call"

    def transaction_details(self, tx_hash: str) -> dict:
        tx = self.w3.eth.get_transaction(tx_hash)
        rc = self.w3.eth.get_transaction_receipt(tx_hash)
        block = self.w3.eth.get_block(rc.blockNumber)
        d = {
            "Status": "Success" if rc.status == 1 else "Failed",
            "Block": rc.blockNumber,
            "Time": block.timestamp,
            "From": tx["from"],
            "To": tx.get("to") or rc.contractAddress,
            "Value (ETH)": float(self.w3.from_wei(tx["value"], "ether")),
            "Gas used": rc.gasUsed,
            "Gas price (gwei)": float(self.w3.from_wei(tx.get("gasPrice", 0), "gwei")),
            "Transaction fee (ETH)": float(self.w3.from_wei(rc.gasUsed * tx.get("gasPrice", 0), "ether")),
            "Nonce": tx["nonce"],
            "Input data (bytes)": len(bytes(tx["input"])),
            "Type": self.describe_call(tx),
        }
        call, events = None, []
        if (tx.get("to") or "").lower() == self.contract.address.lower():
            try:
                fn, args = self.contract.decode_function_input(tx["input"])
                call = {"function": fn.fn_name,
                        "arguments": {k: ("0x" + bytes(v).hex() if isinstance(v, (bytes, bytearray)) else v)
                                      for k, v in args.items()}}
            except Exception:  # noqa: BLE001
                pass
            for ev in (self.contract.events.RiskAssessed, self.contract.events.TransactionSecured,
                       self.contract.events.PQAttestorUpdated):
                for log in ev().process_receipt(rc, errors=DISCARD):
                    args = {k: ("0x" + bytes(v).hex() if isinstance(v, (bytes, bytearray)) else v)
                            for k, v in log["args"].items()}
                    if log["event"] == "RiskAssessed":
                        args["riskLevel"] = f"{args['riskLevel']} ({config.TIER_NAMES.get(args['riskLevel'], '?')})"
                        args["scheme"] = f"{args['scheme']} ({config.SCHEME_NAMES.get(args['scheme'], '?')})"
                    if log["event"] == "TransactionSecured":
                        args["value"] = f"{self.w3.from_wei(args['value'], 'ether')} ETH"
                    events.append({"event": log["event"], **args})
        return {"summary": d, "call": call, "events": events}

    def balance_eth(self, address: str) -> float:
        return float(self.w3.from_wei(self.w3.eth.get_balance(Web3.to_checksum_address(address)), "ether"))

    def _gas_price(self) -> int:
        return int(self.w3.eth.gas_price * 1.25) + 1

    def _send(self, acct, tx: dict):
        tx.setdefault("chainId", self.chain_id)
        tx.setdefault("nonce", self.w3.eth.get_transaction_count(acct.address, "pending"))
        tx.setdefault("gasPrice", self._gas_price())
        signed = acct.sign_transaction(tx)
        tx_hash = self.w3.eth.send_raw_transaction(_raw(signed))
        receipt = self.w3.eth.wait_for_transaction_receipt(tx_hash, timeout=config.TX_TIMEOUT_SECONDS, poll_latency=2)
        return receipt

    def _contract_tx(self, acct, fn, value_wei: int):
        tx = fn.build_transaction({
            "from": acct.address,
            "value": value_wei,
            "chainId": self.chain_id,
            "nonce": self.w3.eth.get_transaction_count(acct.address, "pending"),
            "gasPrice": self._gas_price(),
        })
        return self._send(acct, tx)

    @staticmethod
    def sign_hash(private_key: str, message_hash: bytes) -> bytes:
        """ECDSA signature over a 32-byte hash, same as eth_sign (EIP-191 prefix)."""
        return bytes(Account.sign_message(encode_defunct(primitive=bytes(message_hash)), private_key).signature)

    def payload_hash(self, sender, recipient, data_hash, nonce) -> bytes:
        return bytes(self.w3.solidity_keccak(
            ["address", "address", "bytes32", "uint256", "address"],
            [sender, recipient, data_hash, nonce, self.contract.address],
        ))

    def attestation_hash(self, sender, recipient, data_hash, pq_hash, nonce) -> bytes:
        return bytes(self.w3.solidity_keccak(
            ["address", "address", "bytes32", "bytes32", "uint256", "address"],
            [sender, recipient, data_hash, pq_hash, nonce, self.contract.address],
        ))

    # ------------------------------------------------------------- info
    def contract_info(self) -> dict:
        c = self.contract.functions
        info = {"address": self.contract.address, "chain_id": self.chain_id}
        for name, call in (("version", c.VERSION), ("owner", c.owner)):
            try:
                info[name] = call().call()
            except Exception:  # noqa: BLE001
                info[name] = "?"
        if self.attestor:
            info["attestor"] = self.attestor.address
            info["attestor_approved"] = bool(c.pqAttestors(self.attestor.address).call())
        return info

    # ----------------------------------------------------------- top-up
    def top_up(self, to_address: str, amount_eth: float):
        if not self.faucet:
            raise ValueError("FAUCET_PRIVATE_KEY is not set in lab/.env")
        tx = {"to": Web3.to_checksum_address(to_address), "value": self.w3.to_wei(amount_eth, "ether"), "gas": 21000}
        return self._send(self.faucet, tx)

    # ------------------------------------------------ DoomForge OFF: plain
    def send_plain(self, private_key: str, recipient: str, value_eth: float) -> SendResult:
        t0 = time.time()
        acct = Account.from_key(private_key)
        recipient = Web3.to_checksum_address(recipient)
        steps = [
            Step("DoomForge is OFF", "No risk check. The wallet signs a normal Ethereum transfer with ECDSA, "
                 "like any wallet does today."),
        ]
        try:
            receipt = self._send(acct, {"to": recipient, "value": self.w3.to_wei(value_eth, "ether"), "gas": 21000})
        except Exception as exc:  # noqa: BLE001
            return SendResult(False, "plain", None, "Standard ECDSA (no DoomForge)", None, None, None, steps,
                              error=str(exc), seconds=time.time() - t0)
        h = "0x" + bytes(receipt.transactionHash).hex()
        steps.append(Step("Mined on " + config.NETWORK_NAME,
                          f"Block {receipt.blockNumber}, gas used {receipt.gasUsed:,}. Same protection for every "
                          "sender, risky or not.", {"tx_hash": h}))
        return SendResult(receipt.status == 1, "plain", None, "Standard ECDSA (no DoomForge)", h,
                          receipt.gasUsed, receipt.blockNumber, steps, seconds=time.time() - t0)

    # ------------------------------------------------- DoomForge ON: tiers
    def send_doomforge(self, private_key: str, recipient: str, value_eth: float, tier: int) -> SendResult:
        t0 = time.time()
        acct = Account.from_key(private_key)
        sender = acct.address
        recipient = Web3.to_checksum_address(recipient)
        value_wei = self.w3.to_wei(value_eth, "ether")
        scheme = config.SCHEME_NAMES[tier]
        steps: list[Step] = []
        nonce = self.contract.functions.nonces(sender).call()
        steps.append(Step("Read the wallet's nonce from the contract",
                          f"nonce = {nonce}. It goes into the signed message, so the same signed transaction "
                          "can never be used twice."))
        try:
            if tier in (0, 1):
                if tier == 0:
                    data_hash = ZERO32
                    steps.append(Step("Low tier: no commitment needed", "dataHash = 0x000…000"))
                else:
                    data_hash = bytes(self.w3.keccak(text=f"commitment:{sender}:{recipient}"))
                    steps.append(Step("Medium tier: create the commitment hash",
                                      f"keccak256(\"commitment:\" + sender + \":\" + recipient) = {_short(data_hash)}"))
                msg = self.payload_hash(sender, recipient, data_hash, nonce)
                steps.append(Step("Build the message to sign",
                                  f"keccak256(sender, recipient, dataHash, nonce, contract) = {_short(msg)}"))
                sig = self.sign_hash(private_key, msg)
                steps.append(Step("Wallet signs with ECDSA (secp256k1)",
                                  f"65-byte signature {_short(sig)}"))
                fn = self.contract.functions.submitStandardTransaction(recipient, data_hash, tier, sig, nonce)
                steps.append(Step("Send to the smart contract",
                                  "submitStandardTransaction() checks: tier is Low/Medium, nonce matches, "
                                  + ("commitment hash is not empty, " if tier == 1 else "")
                                  + "and the recovered signer is the sender."))
            else:
                if not self.attestor:
                    raise ValueError("ATTESTOR_PRIVATE_KEY is not set in lab/.env")
                from pq_attestor import create_attestation

                data_hash = bytes(self.w3.keccak(text=f"payload:{sender}:{recipient}"))
                payload = self.payload_hash(sender, recipient, data_hash, nonce)
                steps.append(Step("High tier: build the payload hash",
                                  f"keccak256(sender, recipient, dataHash, nonce, contract) = {_short(payload)}"))
                att = create_attestation(sender, payload)
                steps.append(Step("Wallet signs with Dilithium and SPHINCS+ (post-quantum)",
                                  f"Dilithium (ML-DSA-44) signature {att.dilithium_signature_bytes:,} bytes in "
                                  f"{att.dilithium_sign_ms:.1f} ms; SPHINCS+ (SLH-DSA-SHA2-128f) signature "
                                  f"{att.sphincs_signature_bytes:,} bytes in {att.sphincs_sign_ms:.1f} ms. "
                                  "These stay off-chain."))
                steps.append(Step("Attestor verifies BOTH signatures off-chain",
                                  f"Dilithium OK ({att.dilithium_verify_ms:.1f} ms), SPHINCS+ OK "
                                  f"({att.sphincs_verify_ms:.1f} ms). Audit record saved so anyone can re-check it."))
                pq_hash = att.pq_signature_hash
                steps.append(Step("32-byte summary for the blockchain",
                                  f"keccak256(both public keys + both signatures) = {_short(pq_hash)}"))
                msg = self.attestation_hash(sender, recipient, data_hash, pq_hash, nonce)
                att_sig = self.sign_hash(self.attestor.key, msg)
                steps.append(Step("Approved attestor signs the summary (ECDSA)",
                                  f"Attestor {_short(self.attestor.address, 6)} signature {_short(att_sig)}"))
                fn = self.contract.functions.submitHighRiskTransaction(recipient, data_hash, pq_hash, att_sig, nonce)
                steps.append(Step("Send to the smart contract",
                                  "submitHighRiskTransaction() checks: nonce matches and the approval comes from "
                                  "an attestor on the contract's approved list."))

            receipt = self._contract_tx(acct, fn, value_wei)
        except ContractLogicError as exc:
            steps.append(Step("Contract REJECTED the transaction", reason(exc)))
            return SendResult(False, "doomforge", tier, scheme, None, None, None, steps, error=reason(exc),
                              seconds=time.time() - t0)
        except Exception as exc:  # noqa: BLE001
            steps.append(Step("Failed", str(exc)))
            return SendResult(False, "doomforge", tier, scheme, None, None, None, steps, error=str(exc),
                              seconds=time.time() - t0)

        h = "0x" + bytes(receipt.transactionHash).hex()
        tx_id = None
        for log in self.contract.events.RiskAssessed().process_receipt(receipt, errors=DISCARD):
            tx_id = "0x" + bytes(log["args"]["txId"]).hex()
        steps.append(Step("Contract checks passed, transaction recorded",
                          f"Mined in block {receipt.blockNumber}, gas used {receipt.gasUsed:,}. Recorded as "
                          f"{config.TIER_NAMES[tier]} risk with {scheme}. The ETH was forwarded to the recipient.",
                          {"tx_hash": h, "tx_id": tx_id}))
        return SendResult(receipt.status == 1, "doomforge", tier, scheme, h, receipt.gasUsed, receipt.blockNumber,
                          steps, tx_id=tx_id, seconds=time.time() - t0)

    # ------------------------------------------- attack lab (no gas spent)
    def run_attacks(self, private_key: str) -> list[dict]:
        """Try to cheat the contract with eth_call (a dry run: nothing is mined, no gas is spent)."""
        acct = Account.from_key(private_key)
        sender = acct.address
        recipient = Web3.to_checksum_address(Account.create().address)
        outsider = Account.create()
        nonce = self.contract.functions.nonces(sender).call()
        c = self.contract.functions
        results = []

        def attempt(name, what, fn):
            try:
                fn.call({"from": sender})
                results.append({"attack": name, "what": what, "result": "ACCEPTED (should not happen)", "blocked": False})
            except Exception as exc:  # noqa: BLE001  (a revert is the expected outcome)
                results.append({"attack": name, "what": what, "result": f"Rejected: {reason(exc)}", "blocked": True})

        msg0 = self.payload_hash(sender, recipient, ZERO32, nonce)
        attempt("Skip the commitment hash", "Medium-risk transaction sent with an empty commitment hash",
                c.submitStandardTransaction(recipient, ZERO32, 1, self.sign_hash(private_key, msg0), nonce))
        some = bytes(self.w3.keccak(text="x"))
        msg1 = self.payload_hash(sender, recipient, some, nonce)
        attempt("Use the cheap path for High risk", "High-risk transaction sent through the ECDSA path",
                c.submitStandardTransaction(recipient, some, 2, self.sign_hash(private_key, msg1), nonce))
        attempt("Forge the signature", "Low-risk transaction signed by a different account",
                c.submitStandardTransaction(recipient, ZERO32, 0, self.sign_hash(outsider.key, msg0), nonce))
        bad_nonce = nonce - 1 if nonce > 0 else nonce + 1
        msg2 = self.payload_hash(sender, recipient, ZERO32, bad_nonce)
        attempt("Replay an old transaction", f"Signed message reused with nonce {bad_nonce} (current is {nonce})",
                c.submitStandardTransaction(recipient, ZERO32, 0, self.sign_hash(private_key, msg2), bad_nonce))
        pq = bytes(self.w3.keccak(text="fake pq summary"))
        dh = bytes(self.w3.keccak(text=f"payload:{sender}:{recipient}"))
        msg3 = self.attestation_hash(sender, recipient, dh, pq, nonce)
        attempt("Fake attestor", "High-risk approval signed by an attestor that is not approved",
                c.submitHighRiskTransaction(recipient, dh, pq, self.sign_hash(outsider.key, msg3), nonce))

        # Off-chain: tampered post-quantum signature
        try:
            from pq_attestor import PQVerificationError, load_or_create_keys, sign_payload, verify_and_attest

            keys = load_or_create_keys(sender)
            payload = self.payload_hash(sender, recipient, dh, nonce)
            sig_d, sig_s, _, _ = sign_payload(keys, payload)
            bad = bytearray(sig_d)
            bad[0] ^= 0xFF
            try:
                verify_and_attest(payload, keys.dilithium_pk, keys.sphincs_pk, bytes(bad), sig_s)
                results.append({"attack": "Tamper the post-quantum signature", "what": "One byte of the Dilithium "
                                "signature changed", "result": "ACCEPTED (should not happen)", "blocked": False})
            except PQVerificationError as exc:
                results.append({"attack": "Tamper the post-quantum signature", "what": "One byte of the Dilithium "
                                "signature changed", "result": f"Refused off-chain: {exc}", "blocked": True})
        except Exception as exc:  # noqa: BLE001
            results.append({"attack": "Tamper the post-quantum signature", "what": "PQ library not available",
                            "result": str(exc), "blocked": False})
        return results


def new_private_key() -> tuple[str, str]:
    acct = Account.create()
    return acct.address, "0x" + bytes(acct.key).hex()
