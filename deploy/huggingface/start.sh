#!/bin/sh
# Starts everything DoomForge Lab needs, in order: chain -> contract setup -> collector -> app.
set -e
cd /home/user/app/lab

echo "[start] starting the local Ethereum chain (Ganache)"
ganache --wallet.deterministic --wallet.defaultBalance 1000000 --miner.blockTime 3 \
        --chain.chainId 1337 --chain.hardfork shanghai --database.dbPath chaindata \
        --server.host 127.0.0.1 --server.port 8545 > /tmp/chain.log 2>&1 &

echo "[start] waiting for the chain"
python - <<'PY'
import sys, time
from web3 import Web3
w3 = Web3(Web3.HTTPProvider("http://127.0.0.1:8545"))
for _ in range(90):
    if w3.is_connected():
        print("[start] chain is up, block", w3.eth.block_number)
        sys.exit(0)
    time.sleep(1)
sys.exit("[start] the chain did not start; see /tmp/chain.log")
PY

# First start (or after the server was reset): deploy the contract and write lab/.env.
# ETHERSCAN_API_KEY and ACCESS_CODE come from the Space secrets, not from a file.
if ! grep -q '^CONTRACT_ADDRESS=0x' .env 2>/dev/null; then
    echo "[start] deploying the contract and creating the faucet"
    python setup_local_chain.py
fi

echo "[start] starting the Etherscan collector"
( while true; do python collector.py || true; sleep 10; done ) &

echo "[start] starting the app"
exec streamlit run app.py --server.address 0.0.0.0 --server.port 8501 --server.headless true
