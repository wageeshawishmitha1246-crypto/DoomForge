"""Adaptive Cryptography Security System simulation for blockchain transactions.

This script demonstrates:
1) Synthetic blockchain data generation
2) Feature engineering for behavior and network risk
3) ML-based fraud/risk modeling with RandomForest and XGBoost
4) Continuous risk scoring and adaptive cryptographic controls
5) Attack scenario simulation
6) Visualization and network analysis
7) Interactive security adaptation demo with sliders
8) Performance trade-off analysis across cryptography choices
"""

from __future__ import annotations

import argparse
from dataclasses import dataclass
from pathlib import Path
from typing import Dict, List, Tuple

import matplotlib.pyplot as plt
import networkx as nx
import numpy as np
import pandas as pd
import seaborn as sns
from matplotlib.widgets import Slider
from sklearn.ensemble import RandomForestClassifier
from sklearn.metrics import (
    accuracy_score,
    f1_score,
    precision_score,
    recall_score,
    roc_auc_score,
)
from sklearn.model_selection import train_test_split

try:
    from xgboost import XGBClassifier
except Exception as exc:  # pragma: no cover
    raise ImportError(
        "xgboost is required. Install it with: pip install xgboost"
    ) from exc


sns.set_theme(style="whitegrid")


TRANSACTION_FEATURES = [
    "transaction_value",
    "gas_price",
    "gas_used",
    "transaction_fee",
    "timestamp_unix",
    "contract_interaction",
]

BEHAVIORAL_FEATURES = [
    "sender_transaction_count",
    "avg_transaction_value",
    "transaction_frequency",
    "unique_counterparties",
    "time_since_last_transaction",
]

NETWORK_FEATURES = [
    "in_degree",
    "out_degree",
    "clustering_coefficient",
    "pagerank_score",
    "betweenness_centrality",
]

DERIVED_FEATURES = [
    "fee_value_ratio",
    "transaction_velocity",
    "network_risk_score",
    "behavior_risk_score",
]

MODEL_FEATURES = TRANSACTION_FEATURES + BEHAVIORAL_FEATURES + NETWORK_FEATURES + DERIVED_FEATURES


@dataclass
class NormalizationReference:
    mins: Dict[str, float]
    maxs: Dict[str, float]


def minmax_with_reference(series: pd.Series, min_v: float, max_v: float) -> pd.Series:
    denom = max(max_v - min_v, 1e-9)
    return (series - min_v) / denom


def build_normalization_reference(df: pd.DataFrame, columns: List[str]) -> NormalizationReference:
    return NormalizationReference(
        mins={col: float(df[col].min()) for col in columns},
        maxs={col: float(df[col].max()) for col in columns},
    )


def recompute_derived_features(
    df: pd.DataFrame,
    normalization_reference: NormalizationReference | None = None,
) -> pd.DataFrame:
    """Recompute engineered features from base features.

    If no normalization reference is passed, the function uses the provided
    frame's min/max values. For inference on custom scenarios, pass the
    reference built from training data to keep scaling consistent.
    """
    out = df.copy()

    out["transaction_fee"] = out["gas_price"] * out["gas_used"]
    out["fee_value_ratio"] = out["transaction_fee"] / out["transaction_value"].clip(lower=1e-9)

    # Velocity approximates how quickly an account is transacting in a 24h window.
    out["transaction_velocity"] = out["sender_transaction_count"] / 24.0

    net_cols = ["pagerank_score", "betweenness_centrality", "clustering_coefficient"]
    beh_cols = ["transaction_frequency", "unique_counterparties", "time_since_last_transaction"]

    if normalization_reference is None:
        normalization_reference = build_normalization_reference(out, net_cols + beh_cols)

    pr_n = minmax_with_reference(
        out["pagerank_score"],
        normalization_reference.mins["pagerank_score"],
        normalization_reference.maxs["pagerank_score"],
    )
    bc_n = minmax_with_reference(
        out["betweenness_centrality"],
        normalization_reference.mins["betweenness_centrality"],
        normalization_reference.maxs["betweenness_centrality"],
    )
    cc_n = minmax_with_reference(
        out["clustering_coefficient"],
        normalization_reference.mins["clustering_coefficient"],
        normalization_reference.maxs["clustering_coefficient"],
    )

    tf_n = minmax_with_reference(
        out["transaction_frequency"],
        normalization_reference.mins["transaction_frequency"],
        normalization_reference.maxs["transaction_frequency"],
    )
    cp_n = minmax_with_reference(
        out["unique_counterparties"],
        normalization_reference.mins["unique_counterparties"],
        normalization_reference.maxs["unique_counterparties"],
    )
    tsl_n = minmax_with_reference(
        out["time_since_last_transaction"],
        normalization_reference.mins["time_since_last_transaction"],
        normalization_reference.maxs["time_since_last_transaction"],
    )

    out["network_risk_score"] = 0.45 * pr_n + 0.35 * bc_n + 0.20 * cc_n
    out["behavior_risk_score"] = 0.45 * tf_n + 0.35 * cp_n + 0.20 * (1.0 - tsl_n)

    return out


