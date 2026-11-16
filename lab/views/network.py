import time

import pandas as pd
import streamlit as st

from core import config, network, store

GREEN, PURPLE, AMBER, BLUE = "#00C389", "#8B7CF6", "#F0B90B", "#4C9AFF"

st.title("Ethereum network (mainnet)")
delay_min = config.NETWORK_DELAY_SECONDS // 60
st.caption(f"Real data collected from Etherscan every {config.COLLECT_EVERY_SECONDS} s and shown **{delay_min} minutes "
           "late**, so this page always shows the network as it was an hour ago. Nothing here is simulated.")

hours = st.select_slider("Time window", options=[1, 3, 6, 12, 24], value=6, format_func=lambda h: f"{h} h")


def _ago(seconds: float) -> str:
    return f"{int(seconds)} s ago" if seconds < 120 else f"{int(seconds // 60)} min ago"


@st.fragment(run_every=config.COLLECT_EVERY_SECONDS)
def live_feed() -> None:
    """Redraws itself every time the collector has had time to save a new sample."""
    rows = network.delayed_samples(window_hours=hours)
    count, first_ts, last_ts = store.network_sample_count()
    now = time.time()

    if count == 0:
        st.warning("No samples yet. Start the collector (`python collector.py`) and leave it running.")
        return
    running = now - last_ts < 3 * config.COLLECT_EVERY_SECONDS
    status = (f"<span class='df-dot'></span><b>LIVE</b> collector running · last sample saved {_ago(now - last_ts)}"
              if running else f"⚠️ <b style='color:#F0B90B'>PAUSED</b> collector stopped · last sample {_ago(now - last_ts)}")
    st.markdown(f"<div class='df-live'>{status} · {count:,} samples stored · shown {delay_min} min late · "
                f"page updates every {config.COLLECT_EVERY_SECONDS} s</div>", unsafe_allow_html=True)

    if not rows:
        ready = first_ts + config.NETWORK_DELAY_SECONDS
        mins = max(0, int((ready - now) / 60))
        st.info(f"The collector has {count} samples, but they are less than {delay_min} minutes old. "
                f"The first one appears here in about {mins} minutes.")
        st.progress(min(1.0, max(0.0, (now - first_ts) / config.NETWORK_DELAY_SECONDS)),
                    text=f"Waiting for the first sample to become {delay_min} minutes old")
        return

    df = pd.DataFrame([dict(r) for r in rows])
    df["time"] = pd.to_datetime(df["ts"], unit="s").dt.tz_localize("UTC").dt.tz_convert("Asia/Colombo")
    df = df.set_index("time")
    last = df.iloc[-1]
    prev = df.iloc[-2] if len(df) > 1 else None

    m1, m2, m3, m4 = st.columns(4)
    m1.metric("Block", f"{int(last['block_number']):,}")
    m2.metric("Transactions in block", int(last["tx_count"]),
              delta=None if prev is None else int(last["tx_count"] - prev["tx_count"]), delta_color="off")
    m3.metric("Block fullness", f"{last['gas_used_ratio']:.0%}",
              delta=None if prev is None else f"{(last['gas_used_ratio'] - prev['gas_used_ratio']) * 100:+.0f} pts",
              delta_color="off")
    m4.metric("Suggested gas price", f"{last['propose_gwei']:.3f} gwei",
              delta=None if prev is None else f"{last['propose_gwei'] - prev['propose_gwei']:+.3f}", delta_color="off")
    st.caption(f"As of {df.index[-1]:%Y-%m-%d %H:%M:%S} (Sri Lanka time), {len(df)} samples in this window.")

    left, right = st.columns([1.2, 1], gap="medium")
    with left:
        st.subheader("Transactions per block")
        st.area_chart(df[["tx_count"]].rename(columns={"tx_count": "transactions per block"}), color=GREEN, height=330)
    with right:
        st.subheader("Latest blocks")
        feed = df.tail(12).iloc[::-1]
        st.dataframe(
            pd.DataFrame({
                "Time": feed.index.strftime("%H:%M:%S"),
                "Block": feed["block_number"].astype(int).map("{:,}".format),
                "Txs": feed["tx_count"].astype(int),
                "Full": (feed["gas_used_ratio"] * 100).round(0),
                "Base fee": feed["base_fee_gwei"].round(3),
            }),
            hide_index=True, width="stretch", height=330,
            column_config={"Full": st.column_config.ProgressColumn("Full", format="%d%%", min_value=0, max_value=100),
                           "Base fee": st.column_config.NumberColumn("Base fee (gwei)", format="%.3f")},
        )

    c1, c2 = st.columns(2, gap="medium")
    with c1:
        st.subheader("How full blocks are (%)")
        st.area_chart((df[["gas_used_ratio"]] * 100).rename(columns={"gas_used_ratio": "gas used / gas limit (%)"}),
                      color=PURPLE, height=260)
    with c2:
        st.subheader("Time between blocks (s)")
        st.line_chart(df[["block_time_s"]].rename(columns={"block_time_s": "seconds"}), color=BLUE, height=260)

    st.subheader("Gas price (gwei)")
    st.line_chart(df[["safe_gwei", "propose_gwei", "fast_gwei", "base_fee_gwei"]].rename(columns={
        "safe_gwei": "safe", "propose_gwei": "suggested", "fast_gwei": "fast", "base_fee_gwei": "base fee"}),
        color=[BLUE, AMBER, GREEN, PURPLE], height=300)


live_feed()

with st.expander("How this relates to DoomForge"):
    st.markdown(
        "DoomForge's risk score uses the **sender wallet's own behaviour** (17 features), not the network's "
        "traffic. One feature, the wallet's average gas price, can be compared with the network gas price shown "
        "here (see **My wallet**). Using network signals such as congestion as extra features is future work."
    )
