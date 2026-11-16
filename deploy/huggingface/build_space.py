"""Collect only the files the Hugging Face Space needs into  <repo>/hf_space  (git-ignored).

Run from anywhere:   .venv\\Scripts\\python deploy\\huggingface\\build_space.py

Never copied: lab/.env, lab/.env.sepolia.backup, lab/lab.db, lab/chaindata, PQ keys, logs.
"""

from __future__ import annotations

import shutil
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[1]
OUT = REPO / "hf_space"

LAB_SKIP = shutil.ignore_patterns(".env*", "lab.db*", "chaindata", "*.log", "__pycache__", "*.key",
                                  "pq_keys", "pq_audit", "*.bat")
FILES = [
    "integration/pq_attestor.py",
    "integration/AdaptiveCryptoSecurity_abi.json",
    "ml_pipeline/config.py",
    "ml_pipeline/train_model.py",
    "ml_pipeline/evaluate.py",
    "ml_pipeline/models/random_forest.joblib",
    "ml_pipeline/data/processed/wallet_features_labeled.csv",
]


def main() -> None:
    if OUT.exists():
        shutil.rmtree(OUT)
    OUT.mkdir()
    shutil.copytree(REPO / "lab", OUT / "lab", ignore=LAB_SKIP)
    for rel in FILES:
        dst = OUT / rel
        dst.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(REPO / rel, dst)
    for name in ("Dockerfile", "start.sh", "requirements.txt", "README.md"):
        shutil.copy2(HERE / name, OUT / name)
    (OUT / "start.sh").write_bytes((OUT / "start.sh").read_bytes().replace(b"\r\n", b"\n"))

    secrets = [p for p in OUT.rglob("*") if p.name.startswith(".env") or p.name.startswith("lab.db")
               or "chaindata" in p.parts or "pq_keys" in p.parts]
    if secrets:
        raise SystemExit(f"Stopped: private files were copied: {secrets}")
    files = [p for p in OUT.rglob("*") if p.is_file()]
    print(f"Built {OUT} with {len(files)} files, {sum(p.stat().st_size for p in files) / 1e6:.1f} MB. No private files.")


if __name__ == "__main__":
    main()
