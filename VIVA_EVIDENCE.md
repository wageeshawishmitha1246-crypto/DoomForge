# DoomForge: Viva Evidence

Collected on 2026-11-17 by reading the repository and re-running the existing tests. No code, model, threshold, feature or contract was changed. No private key, `.env` value or `lab.db` content is printed here (only public addresses and transaction hashes).

**Short version: what is solid and what is missing**

| Item | Status |
|---|---|
| Tests (risk tiers, 6 security tests, 6 PQ tests) | Re-run today, all pass |
| Audit record re-verification | Passes |
| PQ benchmark, 50 runs (Table 6.6) | Script and result file exist |
| Model comparison script `compare_models.py` (Tables 6.3 to 6.5) | **Not found anywhere** |
| Gas test with 30 transactions per tier (Table 6.7 / Appendix C) | **Script exists, but the saved result has only 7 transactions** |
| Wallet scoring time, 200 runs (46.3 ms) | **No script or output found** |
| Sepolia full-loop transactions after 30 Oct 2026 | **None found on the contract in the backup env** (see section 8) |

---

## 1. Model comparison (`compare_models.py`)

- **`compare_models.py` does not exist** anywhere under `D:\Wagee` (searched all of it), and git history (a single squashed commit) has no trace of it.
- No `Table_6.3/6.4/6.5` file exists either. The only mention of a thesis table in the repo is a note about Table 6.7 in `lab/README.md`.
- Nothing was run for this section because there is nothing to run.
- Closest existing files (do **not** present them as Tables 6.3 to 6.5):
  - `ml_pipeline/outputs/model_metrics.csv`: RandomForest and XGBoost, every metric 1.0. It is written by `demo/adaptive_cryptography_security_simulation.py` (the **synthetic** simulation, dated 2026-05-02), not by the real 99-wallet pipeline. XGBoost is not part of `ml_pipeline/train_model.py`, which trains Logistic Regression and Random Forest only.
  - `ml_pipeline/train_model.py` and `ml_pipeline/evaluate.py` can compute metrics for the real data, but running `train_model.py` would overwrite the saved model, so I did not run it.
- Saved model files: `ml_pipeline/models/random_forest.joblib` and `ml_pipeline/models/logistic_regression.joblib`.

## 2. Benchmarks

**(a) Post-quantum signing, 50 runs (Table 6.6)**

- Script: `integration/test_pq_attestor.py` (default 50 runs; function `run_benchmark`). Output: `integration/pq_benchmark.csv` (file dated 2026-11-13).
- Saved result:

| Scheme | Public key | Signature | Sign ms (mean ± sd) | Verify ms (mean ± sd) | Runs |
|---|---|---|---|---|---|
| ML-DSA-44 (Dilithium) | 1,312 B | 2,420 B | 9.604 ± 2.096 | 0.182 ± 0.049 | 50 |
| SLH-DSA-SHA2-128f (SPHINCS+) | 32 B | 17,088 B | 22.621 ± 3.848 | 1.444 ± 0.418 | 50 |

- Re-run today (written to a temp file, so the saved CSV was not touched): Dilithium sign 7.53 ± 0.65 ms, verify 0.15 ± 0.03 ms; SPHINCS+ sign 18.16 ± 1.43 ms, verify 1.16 ± 0.18 ms. Sizes are identical; times differ by machine load, so quote the saved CSV in the thesis and say times vary run to run.

**(b) Gas and latency, 30 transactions per tier (Table 6.7 / Appendix C)**

- Script: `integration/batch_test_day3.py` (`--per-tier`, **default 3**, not 30). Output: `integration/day3_gas_log.csv` (dated 2026-07-26).
- **The saved CSV has 7 rows, not 90**: 3 Low (gas 137,747 / 137,759 / 137,771), 1 Medium (178,036), 3 High (180,437 / 180,437 / 180,425). Only 1 Medium row because the model puts only 1 wallet in Medium (see section 6 note). The script can do 30 per tier only if the pool is large enough; Medium cannot, since there is only 1 Medium wallet.
- **No latency column** exists in that CSV and no separate latency output file was found. If Table 6.7 reports latency, its source file is missing.
- **ETH sent per transaction: 0 ETH.** `batch_test_day3.py` calls `process_transaction` without a value, and the default is `value_eth = 0.0` (`integration/adaptive_crypto_bridge.py`, `integration/risk_to_chain.py`). That explains why these gas numbers are lower than the lab's (Low 184,363; Medium 224,640; High 227,029): the lab sends real ETH and the contract forwards it (as stated in `lab/README.md`).

**(c) Wallet scoring time, 200 runs (46.3 ms)**

- **No script and no output file** produce this number. I searched all `.py`, `.md`, `.csv` and `.txt` files for it and for `perf_counter`; only the PQ test and the day-3 script time anything. The only other hit for "46.3" is random digits inside the synthetic CSV.
- If it was measured in a notebook or a one-off command, that evidence is not in this workspace. Either re-measure it with a small script or remove the figure.

## 3. Tests re-run against the local chain

