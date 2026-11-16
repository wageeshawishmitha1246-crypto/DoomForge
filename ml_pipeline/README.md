# Ethereum Transaction Threat/Risk Detection – Phase 1 Baseline

This repository contains the first phase of a research-friendly ML
pipeline for Ethereum transaction / wallet risk detection built on
Python, Etherscan API data, and classic machine learning models.

Phase 1 goals:
- Collect transaction data from the Etherscan API (v2 docs)
- Store raw data as CSV files
- Preprocess and clean the data
- Engineer basic transaction-level and wallet-level behavioral features
- Train baseline models (Logistic Regression, Random Forest)
- Evaluate them with standard metrics
- Save models and processed artifacts for future extensions

## 1. Setup

All commands below assume you run them from the repository root
(`Doomforge/`).

### 1.1. Python environment

```bash
python -m venv .venv
# Windows PowerShell
. .venv/Scripts/Activate.ps1
# or cmd.exe
.venv\Scripts\activate

pip install -r ml_pipeline/requirements.txt
```

### 1.2. Get an Etherscan API key

1. Go to https://etherscan.io/apis
2. Sign in or create an account.
3. Create an API key (free tier is enough for experimentation).
4. Copy the API key string.

### 1.3. Set the `ETHERSCAN_API_KEY` environment variable

On **Windows PowerShell** (current session only):

```powershell
$env:ETHERSCAN_API_KEY = "YOUR_KEY_HERE"
```

On **Windows cmd.exe** (current session only):

```cmd
set ETHERSCAN_API_KEY=YOUR_KEY_HERE
```

On **Linux / macOS (bash/zsh)**:

```bash
export ETHERSCAN_API_KEY="YOUR_KEY_HERE"
```

You can also add the export command to your shell profile so it is
available in future sessions.

## 2. Wallet addresses input

Create a simple text file with one wallet address per line:

- Path (default): `data/wallet_addresses.txt`
- Example contents:

```text
0x742d35Cc6634C0532925a3b844Bc454e4438f44e
0x53d284357ec70cE289D6D64134DfAc8E511c8a3D
```

You can change the path using the `--addresses-file` argument when
running data collection.

## 3. Data collection (Etherscan API v2)

Run the data collection script to download:
- normal transactions by address
- optionally internal transactions
- optionally ERC-20 token transfers

```bash
python ml_pipeline/data_collection.py \
  --addresses-file ml_pipeline/data/wallet_addresses.txt \
  --include-internal \
  --include-erc20
```

Outputs are stored under `data/raw/` as:
- `normal_transactions.csv`
- `internal_transactions.csv` (optional)
- `erc20_transfers.csv` (optional)

The code includes basic pagination and rate-limit-friendly delays. If
the Etherscan API returns an error, it is surfaced with a readable
message.

## 4. Preprocessing

Clean and normalize the raw CSV files:

```bash
python ml_pipeline/preprocessing.py
```

This script:
- standardizes column names
- keeps a consistent set of important fields (hash, from, to, value, gas,
  gasPrice, timeStamp, isError, methodId, functionName, blockNumber,
  contractAddress, etc.)
- converts numeric columns
- parses timestamps into a datetime column
- computes `value_eth` from Wei

Output:
- `data/processed/processed_transactions.csv`

## 5. Feature engineering

Build basic wallet-level behavioral features:

```bash
python ml_pipeline/feature_engineering.py
```

This script uses the cleaned transactions to compute features such as:
- total number of transactions per wallet
- total and average transaction value (ETH)
- gas price statistics
- transaction frequency per wallet
- time gaps between successive transactions
- number of unique counterparties (sent and received)
- sent/received value ratio
- failed transaction ratio
- a simple contract interaction ratio (placeholder for richer analysis)

Output:
- `data/processed/wallet_features.csv`

## 6. Labels and modeling

For **Phase 1**, this project is structured so that you can plug in
labels later:

- The training script expects a binary column named `label` in
  `wallet_features.csv` where `0 = non-risky`, `1 = risky`.
- You can create this column by merging with an external labeled fraud
  dataset (e.g., a CSV mapping wallet_address to label) or by manual
  annotation for research purposes.

Once you add the `label` column, you can train baseline models.

## 7. Train baseline models

Train Logistic Regression and Random Forest models on the wallet
features:

```bash
python ml_pipeline/train_model.py
```

or, specifying a custom feature path or test size:

```bash
python ml_pipeline/train_model.py \
  --features-path ml_pipeline/data/processed/wallet_features.csv \
  --test-size 0.25
```

The training script:
- loads wallet features
- checks for the `label` column
- splits data into train/test sets with stratification
- trains Logistic Regression (with scaling) and Random Forest
- computes metrics using `evaluate.py`:
  - accuracy
  - precision
  - recall
  - F1-score
  - ROC-AUC (when possible)
- saves trained models under `models/`:
  - `logistic_regression.joblib`
  - `random_forest.joblib`

## 8. Future extensions

The code is intentionally kept modular and simple so you can extend it
in later phases with:
- graph-based features (e.g., address transaction networks)
- mempool-level features
- adaptive cryptography logic based on risk scores
- real-time risk scoring APIs or Streamlit dashboards

You can build on top of the existing modules:
- `data_collection.py` for additional Etherscan endpoints
- `preprocessing.py` for richer parsing and cleaning
- `feature_engineering.py` for advanced behavioral and graph features
- `train_model.py` / `evaluate.py` for more models, hyperparameter
  search, and cross-validation

This Phase 1 baseline gives you a clean, reproducible foundation to
iterate on as your research becomes more advanced.
