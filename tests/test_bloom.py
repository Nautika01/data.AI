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


def test_river_features_builds_flow_and_stage_columns():
    from data_ai.bloom import river_features

    dates = pd.date_range("2024-01-01", periods=40, freq="D")
    daily = pd.concat(
        [
            pd.DataFrame(
                {
                    "date": dates,
                    "kind": "fw",
                    "station": "구미대교",
                    "value": np.arange(1, 41) * 10.0,
                }
            ),
            pd.DataFrame(
                {
                    "date": dates,
                    "kind": "wl",
                    "station": "구미보하",
                    "value": np.arange(1, 41) * 0.1,
                }
            ),
            # 0 값은 결측으로 봐야 하는 관측소
            pd.DataFrame({"date": dates, "kind": "wl", "station": "칠곡보상", "value": 0.0}),
        ]
    )
    feat = river_features(
        daily,
        {"HP": {"fw": "구미대교", "wl": "구미보하"}, "GJGR": {"wl": "칠곡보상"}, "CS": {}},
        windows=[7, 28],
        zero_as_missing=["칠곡보상"],
    )
    hp = feat[feat["station_id"] == "HP"].set_index("date")
    row = hp.loc["2024-02-09"]  # 40일째
    assert row["flow"] == 400.0
    assert row["flow_mean7d"] == np.mean(np.arange(34, 41) * 10.0)
    assert abs(row["log_flow_mean7d"] - np.log10(row["flow_mean7d"] + 1)) < 1e-9
    assert row["flow_rel28d"] == row["flow_mean7d"] / (row["flow_mean28d"] + 1.0)
    assert abs(row["stage_diff7d"] - 0.7) < 1e-9  # 4.0 − 3.3
    assert np.isnan(hp.loc["2024-01-05", "stage_diff7d"])  # 7일 전 자료 없음
    # 칠곡보상 0 값은 결측 처리 → GJGR 수위 전부 NaN
    gj = feat[feat["station_id"] == "GJGR"]
    assert gj["stage"].isna().all() and "flow" not in gj.columns or gj["flow"].isna().all()
    assert "CS" not in set(feat["station_id"])  # 매핑 없는 지점은 행 없음


def test_upstream_features_use_only_past_measurements():
    from data_ai.bloom import upstream_features

    d = pd.DataFrame(
        {
            "station_id": ["HP", "HP", "GJGR", "GJGR", "CS", "DCHN"],
            "date": pd.to_datetime(
                ["2024-06-03", "2024-06-17", "2024-06-10", "2024-06-24", "2024-06-10", "2024-06-10"]
            ),
            "cyano_cells": [999.0, 9.0, 99.0, 9999.0, 0.0, 5.0],
        }
    )
    out = upstream_features(
        d,
        chain={"GJGR": "HP", "CS": "GJGR"},
        basins={"nak": ["HP", "GJGR", "CS"]},
        tolerance_days=14,
    )
    g = out[out["station_id"] == "GJGR"].sort_values("date")
    # 6/10 기준: 해평의 6/3 값(999)만 보인다. 6/17 값(9)은 미래이므로 안 씀
    assert np.isclose(g["cells_upstream"].iloc[0], np.log10(1000))
    # 6/24 기준: 해평 최근값은 6/17(9)
    assert np.isclose(g["cells_upstream"].iloc[1], np.log10(10))
    # 해평(최상류)은 상류 없음, 회남은 수계 밖 → 둘 다 결측
    assert out.loc[out["station_id"] == "HP", "cells_upstream"].isna().all()
    assert (
        out.loc[out["station_id"] == "DCHN", ["cells_upstream", "cells_basin_mean"]]
        .isna()
        .all()
        .all()
    )
    # 창녕함안 6/10 기준 수계 평균 = 해평 6/3(999) 과 강정고령 6/10(99) 의 log 평균
    cs = out[out["station_id"] == "CS"]["cells_basin_mean"].iloc[0]
    assert np.isclose(cs, (np.log10(1000) + np.log10(100)) / 2)
