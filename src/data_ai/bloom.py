"""녹조(유해남조류) 7일 예측용 데이터 결합 — 대회 배포 번들 기준.

번들(README '26. 9. 12.):
- algae_measure.csv  조류경보제 측정자료 (station_id, chck_de, iem_bgalage_cell_co=예측 대상 …)
- asos_daily.csv     ASOS 일자료 6개 지점 (stations.csv 의 asos_stn_id 로 연결)
- dam_daily.csv      다목적댐 15개 일자료 (저수위·유입·방류·취수·강우; 저수량 없음)
- eval_pairs.csv     채점 대상 (station_id, base_date, target_date, lag_days, split)
- sample_submission  제출 형식 (station_id, base_date, target_date, pred_cells)

규칙: 기준일 이후 관측값 사용 금지 → 모든 일 자료 집계는 기준일 포함 과거 N일만 사용.
"""

from __future__ import annotations

from collections.abc import Iterable
from pathlib import Path

import numpy as np
import pandas as pd
import yaml

from data_ai.config import PROJECT_ROOT
from data_ai.utils import get_logger

log = get_logger(__name__)

ALERT_THRESHOLDS = {"관심": 1_000, "경계": 10_000, "대발생": 1_000_000}
ALERT_LEVELS = ["정상", "관심", "경계", "대발생"]
SITE_KEY = "station_id"
ID_COLS = {
    "station_id",
    "station_name",
    "site_name",
    "site_code",
    "dam_name",
    "asos_stn_id",
    "dominant_genus",
}
ENCODINGS = ("utf-8-sig", "cp949", "euc-kr")


def load_config(path: str | Path) -> dict:
    with open(path, encoding="utf-8") as f:
        return yaml.safe_load(f)


def read_csv_any(path: str | Path, **kwargs) -> pd.DataFrame:
    last: Exception | None = None
    for enc in ENCODINGS:
        try:
            return pd.read_csv(path, encoding=enc, low_memory=False, **kwargs)
        except UnicodeDecodeError as e:
            last = e
    raise ValueError(f"인코딩을 판별할 수 없음: {path}") from last


def alert_level(cells: pd.Series | np.ndarray) -> pd.Series:
    """세포수 → 경보 단계 코드 (0 정상, 1 관심, 2 경계, 3 대발생). NaN 유지."""
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
    """원본 열 → 표준 열 이름, 날짜 파싱, 숫자 변환(쉼표 제거)."""
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
                df[col].astype(str).str.replace(",", "", regex=False).str.strip(), errors="coerce"
            )
    return df