def select_security_mechanism(risk_score: float, risk_mode: str = "4-level") -> Dict[str, str]:
    if risk_mode not in {"3-level", "4-level"}:
        raise ValueError("risk_mode must be either '3-level' or '4-level'")

    if risk_score < 0.30:
        return {
            "security_level": "LOW",
            "cryptography": "Standard ECDSA",
            "policy": "Very low latency path",
        }
    if risk_score < 0.60:
        return {
            "security_level": "MEDIUM",
            "cryptography": "Post-Quantum Signature (CRYSTALS-Dilithium)",
            "policy": "2FA + post-quantum signature enforcement",
        }

    # In 3-level mode, anything >= 0.60 maps to HIGH.
    if risk_mode == "3-level":
        return {
            "security_level": "HIGH",
            "cryptography": "Post-Quantum Signature (SPHINCS+)",
            "policy": "High-security post-quantum signing",
        }

    if risk_score < 0.80:
        return {
            "security_level": "HIGH",
            "cryptography": "Post-Quantum Signature (SPHINCS+)",
            "policy": "High-security post-quantum signing",
        }
    return {
        "security_level": "CRITICAL",
        "cryptography": "SPHINCS+ + Hardware-backed Multi-Party Verification",
        "policy": "Hardware wallet + multi-party verification",
    }


def compute_demo_risk_score(df: pd.DataFrame) -> pd.Series:
    """Compute a smooth feature-weighted risk score for interactive demos.

    The trained classifier on the synthetic dataset is highly separable, so raw
    predict_proba outputs tend to collapse to extreme values. For slider-driven
    demonstrations, this smoother score makes LOW, MEDIUM, and HIGH bands
    reachable while still reflecting the selected risk features.
    """
    value_score = (df["transaction_value"] / 20_000.0).clip(0.0, 1.0)
    gas_score = (df["gas_price"] / 2_000.0).clip(0.0, 1.0)
    frequency_score = (df["transaction_frequency"] / 120.0).clip(0.0, 1.0)
    counterparty_score = (df["unique_counterparties"] / 500.0).clip(0.0, 1.0)
    pagerank_score = (df["pagerank_score"] / 0.08).clip(0.0, 1.0)

    return (
        0.20 * value_score
        + 0.20 * gas_score
        + 0.25 * frequency_score
        + 0.15 * counterparty_score
        + 0.20 * pagerank_score
    ).clip(0.0, 1.0)


