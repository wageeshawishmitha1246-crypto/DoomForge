# DoomForge Lab: Panel Guide

**AI-Driven Adaptive Cryptography for Real-Time Security Enhancement in Blockchain-Based Digital Currency Transactions**

|                 |                                   |
|-----------------|-----------------------------------|
| **Link**        | `____________________________`    |
| **Access code** | `____________________________`    |

*(Fill in the link and code by hand before sharing. They are deliberately not stored in this file.)*

A Random Forest scores the sender wallet from its real Ethereum history. The score picks the protection for the transaction:

| Risk score | Tier | Protection |
|---|---|---|
| below 0.30 | Low | ECDSA |
| 0.30 to 0.70 | Medium | ECDSA + commitment hash |
| 0.70 or more | High | Dilithium + SPHINCS+ post-quantum signatures, approved on-chain by an attestor |

The demo runs on a private Ethereum test network, so test ETH is unlimited. The same contract was also deployed and tested on the public Sepolia network.

## The 6 pages

1. **Dashboard (Log in):** create a wallet, or open one with its PIN. Nothing else is visible before this.
2. **My wallet:** balance, top-up with test ETH, and the wallet's risk score and tier.
3. **Send / smart contract:** send ETH with DoomForge **off** (plain transfer) or **on** (protection chosen by the tier).
4. **Risk & smart contract:** every transaction with its tier and gas, the risk of the 99 real wallets, and the **attack lab**.
5. **Ethereum network:** real Ethereum mainnet data from Etherscan, shown one hour late.
6. **Block explorer:** look up any block, transaction or address on the test network.

## Try it in 5 steps

1. Open the link, choose **Create a wallet**, enter a name, pick a wallet type, choose a **4 to 8 digit PIN** (you need it to open the wallet again), enter the access code, and click **Create my wallet**.
2. Go to **My wallet** and top up. Note the risk score and tier. Create a second wallet (log out first) with a different history to compare tiers.
3. Go to **Send / smart contract**. Send once with DoomForge **off**, then once **on**. Compare the scheme and gas used. Approximate gas with DoomForge on: Low 184,363, Medium 224,640, High 227,029. Off: 21,000.
4. Go to **Risk & smart contract** and click **Run the attacks**. The contract should block all **6 of 6** attacks.
5. Open **Ethereum network** to see live mainnet signals, then **Block explorer** to inspect your own transactions.

## Good to know

- Each wallet has its own PIN. After 5 wrong PINs a wallet locks for 60 seconds.
- Wallets and transactions are saved, so you can come back later and open your wallet with its PIN.
- If the page does not load, the link may have changed. Ask the student for the current one.