def daily_window_features(
    df: pd.DataFrame,
    key: str,
    aggs: dict[str, Iterable[str]],
    windows: Iterable[int],
    date_col: str = "date",
) -> pd.DataFrame:
    """키별 일 자료를 빠진 날짜 없이 채운 뒤, 날짜 기준 과거 N일(당일 포함) 집계를 만든다.

    결과 열: ``{col}`` (당일 값) 과 ``{col}_{agg}{N}d``.
    """
    windows = list(windows)
    out = []
    for k, g in df.groupby(key, sort=False):
        g = g.drop_duplicates(subset=[date_col]).set_index(date_col).sort_index().asfreq("D")
        frame = pd.DataFrame(index=g.index)
        for col, funcs in aggs.items():
            if col not in g.columns:
                log.warning("집계 대상 열 없음: %s (키=%s)", col, k)
                continue
            frame[col] = g[col]
            for w in windows:
                roll = g[col].rolling(w, min_periods=max(1, w // 2))
                for fn in funcs:
                    frame[f"{col}_{fn}{w}d"] = getattr(roll, fn)()
        frame = frame.reset_index().rename(columns={"index": date_col})
        frame[key] = k
        out.append(frame)
    if not out:
        return pd.DataFrame(columns=[key, date_col])
    return pd.concat(out, ignore_index=True)


def merge_asof_by(
    left: pd.DataFrame, right: pd.DataFrame, key: str, tolerance_days: int, date_col: str = "date"
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


# ---------------------------------------------------------------------------
# 댐: 지점별 상류 댐 합산 + 대표 댐 수위 편차
# ---------------------------------------------------------------------------
def station_dam_features(
    dam_feat: pd.DataFrame,
    station_dams: dict[str, list[str]],
    primary_dam: dict[str, str],
    flow_cols: Iterable[str],
    level_cols: Iterable[str],
    train_max_year: int,
    date_col: str = "date",
) -> pd.DataFrame:
    """댐별 일 집계(daily_window_features 결과)를 지점별로 묶는다.

    - flow_cols 계열(유입·방류·취수·강우)은 지점 상류 댐 전체 합산
    - level_cols 계열(저수위)은 대표 댐 값 + 월별 평년(≤train_max_year) 대비 편차
    """
    flow_cols, level_cols = list(flow_cols), list(level_cols)
    feat_cols = [c for c in dam_feat.columns if c not in ("dam_name", date_col)]
    flow_feats = [c for c in feat_cols if any(c == b or c.startswith(f"{b}_") for b in flow_cols)]
    level_feats = [c for c in feat_cols if any(c == b or c.startswith(f"{b}_") for b in level_cols)]

    # 대표 댐 월별 평년 수위 (학습 구간만 사용 → 누수 방지)
    lv = dam_feat[[date_col, "dam_name", *level_cols]].copy()
    lv["month"] = lv[date_col].dt.month
    clim = (
        lv[lv[date_col].dt.year <= train_max_year]
        .groupby(["dam_name", "month"])[level_cols]
        .median()
        .rename(columns={c: f"{c}_clim" for c in level_cols})
    )

    out = []
    for sid, dams in station_dams.items():
        sub = dam_feat[dam_feat["dam_name"].isin(dams)]
        missing = set(dams) - set(sub["dam_name"].unique())
        if missing:
            log.warning("지점 %s: 댐 자료 없음 %s", sid, sorted(missing))
        flows = sub.groupby(date_col)[flow_feats].sum(min_count=1)
        p = primary_dam.get(sid)
        lev = dam_feat.loc[dam_feat["dam_name"] == p, [date_col, *level_feats]].set_index(date_col)
        lev["month"] = lev.index.month
        lev = lev.join(
            clim.loc[p] if p in clim.index.get_level_values(0) else clim.iloc[0:0], on="month"
        )
        for c in level_cols:
            if f"{c}_clim" in lev.columns:
                lev[f"{c}_anom"] = lev[c] - lev[f"{c}_clim"]
        lev = lev.drop(
            columns=["month"] + [f"{c}_clim" for c in level_cols if f"{c}_clim" in lev.columns]
        )
        frame = flows.join(lev, how="outer")
        frame[SITE_KEY] = sid
        frame["n_dams"] = len(dams)
        out.append(frame.reset_index())
    res = pd.concat(out, ignore_index=True)
    # 체류시간 대리변수: 방류 대비 유입, 최근 방류 대비 장기 방류
    if {"outflow_mean7d", "inflow_mean7d"} <= set(res.columns):
        res["flow_ratio7d"] = res["outflow_mean7d"] / (res["inflow_mean7d"] + 1.0)
    if {"outflow_mean7d", "outflow_mean28d"} <= set(res.columns):
        res["outflow_rel28d"] = res["outflow_mean7d"] / (res["outflow_mean28d"] + 1.0)
    return res


# ---------------------------------------------------------------------------
# 하천: WAMIS 수위·유량 (scripts/fetch_wamis.py 산출물, 선택)
# ---------------------------------------------------------------------------
RIVER_KIND_COL = {"fw": "flow", "wl": "stage"}


def river_features(
    daily: pd.DataFrame,
    station_map: dict[str, dict[str, str]],
    windows: Iterable[int] = (7, 28),
    zero_as_missing: Iterable[str] = (),
    date_col: str = "date",
) -> pd.DataFrame:
    """WAMIS 하천 일자료(long: date, kind, station, value) → 지점별 유량·수위 피처.

    - flow(유량 m³/s): 당일, N일 평균, log10(7일 평균+1), 7일/28일 평균 비
    - stage(수위 m):   당일, N일 평균, 7일 변화량(당일 − 7일 전)
    station_map: {station_id: {"fw": 유량 관측소명, "wl": 수위 관측소명}}
    zero_as_missing 에 든 관측소의 0 값은 결측으로 본다(보 수위 0 = 기록 오류).
    모든 집계는 당일 포함 과거 자료만 쓴다.
    """
    d = daily.copy()
    d[date_col] = pd.to_datetime(d[date_col]).dt.normalize()
    d["value"] = pd.to_numeric(d["value"], errors="coerce")
    d.loc[d["station"].isin(list(zero_as_missing)) & (d["value"] == 0), "value"] = np.nan

    frames = []
    for sid, m in station_map.items():
        parts = []
        for kind, name in (m or {}).items():
            col = RIVER_KIND_COL.get(kind)
            sub = d[(d["kind"] == kind) & (d["station"] == name)]
            if col is None or sub.empty:
                log.warning("지점 %s: 하천 자료 없음 (%s %s)", sid, kind, name)
                continue
            parts.append(sub.groupby(date_col)["value"].mean().rename(col))
        if parts:
            frame = pd.concat(parts, axis=1)
            frame[SITE_KEY] = sid
            frames.append(frame.reset_index())
    if not frames:
        return pd.DataFrame(columns=[SITE_KEY, date_col])

    wide = pd.concat(frames, ignore_index=True)
    aggs = {c: ["mean"] for c in RIVER_KIND_COL.values() if c in wide.columns}
    feat = daily_window_features(wide, SITE_KEY, aggs, windows).sort_values([SITE_KEY, date_col])
    if "flow_mean7d" in feat.columns:
        feat["log_flow_mean7d"] = np.log10(feat["flow_mean7d"].clip(lower=0) + 1)
    if {"flow_mean7d", "flow_mean28d"} <= set(feat.columns):
        feat["flow_rel28d"] = feat["flow_mean7d"] / (feat["flow_mean28d"] + 1.0)
    if "stage" in feat.columns:  # 날짜가 빠짐없이 채워져 있어 shift(7) = 7일 전
        feat["stage_diff7d"] = feat["stage"] - feat.groupby(SITE_KEY)["stage"].shift(7)
    return feat.reset_index(drop=True)


def upstream_features(
    df: pd.DataFrame,
    chain: dict[str, str],
    basins: dict[str, list[str]],
    tolerance_days: int = 14,
    date_col: str = "date",
) -> pd.DataFrame:
    """다른 경보지점의 기준일 이전 최근 세포수를 피처로 붙인다.

    같은 수계 안에서 녹조가 상류 → 하류로 전파되는 정보.
    - cells_upstream:   chain[지점] = 바로 상류 지점.
                        그 지점의 기준일 이전(포함) 최근 log10(세포수+1)
    - cells_basin_mean: 같은 수계(basins) 안 다른 지점들의 기준일 이전 최근
                        log10(세포수+1) 평균
    모두 merge_asof(backward) 이므로 기준일 이후 측정값은 쓰지 않는다.
    tolerance_days 를 넘으면 결측.
    """
    tol = pd.Timedelta(days=tolerance_days)
    d = df.sort_values(date_col).copy()
    obs = d.loc[d["cyano_cells"].notna(), [SITE_KEY, date_col, "cyano_cells"]].copy()
    obs["_lc"] = np.log10(obs["cyano_cells"].clip(lower=0) + 1)
    obs = obs.sort_values(date_col)

    def latest(site: str, name: str) -> pd.DataFrame:
        o = obs.loc[obs[SITE_KEY] == site, [date_col, "_lc"]].rename(columns={"_lc": name})
        return pd.merge_asof(d[[date_col]], o, on=date_col, direction="backward", tolerance=tol)[
            name
        ]

    sites = sorted({s for b in basins.values() for s in b} | set(chain.values()))
    cache = {s: latest(s, f"_c_{s}").to_numpy() for s in sites}

    d["cells_upstream"] = np.nan
    for site, up in chain.items():
        m = (d[SITE_KEY] == site).to_numpy()
        d.loc[m, "cells_upstream"] = cache[up][m]
    d["cells_basin_mean"] = np.nan
    for members in basins.values():
        for site in members:
            others = [o for o in members if o != site]
            if not others:
                continue
            m = (d[SITE_KEY] == site).to_numpy()
            stack = np.vstack([cache[o] for o in others])
            with np.errstate(all="ignore"):
                d.loc[m, "cells_basin_mean"] = np.nanmean(stack, axis=0)[m]
    return d.sort_index()


# ---------------------------------------------------------------------------
# 정답·분할
# ---------------------------------------------------------------------------
def add_lag_features(
    df: pd.DataFrame, cols: Iterable[str], lags: Iterable[int], date_col: str = "date"
) -> pd.DataFrame:
    df = df.sort_values([SITE_KEY, date_col]).reset_index(drop=True)
    g = df.groupby(SITE_KEY, sort=False)
    df["days_since_prev"] = (df[date_col] - g[date_col].shift(1)).dt.days
    for col in cols:
        if col not in df.columns:
            continue
        for k in lags:
            df[f"{col}_lag{k}"] = g[col].shift(k)
    return df


def add_targets_from_pairs(
    df: pd.DataFrame, pairs: pd.DataFrame, date_col: str = "date"
) -> pd.DataFrame:
    """주최 측 eval_pairs (station_id, base_date, target_date, lag_days, split) 로 정답을 붙인다."""
    p = pairs.rename(columns={"base_date": date_col}).copy()
    p[date_col] = pd.to_datetime(p[date_col]).dt.normalize()
    p["target_date"] = pd.to_datetime(p["target_date"]).dt.normalize()
    cells = df[[SITE_KEY, date_col, "cyano_cells"]].rename(
        columns={date_col: "target_date", "cyano_cells": "target_cells"}
    )
    p = p.merge(cells, on=[SITE_KEY, "target_date"], how="left")
    out = df.merge(
        p[[SITE_KEY, date_col, "target_date", "lag_days", "split", "target_cells"]],
        on=[SITE_KEY, date_col],
        how="left",
    )
    out["split"] = out["split"].fillna("none")
    # 번들 측정자료에는 '26년 값까지 들어 있어 test 정답도 조회된다. 누수·룩업 방지를 위해 비운다.
    # (자체 채점은 scripts/score_submission.py 로 원본에서 별도 수행)
    out.loc[out["split"].eq("test"), "target_cells"] = np.nan
    out["target_gap_days"] = out["lag_days"]
    out["target_valid"] = out["split"].isin(["train", "valid"]) & out["target_cells"].notna()
    out["is_test"] = out["split"].eq("test")
    return out


def add_targets(
    df: pd.DataFrame,
    horizon_days: int = 7,
    tolerance_days: int = 3,
    site_col: str = SITE_KEY,
    date_col: str = "date",
) -> pd.DataFrame:
    """(대체 경로) 기준일+horizon 에 가장 가까운 측정(±tolerance)을 정답으로 계산한다."""
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
    return out


def add_split(df: pd.DataFrame, train_max_year: int = 2024, valid_year: int = 2025) -> pd.DataFrame:
    year = df["date"].dt.year
    df = df.copy()
    df["split"] = np.select(
        [year <= train_max_year, year == valid_year], ["train", "valid"], "test"
    )
    return df


def finalize_columns(df: pd.DataFrame) -> pd.DataFrame:
    df = df.copy()
    df["current_level"] = alert_level(df["cyano_cells"])
    df["target_level"] = alert_level(df["target_cells"])
    df["log10_cells"] = np.log10(df["cyano_cells"] + 1)
    df["log10_target_cells"] = np.log10(df["target_cells"] + 1)
    df["year"] = df["date"].dt.year
    df["month"] = df["date"].dt.month
    df["doy"] = df["date"].dt.dayofyear
    genus = [c for c in df.columns if c.startswith("cells_")]
    if genus:
        total = df[genus].sum(axis=1)
        for c in genus:
            df[f"{c}_share"] = df[c] / total.where(total > 0)
    return df


# ---------------------------------------------------------------------------
def build_dataset(cfg: dict, bundle_dir: Path | None = None) -> pd.DataFrame:
    bundle_dir = Path(bundle_dir or PROJECT_ROOT / cfg.get("bundle_dir", "data/raw"))
    s_cfg = cfg.get("split", {})
    train_max_year = s_cfg.get("train_max_year", 2024)

    # 1. 지점
    stations = read_csv_any(bundle_dir / cfg["stations_file"])
    stations.columns = [c.strip() for c in stations.columns]
    stations[SITE_KEY] = stations[SITE_KEY].astype(str).str.strip()
    stations["asos_stn_id"] = stations["asos_stn_id"].astype(str).str.strip()
    log.info("지점: %s", stations[SITE_KEY].tolist())

    # 2. 조류경보제
    a_cfg = cfg["algae"]
    algae = standardize(read_csv_any(bundle_dir / a_cfg["file"]), a_cfg["mapping"])
    n0 = len(algae)
    num_cols = algae.select_dtypes("number").columns
    algae = algae.groupby([SITE_KEY, "date"], as_index=False).agg(
        {
            **{c: "mean" for c in num_cols},
            **{
                c: "first"
                for c in algae.columns
                if c not in num_cols and c not in (SITE_KEY, "date")
            },
        }
    )
    log.info("조류경보제: %d행 → 지점·날짜 정리 후 %d행", n0, len(algae))
    algae = add_lag_features(algae, a_cfg.get("lag_cols", []), a_cfg.get("lags", []))
    merged = algae.merge(
        stations[[SITE_KEY, "station_name", "asos_stn_id", "swmn_code"]], on=SITE_KEY, how="left"
    )

    # 3. 기상
    w_cfg = cfg["weather"]
    weather = standardize(read_csv_any(bundle_dir / w_cfg["file"]), w_cfg["mapping"])
    for c in w_cfg.get("fillna_zero", []):
        if c in weather.columns:
            weather[c] = weather[c].fillna(0.0)
    wfeat = daily_window_features(weather, w_cfg["key"], w_cfg["aggs"], w_cfg["windows"])
    wfeat = wfeat.rename(
        columns={c: f"w_{c}" for c in wfeat.columns if c not in (w_cfg["key"], "date")}
    )
    merged = merge_asof_by(merged, wfeat, w_cfg["key"], w_cfg["tolerance_days"])
    log.info("기상 결합: 결측 %.1f%%", merged["w_temp_mean"].isna().mean() * 100)

    # 4. 댐
    d_cfg = cfg["dam"]
    dam = standardize(read_csv_any(bundle_dir / d_cfg["file"]), d_cfg["mapping"])
    dfeat = daily_window_features(dam, d_cfg["key"], d_cfg["aggs"], d_cfg["windows"])
    sfeat = station_dam_features(
        dfeat,
        d_cfg["station_dams"],
        d_cfg["primary_dam"],
        d_cfg["flow_cols"],
        d_cfg["level_cols"],
        train_max_year,
    )
    sfeat = sfeat.rename(
        columns={c: f"d_{c}" for c in sfeat.columns if c not in (SITE_KEY, "date")}
    )
    merged = merge_asof_by(merged, sfeat, SITE_KEY, d_cfg["tolerance_days"])
    log.info("댐 결합: 결측 %.1f%%", merged["d_outflow_mean7d"].isna().mean() * 100)

    # 4b. 하천 수위·유량 — WAMIS 수집 결과(data/external/wamis_daily.csv)가 있을 때만
    r_cfg = cfg.get("river")
    if r_cfg:
        river_path = Path(r_cfg["file"])
        if not river_path.is_absolute():
            river_path = PROJECT_ROOT / river_path
        if river_path.exists():
            rfeat = river_features(
                read_csv_any(river_path),
                r_cfg["station_map"],
                r_cfg.get("windows", (7, 28)),
                r_cfg.get("zero_as_missing", ()),
            )
            rfeat = rfeat.rename(
                columns={c: f"r_{c}" for c in rfeat.columns if c not in (SITE_KEY, "date")}
            )
            merged = merge_asof_by(merged, rfeat, SITE_KEY, r_cfg.get("tolerance_days", 3))
            r_cols = [c for c in merged.columns if c.startswith("r_")]
            log.info(
                "하천 결합: %d열, 결측 %.1f%% (매핑 지점 외 포함)",
                len(r_cols),
                merged[r_cols].isna().all(axis=1).mean() * 100 if r_cols else 100.0,
            )
        else:
            log.info("하천 자료 없음(%s) → 건너뜀. scripts/fetch_wamis.py 로 수집", river_path)

    # 4c. 같은 수계 다른 경보지점의 기준일 이전 최근 세포수 (상류 → 하류 전파 정보)
    u_cfg = cfg.get("upstream")
    if u_cfg:
        merged = upstream_features(
            merged, u_cfg.get("chain", {}), u_cfg.get("basins", {}), u_cfg.get("tolerance_days", 14)
        )
        log.info(
            "상류 지점 결합: cells_upstream 결측 %.1f%%, cells_basin_mean 결측 %.1f%%",
            merged["cells_upstream"].isna().mean() * 100,
            merged["cells_basin_mean"].isna().mean() * 100,
        )

    # 5. 정답·분할
    pairs_path = bundle_dir / cfg.get("pairs_file", "")
    if cfg.get("pairs_file") and pairs_path.exists():
        pairs = read_csv_any(pairs_path)
        merged = add_targets_from_pairs(merged, pairs)
        log.info("정답: eval_pairs 사용 (%d쌍)", len(pairs))
    else:
        t_cfg = cfg["target"]
        merged = add_targets(merged, t_cfg["horizon_days"], t_cfg["tolerance_days"])
        merged = add_split(merged, train_max_year, s_cfg.get("valid_year", 2025))
        log.warning("정답: eval_pairs 없음 → 규칙으로 계산")
    merged = finalize_columns(merged)
    log.info(
        "최종: %d행 × %d열, %s ~ %s, 분할 %s, 정답 유효 %d",
        len(merged),
        merged.shape[1],
        merged["date"].min().date(),
        merged["date"].max().date(),
        merged["split"].value_counts().to_dict(),
        int(merged["target_valid"].sum()),
    )
    return merged