def generate_synthetic_blockchain_data(
    n_transactions: int = 10_000,
    malicious_ratio: float = 0.05,
    n_accounts: int = 1_500,
    seed: int = 42,
) -> pd.DataFrame:
    rng = np.random.default_rng(seed)

    labels = np.zeros(n_transactions, dtype=int)
    malicious_count = int(n_transactions * malicious_ratio)
    malicious_indices = rng.choice(np.arange(n_transactions), size=malicious_count, replace=False)
    labels[malicious_indices] = 1

    sender_ids = rng.integers(0, n_accounts, size=n_transactions)
    receiver_ids = rng.integers(0, n_accounts, size=n_transactions)
    same_mask = sender_ids == receiver_ids
    receiver_ids[same_mask] = (receiver_ids[same_mask] + 1) % n_accounts

    base_ts = np.datetime64("2025-01-01T00:00:00")
    seconds_offsets = rng.integers(0, 365 * 24 * 3600, size=n_transactions)
    timestamps = base_ts + seconds_offsets.astype("timedelta64[s]")

    df = pd.DataFrame(
        {
            "sender_id": sender_ids,
            "receiver_id": receiver_ids,
            "timestamp": pd.to_datetime(timestamps),
            "transaction_value": rng.lognormal(mean=3.6, sigma=0.85, size=n_transactions),
            "gas_price": rng.gamma(shape=2.2, scale=12.0, size=n_transactions),
            "gas_used": rng.normal(loc=80_000, scale=20_000, size=n_transactions).clip(21_000, 350_000),
            "contract_interaction": rng.binomial(1, 0.35, size=n_transactions),
            "sender_transaction_count": rng.poisson(lam=28, size=n_transactions) + 1,
            "avg_transaction_value": rng.lognormal(mean=3.4, sigma=0.7, size=n_transactions),
            "transaction_frequency": rng.gamma(shape=2.0, scale=0.4, size=n_transactions),
            "unique_counterparties": rng.poisson(lam=9, size=n_transactions) + 1,
            "time_since_last_transaction": rng.exponential(scale=8 * 3600, size=n_transactions),
            "fraud_label": labels,
        }
    )

    # Inject malicious behaviors.
    mal = df["fraud_label"] == 1
    df.loc[mal, "transaction_value"] *= rng.uniform(6.0, 28.0, size=mal.sum())
    df.loc[mal, "gas_price"] *= rng.uniform(7.0, 20.0, size=mal.sum())
    df.loc[mal, "gas_used"] *= rng.uniform(1.2, 2.8, size=mal.sum())
    df.loc[mal, "sender_transaction_count"] = (
        df.loc[mal, "sender_transaction_count"] * rng.uniform(1.8, 4.8, size=mal.sum())
    ).astype(int)
    df.loc[mal, "avg_transaction_value"] *= rng.uniform(2.5, 8.0, size=mal.sum())
    df.loc[mal, "transaction_frequency"] *= rng.uniform(4.0, 15.0, size=mal.sum())
    df.loc[mal, "unique_counterparties"] += rng.integers(20, 120, size=mal.sum())
    df.loc[mal, "time_since_last_transaction"] *= rng.uniform(0.02, 0.25, size=mal.sum())
    df.loc[mal, "contract_interaction"] = rng.binomial(1, 0.85, size=mal.sum())

    # Build graph from transfers and compute graph features.
    graph = nx.DiGraph()
    graph.add_nodes_from(np.arange(n_accounts))

    for s, r in zip(df["sender_id"].values, df["receiver_id"].values):
        if graph.has_edge(s, r):
            graph[s][r]["weight"] += 1
        else:
            graph.add_edge(s, r, weight=1)

    pagerank = nx.pagerank(graph, alpha=0.85, weight="weight")
    clustering = nx.clustering(graph.to_undirected(), weight="weight")
    # Approximate betweenness for faster runtime on larger graph.
    betweenness = nx.betweenness_centrality(
        graph,
        k=min(220, n_accounts),
        normalized=True,
        seed=seed,
        weight="weight",
    )

    in_deg_map = dict(graph.in_degree())
    out_deg_map = dict(graph.out_degree())

    df["in_degree"] = df["sender_id"].map(in_deg_map).astype(float)
    df["out_degree"] = df["sender_id"].map(out_deg_map).astype(float)
    df["clustering_coefficient"] = df["sender_id"].map(clustering).astype(float)
    df["pagerank_score"] = df["sender_id"].map(pagerank).astype(float)
    df["betweenness_centrality"] = df["sender_id"].map(betweenness).astype(float)

    # Strengthen malicious graph centrality profile.
    df.loc[mal, "in_degree"] *= rng.uniform(1.3, 2.6, size=mal.sum())
    df.loc[mal, "out_degree"] *= rng.uniform(1.3, 2.8, size=mal.sum())
    df.loc[mal, "pagerank_score"] *= rng.uniform(2.2, 5.5, size=mal.sum())
    df.loc[mal, "betweenness_centrality"] *= rng.uniform(2.4, 7.5, size=mal.sum())
    df.loc[mal, "clustering_coefficient"] = np.clip(
        df.loc[mal, "clustering_coefficient"] * rng.uniform(1.2, 2.4, size=mal.sum()),
        0.0,
        1.0,
    )

    # Pandas Series does not expose .view; use astype for datetime -> int64.
    df["timestamp_unix"] = df["timestamp"].astype("int64") // 10**9
    df["transaction_fee"] = df["gas_price"] * df["gas_used"]

    return df


