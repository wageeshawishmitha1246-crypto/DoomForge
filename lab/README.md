# DoomForge Lab

A web platform that shows DoomForge working on a real blockchain:

- **Start here**: create a wallet, either *existing* (a real Ethereum wallet's Etherscan history is scored by the
  Random Forest; choose Random, Low, Medium or High) or *new* (no history, treated as Medium/Unknown).
- **My wallet**: Sepolia address, balance, **Top up**, the wallet's risk score and its 17 features.
- **Send / smart contract**: send with **DoomForge OFF** (normal ECDSA transfer) or **ON** (risk → tier →
  ECDSA / commitment hash / Dilithium + SPHINCS+ attestation → contract checks), every step shown.
- **Ethereum network**: real mainnet signals from Etherscan (traffic, block fullness, gas price, block time),
  shown one hour late.
- **Risk & smart contract**: all transactions with tier and gas, the contract's rules, and an **attack lab**.

All transactions are real blockchain transactions (on your local DoomForge Testnet or on Sepolia) with block-explorer links. Nothing is simulated.

## Free mode: DoomForge Testnet on your laptop (no Sepolia ETH needed)

This runs your own Ethereum test network (Ganache) on your laptop. Test ETH is unlimited and free. Everything is
still real: real transactions in real blocks (one every 3 seconds), your real smart contract, real ECDSA and
post-quantum signatures. Only the network is private instead of public. The **Block explorer** page replaces
Sepolia Etherscan, and every transaction link opens it.

**One-time setup** (VS Code terminal, in `Doomforge\lab`):
```
start_chain.bat
```
Leave that window open. In a second terminal:
```
python setup_local_chain.py
```
It deploys a fresh contract, approves your attestor, creates a faucet wallet with 50,000 test ETH and writes
everything into `lab\.env`. Your Sepolia settings are saved as `lab\.env.sepolia.backup`, and your
`ACCESS_CODE` and `ETHERSCAN_API_KEY` are kept.

**Every time you run it**: `start_chain.bat` (window 1), `python collector.py` (window 2),
`streamlit run app.py` (window 3), `cloudflared tunnel --url http://localhost:8501` (window 4).
The chain is saved in `lab\chaindata`, so wallets and transactions survive a restart. Do not run
`setup_local_chain.py` again unless you want a fresh contract.

What to tell the panel: the contract was also deployed and tested on the public Sepolia testnet; the demo runs on a
private Ethereum test network so that test ETH is unlimited.

## Sepolia mode (needs Sepolia ETH)

## One-time setup (Windows, cmd)

You need: Python 3.11+, Node.js (for the Hardhat deploy), your Alchemy Sepolia RPC URL, your Sepolia deployer
private key with some Sepolia ETH (0.3 to 0.5 ETH is plenty), and an Etherscan API key.

**1. Install the Python packages**
```
cd Doomforge\lab
pip install -r requirements.txt
```

**2. Make an attestor key**
```
python make_attestor_key.py
```
Copy the address and the private key it prints.

**3. Deploy a fresh contract to Sepolia, with the attestor approved**
```
cd ..\blockchain
set SEPOLIA_RPC_URL=https://eth-sepolia.g.alchemy.com/v2/YOUR_ALCHEMY_KEY
set SEPOLIA_PRIVATE_KEY=0xYOUR_DEPLOYER_KEY
set ATTESTOR_ADDRESS=0xADDRESS_FROM_STEP_2
npx hardhat run scripts/deploy.ts --network sepolia
```
It prints `AdaptiveCryptoSecurity deployed to: 0x...` and `Registered PQ attestor: 0x...`. Copy the contract address.

**4. Fill in lab\.env**
Copy `.env.example` to `.env` (in the `lab` folder) and fill in:
`RPC_URL` (your Alchemy Sepolia URL), `CONTRACT_ADDRESS` (step 3), `ATTESTOR_PRIVATE_KEY` (step 2),
`FAUCET_PRIVATE_KEY` (your deployer key, which pays for top-ups), `ETHERSCAN_API_KEY`, and change `ACCESS_CODE`.

## Every time you run it

Keep three cmd windows open, all in `Doomforge\lab`.

**Window A: network collector** (start it at least one hour before the demo, because data is shown one hour late)
```
python collector.py
```

**Window B: the platform**
```
streamlit run app.py
```
Open http://localhost:8501 to check it.

**Window C: public link for the panel** (Cloudflare quick tunnel, free, no account)
```
winget install --id Cloudflare.cloudflared
cloudflared tunnel --url http://localhost:8501
```
It prints a link like `https://something.trycloudflare.com`. Send that link and the access code to the panel.
The link changes every time you restart cloudflared, so keep that window open. Your laptop must stay on and online.

## Notes for the viva

- The risk model is the thesis model, unchanged (`ml_pipeline/models/random_forest.joblib`). The deployed model
  puts 36 wallets in Low, 1 in Medium and 62 in High; the thesis explains why (label leakage).
- An existing wallet is a real mainnet address whose key nobody here holds, so a new Sepolia account acts for it:
  its history is scored, and the Sepolia account signs and sends.
- Gas on this platform is higher than Table 6.7 of the thesis because the platform also forwards ETH to the
  recipient. The gap between Medium and High stays about 2,400 gas.
- Demo wallets' private keys are kept in `lab/lab.db` so the platform can sign for them. Sepolia only, never real ETH.
- Tested end to end on a local Ganache chain: top-up, a normal transfer (21,000 gas), Low, Medium and High
  transactions, and 6 of 6 attacks blocked.
