"""LightGBM 학습·예측·저장."""

from __future__ import annotations

from pathlib import Path
from typing import Any

import joblib
import lightgbm as lgb
import numpy as np
import pandas as pd

from data_ai.config import MODELS_DIR, SEED

DEFAULT_PARAMS = {
    "objective": "regression",  # log10 공간 L2 → 공식 지표 rmse_log10 와 일치
    "learning_rate": 0.03,
    "num_leaves": 15,
    "min_child_samples": 20,
    "feature_fraction": 0.8,
    "bagging_fraction": 0.8,
    "bagging_freq": 1,
    "lambda_l2": 1.0,
    "extra_trees": True,  # 분할점 무작위화 — 4차 실험에서 롤링 검증 평균 rmse_log10 0.01 개선
    "verbose": -1,
    "seed": SEED,
}


def fit_lgb(
    x_train: pd.DataFrame,
    y_train: np.ndarray,
    x_valid: pd.DataFrame | None = None,
    y_valid: np.ndarray | None = None,
    params: dict | None = None,
    num_rounds: int = 3000,
    early_stopping: int = 150,
    weight: np.ndarray | None = None,
) -> lgb.Booster:
    p = {**DEFAULT_PARAMS, **(params or {})}
    dtrain = lgb.Dataset(x_train, y_train, weight=weight, free_raw_data=False)
    if x_valid is not None:
        dvalid = lgb.Dataset(x_valid, y_valid, reference=dtrain, free_raw_data=False)
        return lgb.train(
            p,
            dtrain,
            num_boost_round=num_rounds,
            valid_sets=[dvalid],
            callbacks=[lgb.early_stopping(early_stopping, verbose=False)],
        )
    return lgb.train(p, dtrain, num_boost_round=num_rounds)


def predict_cells(model: lgb.Booster, x: pd.DataFrame) -> np.ndarray:
    """log10 예측 → cells/mL (0 이상)."""
    log_pred = model.predict(x, num_iteration=getattr(model, "best_iteration", None) or None)
    return np.clip(10**log_pred - 1, 0, None)


def importance(model: lgb.Booster) -> pd.DataFrame:
    return (
        pd.DataFrame(
            {
                "feature": model.feature_name(),
                "gain": model.feature_importance("gain"),
                "split": model.feature_importance("split"),
            }
        )
        .sort_values("gain", ascending=False)
        .reset_index(drop=True)
    )


def save_model(model: Any, name: str) -> Path:
    MODELS_DIR.mkdir(parents=True, exist_ok=True)
    path = MODELS_DIR / f"{name}.joblib"
    joblib.dump(model, path)
    return path


def load_model(name: str) -> Any:
    return joblib.load(MODELS_DIR / f"{name}.joblib")