- Chain: local Ganache, chainId 1337, port 8545, running.
- These tests need an **unlocked** attestor account that is whitelisted on the contract. The lab's own contract uses a key-based attestor, so I did **not** modify it. Instead I deployed a second copy of the same compiled contract (`lab/contract_build.json`) on the same chain: `0x5b1869D9A4C187F2EAa108f3062412ecf0526b24`, with Ganache account 9 as attestor. Its runtime code is byte-for-byte identical to the lab contract except the last 32 bytes, which are the compiler's metadata hash (not logic). The lab contract `0x529f826b07744926cB536Bb694A22D873F7A3DA2` was not touched.

**`integration/test_risk_tiers.py`** (prints transaction status instead of PASS/FAIL):
```
LOW risk tx status: 1       riskLevel 0, scheme 0
MEDIUM risk tx status: 1    riskLevel 1, scheme 1
PQ attestation: Dilithium sig 2420 B, SPHINCS+ sig 17088 B
HIGH risk tx status: 1      riskLevel 2, scheme 2
```
(There are harmless "MismatchedABI ... discarded" warnings: web3 skips logs of other events when decoding one event type.)

**`integration/test_contract_security.py`:**
```
[PASS] Medium-risk transaction without commitment hash        (revert: Medium risk requires commitment hash)
[PASS] High-risk transaction via the standard ECDSA path      (revert: High risk must use submitHighRiskTransaction)
[PASS] ECDSA signature from a different account               (revert: Invalid sender signature)
[PASS] Replay of an already-used nonce                        (revert: Invalid nonce)
[PASS] High-risk transaction approved by a non-whitelisted attestor  (revert: Invalid or unauthorized PQ attestation)
[PASS] Tampered SPHINCS+ signature (refused off-chain)        (SLH-DSA signature is invalid)
[PASS] Correctly attested High-risk transaction accepted (gas 180437)
ALL SECURITY TESTS PASSED
```

**`integration/test_pq_attestor.py`:**
```
[PASS] valid Dilithium + SPHINCS+ signatures accepted
[PASS] tampered Dilithium signature rejected
[PASS] tampered SPHINCS+ signature rejected
[PASS] signature over a different payload rejected
[PASS] on-chain summary is 32 bytes
[PASS] audit record re-verifies independently
ALL TESTS PASSED
```
Side effect: these runs added 3 audit records and some PQ key files (both git-ignored folders) and some blocks on the local chain.

## 4. Audit record check

`pq_attestor.verify_audit_record()` on `integration/pq_attestations/76379c9f108920ab05eff7efb58f8779722a0e77b60a21566e758442ccb2826a.json` (dated 2026-11-13):

```
verify_audit_record -> True
sender:            0x1111111111111111111111111111111111111111
pq_signature_hash: 0x49ff6e708af4fe3272939672b04c360e7bdb58fabd9b784304fe66b696eb6d3f
```
It re-verifies both signatures from the saved public keys and recomputes keccak256(both public keys + both signatures) and compares it with the stored hash. The sender `0x111…1` is a test address.

## 5. Unchanged core

| File | Last commit date in git | File modified time on disk | Notes |
|---|---|---|---|
| `ml_pipeline/models/random_forest.joblib` | 2026-11-16 (commit 7802bc3) | 2026-10-29 | sha256 below |
| `blockchain/contracts/AdaptiveCryptoSecurity.sol` | 2026-11-16 (commit 7802bc3) | 2026-07-26 | version string `2.0.0` |

- **Git dates are not the real history.** When the project moved to the new GitHub account, the history was squashed into one commit (`7802bc3 new commit`, 2026-11-16), so git cannot prove the model or contract date. The on-disk modified times are the original ones but are weaker evidence (they can be changed). `git status` shows both files unmodified since that commit.
- **sha256 of random_forest.joblib:** `61d2c72f0680a27a9f08656318e3ea63e518eaa677c294ffcb0e57eaee7f6460`
- **What the lab loads:**
  - Model: `lab/core/risk.py` loads `MODELS_DIR / "random_forest.joblib"`, where `MODELS_DIR` is `ml_pipeline/models/` (from `ml_pipeline/config.py`).
  - Contract interface: `lab/core/chain.py` loads `integration/AdaptiveCryptoSecurity_abi.json` and the address `CONTRACT_ADDRESS` from `lab/.env` (currently `0x529f826b07744926cB536Bb694A22D873F7A3DA2` on the local chain, version 2.0.0, 9,158 bytes of runtime code).
  - Contract deployment: `lab/setup_local_chain.py` uses the Hardhat build in `blockchain/artifacts/` if present, otherwise `lab/contract_build.json`. I compared the Hardhat build with `contract_build.json`: same length, and the only differences are in the last ~43 bytes (the compiler metadata hash), not in the logic.
- Thresholds 0.30 / 0.70 are set in `lab/core/config.py` (`LOW_RISK_THRESHOLD`, `HIGH_RISK_THRESHOLD`); I did not change them.

## 6. Feature importance of the real model (not retrained)

