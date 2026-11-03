"""보고서 그림 생성 → reports/figures/. `make train` 산출물(models/, reports/*.csv)이 있어야 한다.

- fig_importance_top20.png    최종 모델 피처 중요도(gain) 상위 20
- fig_valid2025_scatter.png   검증 2025 실측 vs 예측 (log10), 경보 기준선
- fig_valid2025_timeseries.png 검증 2025 지점별 실측·예측 시계열
- fig_metrics_by_split.png    검증·롤링 구간별 rmse_log10 (persistence 기준선 포함)
- fig_submission_2026.png     2026 평가 조합 예측 시계열 (제출값)
"""

from __future__ import annotations

import matplotlib.pyplot as plt
import numpy as np
import pandas as pd

from data_ai.bloom import ALERT_THRESHOLDS
from data_ai.config import FIGURES_DIR, RAW_DIR, REPORTS_DIR, ensure_dirs
from data_ai.utils import get_logger, set_seed
from data_ai.viz import apply_style

log = get_logger("figures")
STATION_NAMES = {
    "HP": "해평",
    "GJGR": "강정·고령",
    "CS": "칠서",
    "MGMR": "물금·매리",
    "DCHN": "회남",
}


def _save(fig, name: str) -> None:
    path = FIGURES_DIR / name
    fig.savefig(path)
    plt.close(fig)
    log.info("저장: %s", path)


def fig_importance() -> None:
    fi = pd.read_csv(REPORTS_DIR / "feature_importance_final.csv").head(20).iloc[::-1]
    fig, ax = plt.subplots(figsize=(7, 6))
    ax.barh(fi["feature"], fi["gain"])
    ax.set_xlabel("gain")
    ax.set_title("최종 모델 피처 중요도 상위 20")
    _save(fig, "fig_importance_top20.png")


def fig_valid_scatter(pv: pd.DataFrame) -> None:
    y, p = np.log10(pv["target_cells"] + 1), np.log10(pv["pred_cells"] + 1)
    fig, ax = plt.subplots(figsize=(5.5, 5.5))
    for sid, g in pv.groupby("station_id"):
        ax.scatter(
            np.log10(g["target_cells"] + 1),
            np.log10(g["pred_cells"] + 1),
            s=18,
            alpha=0.7,
            label=STATION_NAMES.get(sid, sid),
        )
    lim = (0, max(y.max(), p.max()) + 0.3)
    ax.plot(lim, lim, color="#888", linewidth=1, linestyle="--")
    t = np.log10(ALERT_THRESHOLDS["경계"] + 1)
    ax.axvline(t, color="#b55", linewidth=0.8, linestyle=":")
    ax.axhline(t, color="#b55", linewidth=0.8, linestyle=":")
    ax.set_xlim(lim)
    ax.set_ylim(lim)
    ax.set_xlabel("실측 log10(세포수+1)")
    ax.set_ylabel("예측 log10(세포수+1)")
    ax.set_title("검증 2025: 실측 vs 예측 (점선 = 10,000 cells/mL)")
    ax.legend(fontsize=8)
    _save(fig, "fig_valid2025_scatter.png")


def fig_valid_timeseries(pv: pd.DataFrame) -> None:
    sids = [s for s in STATION_NAMES if s in set(pv["station_id"])]
    fig, axes = plt.subplots(len(sids), 1, figsize=(9, 2.2 * len(sids)), sharex=True)
    for ax, sid in zip(np.atleast_1d(axes), sids, strict=True):
        g = pv[pv["station_id"] == sid].sort_values("target_date")
        ax.plot(g["target_date"], g["target_cells"] + 1, marker="o", label="실측")
        ax.plot(g["target_date"], g["pred_cells"] + 1, marker="x", label="예측")
        ax.axhline(ALERT_THRESHOLDS["경계"], color="#b55", linewidth=0.8, linestyle=":")
        ax.set_yscale("log")
        ax.set_ylabel("cells/mL")
        ax.set_title(STATION_NAMES[sid], loc="left", fontsize=10)
    np.atleast_1d(axes)[0].legend(fontsize=8, loc="upper left")
    fig.suptitle("검증 2025: 정답 측정일 기준 실측·예측 (점선 = 경계 10,000)")
    _save(fig, "fig_valid2025_timeseries.png")


def fig_metrics() -> None:
    m = pd.read_csv(REPORTS_DIR / "metrics.csv")
    m = m[m["subset"] == "all"]
    chosen = m.loc[m["set"].str.startswith("rolling"), "strategy"].iloc[0]
    rows = m[m["set"].eq(f"valid2025/{chosen}") | m["set"].str.startswith("rolling2022")]
    rows = pd.concat([rows, m[m["set"].str.startswith("rolling2023")]])
    labels = ["검증 2025", "롤링 2022", "롤링 2023"]
    vals = rows["rmse_log10"].to_numpy()[: len(labels)]
    base = pd.read_csv(REPORTS_DIR / "baseline_valid_2025.csv")
    pers = float(
        base.loc[base.iloc[:, 0].astype(str).str.contains("persistence"), "rmse_log10"].iloc[0]
    )
    fig, ax = plt.subplots(figsize=(6, 3.8))
    ax.bar(labels, vals)
    ax.axhline(pers, color="#b55", linestyle="--", linewidth=1)
    ax.text(
        len(labels) - 0.5,
        pers + 0.01,
        f"persistence (검증 2025) {pers:.3f}",
        ha="right",
        fontsize=8,
    )
    for i, v in enumerate(vals):
        ax.text(i, v + 0.01, f"{v:.3f}", ha="center", fontsize=9)
    ax.set_ylabel("rmse_log10 (낮을수록 좋음)")
    ax.set_ylim(0, max(vals.max(), pers) + 0.12)
    ax.set_title(f"구간별 오차 (결측 전략 {chosen})")
    _save(fig, "fig_metrics_by_split.png")


def fig_submission() -> None:
    sub = pd.read_csv(REPORTS_DIR / "submission.csv", parse_dates=["base_date", "target_date"])
    sids = [s for s in STATION_NAMES if s in set(sub["station_id"])]
    fig, axes = plt.subplots(len(sids), 1, figsize=(9, 2.0 * len(sids)), sharex=True)
    for ax, sid in zip(np.atleast_1d(axes), sids, strict=True):
        g = sub[sub["station_id"] == sid].sort_values("target_date")
        ax.plot(g["target_date"], g["pred_cells"] + 1, marker="o")
        ax.axhline(ALERT_THRESHOLDS["경계"], color="#b55", linewidth=0.8, linestyle=":")
        ax.set_yscale("log")
        ax.set_ylabel("cells/mL")
        ax.set_title(STATION_NAMES[sid], loc="left", fontsize=10)
    fig.suptitle("2026년 5~10월 평가 조합 예측값 (제출 파일)")
    _save(fig, "fig_submission_2026.png")


def main() -> None:
    set_seed()
    ensure_dirs()
    apply_style()
    pv = pd.read_csv(REPORTS_DIR / "pred_valid_2025.csv", parse_dates=["date", "target_date"])
    fig_importance()
    fig_valid_scatter(pv)
    fig_valid_timeseries(pv)
    fig_metrics()
    fig_submission()
    assert (RAW_DIR / "sample_submission.csv").exists()
    log.info("완료: %s", FIGURES_DIR)


if __name__ == "__main__":
    main()
