"""4차 실험: 번들 안에서 아직 쓰지 않은 정보와 모델 다양화. reports/experiments_round4.csv 에 기록.

변형
- base         기준(train.py 설정, 하천 수위 포함)
- upstream     낙동강 상류 경보지점(해평→강정고령→창녕함안→물금매리)의 기준일 이전 최근 세포수(로그)
               + 같은 수계 다른 지점들의 기준일 이전 최근 세포수 평균(로그)
- odor         지오스민·2-MIB(번들 열, 결측 86%) 입력 추가
- extra_trees  LightGBM extra_trees=True (분할점 무작위화로 과적합 완화)
- et_blend     LightGBM + sklearn ExtraTrees 로그 평균 (모델 계열 다양화)
- ridge_blend  LightGBM 0.7 + Ridge(표준화·중앙값 대체) 0.3 로그 가중 평균
- all_feats    upstream + odor 동시 적용
- up_et        upstream + extra_trees 동시 적용
- base_s{1,2}, up_et_s{1,2}  다른 시드 (잡음 폭 측정용)

평가: valid2025(공식), roll2022, roll2023, test2026*(번들 실측 자체 채점 참고값, 선택에 미사용)
"""

from __future__ import annotations

import json

import numpy as np
import pandas as pd
from sklearn.ensemble import ExtraTreesRegressor
from sklearn.linear_model import Ridge
from sklearn.pipeline import make_pipeline
from sklearn.preprocessing import StandardScaler

from data_ai.config import MODELS_DIR, PROCESSED_DIR, RAW_DIR, REPORTS_DIR, SEED
from data_ai.evaluate import bloom_metrics
from data_ai.features import apply_missing_strategy, feature_columns, to_matrix
from data_ai.models import fit_lgb
from data_ai.utils import get_logger, set_seed

log = get_logger("experiments4")
UPSTREAM = {"GJGR": "HP", "CS": "GJGR", "MGMR": "CS"}  # 낙동강 본류 상→하류
NAKDONG = ["HP", "GJGR", "CS", "MGMR"]
TOL = pd.Timedelta(days=14)


def load():
    df = pd.read_parquet(PROCESSED_DIR / "bloom.parquet")
    df["date"] = pd.to_datetime(df["date"])
    algae = pd.read_csv(RAW_DIR / "algae_measure.csv", parse_dates=["chck_de"])
    for c in ("iem_geosm", "iem_mib2"):  # '정량한계미만' → 0
        algae[c] = pd.to_numeric(algae[c].replace("정량한계미만", "0"), errors="coerce")
    g = algae.groupby(["station_id", "chck_de"])
    truth = g["iem_bgalage_cell_co"].mean().rename("_truth")
    df = df.join(truth, on=["station_id", "target_date"])  # 자체 채점 전용(허용 목록 밖)
    df.loc[~df["is_test"], "_truth"] = df["target_cells"]
    odor = g[["iem_geosm", "iem_mib2"]].mean()
    odor = odor.rename(columns={"iem_geosm": "geosmin", "iem_mib2": "mib2"})
    df = df.join(odor, on=["station_id", "date"])
    return df


def add_upstream(df: pd.DataFrame) -> pd.DataFrame:
    """기준일 이전(포함) 최근 측정값만 붙인다(merge_asof backward) — 미래 정보 없음."""
    d = df.sort_values("date").copy()
    obs = d[["station_id", "date", "log10_cells"]].dropna().sort_values("date")
    # 상류 지점 최근 세포수
    up = obs.rename(columns={"station_id": "_up", "log10_cells": "cells_upstream"})
    d["_up"] = d["station_id"].map(UPSTREAM)
    has = d["_up"].notna()
    merged = pd.merge_asof(
        d[has].sort_values("date"), up, on="date", by="_up", direction="backward", tolerance=TOL
    )
    d["cells_upstream"] = np.nan
    d.loc[d.index[has], "cells_upstream"] = merged["cells_upstream"].to_numpy()
    # 같은 수계 다른 지점 평균 (낙동강 4지점; 대청호는 단독)
    cols = []
    for s in NAKDONG:
        o = obs[obs["station_id"] == s][["date", "log10_cells"]].rename(
            columns={"log10_cells": f"_c_{s}"}
        )
        d = pd.merge_asof(d.sort_values("date"), o, on="date", direction="backward", tolerance=TOL)
        cols.append(f"_c_{s}")
    own = d["station_id"].isin(NAKDONG)
    basin = d[cols].copy()
    for s in NAKDONG:  # 자기 자신 제외
        basin.loc[d["station_id"] == s, f"_c_{s}"] = np.nan
    d["cells_basin_mean"] = basin.mean(axis=1).where(own)
    return d.drop(columns=cols + ["_up"]).sort_index()


def matrices(d, cols, tr, va):
    x_tr, cats = to_matrix(d[tr], cols)
    x_va, _ = to_matrix(d[va], cols, cats)
    return x_tr, x_va, d.loc[tr, "log10_target_cells"].to_numpy()


