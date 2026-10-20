"""학습용 피처 행렬 구성과 결측 대체 전략."""

from __future__ import annotations

import numpy as np
import pandas as pd

# 입력 허용 목록(allowlist). 여기 없는 열은 입력에 들어가지 않는다 → 정답·식별자 누수 차단.
ALLOW_EXACT = {
    "station_id",
    "dominant_genus",
    "cyano_cells",
    "log10_cells",
    "water_temp",
    "ph",
    "do",
    "transparency",
    "turbidity",
    "chl_a",
    "mc_lr",
    "days_since_prev",
    "current_level",
    "month",
    "doy",
}
ALLOW_PREFIX = ("w_", "d_", "cells_")  # 기상·댐 집계, 속별 세포수·비율
ALLOW_SUFFIX = ("_lag1", "_lag2", "_lag3", "_isna")
CATEGORICAL = ["station_id", "dominant_genus"]
# 결측 대체 대상(수질 항목). 기상·댐 집계는 결측이 거의 없어 그대로 둔다.
WQ_COLS = [
    "cyano_cells",
    "log10_cells",
    "water_temp",
    "ph",
    "do",
    "transparency",
    "turbidity",
    "chl_a",
    "cells_microcystis_share",
    "cells_anabaena_share",
    "cells_oscillatoria_share",
    "cells_aphanizomenon_share",
]
STRATEGIES = ("native", "ffill_flag", "site_month_median")


def feature_columns(df: pd.DataFrame) -> list[str]:
    """허용 목록에 있는 열만 입력으로 쓴다. target·split·날짜·식별자는 목록에 없으므로 자동 제외."""
    cols = []
    for c in df.columns:
        ok = c in ALLOW_EXACT or c.startswith(ALLOW_PREFIX) or c.endswith(ALLOW_SUFFIX)
        if ok and (c in CATEGORICAL or pd.api.types.is_numeric_dtype(df[c])):
            cols.append(c)
    forbidden = [c for c in cols if "target" in c or c in ("split", "date", "true_cells")]
    assert not forbidden, f"정답 관련 열이 입력에 포함됨: {forbidden}"
    return cols


def apply_missing_strategy(df: pd.DataFrame, strategy: str, train_mask: pd.Series) -> pd.DataFrame:
    """결측 대체 전략을 적용한 복사본을 반환한다. 통계값은 train_mask 행에서만 계산한다(누수 방지).

    - native: 그대로 둠(LightGBM 기본 결측 처리)
    - ffill_flag: 수질 항목을 직전 측정값(lag1)으로 채우고, 채웠는지 표시하는 *_isna 열 추가
    - site_month_median: 수질 항목을 (지점, 월) 학습 구간 중앙값으로 채우고 *_isna 열 추가
    """
    if strategy not in STRATEGIES:
        raise ValueError(f"알 수 없는 전략: {strategy} (가능: {STRATEGIES})")
    out = df.copy()
    if strategy == "native":
        return out
    cols = [c for c in WQ_COLS if c in out.columns]
    for c in cols:
        out[f"{c}_isna"] = out[c].isna().astype(int)
    if strategy == "ffill_flag":
        for c in cols:
            lag = f"{c}_lag1"
            if lag in out.columns:
                out[c] = out[c].fillna(out[lag])
            elif c == "log10_cells" and "cyano_cells_lag1" in out.columns:
                out[c] = out[c].fillna(np.log10(out["cyano_cells_lag1"] + 1))
        # lag 로도 못 채운 값은 지점·월 중앙값으로 마무리
        strategy = "site_month_median"
    if strategy == "site_month_median":
        med = out[train_mask].groupby(["station_id", "month"])[cols].median()
        glob = out[train_mask][cols].median()
        filled = out[["station_id", "month"]].join(med, on=["station_id", "month"])[cols]
        for c in cols:
            out[c] = out[c].fillna(filled[c]).fillna(glob[c])
    return out


def to_matrix(df: pd.DataFrame, cols: list[str], categories: dict[str, list] | None = None):
    """LightGBM 입력용 DataFrame. 범주형은 고정된 category 목록으로 변환한다."""
    x = df[cols].copy()
    categories = categories or {}
    for c in CATEGORICAL:
        if c in x.columns:
            cats = categories.get(c) or sorted(x[c].dropna().astype(str).unique())
            x[c] = pd.Categorical(x[c].astype(str).where(x[c].notna(), None), categories=cats)
            categories[c] = cats
    return x, categories
