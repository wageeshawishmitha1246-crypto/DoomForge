"""The log-in screen: nobody sees the platform until they create or choose a wallet."""

import streamlit as st

from core import config, risk, store
from core.chain import new_private_key


def _create_tab() -> None:
    name = st.text_input("Your name (shown on your transactions)", max_chars=40, placeholder="e.g. Examiner 1")
    kind = st.radio("Wallet type", ["Existing wallet (real Etherscan history)", "New wallet (no history)"])
    tier_choice = None
    if kind.startswith("Existing"):
        counts = risk.tier_counts()
        pick = st.radio(
            "Which history?",
            ["Random", f"Low risk ({counts.get(0, 0)} wallets)", f"Medium risk ({counts.get(1, 0)} wallet"
             f"{'s' if counts.get(1, 0) != 1 else ''})", f"High risk ({counts.get(2, 0)} wallets)"],
            horizontal=True,
        )
        tier_choice = {"R": None, "L": 0, "M": 1, "H": 2}[pick[0]]
    else:
        st.info("A new wallet has no transactions, so the model has no features to score. "
                "The platform treats it as **Unknown → Medium tier** (a safety rule, not a model prediction).")

    pin = st.text_input("Choose a PIN (4 to 8 digits). You need it to open this wallet again.",
                        type="password", max_chars=8, key="new_pin")
    pin2 = st.text_input("Repeat the PIN", type="password", max_chars=8, key="new_pin2")
    code = st.text_input("Access code (from the user guide)", type="password") if config.ACCESS_CODE else ""

    if st.button("Create my wallet", type="primary", width="stretch"):
        if config.ACCESS_CODE and code.strip() != config.ACCESS_CODE:
            st.error("Wrong access code.")
        elif not name.strip():
            st.error("Please enter a name.")
        elif store.check_pin_format(pin):
            st.error(store.check_pin_format(pin))
        elif pin != pin2:
            st.error("The two PINs are not the same.")
        elif store.get_account_by_name(name.strip()):
            st.error("That name is taken. Use another name, or open the 'I already have one' tab.")
        else:
            address, key = new_private_key()
            if kind.startswith("Existing"):
                row = risk.pick_wallet(tier_choice)
                acc_id = store.create_account(name.strip(), address, key, "history", row["wallet_address"],
                                              float(row["risk_score"]), int(row["tier"]), pin)
            else:
                acc_id = store.create_account(name.strip(), address, key, "new", None, None,
                                              config.NEW_WALLET_TIER, pin)
            store.start_session(acc_id)
            st.session_state["account_id"] = acc_id
            st.rerun()


def _existing_tab() -> None:
    accounts = store.list_accounts()
    if not accounts:
        st.caption("No wallets yet.")
        return
    choice = st.selectbox("Choose your wallet", [a["name"] for a in accounts])
    pin = st.text_input("Your PIN", type="password", max_chars=8, key="open_pin")
    if st.button("Continue", width="stretch"):
        acc = store.get_account_by_name(choice)
        ok, msg = store.verify_pin(acc["id"], pin)
        if ok:
            store.start_session(acc["id"])
            st.session_state["account_id"] = acc["id"]
            st.rerun()
        else:
            st.error(msg)


def render() -> None:
    left, right = st.columns([1.05, 1], gap="large")
    with left:
        st.image("assets/logo.svg", width=230)
        st.markdown(
            "<div class='df-hero'>Security that adapts<br>to <span>every wallet</span>.</div>"
            "<p class='df-sub'>An AI model scores the sender wallet, and the score chooses the cryptography "
            "for the transaction on Ethereum.</p>",
            unsafe_allow_html=True,
        )
        for icon, head, text in (
            ("psychology", "AI risk score", "A Random Forest scores the wallet's real Etherscan history."),
            ("encrypted", "Three protection tiers", "ECDSA, ECDSA + commitment hash, or post-quantum signatures."),
            ("deployed_code", "Checked on-chain", f"A smart contract on {config.NETWORK_NAME} verifies each one."),
        ):
            st.markdown(
                f"<div class='df-feat'><span class='material-symbols-rounded'>{icon}</span>"
                f"<div><b>{head}</b><br><small>{text}</small></div></div>",
                unsafe_allow_html=True,
            )
    with right:
        with st.container(border=True):
            st.subheader("Log in with a wallet")
            st.caption("Create a wallet to enter the platform. It takes a few seconds and uses test ETH only.")
            tab_new, tab_back = st.tabs(["Create a wallet", "I already have one"])
            with tab_new:
                _create_tab()
            with tab_back:
                _existing_tab()
