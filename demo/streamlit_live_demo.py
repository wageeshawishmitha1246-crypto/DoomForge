"""Live Streamlit demo for adaptive blockchain cryptography security."""

from __future__ import annotations

import numpy as np
import pandas as pd
import streamlit as st
from xgboost import XGBClassifier
from sklearn.model_selection import train_test_split

from demo.adaptive_cryptography_security_simulation import (
    MODEL_FEATURES,
    NormalizationReference,
    build_normalization_reference,
    compute_demo_risk_score,
    recompute_derived_features,
    select_security_mechanism,
    generate_synthetic_blockchain_data,
)


@st.cache_resource
def train_live_model(seed: int = 42):
    df = generate_synthetic_blockchain_data(n_transactions=10_000, malicious_ratio=0.05, seed=seed)
    norm_columns = [
        "pagerank_score",
        "betweenness_centrality",
        "clustering_coefficient",
        "transaction_frequency",
        "unique_counterparties",
        "time_since_last_transaction",
    ]
    norm_ref: NormalizationReference = build_normalization_reference(df, norm_columns)
    df = recompute_derived_features(df, normalization_reference=norm_ref)

    X = df[MODEL_FEATURES]
    y = df["fraud_label"]

    X_train, X_test, y_train, y_test = train_test_split(
        X,
        y,
        test_size=0.20,
        random_state=seed,
        stratify=y,
    )

    scale_pos = (y_train == 0).sum() / max((y_train == 1).sum(), 1)
    model = XGBClassifier(
        n_estimators=350,
        max_depth=6,
        learning_rate=0.05,
        subsample=0.9,
        colsample_bytree=0.9,
        objective="binary:logistic",
        eval_metric="logloss",
        random_state=seed,
        n_jobs=-1,
        scale_pos_weight=scale_pos,
    )
    model.fit(X_train, y_train)

    baseline = df[MODEL_FEATURES].median()
    return model, baseline, norm_ref


def build_live_row(
    baseline: pd.Series,
    transaction_value: float,
    gas_price: float,
    transaction_frequency: float,
    unique_counterparties: float,
    pagerank_score: float,
) -> pd.DataFrame:
    row = baseline.copy()
    row["transaction_value"] = transaction_value
    row["gas_price"] = gas_price
    row["transaction_frequency"] = transaction_frequency
    row["unique_counterparties"] = unique_counterparties
    row["pagerank_score"] = pagerank_score

    # Keep correlated network dimensions coherent with pagerank movement.
    row["betweenness_centrality"] = max(0.0, pagerank_score * 1.8)
    row["clustering_coefficient"] = min(1.0, 0.15 + pagerank_score * 8.0)

    return pd.DataFrame([row])


def main() -> None:
    st.set_page_config(page_title="Adaptive Cryptography Live Demo", layout="wide")
    st.title("Adaptive Cryptography Security System - Live Demonstration")
    st.caption("Adjust transaction and network risk features to see real-time cryptography policy adaptation.")

    with st.spinner("Training model and preparing synthetic blockchain environment..."):
        model, baseline, norm_ref = train_live_model(seed=42)

    st.subheader("Risk Policy Mode")
    risk_mode = st.radio(
        "Select adaptation mode",
        options=["3-level", "4-level"],
        index=0,
        horizontal=True,
        help="3-level = LOW/MEDIUM/HIGH, 4-level adds CRITICAL for highest-risk transactions.",
    )

    st.subheader("Feature Controls")
    col1, col2, col3 = st.columns(3)

    with col1:
        transaction_value = st.slider("transaction_value", min_value=1.0, max_value=20_000.0, value=float(baseline["transaction_value"]))
        gas_price = st.slider("gas_price", min_value=1.0, max_value=2_000.0, value=float(baseline["gas_price"]))

    with col2:
        transaction_frequency = st.slider("transaction_frequency", min_value=0.01, max_value=120.0, value=float(baseline["transaction_frequency"]))
        unique_counterparties = st.slider("unique_counterparties", min_value=1.0, max_value=500.0, value=float(baseline["unique_counterparties"]))

    with col3:
        pagerank_score = st.slider("pagerank_score", min_value=0.0, max_value=0.08, value=float(baseline["pagerank_score"]))

    scenario = build_live_row(
        baseline,
        transaction_value=transaction_value,
        gas_price=gas_price,
        transaction_frequency=transaction_frequency,
        unique_counterparties=unique_counterparties,
        pagerank_score=pagerank_score,
    )
    scenario = recompute_derived_features(scenario, normalization_reference=norm_ref)

    model_signal = float(np.clip(model.predict_proba(scenario[MODEL_FEATURES])[:, 1][0], 0.0, 1.0))
    risk_score = float(compute_demo_risk_score(scenario).iloc[0])
    mechanism = select_security_mechanism(risk_score, risk_mode=risk_mode)

    st.subheader("Live Output")
    m1, m2, m3, m4 = st.columns(4)
    m1.metric("risk_score", f"{risk_score:.4f}")
    m2.metric("security_level", mechanism["security_level"])
    m3.metric("cryptography", mechanism["cryptography"])
    m4.metric("model_signal", f"{model_signal:.4f}")

    st.write(f"Security policy: {mechanism['policy']}")
    st.caption("The live security level uses a smoothed feature-weighted demo risk score so LOW, MEDIUM, and HIGH are reachable with the sliders. The raw ML model probability is shown separately as model_signal.")

    st.progress(risk_score)

    st.subheader("Current Scenario Snapshot")
    st.dataframe(scenario[MODEL_FEATURES].T.rename(columns={0: "value"}), use_container_width=True)


if __name__ == "__main__":
    main()