`random_forest.joblib`: 200 trees, 17 input features, `class_weight=balanced`, median imputer. Trained on 99 wallets (62 label 1, 37 label 0).

| # | Feature | Importance |
|---|---|---|
| 1 | from_active_days | 0.1754 |
| 2 | tx_frequency_per_day | 0.1631 |
| 3 | sent_tx_count | 0.1367 |
| 4 | sent_failed_ratio | 0.1013 |
| 5 | sent_avg_value_eth | 0.0929 |
| 6 | sent_total_value_eth | 0.0702 |
| 7 | recv_tx_count | 0.0602 |
| 8 | from_min_time_between_txs_sec | 0.0581 |
| 9 | total_tx_count | 0.0504 |
| 10 | sent_avg_gas_price | 0.0475 |
| 11 | from_avg_time_between_txs_sec | 0.0341 |
| 12 | recv_total_value_eth | 0.0039 |
| 13 | recv_avg_value_eth | 0.0037 |
| 14 | sent_received_value_ratio | 0.0013 |
| 15 | unique_counterparties_sent | 0.0011 |
| 16 | unique_counterparties_received | 0.0000 |
| 17 | contract_interaction_ratio | 0.0000 |

(sum = 1.0000)

**Things a panel can see in this evidence (be ready to explain them):**
1. **Label source:** in `wallet_features_labeled.csv`, all 62 positive labels are `heuristic` and all 37 negatives are `default_negative`. There are **zero** wallets matched to a known-scam list. The positive labels come from risk indicators computed from the same kind of features the model then learns (e.g. transaction frequency, failed ratio, value), so high scores partly reflect the labelling rule. `lab/README.md` calls this "label leakage".
2. **Tier split:** the model puts **36 Low, 1 Medium, 62 High** among the 99 wallets (`lab/README.md`). That is why Medium has only one real example.
3. **Perfect scores:** the 1.0 values in `model_metrics.csv` come from the synthetic simulation and must not be quoted as the real model's accuracy.
4. Two features have importance ~0 (`unique_counterparties_received`, `contract_interaction_ratio`).

## 7. Local-only files (not on GitHub)

`git status`: **no untracked and no modified source files** (one tracked `.pyc` was touched by my test run and restored with `git checkout`). Branch `main` is **ahead of `origin/main` by 1 commit** (`a6d0906`, PINs and panel guide), which is **not pushed yet**.

Git-ignored files that exist only on this laptop:

| Folder | Local-only content |
|---|---|
| `blockchain/` | `.env`, `artifacts/`, `cache/`, `types/`, an extra `blockchain/blockchain/` folder, `node_modules/` |
| `integration/` | `pq_attestations/` (6 audit records), `pq_keys/` (8 key files; demo PQ secret keys) |
| `lab/` | `.env`, `.env.sepolia.backup`, `chaindata/` (the Ganache chain), `lab.db` (wallets, PINs, transactions), `tunnel.log` |
| repo root | `hf_space/` (old Hugging Face build), `.claude/` |
| `.venv/` | the Python environment |

Notes: `.gitignore` keeps secrets and databases off GitHub. About 20 compiled `.pyc` files **are** tracked in git (e.g. `__pycache__/` at the root and in `integration/`, `ml_pipeline/`); they are harmless but untidy. The model and the data CSVs **are** tracked.

## 8. Sepolia

- **Contract on Sepolia (from `lab/.env.sepolia.backup`):** `0xcd89B1251C942Db70a8A3838d714D994A6AF922B`. Verified live through a public Sepolia endpoint: it has code (9,158 bytes) and `VERSION()` returns `2.0.0`. No other Sepolia address is recorded anywhere in the repo.
- **Transactions on it since 30 Oct 2026 (read from chain logs, 12022962 to latest block):** only two, both setup:
  - Deployment, 2026-11-12 21:10 UTC, block 12121423: `0x2f400a62a9376081fa62c2e69ec701ec93f069d44d3298106b1cc72f78cef1b4`
  - `setPQAttestor`, 2026-11-12 21:10 UTC, block 12121424: `0xfd5195922fbc3aa11e4f2227548c100c05218d8d3141c9884da16b24402464d8`
- **No full-loop transaction found** (no `submitStandardTransaction` or `submitHighRiskTransaction`, no `TransactionSecured` event) on this contract. So I cannot list full-loop hashes. If you sent Sepolia transactions, they were either on a different contract (a different earlier address is not recorded in this repo), or they have not happened. Check your wallet history on Sepolia Etherscan and add the hashes by hand.
- Limits of this check: the Etherscan key in your env was rejected as invalid, and the Alchemy URL in the backup is a placeholder (`YOUR_ALCHEMY_KEY`), so I used a keyless public RPC instead. A public node answers `getLogs` honestly for this range, but if you want a second source, open `https://sepolia.etherscan.io/address/0xcd89B1251C942Db70a8A3838d714D994A6AF922B`.
- The lab was switched from Sepolia to the local Ganache chain (`lab/.env` now points at `127.0.0.1:8545`); the Sepolia settings are kept only in the backup file.
