"""LightGBM 학습·검증·예측 파일 생성.

1. 결측 전략 3안을 공식 분할(train ~'24 → valid '25)에서 비교
2. 선택 전략으로 롤링 검증('22·'23·'25: 각 연도 이전 자료만으로 학습) — 안정성 확인
3. train+valid(≤'25) 로 최종 학습 → '26 평가 조합 예측 → reports/submission.csv

규정 준수: 입력은 기준일 포함 과거 자료만(결합 단계에서 보장), test 정답 미사용, 시드 고정.
"""

from __future__ import annotations

import argparse
import json

import numpy as np
import pandas as pd

from data_ai.config import MODELS_DIR, PROCESSED_DIR, REPORTS_DIR, ensure_dirs
from data_ai.evaluate import bloom_metrics
from data_ai.features import STRATEGIES, apply_missing_strategy, feature_columns, to_matrix
from data_ai.models import fit_lgb, importance, predict_cells, save_model
from data_ai.utils import get_logger, set_seed

log = get_logger("train")
ROLLING_YEARS = (2022, 2023, 2025)


def metrics_block(df: pd.DataFrame, pred: np.ndarray, label: str) -> list[dict]:
    """전체 / 5~10월 / 지점별 지표."""
    rows = []
    d = df.assign(pred=pred)
    rows.append({"set": label, "subset": "all", **bloom_metrics(d["target_cells"], d["pred"])})
    s = d[d["month"].between(5, 10)]
    rows.append({"set": label, "subset": "may_oct", **bloom_metrics(s["target_cells"], s["pred"])})
    for sid, g in d.groupby("station_id"):
        rows.append({"set": label, "subset": sid, **bloom_metrics(g["target_cells"], g["pred"])})
    return rows


