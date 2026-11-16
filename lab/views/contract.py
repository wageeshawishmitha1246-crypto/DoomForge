import time

import pandas as pd
import streamlit as st

import ui
from core import config, risk, store

chain = ui.chain_or_stop()

st.title("🛡️ Risk & smart contract")

# ------------------------------------------------------------ contract
info = chain.contract_info()
st.subheader("The DoomForge smart contract")
c1, c2, c3 = st.columns(3)
c1.markdown(f"**Contract**  \n[`{ui.short(info['address'], 8)}`]({chain.address_link(info['address'])})")
c2.markdown(f"**Version**  \n{info.get('version', '?')} on {config.NETWORK_NAME} (chain {info['chain_id']})")
if "attestor" in info:
    c3.markdown(f"**Post-quantum attestor**  \n`{ui.short(info['attestor'])}` "
                + ("✅ approved" if info["attestor_approved"] else "❌ NOT approved"))

st.markdown(
    "| Tier | Risk score | Protection | What the contract checks |\n|---|---|---|---|\n"
    "| Low | below 0.30 | Standard ECDSA | nonce, signer = sender |\n"
    "| Medium | 0.30 to 0.70, or a new wallet | ECDSA + commitment hash | nonce, signer, commitment hash not empty |\n"
    "| High | 0.70 or more | Dilithium + SPHINCS+, attested | nonce, approval from an approved attestor |"
)

# -------------------------------------------------------- transactions
st.subheader("All transactions on this platform")
txs = store.list_transactions()
accounts = {a["id"]: a["name"] for a in store.list_accounts()}
if not txs:
    st.caption("No transactions yet.")
else:
    df = pd.DataFrame([{
        "When": time.strftime("%d %b %H:%M", time.localtime(t["created_at"])),
        "Who": accounts.get(t["account_id"], "?"),
        "DoomForge": "ON" if t["mode"] == "doomforge" else "OFF",
        "Tier": config.TIER_NAMES.get(t["tier"], "—") if t["tier"] is not None else "—",
        "Protection": t["scheme"],
        "ETH": t["value_eth"],
        "Gas used": t["gas_used"],
        "Result": "OK" if t["status"] else "Failed",
        "Explorer": chain.tx_link(t["tx_hash"]) if t["tx_hash"] else "",
    } for t in txs])
    st.dataframe(df, hide_index=True, width="stretch",
                 column_config={"Explorer": st.column_config.LinkColumn("Explorer", display_text="open")})
    ok = df[df["Result"] == "OK"]
    if not ok.empty:
        st.markdown("**Average gas by protection** (successful transactions on this platform)")
        st.bar_chart(ok.groupby("Protection")["Gas used"].mean().sort_values())

# --------------------------------------------------------- risk model
st.subheader("Risk of the 99 real wallets")
counts = risk.tier_counts()
m1, m2, m3 = st.columns(3)
m1.metric("Low", counts.get(0, 0))
m2.metric("Medium", counts.get(1, 0))
m3.metric("High", counts.get(2, 0))
st.caption("Scored by the deployed Random Forest (200 trees, 17 features). The score is the share of trees voting "
           "“risky”. The deployed model is very confident, so few wallets land in Medium; the thesis discusses "
           "why (label leakage).")

# ---------------------------------------------------------- attack lab
st.subheader("🧪 Attack lab")
st.markdown("Try to cheat the contract. Each attack is a **dry run** (`eth_call`): the contract runs its real checks, "
            "but nothing is mined and no gas is spent.")
acc = ui.current_account()
if acc is None:
    st.caption("Create a wallet on **Start here** to run the attack lab.")
elif st.button("Run the attacks", type="primary", width="stretch"):
    with st.spinner("Running the attacks against the deployed contract…"):
        results = chain.run_attacks(acc["private_key"])
    for r in results:
        icon = "🛑" if r["blocked"] else "⚠️"
        st.markdown(f"{icon} **{r['attack']}** — {r['what']}  \n`{r['result']}`")
    blocked = sum(r["blocked"] for r in results)
    if blocked == len(results):
        st.success(f"{blocked} of {len(results)} attacks were blocked.")
    else:
        st.error(f"Only {blocked} of {len(results)} attacks were blocked.")
