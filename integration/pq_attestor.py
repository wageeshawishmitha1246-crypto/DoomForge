"""Real post-quantum signing and off-chain attestation for High-risk transactions.

The EVM has no precompile for post-quantum signature verification, so
High-risk transactions are protected off-chain and only a 32-byte summary is
anchored on-chain:

1. The sender signs the transaction payload hash with TWO NIST post-quantum
   schemes that rest on different hardness assumptions:
     * CRYSTALS-Dilithium  -> ML-DSA-44         (FIPS 204, lattice-based)
     * SPHINCS+            -> SLH-DSA-SHA2-128f (FIPS 205, hash-based)
2. The attestor service verifies BOTH signatures. If either check fails the
   transaction is refused and nothing is sent on-chain.
3. pq_signature_hash = keccak256(pk_dilithium || pk_sphincs || sig_dilithium || sig_sphincs)
   is passed to AdaptiveCryptoSecurity.submitHighRiskTransaction, and the
   whitelisted attestor ECDSA-signs it (existing contract logic).
4. The full keys and signatures are written to an audit record so anyone can
   recompute pq_signature_hash and check it against the on-chain transaction.

Keys are stored per sender in integration/pq_keys/ (demo only; in production
the post-quantum secret key would live in the user's wallet, never on a server).

Requires: pip install pqcrypto>=1.0
"""

from __future__ import annotations

import json
import time
from dataclasses import asdict, dataclass
from pathlib import Path

from web3 import Web3

try:
    from pqcrypto.sign import ml_dsa_44 as dilithium
    from pqcrypto.sign import slh_dsa_sha2_128f as sphincs
except ImportError as exc:  # pragma: no cover
    raise ImportError(
        "pqcrypto is required for real post-quantum signatures. "
        "Install it with: pip install pqcrypto"
    ) from exc

DILITHIUM_NAME = "ML-DSA-44 (CRYSTALS-Dilithium)"
SPHINCS_NAME = "SLH-DSA-SHA2-128f (SPHINCS+)"

KEY_DIR = Path(__file__).with_name("pq_keys")
AUDIT_DIR = Path(__file__).with_name("pq_attestations")


class PQVerificationError(Exception):
    """Raised when a post-quantum signature fails verification."""


@dataclass
class PQKeyPair:
    dilithium_pk: bytes
    dilithium_sk: bytes
    sphincs_pk: bytes
    sphincs_sk: bytes


@dataclass
class PQAttestation:
    payload_hash: str            # 0x-hex of the 32-byte message that was signed
    pq_signature_hash: bytes     # 32 bytes, goes on-chain
    dilithium_signature_bytes: int
    sphincs_signature_bytes: int
    dilithium_sign_ms: float
    sphincs_sign_ms: float
    dilithium_verify_ms: float
    sphincs_verify_ms: float
    audit_file: str


# --------------------------------------------------------------------------- keys
def load_or_create_keys(owner_address: str) -> PQKeyPair:
    """Return the post-quantum key pairs for an address, generating them once."""
    KEY_DIR.mkdir(exist_ok=True)
    path = KEY_DIR / f"{owner_address.lower()}.json"
    if path.exists():
        data = json.loads(path.read_text(encoding="utf-8"))
        return PQKeyPair(**{k: bytes.fromhex(v) for k, v in data.items()})

    d_pk, d_sk = dilithium.keygen()
    s_pk, s_sk = sphincs.keygen()
    keys = PQKeyPair(d_pk, d_sk, s_pk, s_sk)
    path.write_text(json.dumps({k: v.hex() for k, v in asdict(keys).items()}), encoding="utf-8")
    return keys


# ------------------------------------------------------------ sender side: sign
def sign_payload(keys: PQKeyPair, payload_hash: bytes) -> tuple[bytes, bytes, float, float]:
    """Sign the payload with both schemes. Returns (sig_d, sig_s, ms_d, ms_s)."""
    t0 = time.perf_counter()
    sig_d = dilithium.sign(keys.dilithium_sk, payload_hash)
    t1 = time.perf_counter()
    sig_s = sphincs.sign(keys.sphincs_sk, payload_hash)
    t2 = time.perf_counter()
    return sig_d, sig_s, (t1 - t0) * 1000, (t2 - t1) * 1000


