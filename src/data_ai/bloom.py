"""녹조(유해남조류) 7일 예측용 데이터 결합.

공식 과제 정의(2026-10-15 개정):
- 기준일(base_date)은 실제 측정이 있는 날짜. 정답은 base_date+7일에 가장 가까운 측정값(±3일 이내).
- 예측 대상 iem_bgalage_cell_co(유해남조류 세포수 합계, cells/mL) → 표준 열 이름 cyano_cells.
- 분할: ~2024 학습 / 2025 검증 / 2026 평가. 기준일 이후 관측값 사용 금지.

흐름: 조류경보제(비정기·주간) ← 지점 매핑표 ← 기상(일) 과거 N일 집계 ← 댐 운영(일) 과거 N일 집계
→ 정답·분할 열을 붙여 data/processed/bloom.parquet 저장.
"""

from __future__ import annotations

from collections.abc import Iterable
from pathlib import Path

import numpy as np
import pandas as pd
import yaml

from data_ai.config import EXTERNAL_DIR, RAW_DIR
from data_ai.utils import get_logger

log = get_logger(__name__)

# 조류경보제 발령 기준 (cells/mL)
ALERT_THRESHOLDS = {"관심": 1_000, "경계": 10_000, "대발생": 1_000_000}
ALERT_LEVELS = ["정상", "관심", "경계", "대발생"]
ID_COLS = {"site_name", "site_code", "site_id", "site_type", "dam_name", "asos_id"}
SITE_KEY = "site_code"
ENCODINGS = ("utf-8-sig", "cp949", "euc-kr")


def load_config(path: str | Path) -> dict:
    with open(path, encoding="utf-8") as f:
        return yaml.safe_load(f)


def read_csv_any(path: str | Path, **kwargs) -> pd.DataFrame:
    """utf-8 → cp949 → euc-kr 순으로 인코딩을 바꿔 가며 CSV를 읽는다."""
    last: Exception | None = None
    for enc in ENCODINGS:
        try:
            return pd.read_csv(path, encoding=enc, **kwargs)
        except UnicodeDecodeError as e:
            last = e
    raise ValueError(f"인코딩을 판별할 수 없음: {path}") from last


def alert_level(cells: pd.Series | np.ndarray) -> pd.Series:
    """남조류 세포수 → 경보 단계 코드 (0 정상, 1 관심, 2 경계, 3 대발생). NaN은 NaN."""
    c = pd.Series(np.asarray(cells, dtype=float))
    level = np.select(
        [
            c >= ALERT_THRESHOLDS["대발생"],
            c >= ALERT_THRESHOLDS["경계"],
            c >= ALERT_THRESHOLDS["관심"],
        ],
        [3, 2, 1],
        default=0,
    ).astype(float)
    level[c.isna().to_numpy()] = np.nan
    return pd.Series(level, index=c.index)


def standardize(df: pd.DataFrame, mapping: dict[str, str], date_col: str = "date") -> pd.DataFrame:
    """원본 열 이름을 표준 이름으로 바꾸고, 날짜·숫자형을 정리한다."""
    df = df.copy()
    df.columns = [str(c).strip() for c in df.columns]
    missing = [raw for raw in mapping if raw not in df.columns]
    if missing:
        log.warning("매핑에 있으나 파일에 없는 열: %s", missing)
    present = {raw: std for raw, std in mapping.items() if raw in df.columns}
    df = df[list(present)].rename(columns=present)
    if date_col not in df.columns:
        raise ValueError(f"날짜 열({date_col})을 찾을 수 없습니다. mapping을 확인하세요.")
    df[date_col] = pd.to_datetime(df[date_col], errors="coerce").dt.normalize()
    df = df.dropna(subset=[date_col])
    for col in df.columns:
        if col == date_col:
            continue
        if col in ID_COLS:
            df[col] = df[col].astype(str).str.strip()
        else:
            df[col] = pd.to_numeric(
                df[col].astype(str).str.replace(",", "", regex=False).str.strip(),
                errors="coerce",
            )
    return df