def evaluate_model(model, X_train, X_test, y_train, y_test) -> Tuple[Dict[str, float], np.ndarray]:
    model.fit(X_train, y_train)
    y_pred = model.predict(X_test)
    y_prob = model.predict_proba(X_test)[:, 1]

    metrics = {
        "accuracy": accuracy_score(y_test, y_pred),
        "precision": precision_score(y_test, y_pred, zero_division=0),
        "recall": recall_score(y_test, y_pred, zero_division=0),
        "f1_score": f1_score(y_test, y_pred, zero_division=0),
        "roc_auc": roc_auc_score(y_test, y_prob),
    }
    return metrics, y_prob


def plot_feature_importance(model, feature_names: List[str], title: str, output_path: Path) -> None:
    importances = model.feature_importances_
    order = np.argsort(importances)[::-1][:15]

    fig, ax = plt.subplots(figsize=(10, 6))
    sns.barplot(x=importances[order], y=np.array(feature_names)[order], palette="viridis", ax=ax)
    ax.set_title(title)
    ax.set_xlabel("Importance")
    ax.set_ylabel("Feature")
    fig.tight_layout()
    fig.savefig(output_path, dpi=180)
    plt.close(fig)


def simulate_attack_scenarios(
    reference_df: pd.DataFrame,
    model,
    model_features: List[str],
    norm_ref: NormalizationReference,
    risk_mode: str,
) -> pd.DataFrame:
    baseline = reference_df[model_features].median().to_dict()
    now_ts = float(reference_df["timestamp_unix"].max())

    scenarios = {
        "Front-Running Attack": {
            "transaction_value": baseline["transaction_value"] * 2.2,
            "gas_price": baseline["gas_price"] * 15.0,
            "transaction_frequency": baseline["transaction_frequency"] * 10.0,
            "time_since_last_transaction": baseline["time_since_last_transaction"] * 0.08,
            "unique_counterparties": baseline["unique_counterparties"] * 1.8,
            "timestamp_unix": now_ts,
        },
        "Sandwich Attack": {
            "transaction_value": baseline["transaction_value"] * 3.0,
            "gas_price": baseline["gas_price"] * 8.0,
            "transaction_frequency": baseline["transaction_frequency"] * 7.5,
            "out_degree": baseline["out_degree"] * 2.0,
            "unique_counterparties": baseline["unique_counterparties"] * 1.5,
            "timestamp_unix": now_ts,
        },
        "Flash Loan Attack": {
            "transaction_value": baseline["transaction_value"] * 30.0,
            "contract_interaction": 1.0,
            "gas_price": baseline["gas_price"] * 4.0,
            "gas_used": baseline["gas_used"] * 3.5,
            "transaction_frequency": baseline["transaction_frequency"] * 4.5,
            "timestamp_unix": now_ts,
        },
        "Phishing Attack": {
            "transaction_value": baseline["transaction_value"] * 0.45,
            "in_degree": baseline["in_degree"] * 4.5,
            "unique_counterparties": baseline["unique_counterparties"] * 6.0,
            "transaction_frequency": baseline["transaction_frequency"] * 3.0,
            "time_since_last_transaction": baseline["time_since_last_transaction"] * 0.35,
            "timestamp_unix": now_ts,
        },
    }

    rows = []
    for scenario_name, updates in scenarios.items():
        row = baseline.copy()
        row.update(updates)
        rows.append((scenario_name, row))

    scenario_df = pd.DataFrame([row for _, row in rows])
    scenario_df = recompute_derived_features(scenario_df, normalization_reference=norm_ref)

    risk_scores = model.predict_proba(scenario_df[model_features])[:, 1]

    records = []
    for (scenario_name, _), score in zip(rows, risk_scores):
        mechanism = select_security_mechanism(float(score), risk_mode=risk_mode)
        records.append(
            {
                "attack_scenario": scenario_name,
                "risk_score": float(np.clip(score, 0.0, 1.0)),
                "security_level": mechanism["security_level"],
                "cryptography": mechanism["cryptography"],
                "security_policy": mechanism["policy"],
            }
        )

    return pd.DataFrame(records).sort_values("risk_score", ascending=False)


