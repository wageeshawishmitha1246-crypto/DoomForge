import pandas as pd
import streamlit as st

import ui
from core import config, network, risk, store

acc = ui.require_account()
chain = ui.chain_or_stop()

st.title("👛 My wallet")

c1, c2 = st.columns(2)
with c1:
    st.markdown(f"**{config.NETWORK_NAME} address**  \n[`{acc['address']}`]({chain.address_link(acc['address'])})")
    bal = chain.balance_eth(acc["address"])
    st.metric("Balance", f"{bal:.5f} ETH")
with c2:
    left = config.MAX_TOPUPS_PER_ACCOUNT - acc["topups"]
    st.markdown(f"**Top up** gives {config.TOPUP_ETH} test ETH from the platform faucet ({left} left).")
    if st.button(f"Top up {config.TOPUP_ETH} ETH", type="primary", disabled=left <= 0, width="stretch"):
        with st.spinner(f"Sending test ETH on {config.NETWORK_NAME}… (a few seconds)"):
            try:
                r = chain.top_up(acc["address"], config.TOPUP_ETH)
                store.add_topup(acc["id"])
                h = "0x" + bytes(r.transactionHash).hex()
                st.success(f"Topped up. [View the transaction]({chain.tx_link(h)})")
                st.rerun()
            except Exception as exc:  # noqa: BLE001
                st.error(f"Top-up failed: {exc}")

st.divider()
st.subheader("Risk of this wallet")

if acc["kind"] == "new":
    st.markdown(ui.tier_badge(acc["tier"], unknown=True))
    st.markdown(
        "This wallet was just created and has **no transaction history**, so none of the 17 features can be "
        "calculated and the model cannot score it. The platform therefore treats it as **Unknown** and gives it "
        "the **Medium** tier: ECDSA plus a commitment hash. Fresh wallets are common in scams, so starting them "
        "at Low would be unsafe."
    )
else:
    row = risk.wallet_row(acc["history_wallet"])
    score = float(acc["risk_score"])
    trees = round(score * 200)
    st.markdown(
        f"This demo wallet acts for the real Ethereum wallet "
        f"[`{ui.short(acc['history_wallet'], 8)}`](https://etherscan.io/address/{acc['history_wallet']}). "
        "Its real history was collected from Etherscan, turned into 17 features, and scored by the Random Forest."
    )
    m1, m2, m3 = st.columns(3)
    m1.metric("Risk score R(w)", f"{score:.3f}")
    m2.metric("Trees voting “risky”", f"{trees} / 200")
    m3.metric("Tier", config.TIER_NAMES[acc["tier"]])
    st.markdown(ui.tier_badge(acc["tier"]) + f" → protection: **{config.SCHEME_NAMES[acc['tier']]}**")
    st.progress(min(max(score, 0.0), 1.0), text="0 ← Low · 0.30 · Medium · 0.70 · High → 1")

    with st.expander("The 17 features the model used"):
        st.dataframe(risk.feature_table(row), hide_index=True, width="stretch")
        st.caption("† = also used by the labelling rules (label leakage, discussed in the thesis).")

    samples = network.delayed_samples(window_hours=6)
    gp = row.get("sent_avg_gas_price")
    if samples and pd.notna(gp):
        latest = samples[-1]
        st.markdown(
            f"**Gas price in context:** this wallet paid on average **{gp / 1e9:,.2f} gwei** in its history. "
            f"The Ethereum network's suggested price an hour ago was **{latest['propose_gwei']:.3f} gwei**. "
            "(The model uses the wallet's own gas price only; network signals are shown for context.)"
        )
