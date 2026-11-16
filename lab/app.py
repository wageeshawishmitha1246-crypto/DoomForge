"""DoomForge Lab: run with  streamlit run app.py  (from the lab folder)."""

import streamlit as st

st.set_page_config(page_title="DoomForge Lab", page_icon="assets/icon.svg", layout="wide")

import ui  # noqa: E402  (after set_page_config)

acc = ui.current_account()
home = st.Page("views/home.py", title="Dashboard" if acc else "Log in", icon=":material/space_dashboard:", default=True)
explorer = st.Page("views/explorer.py", title="Block explorer", icon=":material/travel_explore:", url_path="explorer")
pages = st.navigation(
    {
        "Wallet": [
            home,
            st.Page("views/wallet.py", title="My wallet", icon=":material/account_balance_wallet:"),
            st.Page("views/send.py", title="Send / smart contract", icon=":material/send:"),
        ],
        "Security": [
            st.Page("views/contract.py", title="Risk & smart contract", icon=":material/verified_user:"),
        ],
        "Network": [
            st.Page("views/network.py", title="Ethereum network", icon=":material/monitoring:"),
            explorer,
        ],
    },
    position="sidebar" if acc else "hidden",
)
ui.apply_style(logged_in=acc is not None)
if acc is None and pages.url_path not in (home.url_path, explorer.url_path):
    st.switch_page(home)  # not logged in: every page except the block explorer goes to the log-in screen
if acc is not None:
    st.logo("assets/logo.svg", icon_image="assets/icon.svg", size="large")
    ui.sidebar_account()
pages.run()
