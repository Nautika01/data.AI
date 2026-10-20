"""3차 실험: 아직 쓰지 않은 정보와 평가 구간 분포 적합. reports/experiments_round3.csv 에 기록.

변형
- base            기준(train.py 설정)
- lagdays         정답 측정일 간격(lag_days) 입력 추가 — 제출 양식 target_date 로 기준일에 아는 정보
- season_only     5~10월 기준일만 학습
- season_weight   5~10월 기준일 가중 3배
- recency         최근 연도 가중 (0.85^(기준연도−해당연도))
- hurdle_mix      P(정답≥10,000) 분류 × 구간별 회귀, 로그 공간 기대값
- hurdle_switch   분류 확률 0.5 기준으로 저농도/고농도 회귀 중 택일
- hpo_best        무작위 탐색 24개 조합 중 세 검증 평균 rmse_log10 최소 조합

평가: valid2025(공식), roll2022, roll2023, test2026*(번들 실측 자체 채점 참고값, 선택에 미사용)
"""

from __future__ import annotations

import itertools
import json

import numpy as np
import pandas as pd

from data_ai.config import MODELS_DIR, PROCESSED_DIR, RAW_DIR, REPORTS_DIR
from data_ai.evaluate import bloom_metrics
from data_ai.features import apply_missing_strategy, feature_columns, to_matrix
from data_ai.models import fit_lgb
from data_ai.utils import get_logger, set_seed

log = get_logger("experiments3")
THRESH_LOG = np.log10(10_000 + 1)


def load():
    df = pd.read_parquet(PROCESSED_DIR / "bloom.parquet")
    df["date"] = pd.to_datetime(df["date"])
    algae = pd.read_csv(RAW_DIR / "algae_measure.csv", parse_dates=["chck_de"])
    truth = algae.groupby(["station_id", "chck_de"])["iem_bgalage_cell_co"].mean().rename("_truth")
    df = df.join(truth, on=["station_id", "target_date"])  # 자체 채점 전용(허용 목록 밖)
    df.loc[~df["is_test"], "_truth"] = df["target_cells"]
    return df


def matrices(d, cols, tr, va):
    x_tr, cats = to_matrix(d[tr], cols)
    x_va, _ = to_matrix(d[va], cols, cats)
    return x_tr, x_va, d.loc[tr, "log10_target_cells"].to_numpy()


def predict_log(x_tr, y, x_va, rounds, params=None, weight=None):
    m = fit_lgb(x_tr, y, params=params, num_rounds=rounds, weight=weight)
    return m.predict(x_va)