def pq_signature_hash(d_pk: bytes, s_pk: bytes, sig_d: bytes, sig_s: bytes) -> bytes:
    """32-byte on-chain summary binding both public keys and both signatures."""
    return bytes(Web3.keccak(d_pk + s_pk + sig_d + sig_s))


# -------------------------------------------------------- attestor side: verify
def verify_and_attest(
    payload_hash: bytes,
    d_pk: bytes,
    s_pk: bytes,
    sig_d: bytes,
    sig_s: bytes,
) -> tuple[bytes, float, float]:
    """Verify BOTH signatures; return (pq_signature_hash, ms_d, ms_s) or raise."""
    t0 = time.perf_counter()
    try:
        dilithium.verify(d_pk, payload_hash, sig_d)
    except Exception as exc:  # pqcrypto raises InvalidSignatureError
        raise PQVerificationError("Dilithium (ML-DSA-44) signature is invalid") from exc
    t1 = time.perf_counter()
    try:
        sphincs.verify(s_pk, payload_hash, sig_s)
    except Exception as exc:
        raise PQVerificationError("SPHINCS+ (SLH-DSA) signature is invalid") from exc
    t2 = time.perf_counter()
    return pq_signature_hash(d_pk, s_pk, sig_d, sig_s), (t1 - t0) * 1000, (t2 - t1) * 1000


# ------------------------------------------------------------ full workflow
def create_attestation(sender_address: str, payload_hash: bytes) -> PQAttestation:
    """Sender signs with both schemes, attestor verifies both, audit record saved."""
    if len(payload_hash) != 32:
        raise ValueError("payload_hash must be 32 bytes")

    keys = load_or_create_keys(sender_address)
    sig_d, sig_s, sign_d_ms, sign_s_ms = sign_payload(keys, payload_hash)
    pq_hash, ver_d_ms, ver_s_ms = verify_and_attest(
        payload_hash, keys.dilithium_pk, keys.sphincs_pk, sig_d, sig_s
    )

    AUDIT_DIR.mkdir(exist_ok=True)
    audit_path = AUDIT_DIR / f"{payload_hash.hex()}.json"
    audit_path.write_text(
        json.dumps(
            {
                "sender": sender_address,
                "payload_hash": "0x" + payload_hash.hex(),
                "pq_signature_hash": "0x" + pq_hash.hex(),
                "dilithium": {"scheme": DILITHIUM_NAME, "public_key": keys.dilithium_pk.hex(), "signature": sig_d.hex()},
                "sphincs": {"scheme": SPHINCS_NAME, "public_key": keys.sphincs_pk.hex(), "signature": sig_s.hex()},
                "recompute": "keccak256(dilithium.public_key || sphincs.public_key || dilithium.signature || sphincs.signature)",
            },
            indent=2,
        ),
        encoding="utf-8",
    )

    return PQAttestation(
        payload_hash="0x" + payload_hash.hex(),
        pq_signature_hash=pq_hash,
        dilithium_signature_bytes=len(sig_d),
        sphincs_signature_bytes=len(sig_s),
        dilithium_sign_ms=sign_d_ms,
        sphincs_sign_ms=sign_s_ms,
        dilithium_verify_ms=ver_d_ms,
        sphincs_verify_ms=ver_s_ms,
        audit_file=str(audit_path),
    )


def verify_audit_record(audit_file: str | Path) -> bool:
    """Re-verify a saved attestation from its audit file (for auditors/examiners)."""
    rec = json.loads(Path(audit_file).read_text(encoding="utf-8"))
    payload = bytes.fromhex(rec["payload_hash"][2:])
    d_pk = bytes.fromhex(rec["dilithium"]["public_key"])
    s_pk = bytes.fromhex(rec["sphincs"]["public_key"])
    sig_d = bytes.fromhex(rec["dilithium"]["signature"])
    sig_s = bytes.fromhex(rec["sphincs"]["signature"])
    pq_hash, _, _ = verify_and_attest(payload, d_pk, s_pk, sig_d, sig_s)
    return "0x" + pq_hash.hex() == rec["pq_signature_hash"]
