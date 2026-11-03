"""저장된 최종 모델(models/lgb_final.joblib)로 평가 조합을 추론하는 데모·검증 스크립트.

`make train` 이 만든 모델과 train_meta.json 을 읽어 2026년 평가 조합 124건을 다시 예측하고,
reports/submission.csv 와 같은지 확인한다. 학습은 하지 않는다.

    python scripts/predict.py                 # 전체 124건 추론 + 제출 파일과 비교
    python scripts/predict.py --station HP    # 한 지점만 표로 출력
"""

from __future__ import annotations

import argparse
import json

import numpy as np
import pandas as pd

from data_ai.config import MODELS_DIR, PROCESSED_DIR, REPORTS_DIR
from data_ai.features import apply_missing_strategy, feature_columns, to_matrix
from data_ai.models import load_model, predict_cells
from data_ai.utils import get_logger

log = get_logger("predict")


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--station", default=None, help="지점 ID (HP, GJGR, CS, MGMR, DCHN)")
    args = ap.parse_args()

    meta = json.loads((MODELS_DIR / "train_meta.json").read_text(encoding="utf-8"))
    model = load_model("lgb_final")
    log.info(
        "모델: lgb_final.joblib, 결측 전략 %s, 피처 %d개", meta["strategy"], meta["n_features"]
    )

    df = pd.read_parquet(PROCESSED_DIR / "bloom.parquet")
    labeled = df["target_valid"]
    final_mask = labeled & df["split"].isin(["train", "valid"])  # 학습에 쓴 행(결측 통계·범주 기준)
    d = apply_missing_strategy(df, meta["strategy"], final_mask)
    cols = feature_columns(d)
    assert cols == meta["features"], "피처 목록이 학습 시점과 다름"
    _, cats = to_matrix(d[final_mask], cols)

    test = d[d["is_test"]].copy()
    x_te, _ = to_matrix(test, cols, cats)
    test["pred_cells"] = np.rint(predict_cells(model, x_te)).astype(int)
    log.info(
        "추론: 평가 조합 %d건 (기준일 %s ~ %s)",
        len(test),
        test["date"].min().date(),
        test["date"].max().date(),
    )

    sub = pd.read_csv(REPORTS_DIR / "submission.csv", parse_dates=["base_date"])
    chk = sub.merge(
        test[["station_id", "date", "pred_cells"]].rename(columns={"date": "base_date"}),
        on=["station_id", "base_date"],
        suffixes=("_submitted", "_now"),
    )
    n_diff = int((chk["pred_cells_submitted"] != chk["pred_cells_now"]).sum())
    log.info("제출 파일과 비교: %d건 중 불일치 %d건", len(chk), n_diff)

    show = test if args.station is None else test[test["station_id"] == args.station]
    out = show[["station_id", "date", "target_date", "cyano_cells", "current_level", "pred_cells"]]
    out = out.rename(columns={"date": "base_date", "cyano_cells": "base_cells"})
    pd.set_option("display.width", 160)
    print(out.head(30).to_string(index=False))


if __name__ == "__main__":
    main()
