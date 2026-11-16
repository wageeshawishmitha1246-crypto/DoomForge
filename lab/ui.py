"""Shared Streamlit helpers for DoomForge Lab."""

from __future__ import annotations

import streamlit as st

from core import config, store
from core.chain import Chain

TIER_COLOURS = {0: "#2563A8", 1: "#C98A16", 2: "#B4452F"}

# Look only (dark dashboard with cards and a green highlight card); colours come from .streamlit/config.toml.
_STYLE = """
<style>
@import url('https://fonts.googleapis.com/css2?family=Poppins:wght@400;500;600;700&display=swap');
@import url('https://fonts.googleapis.com/css2?family=Material+Symbols+Rounded:opsz,wght,FILL,GRAD@24,400,1,0');
html, body, .stApp, [data-testid="stSidebar"], button, input, textarea {
    font-family: 'Poppins', 'Segoe UI', sans-serif;
}
[data-testid="stMain"] .block-container { padding-top: 2.5rem; max-width: 1250px; }
h1 { font-weight: 700; letter-spacing: -0.5px; }
h2, h3 { font-weight: 600; }

/* cards */
[data-testid="stMetric"] {
    background: #1F2229; border: 1px solid #2B2F38; border-radius: 16px; padding: 18px 22px;
}
[data-testid="stMetricLabel"] { opacity: 0.75; }
[data-testid="stMetricValue"] { font-weight: 600; font-size: 1.7rem; }
[data-testid="stMetricValue"] > div { white-space: normal; overflow: visible; }
/* the first card of a row is the highlight card */
[data-testid="stColumn"]:first-child [data-testid="stMetric"] {
    background: linear-gradient(135deg, #00C389 0%, #00996B 100%); border: none;
    box-shadow: 0 10px 30px rgba(0, 179, 122, 0.25);
}
[data-testid="stColumn"]:first-child [data-testid="stMetric"] * { color: #FFFFFF; }
[data-testid="stExpander"] details, [data-testid="stDataFrame"], [data-testid="stTable"] {
    background: #1F2229; border-radius: 16px; overflow: hidden;
}
[data-testid="stAlert"] { border-radius: 14px; }

/* buttons */
.stButton > button {
    border-radius: 10px; font-weight: 600; letter-spacing: 0.4px; padding: 0.6rem 1.2rem;
    transition: transform 0.08s ease, box-shadow 0.15s ease;
}
.stButton > button[kind="primary"] { box-shadow: 0 8px 22px rgba(0, 179, 122, 0.28); }
.stButton > button:hover { transform: translateY(-1px); }

[data-testid="stVerticalBlockBorderWrapper"] { border-radius: 18px; }
.material-symbols-rounded { font-family: 'Material Symbols Rounded'; font-size: 24px; line-height: 1; }

/* sidebar */
[data-testid="stSidebar"] { border-right: 1px solid #23262E; }
[data-testid="stSidebarNav"] a { border-radius: 12px; margin: 3px 0; padding: 0.55rem 0.8rem; }
[data-testid="stSidebarNav"] a span { font-weight: 500; }
[data-testid="stSidebarNav"] a:hover { background: rgba(255, 255, 255, 0.05); }
[data-testid="stSidebarNav"] a[aria-current="page"] {
    background: linear-gradient(90deg, rgba(0, 195, 137, 0.22), rgba(0, 195, 137, 0.04));
    box-shadow: inset 3px 0 0 #00C389;
}
[data-testid="stSidebarNav"] a[aria-current="page"] * { color: #00D395; }
[data-testid="stNavSectionHeader"] { text-transform: uppercase; letter-spacing: 1.4px; font-size: 0.68rem; opacity: 0.55; }

/* sidebar account card */
.df-acc { background: #1A1D23; border: 1px solid #2B2F38; border-radius: 16px; padding: 14px; margin: 6px 0 10px; }
.df-acc-top { display: flex; align-items: center; gap: 10px; }
.df-avatar { width: 38px; height: 38px; border-radius: 50%; flex: none; }
.df-acc-name { font-weight: 600; line-height: 1.2; }
.df-acc-addr { font-family: Consolas, monospace; font-size: 0.75rem; opacity: 0.6; }
.df-acc-bal { font-size: 1.25rem; font-weight: 600; margin-top: 12px; }
.df-acc-bal small { font-size: 0.75rem; opacity: 0.6; font-weight: 500; }
.df-pill { display: inline-block; border-radius: 999px; padding: 2px 10px; font-size: 0.72rem; font-weight: 600; margin-top: 8px; }
.df-net { display: flex; align-items: center; gap: 8px; font-size: 0.75rem; opacity: 0.8; margin-top: 10px; }
.df-dot { width: 8px; height: 8px; border-radius: 50%; background: #00D395; box-shadow: 0 0 0 0 rgba(0, 211, 149, 0.7);
          animation: df-pulse 1.8s infinite; flex: none; display: inline-block; }
@keyframes df-pulse { 70% { box-shadow: 0 0 0 8px rgba(0, 211, 149, 0); } 100% { box-shadow: 0 0 0 0 rgba(0, 211, 149, 0); } }

/* live strip on the network page */
.df-live { display: flex; align-items: center; gap: 10px; background: #1A1D23; border: 1px solid #2B2F38;
           border-radius: 12px; padding: 10px 16px; font-size: 0.85rem; margin-bottom: 14px; flex-wrap: wrap; }
.df-live b { color: #00D395; letter-spacing: 1px; }

/* log-in screen */
.df-hero { font-size: 2.7rem; font-weight: 700; line-height: 1.15; letter-spacing: -1px; margin: 26px 0 12px; }
.df-hero span { color: #00D395; }
.df-sub { opacity: 0.7; font-size: 1.02rem; max-width: 30rem; margin-bottom: 22px; }
.df-feat { display: flex; align-items: center; gap: 14px; margin: 14px 0; }
.df-feat .material-symbols-rounded { background: rgba(0, 195, 137, 0.14); color: #00D395; border-radius: 12px; padding: 10px; }
.df-feat small { opacity: 0.65; }
</style>
"""