def plot_risk_relationships(df: pd.DataFrame, output_dir: Path, show_plots: bool) -> None:
    sample = df.sample(n=min(3_500, len(df)), random_state=42)

    fig, axes = plt.subplots(1, 3, figsize=(20, 5))
    sns.scatterplot(
        data=sample,
        x="transaction_value",
        y="risk_score",
        hue="fraud_label",
        alpha=0.5,
        ax=axes[0],
        palette={0: "#2a9d8f", 1: "#e76f51"},
    )
    axes[0].set_title("Risk Score vs Transaction Value")

    sns.scatterplot(
        data=sample,
        x="transaction_frequency",
        y="risk_score",
        hue="fraud_label",
        alpha=0.5,
        ax=axes[1],
        palette={0: "#2a9d8f", 1: "#e76f51"},
        legend=False,
    )
    axes[1].set_title("Risk Score vs Transaction Frequency")

    sns.scatterplot(
        data=sample,
        x="network_risk_score",
        y="risk_score",
        hue="fraud_label",
        alpha=0.5,
        ax=axes[2],
        palette={0: "#2a9d8f", 1: "#e76f51"},
        legend=False,
    )
    axes[2].set_title("Risk Score vs Network Centrality")

    fig.tight_layout()
    fig.savefig(output_dir / "risk_vs_features.png", dpi=180)
    if show_plots:
        plt.show()
    plt.close(fig)

    fig2, ax2 = plt.subplots(figsize=(10, 5))
    order = (
        df["selected_cryptography"]
        .value_counts()
        .sort_values(ascending=False)
        .index
    )
    sns.countplot(
        data=df,
        x="selected_cryptography",
        order=order,
        palette="magma",
        ax=ax2,
    )
    ax2.set_title("Security Mechanism Distribution")
    ax2.set_xlabel("Cryptography")
    ax2.set_ylabel("Transaction Count")
    ax2.tick_params(axis="x", rotation=20)

    fig2.tight_layout()
    fig2.savefig(output_dir / "security_mechanism_distribution.png", dpi=180)
    if show_plots:
        plt.show()
    plt.close(fig2)


