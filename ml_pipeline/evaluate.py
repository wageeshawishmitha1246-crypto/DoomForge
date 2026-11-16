"""Evaluation utilities for baseline Ethereum risk models.

This module provides helper functions to compute and print common
classification metrics so they can be reused by training and
post-hoc evaluation scripts.
"""

from __future__ import annotations

from typing import Dict

import numpy as np
from sklearn.metrics import (
    accuracy_score,
    f1_score,
    precision_score,
    recall_score,
    roc_auc_score,
)


def compute_classification_metrics(
    y_true,
    y_pred,
    y_proba=None,
) -> Dict[str, float]:
    """Compute standard binary classification metrics.

    Parameters
    ----------
    y_true:
        True labels (array-like).
    y_pred:
        Predicted class labels (array-like).
    y_proba:
        Optional predicted probabilities for the positive class. If not
        provided, ROC-AUC is set to NaN.
    """

    metrics = {
        "accuracy": accuracy_score(y_true, y_pred),
        "precision": precision_score(y_true, y_pred, zero_division=0),
        "recall": recall_score(y_true, y_pred, zero_division=0),
        "f1_score": f1_score(y_true, y_pred, zero_division=0),
        "roc_auc": np.nan,
    }

    if y_proba is not None:
        try:
            metrics["roc_auc"] = roc_auc_score(y_true, y_proba)
        except ValueError:
            # This can happen if only one class is present in y_true.
            metrics["roc_auc"] = np.nan

    return metrics


def pretty_print_metrics(title: str, metrics: Dict[str, float]) -> None:
    """Print metrics in a readable table-like format."""

    print(f"\n{title}")
    print("-" * len(title))
    for key, value in metrics.items():
        if np.isnan(value):
            print(f"{key:>10}:   NaN")
        else:
            print(f"{key:>10}: {value:6.4f}")