def run_variant(variant, df, strategy, rounds, tr, va, hp=None):
    d = apply_missing_strategy(df, strategy, tr)
    extra = ("lag_days",) if variant == "lagdays" else ()
    cols = feature_columns(d, extra=extra)
    weight = None
    if variant == "season_only":
        tr = tr & d["month"].between(5, 10)
    elif variant == "season_weight":
        weight = np.where(d.loc[tr, "month"].between(5, 10), 3.0, 1.0)
    elif variant == "recency":
        ref = int(d.loc[tr, "year"].max())
        weight = 0.85 ** (ref - d.loc[tr, "year"].to_numpy())
    x_tr, x_va, y = matrices(d, cols, tr, va)

    if variant.startswith("hurdle"):
        hi_tr = y >= THRESH_LOG
        clf = fit_lgb(x_tr, hi_tr.astype(int), params={"objective": "binary"}, num_rounds=rounds)
        p_hi = clf.predict(x_va)
        lo = predict_log(x_tr[~hi_tr], y[~hi_tr], x_va, rounds)
        hi = predict_log(x_tr[hi_tr], y[hi_tr], x_va, max(rounds // 2, 50))
        pl = (
            p_hi * hi + (1 - p_hi) * lo
            if variant == "hurdle_mix"
            else np.where(p_hi >= 0.5, hi, lo)
        )
    elif variant == "hpo_best":
        pl = predict_log(x_tr, y, x_va, hp["rounds"], params=hp["params"])
    else:
        pl = predict_log(x_tr, y, x_va, rounds, weight=weight)
    pred = np.clip(10**pl - 1, 0, None)
    m = bloom_metrics(d.loc[va, "_truth"], pred)
    sub = d.loc[va, "month"].between(5, 10).to_numpy()
    m["rmse_log10_may_oct"] = bloom_metrics(d.loc[va, "_truth"][sub], pred[sub])["rmse_log10"]
    return m


def hpo(df, strategy, sets, n_trials=24, seed=42):
    """무작위 탐색. 선택 기준은 valid2025·roll2022·roll2023 rmse_log10 평균(test 미사용)."""
    cache = REPORTS_DIR / "hpo_round3.csv"
    rng = np.random.default_rng(seed)
    grid = {
        "num_leaves": [7, 15, 31],
        "min_child_samples": [10, 20, 40],
        "learning_rate": [0.02, 0.05],
        "feature_fraction": [0.6, 0.8, 1.0],
        "lambda_l2": [0.0, 1.0, 5.0],
    }
    combos = list(itertools.product(*grid.values()))
    idx = rng.choice(len(combos), size=min(n_trials, len(combos)), replace=False)
    results = []
    if cache.exists():
        res = pd.read_csv(cache).sort_values("mean_rmse_log10")
        log.info("HPO 결과 캐시 사용: %s", cache)
        idx = []
    for i in idx:
        params = dict(zip(grid.keys(), combos[i], strict=True))
        rounds = int(131 * 0.03 / params["learning_rate"])
        scores = []
        for name in ("valid2025", "roll2022", "roll2023"):
            tr, va = sets[name]
            d = apply_missing_strategy(df, strategy, tr)
            cols = feature_columns(d)
            x_tr, x_va, y = matrices(d, cols, tr, va)
            pl = predict_log(x_tr, y, x_va, rounds, params=params)
            scores.append(
                bloom_metrics(d.loc[va, "_truth"], np.clip(10**pl - 1, 0, None))["rmse_log10"]
            )
        results.append({**params, "rounds": rounds, "mean_rmse_log10": float(np.mean(scores))})
        log.info("hpo %s → %.4f", params, np.mean(scores))
    if results:
        res = pd.DataFrame(results).sort_values("mean_rmse_log10")
        res.to_csv(cache, index=False, encoding="utf-8-sig")
    best = res.iloc[0]
    int_keys = ("num_leaves", "min_child_samples")
    params = {k: (int(best[k]) if k in int_keys else float(best[k])) for k in grid}
    return {
        "params": params,
        "rounds": int(best["rounds"]),
        "score": float(best["mean_rmse_log10"]),
    }


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
    hp = hpo(df, strategy, sets)
    log.info("HPO 최적: %s rounds=%d mean=%.4f", hp["params"], hp["rounds"], hp["score"])
    rows = []
    for variant in [
        "base",
        "lagdays",
        "season_only",
        "season_weight",
        "recency",
        "hurdle_mix",
        "hurdle_switch",
        "hpo_best",
    ]:
        for name, (tr, va) in sets.items():
            r = run_variant(variant, df, strategy, rounds, tr, va, hp)
            rows.append({"variant": variant, "set": name, **r})
            log.info(
                "%-14s %-10s rmse_log10 %.3f  R² %.3f  F1 %.3f",
                variant,
                name,
                r["rmse_log10"],
                r["r2"],
                r["f1_over_threshold"],
            )
    res = pd.DataFrame(rows)
    res.to_csv(REPORTS_DIR / "experiments_round3.csv", index=False, encoding="utf-8-sig")
    pd.set_option("display.width", 200, "display.float_format", "{:,.3f}".format)
    for k in ("rmse_log10", "r2", "f1_over_threshold", "rmse_log10_may_oct"):
        print(f"\n## {k}")
        print(res.pivot(index="variant", columns="set", values=k).round(3).to_string())
    print("\nHPO 최적:", hp)


if __name__ == "__main__":
    main()