def run_split(
    df: pd.DataFrame,
    strategy: str,
    train_mask: pd.Series,
    valid_mask: pd.Series,
    label: str,
    num_rounds: int | None = None,
):
    d = apply_missing_strategy(df, strategy, train_mask)
    cols = feature_columns(d)
    x_tr, cats = to_matrix(d[train_mask], cols)
    x_va, _ = to_matrix(d[valid_mask], cols, cats)
    y_tr = d.loc[train_mask, "log10_target_cells"].to_numpy()
    y_va = d.loc[valid_mask, "log10_target_cells"].to_numpy()
    if num_rounds:
        model = fit_lgb(x_tr, y_tr, num_rounds=num_rounds)
    else:
        model = fit_lgb(x_tr, y_tr, x_va, y_va)
    pred = predict_cells(model, x_va)
    return model, pred, metrics_block(d[valid_mask], pred, label), cols, cats


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument(
        "--strategy",
        choices=STRATEGIES,
        default=None,
        help="지정하지 않으면 검증 rmse_log10 최소 전략 선택",
    )
    ap.add_argument("--skip-rolling", action="store_true")
    args = ap.parse_args()
    set_seed()
    ensure_dirs()

    df = pd.read_parquet(PROCESSED_DIR / "bloom.parquet")
    df["date"] = pd.to_datetime(df["date"])
    labeled = df["target_valid"]
    train_mask = labeled & df["split"].eq("train")
    valid_mask = labeled & df["split"].eq("valid")
    log.info(
        "학습 %d행, 검증 %d행, 평가 %d행", train_mask.sum(), valid_mask.sum(), df["is_test"].sum()
    )

    # 1. 결측 전략 비교 (공식 분할)
    results, best = [], {}
    for strategy in STRATEGIES:
        model, pred, rows, cols, cats = run_split(
            df, strategy, train_mask, valid_mask, f"valid2025/{strategy}"
        )
        for r in rows:
            r["strategy"] = strategy
        results += rows
        overall = rows[0]
        best[strategy] = {
            "rmse_log10": overall["rmse_log10"],
            "best_iter": model.best_iteration,
            "n_features": len(cols),
        }
        log.info(
            "전략 %-18s rmse_log10 %.4f  R² %.3f  NSE %.3f  F1 %.3f  (iter %d)",
            strategy,
            overall["rmse_log10"],
            overall["r2"],
            overall["nse"],
            overall["f1_over_threshold"],
            model.best_iteration,
        )
    strategy = args.strategy or min(best, key=lambda k: best[k]["rmse_log10"])
    best_iter = max(int(best[strategy]["best_iter"]), 50)
    log.info("선택 전략: %s (best_iter %d)", strategy, best_iter)

    # 2. 롤링 검증
    if not args.skip_rolling:
        for y in ROLLING_YEARS:
            tr = labeled & (df["year"] < y) & ~df["is_test"]
            va = labeled & (df["year"] == y)
            if va.sum() == 0:
                continue
            _, pred, rows, _, _ = run_split(
                df, strategy, tr, va, f"rolling{y}", num_rounds=best_iter
            )
            for r in rows:
                r["strategy"] = strategy
            results += rows
            log.info(
                "롤링 %d: rmse_log10 %.4f  R² %.3f  NSE %.3f  (n=%d)",
                y,
                rows[0]["rmse_log10"],
                rows[0]["r2"],
                rows[0]["nse"],
                rows[0]["n"],
            )

    # 검증 예측 저장 (evaluate.py 용)
    model_v, pred_v, _, cols, cats = run_split(df, strategy, train_mask, valid_mask, "valid")
    pv = df.loc[
        valid_mask,
        [
            "station_id",
            "station_name",
            "date",
            "target_date",
            "month",
            "cyano_cells",
            "target_cells",
        ],
    ].copy()
    pv["pred_cells"] = pred_v
    pv.to_csv(REPORTS_DIR / "pred_valid_2025.csv", index=False, encoding="utf-8-sig")
    importance(model_v).to_csv(
        REPORTS_DIR / "feature_importance_valid.csv", index=False, encoding="utf-8-sig"
    )

    # 3. 최종 학습 (train+valid) → 평가 조합 예측
    final_mask = labeled & df["split"].isin(["train", "valid"])
    d = apply_missing_strategy(df, strategy, final_mask)
    cols = feature_columns(d)
    x_all, cats = to_matrix(d[final_mask], cols)
    model = fit_lgb(
        x_all, d.loc[final_mask, "log10_target_cells"].to_numpy(), num_rounds=int(best_iter * 1.1)
    )
    test = d[d["is_test"]]
    x_te, _ = to_matrix(test, cols, cats)
    test_pred = predict_cells(model, x_te)
    sub = pd.read_csv(
        PROCESSED_DIR.parent / "raw" / "sample_submission.csv",
        parse_dates=["base_date", "target_date"],
    )
    pred_df = (
        test[["station_id", "date"]]
        .assign(pred_cells=np.rint(test_pred).astype(int))
        .rename(columns={"date": "base_date"})
    )
    out = sub.drop(columns="pred_cells").merge(pred_df, on=["station_id", "base_date"], how="left")
    assert out["pred_cells"].notna().all(), "예측이 비어 있는 평가 조합이 있음"
    for c in ("base_date", "target_date"):
        out[c] = out[c].dt.strftime("%Y-%m-%d")
    out.to_csv(REPORTS_DIR / "submission.csv", index=False, encoding="utf-8")
    save_model(model, "lgb_final")
    importance(model).to_csv(
        REPORTS_DIR / "feature_importance_final.csv", index=False, encoding="utf-8-sig"
    )

    pd.DataFrame(results).to_csv(REPORTS_DIR / "metrics.csv", index=False, encoding="utf-8-sig")
    (MODELS_DIR / "train_meta.json").write_text(
        json.dumps(
            {
                "strategy": strategy,
                "best_iter": best_iter,
                "n_features": len(cols),
                "features": cols,
            },
            ensure_ascii=False,
            indent=2,
        ),
        encoding="utf-8",
    )
    log.info(
        "저장: reports/submission.csv (%d행), reports/metrics.csv, models/lgb_final.joblib",
        len(out),
    )


if __name__ == "__main__":
    main()