def numeric_fill(x_tr: pd.DataFrame, x_va: pd.DataFrame):
    """sklearn 용: 범주형 → 코드, 결측 → 학습 중앙값."""
    a, b = x_tr.copy(), x_va.copy()
    for c in a.columns:
        if str(a[c].dtype) == "category":
            a[c], b[c] = a[c].cat.codes, b[c].cat.codes
    med = a.median()
    return a.fillna(med).fillna(0), b.fillna(med).fillna(0)


def run_variant(variant, df, strategy, rounds, tr, va):
    d = apply_missing_strategy(df, strategy, tr)
    extra: tuple[str, ...] = ()
    if variant in ("upstream", "all_feats") or variant.startswith("up_et"):
        extra += ("cells_upstream", "cells_basin_mean")
    if variant in ("odor", "all_feats"):
        extra += ("geosmin", "mib2")
    cols = feature_columns(d, extra=extra)
    up_cols = ("cells_upstream", "cells_basin_mean")  # 'cells_' 접두사로 자동 허용되므로 명시 제어
    if variant not in ("upstream", "all_feats") and not variant.startswith("up_et"):
        cols = [c for c in cols if c not in up_cols]
    x_tr, x_va, y = matrices(d, cols, tr, va)
    params = {}
    if variant == "extra_trees" or variant.startswith("up_et"):
        params["extra_trees"] = True
    if variant[-3:-1] == "_s":  # *_s1, *_s2: 시드 변경(잡음 폭 측정)
        params["seed"] = SEED + int(variant[-1])
    pl = fit_lgb(x_tr, y, params=params, num_rounds=rounds).predict(x_va)
    if variant in ("et_blend", "ridge_blend"):
        a, b = numeric_fill(x_tr, x_va)
        if variant == "et_blend":
            et = ExtraTreesRegressor(
                n_estimators=500, min_samples_leaf=5, max_features=0.5, random_state=SEED, n_jobs=-1
            ).fit(a, y)
            pl = 0.5 * pl + 0.5 * et.predict(b)
        else:
            rg = make_pipeline(StandardScaler(), Ridge(alpha=30.0)).fit(a, y)
            pl = 0.7 * pl + 0.3 * rg.predict(b)
    pred = np.clip(10**pl - 1, 0, None)
    m = bloom_metrics(d.loc[va, "_truth"], pred)
    sub = d.loc[va, "month"].between(5, 10).to_numpy()
    m["rmse_log10_may_oct"] = bloom_metrics(d.loc[va, "_truth"][sub], pred[sub])["rmse_log10"]
    return m


def main() -> None:
    set_seed()
    df = add_upstream(load())
    log.info(
        "upstream 결측률 %.2f, basin_mean 결측률 %.2f, 상관(log target) up=%.3f basin=%.3f",
        df["cells_upstream"].isna().mean(),
        df["cells_basin_mean"].isna().mean(),
        df[["cells_upstream", "log10_target_cells"]].corr().iloc[0, 1],
        df[["cells_basin_mean", "log10_target_cells"]].corr().iloc[0, 1],
    )
    meta = json.loads((MODELS_DIR / "train_meta.json").read_text(encoding="utf-8"))
    strategy, rounds = meta["strategy"], int(meta["best_iter"])
    labeled = df["target_valid"]
    sets = {
        "valid2025": (labeled & df["split"].eq("train"), labeled & df["split"].eq("valid")),
        "roll2022": (labeled & (df["year"] < 2022), labeled & (df["year"] == 2022)),
        "roll2023": (labeled & (df["year"] < 2023), labeled & (df["year"] == 2023)),
        "roll2024": (labeled & (df["year"] < 2024), labeled & (df["year"] == 2024)),
        "test2026*": (labeled & df["split"].isin(["train", "valid"]), df["is_test"]),
    }
    rows = []
    variants = [
        "base",
        "base_s1",
        "base_s2",
        "upstream",
        "odor",
        "all_feats",
        "extra_trees",
        "up_et",
        "up_et_s1",
        "up_et_s2",
        "et_blend",
        "ridge_blend",
    ]
    for variant in variants:
        for name, (tr, va) in sets.items():
            r = run_variant(variant, df, strategy, rounds, tr, va)
            rows.append({"variant": variant, "set": name, **r})
            log.info(
                "%-12s %-10s rmse_log10 %.3f  R² %.3f  F1 %.3f",
                variant,
                name,
                r["rmse_log10"],
                r["r2"],
                r["f1_over_threshold"],
            )
    res = pd.DataFrame(rows)
    res.to_csv(REPORTS_DIR / "experiments_round4.csv", index=False, encoding="utf-8-sig")
    pd.set_option("display.width", 200, "display.float_format", "{:,.3f}".format)
    for k in ("rmse_log10", "r2", "f1_over_threshold"):
        print(f"\n## {k}")
        piv = res.pivot(index="variant", columns="set", values=k).round(3)
        piv["mean_val"] = (
            piv[["valid2025", "roll2022", "roll2023", "roll2024"]].mean(axis=1).round(3)
        )
        print(piv.to_string())


if __name__ == "__main__":
    main()
