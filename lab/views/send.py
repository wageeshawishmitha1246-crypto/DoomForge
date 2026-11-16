import time

import streamlit as st
from web3 import Web3

import ui
from core import config, store

acc = ui.require_account()
chain = ui.chain_or_stop()

st.title("📤 Send / smart contract")

balance = chain.balance_eth(acc["address"])
st.caption(f"From **{acc['name']}** · `{ui.short(acc['address'])}` · balance **{balance:.5f} ETH**")
if balance < 0.0005:
    st.warning("Your balance is too low. Go to **My wallet** and press **Top up** first.")

# ---------------------------------------------------------------- inputs
others = [a for a in store.list_accounts() if a["id"] != acc["id"]]
way = st.radio("Send to", ["Another wallet on this platform", "Paste an address"], horizontal=True)
recipient = None
if way.startswith("Another"):
    if others:
        pick = st.selectbox("Recipient", [f"{a['name']} · {ui.short(a['address'])}" for a in others])
        recipient = others[[f"{a['name']} · {ui.short(a['address'])}" for a in others].index(pick)]["address"]
    else:
        st.caption("No other wallets yet. Paste an address, or create a second wallet on Start here.")
else:
    pasted = st.text_input("Recipient address (0x…)")
    if pasted and Web3.is_address(pasted.strip()):
        recipient = Web3.to_checksum_address(pasted.strip())
    elif pasted:
        st.error("That is not a valid Ethereum address.")

amount = st.number_input("Amount (ETH)", min_value=0.0001, max_value=1.0, value=0.0002, step=0.0005, format="%.4f")
protect = st.toggle("🛡️ DoomForge protection", value=True)

tier = acc["tier"]
if protect:
    st.markdown(
        f"**Plan:** sender risk → {ui.tier_badge(tier, acc['kind'] == 'new')} → **{config.SCHEME_NAMES[tier]}** "
        "→ smart contract checks → recipient receives the ETH."
    )
    st.caption("The tier comes from the sender wallet's history only. Changing the amount does not change it.")
else:
    st.markdown("**Plan:** normal Ethereum transfer, one ECDSA signature, no risk check (how wallets work today).")

# ------------------------------------------------------------------ send
if st.button("Send transaction", type="primary", width="stretch", disabled=recipient is None):
    label = "DoomForge" if protect else "Normal transfer"
    with st.status(f"{label}: working on {config.NETWORK_NAME}… (waiting for the next block)",
                   expanded=True) as status:
        if protect:
            result = chain.send_doomforge(acc["private_key"], recipient, amount, tier)
        else:
            result = chain.send_plain(acc["private_key"], recipient, amount)
        for i, s in enumerate(result.steps, 1):
            st.markdown(f"**{i}. {s.title}**  \n{s.detail}")
        status.update(label=("✅ Done" if result.ok else "❌ Not completed") + f" in {result.seconds:.1f} s",
                      state="complete" if result.ok else "error")

    store.record_transaction(acc["id"], acc["address"], recipient, amount, result.mode, result.tier,
                             acc["risk_score"], result.scheme, result.gas_used, result.tx_hash,
                             1 if result.ok else 0, {"steps": [s.__dict__ for s in result.steps],
                                                     "error": result.error, "tx_id": result.tx_id})
    if result.ok:
        m1, m2, m3 = st.columns(3)
        m1.metric("Protection", result.scheme)
        m2.metric("Gas used", f"{result.gas_used:,}")
        m3.metric("Block", f"{result.block:,}")
        st.markdown(f"🔗 [View this transaction on the block explorer]({chain.tx_link(result.tx_hash)})")
    else:
        st.error(result.error or "The transaction failed.")

# ------------------------------------------------------------- history
mine = store.list_transactions(acc["id"])
if mine:
    st.divider()
    st.subheader("Your transactions")
    st.dataframe(
        [{
            "When": time.strftime("%H:%M:%S", time.localtime(t["created_at"])),
            "DoomForge": "ON" if t["mode"] == "doomforge" else "OFF",
            "Protection": t["scheme"],
            "Amount (ETH)": t["value_eth"],
            "Gas used": t["gas_used"],
            "Result": "OK" if t["status"] else "Failed",
            "Explorer": chain.tx_link(t["tx_hash"]) if t["tx_hash"] else "",
        } for t in mine],
        hide_index=True, width="stretch",
        column_config={"Explorer": st.column_config.LinkColumn("Explorer", display_text="open")},
    )
