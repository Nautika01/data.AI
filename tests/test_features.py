import numpy as np
import pandas as pd

from data_ai.evaluate import classification_report, regression_report
from data_ai.features import add_lag_features, add_rolling_features, add_time_features


def _df():
    return pd.DataFrame(
        {
            "ts": pd.date_range("2026-01-03", periods=6, freq="D"),  # 토요일 시작
            "x": [1.0, 2.0, 3.0, 4.0, 5.0, 6.0],
        }
    )


def test_time_features():
    out = add_time_features(_df(), "ts")
    assert out["ts_is_weekend"].tolist() == [1, 1, 0, 0, 0, 0]
    assert out["ts_month"].eq(1).all()


def test_lag_features():
    out = add_lag_features(_df(), ["x"], [1, 2])
    assert np.isnan(out["x_lag1"].iloc[0])
    assert out["x_lag1"].iloc[1] == 1.0
    assert out["x_lag2"].iloc[3] == 2.0


def test_rolling_features_exclude_current():
    out = add_rolling_features(_df(), ["x"], [2])
    # t=2: mean of x[0], x[1] = 1.5
    assert out["x_rmean2"].iloc[2] == 1.5


def test_regression_report():
    r = regression_report([1, 2, 3], [1, 2, 3])
    assert r["mae"] == 0 and r["rmse"] == 0 and r["r2"] == 1


def test_classification_report():
    r = classification_report([0, 1, 1, 0], [0, 1, 0, 0], y_prob=[0.1, 0.9, 0.4, 0.2])
    assert 0 <= r["f1"] <= 1
    assert "roc_auc" in r
