"""평가 지표."""

from __future__ import annotations

import numpy as np
from sklearn import metrics


def regression_report(y_true, y_pred) -> dict[str, float]:
    y_true = np.asarray(y_true, dtype=float)
    y_pred = np.asarray(y_pred, dtype=float)
    mae = metrics.mean_absolute_error(y_true, y_pred)
    rmse = float(np.sqrt(metrics.mean_squared_error(y_true, y_pred)))
    denom = np.where(y_true == 0, np.nan, np.abs(y_true))
    mape = float(np.nanmean(np.abs(y_true - y_pred) / denom) * 100)
    return {
        "mae": float(mae),
        "rmse": rmse,
        "mape": mape,
        "r2": float(metrics.r2_score(y_true, y_pred)),
    }


def classification_report(y_true, y_pred, y_prob=None) -> dict[str, float]:
    out = {
        "accuracy": float(metrics.accuracy_score(y_true, y_pred)),
        "precision": float(
            metrics.precision_score(y_true, y_pred, average="macro", zero_division=0)
        ),
        "recall": float(metrics.recall_score(y_true, y_pred, average="macro", zero_division=0)),
        "f1": float(metrics.f1_score(y_true, y_pred, average="macro", zero_division=0)),
    }
    if y_prob is not None:
        try:
            out["roc_auc"] = float(metrics.roc_auc_score(y_true, y_prob))
        except ValueError:
            pass
    return out
