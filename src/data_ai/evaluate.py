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


def nse(y_true, y_pred) -> float:
    """Nash–Sutcliffe efficiency = 1 − Σ(obs−pred)² / Σ(obs−mean(obs))²."""
    y_true = np.asarray(y_true, dtype=float)
    y_pred = np.asarray(y_pred, dtype=float)
    denom = np.sum((y_true - y_true.mean()) ** 2)
    if denom == 0:
        return float("nan")
    return float(1 - np.sum((y_true - y_pred) ** 2) / denom)


def bloom_metrics(cells_true, cells_pred, threshold: float = 10_000) -> dict[str, float]:
    """공식 평가 지표: log10(세포수+1) RMSE·MAE, 원 단위 R²·NSE, 보조 F1(threshold 초과 여부)."""
    y = np.asarray(cells_true, dtype=float)
    p = np.clip(np.asarray(cells_pred, dtype=float), 0, None)
    mask = ~np.isnan(y) & ~np.isnan(p)
    y, p = y[mask], p[mask]
    ly, lp = np.log10(y + 1), np.log10(p + 1)
    out = {
        "n": int(len(y)),
        "rmse_log10": float(np.sqrt(np.mean((ly - lp) ** 2))),
        "mae_log10": float(np.mean(np.abs(ly - lp))),
        "r2": float(metrics.r2_score(y, p)) if len(y) > 1 else float("nan"),
        "nse": nse(y, p),
    }
    if (y >= threshold).any():
        out["f1_over_threshold"] = float(
            metrics.f1_score(y >= threshold, p >= threshold, zero_division=0)
        )
    else:
        out["f1_over_threshold"] = float("nan")
    return out
