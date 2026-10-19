"""피처 엔지니어링 공통 함수."""

from __future__ import annotations

from collections.abc import Iterable

import pandas as pd


def add_time_features(df: pd.DataFrame, time_col: str) -> pd.DataFrame:
    """datetime 컬럼에서 연·월·일·시·요일·주말 여부를 파생한다."""
    out = df.copy()
    t = pd.to_datetime(out[time_col])
    out[f"{time_col}_year"] = t.dt.year
    out[f"{time_col}_month"] = t.dt.month
    out[f"{time_col}_day"] = t.dt.day
    out[f"{time_col}_hour"] = t.dt.hour
    out[f"{time_col}_dow"] = t.dt.dayofweek
    out[f"{time_col}_is_weekend"] = (t.dt.dayofweek >= 5).astype(int)
    return out


def add_lag_features(
    df: pd.DataFrame,
    cols: Iterable[str],
    lags: Iterable[int],
    group_col: str | None = None,
) -> pd.DataFrame:
    """시계열 예측용 지연(lag) 피처를 추가한다. 반드시 시간순 정렬 후 호출한다."""
    out = df.copy()
    for col in cols:
        for lag in lags:
            name = f"{col}_lag{lag}"
            if group_col:
                out[name] = out.groupby(group_col)[col].shift(lag)
            else:
                out[name] = out[col].shift(lag)
    return out


def add_rolling_features(
    df: pd.DataFrame,
    cols: Iterable[str],
    windows: Iterable[int],
    group_col: str | None = None,
) -> pd.DataFrame:
    """이동 평균·표준편차 피처를 추가한다(현재 시점 제외, shift(1))."""
    out = df.copy()
    for col in cols:
        series = out.groupby(group_col)[col] if group_col else out[col]
        for w in windows:
            shifted = series.shift(1)
            out[f"{col}_rmean{w}"] = (
                shifted.rolling(w, min_periods=1).mean().reset_index(level=0, drop=True)
                if group_col
                else shifted.rolling(w, min_periods=1).mean()
            )
            out[f"{col}_rstd{w}"] = (
                shifted.rolling(w, min_periods=2).std().reset_index(level=0, drop=True)
                if group_col
                else shifted.rolling(w, min_periods=2).std()
            )
    return out
