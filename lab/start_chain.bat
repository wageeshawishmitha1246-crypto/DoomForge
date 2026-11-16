@echo off
REM DoomForge Testnet: a free local Ethereum chain (Ganache). Keep this window open.
REM Blocks are mined every 3 seconds, like a real network. The chain is saved in lab\chaindata,
REM so your contract, wallets and transactions are still there after a restart.
cd /d "%~dp0"
npx --yes ganache@7 --wallet.deterministic --wallet.defaultBalance 1000000 --miner.blockTime 3 --chain.chainId 1337 --chain.hardfork shanghai --database.dbPath chaindata --server.host 127.0.0.1 --server.port 8545
