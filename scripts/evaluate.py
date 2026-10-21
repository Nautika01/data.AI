"""저장된 검증 예측(reports/pred_valid_2025.csv)과 metrics.csv 를 표로 정리해 출력한다."""

from __future__ import annotations

import pandas as pd

from data_ai.config import REPORTS_DIR
from data_ai.evaluate import bloom_metrics


def main() -> None:
    pd.set_option(
        "display.width", 200, "display.max_columns", 20, "display.float_format", "{:,.3f}".format
    )
    m = pd.read_csv(REPORTS_DIR / "metrics.csv")
    print("## 결측 전략 비교 (검증 2025, 전체)")
    print(
        m[(m["subset"] == "all") & m["set"].str.startswith("valid2025")][
            [
                "strategy",
                "n",
                "rmse_log10",
                "mae_log10",
                "r2",
                "r2_pearson",
                "nse",
                "f1_over_threshold",
            ]
        ].to_string(index=False)
    )
    print("\n## 롤링 검증 (선택 전략)")
    print(
        m[m["set"].str.startswith("rolling") & (m["subset"].isin(["all", "may_oct"]))][
            ["set", "subset", "n", "rmse_log10", "r2", "r2_pearson", "nse", "f1_over_threshold"]
        ].to_string(index=False)
    )
    pv = pd.read_csv(REPORTS_DIR / "pred_valid_2025.csv")
    print("\n## 검증 2025 — 전체 / 5~10월 / 지점별")
    rows = [
        {"subset": "all", **bloom_metrics(pv["target_cells"], pv["pred_cells"])},
        {
            "subset": "may_oct",
            **bloom_metrics(
                pv.loc[pv["month"].between(5, 10), "target_cells"],
                pv.loc[pv["month"].between(5, 10), "pred_cells"],
            ),
        },
    ]
    rows += [
        {"subset": n, **bloom_metrics(g["target_cells"], g["pred_cells"])}
        for n, g in pv.groupby("station_name")
    ]
    print(pd.DataFrame(rows).to_string(index=False))
    fi = pd.read_csv(REPORTS_DIR / "feature_importance_valid.csv")
    print("\n## 피처 중요도 상위 15 (gain)")
    print(fi.head(15).to_string(index=False))


if __name__ == "__main__":
    main()
