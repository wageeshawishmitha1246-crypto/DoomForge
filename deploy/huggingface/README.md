---
title: DoomForge Lab
emoji: 🛡️
colorFrom: green
colorTo: gray
sdk: docker
app_port: 8501
pinned: false
short_description: AI-driven adaptive cryptography for Ethereum transactions
---

# DoomForge Lab

Demo platform for the thesis *AI-Driven Adaptive Cryptography for Real-Time Security Enhancement in
Blockchain-Based Digital Currency Transactions*.

A Random Forest scores the sender wallet's behaviour, and the score chooses the protection for the
transaction: Low → ECDSA, Medium → ECDSA + commitment hash, High → Dilithium + SPHINCS+ post-quantum
signatures approved on-chain by an attestor.

The demo runs on a private Ethereum test network inside this Space, so test ETH is unlimited. The same
contract was also deployed and tested on the public Sepolia network. The **Ethereum network** page shows
real mainnet data from Etherscan, one hour late.

If the Space restarts, the chain, the wallets and the network samples start again from zero.