def visualize_transaction_network(df: pd.DataFrame, output_dir: Path, show_plots: bool, seed: int = 42) -> None:
    """Draw a manageable subgraph and highlight nodes involved in malicious activity."""
    top_accounts = df["sender_id"].value_counts().head(160).index
    sub_edges = df[df["sender_id"].isin(top_accounts) & df["receiver_id"].isin(top_accounts)]

    graph = nx.from_pandas_edgelist(
        sub_edges,
        source="sender_id",
        target="receiver_id",
        create_using=nx.DiGraph(),
    )

    malicious_nodes = set(df.loc[df["fraud_label"] == 1, "sender_id"].unique())
    node_colors = ["#d62828" if n in malicious_nodes else "#1d3557" for n in graph.nodes()]

    fig, ax = plt.subplots(figsize=(12, 10))
    pos = nx.spring_layout(graph, seed=seed, k=0.35)
    nx.draw_networkx_nodes(graph, pos, node_size=70, node_color=node_colors, alpha=0.8, ax=ax)
    nx.draw_networkx_edges(graph, pos, alpha=0.18, width=0.7, edge_color="#8d99ae", ax=ax)
    ax.set_title("Transaction Network (Malicious Nodes in Red)")
    ax.axis("off")

    fig.tight_layout()
    fig.savefig(output_dir / "transaction_network.png", dpi=180)
    if show_plots:
        plt.show()
    plt.close(fig)


def run_interactive_slider_demo(
    model,
    baseline_row: pd.Series,
    model_features: List[str],
    norm_ref: NormalizationReference,
    risk_mode: str,
) -> None:
    """Interactive matplotlib slider simulation for adaptive security response."""
    fig, ax = plt.subplots(figsize=(10, 6))
    plt.subplots_adjust(left=0.12, bottom=0.48)
    ax.axis("off")

    txt = ax.text(
        0.02,
        0.75,
        "Use sliders to update transaction characteristics.",
        fontsize=12,
        transform=ax.transAxes,
    )

    ax_tv = plt.axes([0.12, 0.37, 0.76, 0.03])
    ax_gp = plt.axes([0.12, 0.32, 0.76, 0.03])
    ax_tf = plt.axes([0.12, 0.27, 0.76, 0.03])
    ax_uc = plt.axes([0.12, 0.22, 0.76, 0.03])
    ax_pr = plt.axes([0.12, 0.17, 0.76, 0.03])

    s_tv = Slider(ax_tv, "transaction_value", 1.0, 10_000.0, valinit=float(baseline_row["transaction_value"]))
    s_gp = Slider(ax_gp, "gas_price", 1.0, 1500.0, valinit=float(baseline_row["gas_price"]))
    s_tf = Slider(
        ax_tf,
        "transaction_frequency",
        0.01,
        100.0,
        valinit=float(baseline_row["transaction_frequency"]),
    )
    s_uc = Slider(
        ax_uc,
        "unique_counterparties",
        1.0,
        300.0,
        valinit=float(baseline_row["unique_counterparties"]),
    )
    s_pr = Slider(ax_pr, "pagerank_score", 0.0, 0.05, valinit=float(baseline_row["pagerank_score"]))

    def update(_):
        row = baseline_row.copy()
        row["transaction_value"] = s_tv.val
        row["gas_price"] = s_gp.val
        row["transaction_frequency"] = s_tf.val
        row["unique_counterparties"] = s_uc.val
        row["pagerank_score"] = s_pr.val

        # Keep correlated network features coherent with pagerank slider movement.
        row["betweenness_centrality"] = max(0.0, s_pr.val * 1.8)
        row["clustering_coefficient"] = min(1.0, 0.15 + s_pr.val * 8.0)

        scenario = pd.DataFrame([row])
        scenario = recompute_derived_features(scenario, normalization_reference=norm_ref)
        risk = float(compute_demo_risk_score(scenario).iloc[0])
        mechanism = select_security_mechanism(risk, risk_mode=risk_mode)

        txt.set_text(
            f"risk_score: {risk:.3f}\n"
            f"security_level: {mechanism['security_level']}\n"
            f"cryptography: {mechanism['cryptography']}\n"
            f"policy: {mechanism['policy']}"
        )
        fig.canvas.draw_idle()

    s_tv.on_changed(update)
    s_gp.on_changed(update)
    s_tf.on_changed(update)
    s_uc.on_changed(update)
    s_pr.on_changed(update)

    update(None)
    plt.show()


