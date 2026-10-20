import numpy as np
import pandas as pd

from data_ai.bloom import (
    add_split,
    add_targets,
    alert_level,
    daily_window_features,
    merge_asof_by,
    standardize,
)
from data_ai.evaluate import bloom_metrics


def test_alert_level_thresholds():
    lv = alert_level(pd.Series([0, 999, 1000, 9999, 10000, 1_000_000, np.nan]))
    assert lv.tolist()[:6] == [0, 0, 1, 1, 2, 3]
    assert np.isnan(lv.iloc[6])


def test_standardize_renames_and_parses():
    raw = pd.DataFrame(
        {"측정소명": [" A "], "측정일자": ["2024-05-06"], "남조류세포수(cells/mL)": ["1,234"]}
    )
    out = standardize(
        raw, {"측정소명": "site_name", "측정일자": "date", "남조류세포수(cells/mL)": "cyano_cells"}
    )
    assert out.loc[0, "site_name"] == "A"
    assert out.loc[0, "date"] == pd.Timestamp("2024-05-06")
    assert out.loc[0, "cyano_cells"] == 1234


def test_daily_window_fills_gaps_and_sums_past_days():
    df = pd.DataFrame(
        {
            "k": "s",
            "date": pd.to_datetime(["2024-01-01", "2024-01-02", "2024-01-04"]),
            "p": [1.0, 2.0, 4.0],
        }
    )
    out = daily_window_features(df, "k", {"p": ["sum"]}, [3])
    assert len(out) == 4  # 1/3 가 채워짐
    row = out[out["date"] == "2024-01-04"].iloc[0]
    assert row["p_sum3d"] == 6.0  # 1/2, 1/3(NaN), 1/4


def test_merge_asof_by_backward_within_tolerance():
    left = pd.DataFrame(
        {"k": ["a", "a", "b"], "date": pd.to_datetime(["2024-01-05", "2024-01-20", "2024-01-05"])}
    )
    right = pd.DataFrame(
        {"k": ["a", "a"], "date": pd.to_datetime(["2024-01-04", "2024-01-10"]), "v": [1.0, 2.0]}
    )
    out = merge_asof_by(left, right, "k", tolerance_days=3)
    assert out["v"].tolist()[0] == 1.0
    assert np.isnan(out["v"].tolist()[1])  # 1/10 → 1/20 은 10일 차, 허용 초과
    assert np.isnan(out["v"].tolist()[2])  # b 없음


def test_add_targets_picks_nearest_to_plus7_within_3_days():
    df = pd.DataFrame(
        {
            "station_id": ["s"] * 5,
            "date": pd.to_datetime(
                ["2024-06-03", "2024-06-09", "2024-06-12", "2024-06-24", "2024-07-01"]
            ),
            "cyano_cells": [500.0, 2000.0, 15000.0, 800.0, np.nan],
        }
    )
    out = add_targets(df, horizon_days=7, tolerance_days=3)
    # 6/3 + 7 = 6/10 → 6/9(1일 차)가 6/12(2일 차)보다 가까움
    assert out.loc[0, "target_cells"] == 2000.0 and out.loc[0, "target_gap_days"] == 6
    # 6/9 + 7 = 6/16 → 6/12(4일 차) 허용 초과, 정답 없음
    assert not out.loc[1, "target_valid"]
    # 6/24 + 7 = 7/1 → 측정은 있으나 세포수 결측 → 채점 제외
    assert not out.loc[3, "target_valid"]
    assert out.loc[2, "cyano_cells"] == 15000.0


def test_add_split_years():
    df = pd.DataFrame(
        {"date": pd.to_datetime(["2023-01-01", "2024-12-31", "2025-06-01", "2026-05-18"])}
    )
    out = add_split(df, 2024, 2025)
    assert out["split"].tolist() == ["train", "train", "valid", "test"]


def test_bloom_metrics_perfect_and_nse():
    y = [100, 2000, 30000, 500]
    m = bloom_metrics(y, y)
    assert m["rmse_log10"] == 0 and m["r2"] == 1 and m["nse"] == 1 and m["f1_over_threshold"] == 1
    m2 = bloom_metrics(y, [np.mean(y)] * 4)
    assert abs(m2["nse"]) < 1e-9  # 평균 예측 → NSE 0


def test_add_targets_from_pairs_and_station_dam_features():
    from data_ai.bloom import add_targets_from_pairs, station_dam_features

    df = pd.DataFrame(
        {
            "station_id": ["HP", "HP", "HP"],
            "date": pd.to_datetime(["2024-06-03", "2024-06-10", "2026-06-01"]),
            "cyano_cells": [100.0, 5000.0, 20000.0],
        }
    )
    pairs = pd.DataFrame(
        {
            "station_id": ["HP", "HP"],
            "base_date": ["2024-06-03", "2026-06-01"],
            "target_date": ["2024-06-10", "2026-06-08"],
            "lag_days": [7, 7],
            "split": ["train", "test"],
        }
    )
    out = add_targets_from_pairs(df, pairs)
    assert out.loc[0, "target_cells"] == 5000.0 and out.loc[0, "target_valid"]
    assert out.loc[1, "split"] == "none" and not out.loc[1, "target_valid"]
    assert out.loc[2, "is_test"] and np.isnan(out.loc[2, "target_cells"])

    dates = pd.to_datetime(["2024-01-01", "2024-01-02"])
    feat = pd.DataFrame(
        {
            "date": list(dates) * 2,
            "dam_name": ["A", "A", "B", "B"],
            "inflow_mean7d": [1.0, 2.0, 10.0, 20.0],
            "outflow_mean7d": [1.0, 1.0, 5.0, 5.0],
            "outflow_mean28d": [1.0, 1.0, 5.0, 5.0],
            "level": [100.0, 101.0, 50.0, 51.0],
        }
    )
    sf = station_dam_features(
        feat, {"X": ["A", "B"]}, {"X": "A"}, ["inflow", "outflow"], ["level"], 2024
    )
    assert sf["inflow_mean7d"].tolist() == [11.0, 22.0]  # 두 댐 합산
    assert sf["level"].tolist() == [100.0, 101.0]  # 대표 댐 A 수위
    assert abs(sf["level_anom"].iloc[0] + 0.5) < 1e-9  # 1월 중앙값 100.5 대비
