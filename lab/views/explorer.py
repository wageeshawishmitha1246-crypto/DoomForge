import time

import pandas as pd
import streamlit as st
from web3 import Web3

import ui
from core import config

chain = ui.chain_or_stop()


def when(ts: int) -> str:
    return time.strftime("%d %b %H:%M:%S", time.localtime(ts))


st.title("🔎 Block explorer")
st.caption(f"Live view of **{config.NETWORK_NAME}** (chain id {chain.chain_id}). Every block and transaction here "
           "is real and read directly from the chain.")

q = st.query_params
query = st.text_input("Search by transaction hash, address or block number",
                      value=q.get("tx") or q.get("address") or q.get("block") or "")
query = query.strip()

# ------------------------------------------------------------- details
if query:
    try:
        if query.startswith("0x") and len(query) == 66:
            info = chain.transaction_details(query)
            s = info["summary"]
            st.subheader("Transaction")
            st.code(query, language=None)
            (st.success if s["Status"] == "Success" else st.error)(f"{s['Status']} · {s['Type']}")
            rows = {**s, "Time": when(s["Time"])}
            st.dataframe(pd.DataFrame({"Field": list(rows), "Value": [str(v) for v in rows.values()]}),
                         hide_index=True, width="stretch")
            if info["call"]:
                st.markdown(f"**Smart contract function:** `{info['call']['function']}`")
                st.json(info["call"]["arguments"], expanded=False)
            if info["events"]:
                st.markdown("**Events emitted by the contract**")
                for e in info["events"]:
                    st.json(e, expanded=True)
        elif Web3.is_address(query):
            addr = Web3.to_checksum_address(query)
            st.subheader("Address")
            st.code(addr, language=None)
            is_contract = len(chain.w3.eth.get_code(addr)) > 0
            c1, c2, c3 = st.columns(3)
            c1.metric("Balance", f"{chain.balance_eth(addr):.4f} ETH")
            c2.metric("Transactions sent", chain.w3.eth.get_transaction_count(addr))
            c3.metric("Type", "Smart contract" if is_contract else "Wallet")
            txs = chain.recent_transactions(address=addr, limit=30)
            if txs:
                st.dataframe(pd.DataFrame([{**t, "time": when(t["time"]), "open": chain.tx_link(t["hash"])}
                                           for t in txs]), hide_index=True, width="stretch",
                             column_config={"open": st.column_config.LinkColumn("open", display_text="view")})
        elif query.isdigit():
            b = chain.w3.eth.get_block(int(query), full_transactions=True)
            st.subheader(f"Block {int(query):,}")
            st.markdown(f"Mined {when(b.timestamp)} · {len(b.transactions)} transactions · gas used {b.gasUsed:,}")
            for tx in b.transactions:
                h = "0x" + bytes(tx["hash"]).hex()
                st.markdown(f"- [{ui.short(h, 10)}]({chain.tx_link(h)}) · {chain.describe_call(tx)}")
        else:
            st.warning("Enter a transaction hash (0x + 64 characters), an address (0x + 40) or a block number.")
    except Exception as exc:  # noqa: BLE001
        st.error(f"Not found on this chain: {exc}")
    st.divider()

# -------------------------------------------------------------- latest
c1, c2 = st.columns(2)
with c1:
    st.subheader("Latest blocks")
    blocks = chain.latest_blocks(10)
    st.dataframe(pd.DataFrame([{"Block": b["number"], "Mined": when(b["time"]), "Txs": b["txs"],
                                "Gas used": b["gas_used"]} for b in blocks]), hide_index=True, width="stretch")
with c2:
    st.subheader("Latest transactions")
    txs = chain.recent_transactions(limit=10)
    if txs:
        st.dataframe(pd.DataFrame([{"Type": t["kind"], "From": ui.short(t["from"]), "ETH": t["value_eth"],
                                    "Block": t["block"], "open": chain.tx_link(t["hash"])} for t in txs]),
                     hide_index=True, width="stretch",
                     column_config={"open": st.column_config.LinkColumn("open", display_text="view")})
    else:
        st.caption("No transactions yet.")
if st.button("Refresh", width="stretch"):
    st.rerun()