def run_performance_analysis(output_dir: Path, show_plots: bool) -> pd.DataFrame:
    perf = pd.DataFrame(
        [
            {
                "cryptography": "ECDSA",
                "security_strength": 55,
                "signature_time_ms": 2.1,
                "verification_time_ms": 1.3,
                "transaction_latency_ms": 42,
            },
            {
                "cryptography": "MultiSig",
                "security_strength": 72,
                "signature_time_ms": 6.3,
                "verification_time_ms": 4.4,
                "transaction_latency_ms": 86,
            },
            {
                "cryptography": "MPC",
                "security_strength": 86,
                "signature_time_ms": 20.5,
                "verification_time_ms": 10.8,
                "transaction_latency_ms": 164,
            },
            {
                "cryptography": "Dilithium",
                "security_strength": 93,
                "signature_time_ms": 8.2,
                "verification_time_ms": 5.6,
                "transaction_latency_ms": 114,
            },
            {
                "cryptography": "SPHINCS+",
                "security_strength": 98,
                "signature_time_ms": 35.0,
                "verification_time_ms": 18.5,
                "transaction_latency_ms": 245,
            },
        ]
    )

    fig, ax = plt.subplots(figsize=(9, 6))
    sns.scatterplot(
        data=perf,
        x="transaction_latency_ms",
        y="security_strength",
        hue="cryptography",
        s=160,
        palette="Set2",
        ax=ax,
    )

    for _, row in perf.iterrows():
        ax.text(
            row["transaction_latency_ms"] + 2,
            row["security_strength"] + 0.4,
            row["cryptography"],
            fontsize=9,
        )

    ax.set_title("Security Strength vs Latency Trade-off")
    ax.set_xlabel("Transaction Latency (ms)")
    ax.set_ylabel("Security Strength (0-100)")
    fig.tight_layout()
    fig.savefig(output_dir / "security_strength_vs_latency.png", dpi=180)

    if show_plots:
        plt.show()
    plt.close(fig)

    return perf