_LOGGED_OUT_STYLE = """
<style>
[data-testid="stSidebar"], [data-testid="stSidebarCollapsedControl"], [data-testid="stExpandSidebarButton"] { display: none; }
[data-testid="stMain"] .block-container { max-width: 1100px; padding-top: 4.5rem; }
</style>
"""

_PILL = {0: ("#2563A8", "Low risk"), 1: ("#C98A16", "Medium risk"), 2: ("#B4452F", "High risk")}


def apply_style(logged_in: bool = True) -> None:
    st.markdown(_STYLE + ("" if logged_in else _LOGGED_OUT_STYLE), unsafe_allow_html=True)


@st.cache_resource(show_spinner="Connecting to the blockchain…")
def get_chain() -> Chain:
    return Chain()


def chain_or_stop() -> Chain:
    try:
        return get_chain()
    except Exception as exc:  # noqa: BLE001
        st.error(f"Blockchain connection problem: {exc}")
        st.stop()


def current_account():
    """The logged-in wallet. It is also kept in the page link (?w=address) so a refresh keeps you logged in."""
    acc_id = st.session_state.get("account_id")
    if acc_id is None and st.query_params.get("w"):
        for a in store.list_accounts():
            if a["address"].lower() == st.query_params["w"].lower():
                st.session_state["account_id"] = acc_id = a["id"]
                break
    acc = store.get_account(acc_id) if acc_id else None
    if acc is not None and st.query_params.get("w") != acc["address"]:
        st.query_params["w"] = acc["address"]
    return acc


def require_account():
    acc = current_account()
    if acc is None:
        st.info("Please start on **Start here** and create or choose a wallet first.")
        st.page_link("views/home.py", label="Go to Start here", icon="➡️")
        st.stop()
    return acc


def tier_badge(tier: int | None, unknown: bool = False) -> str:
    if tier is None:
        return "—"
    name = config.TIER_NAMES[tier] + (" (Unknown: new wallet)" if unknown else "")
    return f":{['blue', 'orange', 'red'][tier]}-background[**{name} risk**]"


def short(addr: str, n: int = 6) -> str:
    return f"{addr[:n + 2]}…{addr[-4:]}" if addr and len(addr) > 2 * n else addr


def sidebar_account() -> None:
    acc = current_account()
    if not acc:
        return
    with st.sidebar:
        try:
            balance = f"{get_chain().balance_eth(acc['address']):.4f}"
        except Exception:  # noqa: BLE001
            balance = "—"
        colour, label = _PILL[acc["tier"]]
        if acc["kind"] == "new":
            label = "Medium risk (Unknown)"
        a = acc["address"]
        name = acc["name"].replace("<", "&lt;").replace(">", "&gt;")
        st.markdown(
            f"<div class='df-acc'><div class='df-acc-top'>"
            f"<div class='df-avatar' style='background:linear-gradient(135deg,#{a[2:8]},#{a[-6:]})'></div>"
            f"<div><div class='df-acc-name'>{name}</div><div class='df-acc-addr'>{short(a)}</div></div></div>"
            f"<div class='df-acc-bal'>{balance} <small>ETH</small></div>"
            f"<span class='df-pill' style='background:{colour}33;color:#fff;border:1px solid {colour}'>{label}</span>"
            f"<div class='df-net'><span class='df-dot'></span>{config.NETWORK_NAME}</div></div>",
            unsafe_allow_html=True,
        )
        if st.button("Log out", icon=":material/logout:", width="stretch"):
            st.session_state.pop("account_id", None)
            st.query_params.clear()
            st.rerun()
