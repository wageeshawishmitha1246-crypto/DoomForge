"""Tests and benchmark for the real post-quantum attestor (no blockchain needed).

Run:  python test_pq_attestor.py            (tests + 50-run benchmark)
      python test_pq_attestor.py --runs 200

Checks
  1. Valid Dilithium + SPHINCS+ signatures are accepted.
  2. A tampered Dilithium signature is rejected.
  3. A tampered SPHINCS+ signature is rejected.
  4. A signature over a different payload is rejected.
  5. A saved audit record can be re-verified independently.
Then writes pq_benchmark.csv with key/signature sizes and sign/verify times.
"""

from __future__ import annotations

import argparse
import csv
import os
import statistics
import tempfile
from pathlib import Path

import pq_attestor as pq


def check(name: str, condition: bool) -> bool:
    print(f"  [{'PASS' if condition else 'FAIL'}] {name}")
    return condition


def run_tests() -> bool:
    print("Functional tests")
    sender = "0x" + "11" * 20
    payload = os.urandom(32)
    keys = pq.load_or_create_keys(sender)
    sig_d, sig_s, _, _ = pq.sign_payload(keys, payload)
    ok = True

    try:
        pq.verify_and_attest(payload, keys.dilithium_pk, keys.sphincs_pk, sig_d, sig_s)
        ok &= check("valid Dilithium + SPHINCS+ signatures accepted", True)
    except pq.PQVerificationError:
        ok &= check("valid Dilithium + SPHINCS+ signatures accepted", False)

    def rejected(sd: bytes, ss: bytes, msg: bytes) -> bool:
        try:
            pq.verify_and_attest(msg, keys.dilithium_pk, keys.sphincs_pk, sd, ss)
            return False
        except pq.PQVerificationError:
            return True

    bad_d = bytes([sig_d[0] ^ 0xFF]) + sig_d[1:]
    bad_s = bytes([sig_s[0] ^ 0xFF]) + sig_s[1:]
    ok &= check("tampered Dilithium signature rejected", rejected(bad_d, sig_s, payload))
    ok &= check("tampered SPHINCS+ signature rejected", rejected(sig_d, bad_s, payload))
    ok &= check("signature over a different payload rejected", rejected(sig_d, sig_s, os.urandom(32)))

    att = pq.create_attestation(sender, payload)
    ok &= check("on-chain summary is 32 bytes", len(att.pq_signature_hash) == 32)
    ok &= check("audit record re-verifies independently", pq.verify_audit_record(att.audit_file))
    return ok


def run_benchmark(runs: int, out: Path) -> None:
    print(f"\nBenchmark ({runs} runs)")
    keys = pq.load_or_create_keys("0x" + "22" * 20)
    rows = {"dilithium": {"sign": [], "verify": []}, "sphincs": {"sign": [], "verify": []}}
    sig_sizes = {}
    for _ in range(runs):
        payload = os.urandom(32)
        sig_d, sig_s, sd_ms, ss_ms = pq.sign_payload(keys, payload)
        _, vd_ms, vs_ms = pq.verify_and_attest(payload, keys.dilithium_pk, keys.sphincs_pk, sig_d, sig_s)
        rows["dilithium"]["sign"].append(sd_ms); rows["dilithium"]["verify"].append(vd_ms)
        rows["sphincs"]["sign"].append(ss_ms); rows["sphincs"]["verify"].append(vs_ms)
        sig_sizes = {"dilithium": len(sig_d), "sphincs": len(sig_s)}

    table = [
        ("ML-DSA-44 (Dilithium)", len(keys.dilithium_pk), sig_sizes["dilithium"], rows["dilithium"]),
        ("SLH-DSA-SHA2-128f (SPHINCS+)", len(keys.sphincs_pk), sig_sizes["sphincs"], rows["sphincs"]),
    ]
    with out.open("w", newline="", encoding="utf-8") as f:
        w = csv.writer(f)
        w.writerow(["scheme", "public_key_bytes", "signature_bytes",
                    "sign_ms_mean", "sign_ms_std", "verify_ms_mean", "verify_ms_std", "runs"])
        for name, pk, sig, t in table:
            r = [name, pk, sig,
                 round(statistics.mean(t["sign"]), 3), round(statistics.pstdev(t["sign"]), 3),
                 round(statistics.mean(t["verify"]), 3), round(statistics.pstdev(t["verify"]), 3), runs]
            w.writerow(r)
            print(f"  {name:30s} pk={pk:5d} B  sig={sig:6d} B  "
                  f"sign={r[3]:.2f}±{r[4]:.2f} ms  verify={r[5]:.2f}±{r[6]:.2f} ms")
        total_sign = statistics.mean(a + b for a, b in zip(rows["dilithium"]["sign"], rows["sphincs"]["sign"]))
        total_ver = statistics.mean(a + b for a, b in zip(rows["dilithium"]["verify"], rows["sphincs"]["verify"]))
        print(f"  Total per High-tier transaction: sign {total_sign:.2f} ms, verify {total_ver:.2f} ms, "
              f"on-chain data 32 B (instead of {sig_sizes['dilithium'] + sig_sizes['sphincs']:,} B of signatures)")
    print(f"Saved {out}")


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--runs", type=int, default=50)
    ap.add_argument("--out", default="pq_benchmark.csv")
    args = ap.parse_args()
    passed = run_tests()
    run_benchmark(args.runs, Path(args.out))
    print("\nALL TESTS PASSED" if passed else "\nSOME TESTS FAILED")
    raise SystemExit(0 if passed else 1)


if __name__ == "__main__":
    main()