def main() -> None:
    parser = argparse.ArgumentParser(description="Adaptive Cryptography Security System Simulation")
    parser.add_argument("--n-transactions", type=int, default=10_000)
    parser.add_argument("--seed", type=int, default=42)
    parser.add_argument("--output-dir", type=str, default="outputs")
    parser.add_argument(
        "--show-plots",
        action="store_true",
        help="Display plots interactively in addition to saving them.",
    )
    parser.add_argument(
        "--interactive-demo",
        action="store_true",
        help="Launch matplotlib slider demo for adaptive security selection.",
    )
    parser.add_argument(
        "--risk-mode",
        type=str,
        choices=["3-level", "4-level"],
        default="4-level",
        help="Use 3-level (LOW/MEDIUM/HIGH) or 4-level (LOW/MEDIUM/HIGH/CRITICAL) policy.",
    )
    args = parser.parse_args()

    output_dir = Path(args.output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)

    print("\n[1/8] Generating synthetic dataset...")
    df = generate_synthetic_blockchain_data(
        n_transactions=args.n_transactions,
        malicious_ratio=0.05,
        seed=args.seed,
    )

    norm_columns = [
        "pagerank_score",
        "betweenness_centrality",
        "clustering_coefficient",
        "transaction_frequency",
        "unique_counterparties",
        "time_since_last_transaction",
    ]
    norm_ref = build_normalization_reference(df, norm_columns)
    df = recompute_derived_features(df, normalization_reference=norm_ref)

    print("\n[2/8] Training ML models (RandomForest + XGBoost)...")
    X = df[MODEL_FEATURES]
    y = df["fraud_label"]

    X_train, X_test, y_train, y_test = train_test_split(
        X,
        y,
        test_size=0.20,
        random_state=args.seed,
        stratify=y,
    )

    class_weight_scale = (y_train == 0).sum() / max((y_train == 1).sum(), 1)

    rf = RandomForestClassifier(
        n_estimators=350,
        max_depth=None,
        min_samples_split=4,
        min_samples_leaf=2,
        class_weight="balanced",
        random_state=args.seed,
        n_jobs=-1,
    )

    xgb = XGBClassifier(
        n_estimators=450,
        max_depth=6,
        learning_rate=0.05,
        subsample=0.9,
        colsample_bytree=0.9,
        objective="binary:logistic",
        eval_metric="logloss",
        random_state=args.seed,
        n_jobs=-1,
        scale_pos_weight=class_weight_scale,
    )

    rf_metrics, _ = evaluate_model(rf, X_train, X_test, y_train, y_test)
    xgb_metrics, _ = evaluate_model(xgb, X_train, X_test, y_train, y_test)

    metrics_df = pd.DataFrame(
        [
            {"model": "RandomForest", **rf_metrics},
            {"model": "XGBoost", **xgb_metrics},
        ]
    )

    print("\nModel Evaluation Metrics:")
    print(metrics_df.to_string(index=False, float_format=lambda x: f"{x:.4f}"))

    plot_feature_importance(
        rf,
        MODEL_FEATURES,
        "RandomForest Feature Importance",
        output_dir / "rf_feature_importance.png",
    )
    plot_feature_importance(
        xgb,
        MODEL_FEATURES,
        "XGBoost Feature Importance",
        output_dir / "xgb_feature_importance.png",
    )

    print("\n[3/8] Generating continuous risk scores and adaptive mechanisms...")
    best_model = xgb if xgb_metrics["roc_auc"] >= rf_metrics["roc_auc"] else rf
    best_name = "XGBoost" if best_model is xgb else "RandomForest"
    print(f"Selected model for risk engine: {best_name}")
    print(f"Selected risk policy mode: {args.risk_mode}")

    df["risk_score"] = np.clip(best_model.predict_proba(df[MODEL_FEATURES])[:, 1], 0.0, 1.0)

    mechanism_records = df["risk_score"].apply(lambda r: select_security_mechanism(float(r), risk_mode=args.risk_mode))
    df["security_level"] = mechanism_records.map(lambda x: x["security_level"])
    df["selected_cryptography"] = mechanism_records.map(lambda x: x["cryptography"])
    df["security_policy"] = mechanism_records.map(lambda x: x["policy"])

    print("\n[4/8] Simulating attack scenarios...")
    attack_results = simulate_attack_scenarios(df, best_model, MODEL_FEATURES, norm_ref, risk_mode=args.risk_mode)
    print("\nAttack Scenario Results:")
    print(attack_results.to_string(index=False, float_format=lambda x: f"{x:.4f}"))

    print("\n[5/8] Creating visualizations...")
    plot_risk_relationships(df, output_dir=output_dir, show_plots=args.show_plots)
    visualize_transaction_network(df, output_dir=output_dir, show_plots=args.show_plots)

    print("\n[6/8] Running cryptography performance analysis...")
    perf_df = run_performance_analysis(output_dir=output_dir, show_plots=args.show_plots)

    print("\n[7/8] Saving outputs...")
    df.to_csv(output_dir / "synthetic_blockchain_transactions_with_risk.csv", index=False)
    metrics_df.to_csv(output_dir / "model_metrics.csv", index=False)
    attack_results.to_csv(output_dir / "attack_scenario_results.csv", index=False)
    perf_df.to_csv(output_dir / "cryptography_performance.csv", index=False)

    if args.interactive_demo:
        print("\n[8/8] Launching interactive adaptation demo...")
        baseline = df[MODEL_FEATURES].median()
        run_interactive_slider_demo(best_model, baseline, MODEL_FEATURES, norm_ref, risk_mode=args.risk_mode)
    else:
        print("\n[8/8] Interactive demo skipped. Use --interactive-demo to launch it.")

    print(f"\nSimulation complete. Outputs saved to: {output_dir.resolve()}")


if __name__ == "__main__":
    main()