def daily_window_features(
    df: pd.DataFrame,
    key: str,
    aggs: dict[str, Iterable[str]],
    windows: Iterable[int],
    date_col: str = "date",
) -> pd.DataFrame:
    """키별 일 자료를 빠진 날짜 없이 채운 뒤, 각 날짜 기준 과거 N일 집계를 만든다.

    결과 열 이름: ``{col}_{agg}{N}d`` (예: precip_sum7d). 현재 날짜를 포함한 과거 N일이다.
    """
    windows = list(windows)
    out = []
    for k, g in df.groupby(key, sort=False):
        g = g.drop_duplicates(subset=[date_col]).set_index(date_col).sort_index()
        g = g.asfreq("D")
        feats = {key: k}
        frame = pd.DataFrame(index=g.index)
        for col, funcs in aggs.items():
            if col not in g.columns:
                log.warning("집계 대상 열 없음: %s (키=%s)", col, k)
                continue
            frame[col] = g[col]  # 당일 값
            for w in windows:
                roll = g[col].rolling(w, min_periods=max(1, w // 2))
                for fn in funcs:
                    frame[f"{col}_{fn}{w}d"] = getattr(roll, fn)()
        frame = frame.reset_index().rename(columns={"index": date_col})
        for c, v in feats.items():
            frame[c] = v
        out.append(frame)
    if not out:
        return pd.DataFrame(columns=[key, date_col])
    return pd.concat(out, ignore_index=True)


def merge_asof_by(
    left: pd.DataFrame,
    right: pd.DataFrame,
    key: str,
    tolerance_days: int,
    date_col: str = "date",
) -> pd.DataFrame:
    """키별로 가장 가까운 과거 날짜의 오른쪽 행을 붙인다(허용 오차 내)."""
    left = left.copy()
    right = right.copy()
    left["_order"] = np.arange(len(left))
    has_key = left[key].notna()
    l_in = left[has_key].sort_values(date_col)
    r = right.dropna(subset=[key]).sort_values(date_col)
    l_in[key] = l_in[key].astype(str)
    r[key] = r[key].astype(str)
    merged = pd.merge_asof(
        l_in,
        r,
        on=date_col,
        by=key,
        direction="backward",
        tolerance=pd.Timedelta(days=tolerance_days),
    )
    result = pd.concat([merged, left[~has_key]], ignore_index=True).sort_values("_order")
    return result.drop(columns="_order").reset_index(drop=True)


def add_targets(
    df: pd.DataFrame,
    horizon_days: int = 7,
    tolerance_days: int = 3,
    site_col: str = SITE_KEY,
    date_col: str = "date",
) -> pd.DataFrame:
    """기준일 + horizon 일에 가장 가까운 측정값(±tolerance 일)을 정답으로 붙인다.

    공식 규칙: 범위 안에 측정이 없거나 정답 세포수가 결측이면 채점 제외 → target_valid=False.
    """
    df = df.sort_values([site_col, date_col]).reset_index(drop=True)
    df["anchor"] = df[date_col] + pd.Timedelta(days=horizon_days)
    right = df[[site_col, date_col, "cyano_cells"]].rename(
        columns={date_col: "target_date", "cyano_cells": "target_cells"}
    )
    right["anchor"] = right["target_date"]
    out = pd.merge_asof(
        df.sort_values("anchor"),
        right.sort_values("anchor"),
        on="anchor",
        by=site_col,
        direction="nearest",
        tolerance=pd.Timedelta(days=tolerance_days),
    )
    out = out.sort_values([site_col, date_col]).reset_index(drop=True).drop(columns="anchor")
    out["target_gap_days"] = (out["target_date"] - out[date_col]).dt.days
    out["target_valid"] = out["target_cells"].notna()
    out["days_since_prev"] = (
        out[date_col] - out.groupby(site_col, sort=False)[date_col].shift(1)
    ).dt.days
    out["prev_cells"] = out.groupby(site_col, sort=False)["cyano_cells"].shift(1)
    out["current_level"] = alert_level(out["cyano_cells"])
    out["target_level"] = alert_level(out["target_cells"])
    out["log10_cells"] = np.log10(out["cyano_cells"] + 1)
    out["log10_target_cells"] = np.log10(out["target_cells"] + 1)
    return out


def add_split(df: pd.DataFrame, train_max_year: int = 2024, valid_year: int = 2025) -> pd.DataFrame:
    """공식 분할 열 추가: train(~train_max_year) / valid(valid_year) / test(그 이후)."""
    year = df["date"].dt.year
    df = df.copy()
    df["split"] = np.select(
        [year <= train_max_year, year == valid_year], ["train", "valid"], "test"
    )
    return df


def build_dataset(
    cfg: dict,
    raw_dir: Path = RAW_DIR,
    external_dir: Path = EXTERNAL_DIR,
) -> pd.DataFrame:
    """설정에 따라 조류경보제 + 기상 + 댐 운영 자료를 결합한 학습용 테이블을 만든다."""
    # 1. 지점 매핑표
    sites = read_csv_any(external_dir / cfg["sites_file"])
    sites.columns = [c.strip() for c in sites.columns]
    for c in ("site_code", "site_name", "asos_id", "dam_name"):
        if c in sites.columns:
            sites[c] = sites[c].astype("string").str.strip()
    sites.loc[sites["dam_name"].isin(["", "nan", "<NA>"]), "dam_name"] = pd.NA
    log.info("지점 매핑표: %d개 지점", len(sites))

    # 2. 조류경보제
    a_cfg = cfg["algae"]
    algae = standardize(read_csv_any(raw_dir / a_cfg["file"]), a_cfg["mapping"])
    n_before = len(algae)
    key = SITE_KEY if SITE_KEY in algae.columns else "site_name"
    algae = (
        algae.groupby([key, "date"], as_index=False)
        .mean(numeric_only=True)
        .sort_values([key, "date"])
    )
    log.info("조류경보제: %d행 → 지점·날짜 중복 평균 후 %d행 (키=%s)", n_before, len(algae), key)
    unknown = sorted(set(algae[key]) - set(sites[key]))
    if unknown:
        log.warning("매핑표에 없는 지점(제외됨): %s", unknown)
    merged = algae.merge(sites, on=key, how="inner")
    if SITE_KEY not in merged.columns:
        merged[SITE_KEY] = merged["site_name"]

    # 3. 기상
    w_cfg = cfg["weather"]
    weather = standardize(read_csv_any(external_dir / w_cfg["file"]), w_cfg["mapping"])
    wfeat = daily_window_features(weather, w_cfg["key"], w_cfg["aggs"], w_cfg["windows"])
    wfeat = wfeat.rename(
        columns={c: f"w_{c}" for c in wfeat.columns if c not in (w_cfg["key"], "date")}
    )
    merged = merge_asof_by(merged, wfeat, w_cfg["key"], w_cfg["tolerance_days"])
    log.info(
        "기상 결합: %d행, 기상 결측 %.1f%%", len(merged), merged["w_temp_mean"].isna().mean() * 100
    )

    # 4. 댐 운영
    d_cfg = cfg["dam"]
    dam_path = external_dir / d_cfg["file"]
    if dam_path.exists():
        dam = standardize(read_csv_any(dam_path), d_cfg["mapping"])
        dfeat = daily_window_features(dam, d_cfg["key"], d_cfg["aggs"], d_cfg["windows"])
        dfeat = dfeat.rename(
            columns={c: f"d_{c}" for c in dfeat.columns if c not in (d_cfg["key"], "date")}
        )
        merged = merge_asof_by(merged, dfeat, d_cfg["key"], d_cfg["tolerance_days"])
        if {"d_storage", "d_outflow"} <= set(merged.columns):
            # 체류시간(일) ≈ 저수량(백만 m3) / (방류량 m3/s × 86400 s) × 1e6
            merged["d_residence_days"] = merged["d_storage"] * 1e6 / (merged["d_outflow"] * 86400)
            merged.loc[~np.isfinite(merged["d_residence_days"]), "d_residence_days"] = np.nan
        log.info("댐 운영 결합: 댐 지점 %d행", merged["dam_name"].notna().sum())
    else:
        log.warning("댐 운영 파일 없음(건너뜀): %s", dam_path)

    # 5. 정답 및 달력 피처
    t_cfg = cfg["target"]
    merged = add_targets(merged, t_cfg["horizon_days"], t_cfg["tolerance_days"])
    s_cfg = cfg.get("split", {})
    merged = add_split(merged, s_cfg.get("train_max_year", 2024), s_cfg.get("valid_year", 2025))
    merged["year"] = merged["date"].dt.year
    merged["month"] = merged["date"].dt.month
    merged["doy"] = merged["date"].dt.dayofyear
    log.info(
        "최종: %d행, %d지점, %s ~ %s, 정답 유효 %d행, 분할 %s",
        len(merged),
        merged[SITE_KEY].nunique(),
        merged["date"].min().date(),
        merged["date"].max().date(),
        int(merged["target_valid"].sum()),
        merged["split"].value_counts().to_dict(),
    )
    return merged
