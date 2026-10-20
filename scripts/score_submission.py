"""제출 파일을 번들의 실측으로 자체 채점한다 (참고용).

번들 algae_measure.csv 에는 '26년 9월까지 실측이 있어 평가 조합의 정답을 조회할 수 있다.
이 스크립트는 **제출 전 점검용**이며, 실측을 모델 입력이나 예측값에 쓰면 실격이다.

  python scripts/score_submission.py reports/submission.csv
"""

from __future__ import annotations

import argparse
from pathlib import Path

import pandas as pd

from data_ai.config import RAW_DIR
from data_ai.evaluate import bloom_metrics


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("submission", type=Path)
    ap.add_argument("--bundle-dir", type=Path, default=RAW_DIR)
    args = ap.parse_args()

    sub = pd.read_csv(args.submission, parse_dates=["base_date", "target_date"])
    sample = pd.read_csv(
        args.bundle_dir / "sample_submission.csv", parse_dates=["base_date", "target_date"]
    )
    key = ["station_id", "base_date", "target_date"]
    assert list(sub.columns) == ["station_id", "base_date", "target_date", "pred_cells"], (
        "열 구성이 다름"
    )
    assert sub[key].equals(sample[key]), "행 구성·순서가 sample_submission.csv 와 다름"
    assert (sub["pred_cells"] >= 0).all() and (
        sub["pred_cells"] == sub["pred_cells"].round()
    ).all(), "pred_cells 는 0 이상 정수"

    algae = pd.read_csv(args.bundle_dir / "algae_measure.csv", parse_dates=["chck_de"])
    truth = (
        algae.groupby(["station_id", "chck_de"], as_index=False)["iem_bgalage_cell_co"]
        .mean()
        .rename(columns={"chck_de": "target_date", "iem_bgalage_cell_co": "true_cells"})
    )
    s = sub.merge(truth, on=["station_id", "target_date"], how="left")
    missing = s["true_cells"].isna().sum()
    pd.set_option("display.float_format", "{:,.3f}".format)
    print(f"형식 검사 통과: {len(sub)}행. 실측 조회 가능 {len(sub) - missing}행 (결측 {missing})")
    print(pd.Series(bloom_metrics(s["true_cells"], s["pred_cells"])).to_string())
    s["month"] = s["base_date"].dt.month
    print("\n지점별:")
    print(
        pd.DataFrame(
            {
                sid: bloom_metrics(g["true_cells"], g["pred_cells"])
                for sid, g in s.groupby("station_id")
            }
        ).T.to_string()
    )


if __name__ == "__main__":
    main()
