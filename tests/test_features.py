import numpy as np
import pandas as pd

from data_ai.evaluate import classification_report, regression_report
from data_ai.features import apply_missing_strategy, feature_columns


def test_regression_report():
    r = regression_report([1, 2, 3], [1, 2, 3])
    assert r["mae"] == 0 and r["rmse"] == 0 and r["r2"] == 1


def test_classification_report():
    r = classification_report([0, 1, 1, 0], [0, 1, 0, 0], y_prob=[0.1, 0.9, 0.4, 0.2])
    assert 0 <= r["f1"] <= 1
    assert "roc_auc" in r


def test_feature_columns_blocks_target_like_columns():
    df = pd.DataFrame(
        {
            "station_id": ["a"],
            "cyano_cells": [1.0],
            "w_temp_mean7d": [1.0],
            "target_cells": [2.0],
            "true_cells": [2.0],
            "log10_target_cells": [0.3],
            "split": ["train"],
            "date": ["2024-01-01"],
        }
    )
    assert feature_columns(df) == ["station_id", "cyano_cells", "w_temp_mean7d"]


def test_missing_strategies_fill_only_from_train_stats():
    df = pd.DataFrame(
        {
            "station_id": ["a"] * 4,
            "month": [6, 6, 6, 6],
            "water_temp": [20.0, np.nan, 30.0, np.nan],
            "water_temp_lag1": [np.nan, 20.0, np.nan, 30.0],
            "cyano_cells": [1.0, 2.0, 3.0, 4.0],
        }
    )
    train = pd.Series([True, True, False, False])
    out = apply_missing_strategy(df, "ffill_flag", train)
    assert out["water_temp"].tolist() == [20.0, 20.0, 30.0, 30.0]
    assert out["water_temp_isna"].tolist() == [0, 1, 0, 1]
    out2 = apply_missing_strategy(df, "site_month_median", train)
    assert out2["water_temp"].iloc[3] == 20.0  # 학습 구간(첫 두 행) 중앙값 → 30 은 쓰이지 않음
    assert apply_missing_strategy(df, "native", train)["water_temp"].isna().sum() == 2
