"""2차 실험: 기준 모델 대비 변형을 같은 분할에서 비교해 reports/experiments.csv 에 기록한다.

변형
- base            기준(train.py 와 동일 설정)
- dynamics        동역학 피처 추가(최근 2회 측정 기울기, 적산온도, 평년 편차 등)
- per_station     지점별 개별 모델
- drop_dchn_early 회남 2012~2015(수온 전부 결측) 학습 제외
- ensemble5       시드 5개 평균
- quantile        q10/q90 분위수 모델 → 예측 구간 폭·포함률(참고)

평가: valid2025(공식), roll2022, roll2023. test2026* 은 번들 실측 자체 채점 참고값(선택에 미사용).
"""

from __future__ import annotations

import json

import numpy as np
import pandas as pd

from data_ai.config import MODELS_DIR, PROCESSED_DIR, RAW_DIR, REPORTS_DIR
from data_ai.evaluate import bloom_metrics
from data_ai.features import (
    add_dynamics_features,
    apply_missing_strategy,
    feature_columns,
    to_matrix,
)
from data_ai.models import DEFAULT_PARAMS, fit_lgb
from data_ai.utils import get_logger, set_seed

log = get_logger("experiments")


def load():
    df = pd.read_parquet(PROCESSED_DIR / "bloom.parquet")
    df["date"] = pd.to_datetime(df["date"])
    algae = pd.read_csv(RAW_DIR / "algae_measure.csv", parse_dates=["chck_de"])
    truth = algae.groupby(["station_id", "chck_de"])["iem_bgalage_cell_co"].mean().rename("_truth")
    # 자체 채점 전용 열. 허용 목록에 없어 입력으로 쓰일 수 없다(feature_columns 가 보장).
    df = df.join(truth, on=["station_id", "target_date"])
    df.loc[~df["is_test"], "_truth"] = df["target_cells"]
    return df


def prepare(df, strategy, tr, dynamics):
    d = apply_missing_strategy(df, strategy, tr)
    if dynamics:
        d = add_dynamics_features(d, tr)
    return d, feature_columns(d)


def fit_predict(
    d, cols, tr, va, rounds, seeds=(DEFAULT_PARAMS["seed"],), objective=None, alpha=None
):
    x_tr, cats = to_matrix(d[tr], cols)
    x_va, _ = to_matrix(d[va], cols, cats)
    y = d.loc[tr, "log10_target_cells"].to_numpy()
    preds = []
    for sd in seeds:
        params = {"seed": sd}
        if objective:
            params["objective"] = objective
        if alpha is not None:
            params["alpha"] = alpha
        m = fit_lgb(x_tr, y, params=params, num_rounds=rounds)
        preds.append(m.predict(x_va))
    return np.mean(preds, axis=0)


def run_variant(variant, df, strategy, rounds, tr, va):
    d, cols = prepare(df, strategy, tr, variant == "dynamics")
    if variant == "drop_dchn_early":
        tr = tr & ~(df["station_id"].eq("DCHN") & (df["year"] < 2016))
    extra = {}
    if variant == "per_station":
        pl = pd.Series(np.nan, index=d.index[va])
        for sid in d.loc[va, "station_id"].unique():
            tr_s, va_s = tr & d["station_id"].eq(sid), va & d["station_id"].eq(sid)
            if tr_s.sum() < 100:
                tr_s = tr
            pl[d.index[va_s]] = fit_predict(d, cols, tr_s, va_s, rounds)
        pl = pl.to_numpy()
    elif variant == "ensemble5":
        pl = fit_predict(d, cols, tr, va, rounds, seeds=(1, 2, 3, 4, 5))
    elif variant == "quantile":
        pl = fit_predict(d, cols, tr, va, rounds)
        lo = fit_predict(d, cols, tr, va, rounds, objective="quantile", alpha=0.1)
        hi = fit_predict(d, cols, tr, va, rounds, objective="quantile", alpha=0.9)
        yv = d.loc[va, "log10_target_cells"].to_numpy()
        ok = ~np.isnan(yv)
        extra = {
            "q10_q90_coverage": float(np.mean((yv[ok] >= lo[ok]) & (yv[ok] <= hi[ok]))),
            "q10_q90_width_log10": float(np.mean(hi[ok] - lo[ok])),
        }
    else:
        pl = fit_predict(d, cols, tr, va, rounds)
    pred = np.clip(10**pl - 1, 0, None)
    m = bloom_metrics(d.loc[va, "_truth"], pred)
    sub = d.loc[va, "month"].between(5, 10).to_numpy()
    m["rmse_log10_may_oct"] = bloom_metrics(d.loc[va, "_truth"][sub], pred[sub])["rmse_log10"]
    return {**m, **extra}


def main() -> None:
    set_seed()
    df = load()
    meta = json.loads((MODELS_DIR / "train_meta.json").read_text(encoding="utf-8"))
    strategy, rounds = meta["strategy"], int(meta["best_iter"])
    labeled = df["target_valid"]
    sets = {
        "valid2025": (labeled & df["split"].eq("train"), labeled & df["split"].eq("valid")),
        "roll2022": (labeled & (df["year"] < 2022), labeled & (df["year"] == 2022)),
        "roll2023": (labeled & (df["year"] < 2023), labeled & (df["year"] == 2023)),
        "test2026*": (labeled & df["split"].isin(["train", "valid"]), df["is_test"]),
    }
    rows = []
    for variant in ["base", "dynamics", "per_station", "drop_dchn_early", "ensemble5", "quantile"]:
        for name, (tr, va) in sets.items():
            r = run_variant(variant, df, strategy, rounds, tr, va)
            rows.append({"variant": variant, "set": name, **r})
            log.info(
                "%-16s %-10s rmse_log10 %.3f  R² %.3f  F1 %.3f",
                variant,
                name,
                r["rmse_log10"],
                r["r2"],
                r["f1_over_threshold"],
            )
    res = pd.DataFrame(rows)
    res.to_csv(REPORTS_DIR / "experiments.csv", index=False, encoding="utf-8-sig")
    pd.set_option("display.width", 200, "display.float_format", "{:,.3f}".format)
    for k in ("rmse_log10", "r2", "f1_over_threshold"):
        print(f"\n## {k}")
        print(res.pivot(index="variant", columns="set", values=k).round(3).to_string())
    q = res[res["variant"] == "quantile"][["set", "q10_q90_coverage", "q10_q90_width_log10"]]
    print("\n## 예측 구간(q10~q90) 포함률·폭")
    print(q.to_string(index=False))


if __name__ == "__main__":
    main()
