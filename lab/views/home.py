import streamlit as st

import login_form
import ui
from core import config

acc = ui.current_account()
if acc is None:
    login_form.render()
    st.stop()

st.title("DoomForge Lab")
st.markdown(
    "**AI-driven adaptive cryptography for Ethereum transactions.** A normal Ethereum transaction is protected "
    "by one ECDSA signature, whoever sends it. With **DoomForge ON**, a Random Forest scores the sender wallet's "
    "behaviour and the score chooses the protection: **Low → ECDSA**, **Medium → ECDSA + commitment hash**, "
    "**High → Dilithium + SPHINCS+ post-quantum signatures, approved on-chain by an attestor**."
)
st.caption(f"Every transaction here is a real transaction on **{config.NETWORK_NAME}**, with a link to the block explorer. "
           "Wallet histories are real Ethereum mainnet wallets collected from Etherscan.")

st.success(f"You are using **{acc['name']}** ({ui.short(acc['address'])}). Go to **My wallet** to top up.")

c1, c2, c3 = st.columns(3)
with c1, st.container(border=True):
    st.markdown("#### :material/account_balance_wallet: 1. Top up")
    st.caption("Get test ETH from the platform faucet.")
    st.page_link("views/wallet.py", label="Open My wallet", icon=":material/arrow_forward:")
with c2, st.container(border=True):
    st.markdown("#### :material/send: 2. Send")
    st.caption("Send once with DoomForge OFF, then ON, and compare.")
    st.page_link("views/send.py", label="Open Send", icon=":material/arrow_forward:")
with c3, st.container(border=True):
    st.markdown("#### :material/verified_user: 3. Attack lab")
    st.caption("See every transaction's tier and gas, and run six attacks.")
    st.page_link("views/contract.py", label="Open Risk & smart contract", icon=":material/arrow_forward:")

with st.expander("How to use this platform (5 steps)"):
    st.markdown(
        "1. You are logged in with a wallet. An *existing wallet* has a real Etherscan history that is scored; "
        "a *new wallet* has no history, so it is treated as Medium risk.\n"
        "2. Open **My wallet** and press **Top up** to get test ETH.\n"
        "3. Open **Send / smart contract**. Send once with **DoomForge OFF** (a normal transfer), then with "
        "**DoomForge ON** and watch each security step between your wallet, the contract and the recipient.\n"
        "4. Open **Risk & smart contract** to see every transaction's tier and gas, and run the **attack lab**.\n"
        "5. Open **Ethereum network** to see real mainnet signals (shown one hour late)."
    )
