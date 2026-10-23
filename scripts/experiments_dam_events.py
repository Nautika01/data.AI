"""댐 방류 급증·급감 이벤트 피처 확인. 상류 댐 합산 방류량(일)에서 기준일 이전 창으로 계산.

결과는 docs/modeling_notes.md 「댐 방류 급증·급감 이벤트 피처 확인」 절 참고 (효과 없음, 미채택).
"""

from __future__ import annotations

import json

import numpy as np
import pandas as pd
import yaml

from data_ai.config import MODELS_DIR, PROCESSED_DIR, RAW_DIR
from data_ai.evaluate import bloom_metrics
from data_ai.features import apply_missing_strategy, feature_columns, to_matrix
from data_ai.models import fit_lgb
from data_ai.utils import set_seed

set_seed()
cfg = yaml.safe_load(open("configs/bloom.yaml", encoding="utf-8"))
df = pd.read_parquet(PROCESSED_DIR / "bloom.parquet")
df["date"] = pd.to_datetime(df["date"])
algae = pd.read_csv(RAW_DIR / "algae_measure.csv", parse_dates=["chck_de"])
truth = algae.groupby(["station_id", "chck_de"])["iem_bgalage_cell_co"].mean().rename("_truth")
df = df.join(truth, on=["station_id", "target_date"])
df.loc[~df["is_test"], "_truth"] = df["target_cells"]

dam = pd.read_csv(RAW_DIR / "dam_daily.csv", parse_dates=["obs_date"])
dam["outflow"] = pd.to_numeric(dam["tdqty"], errors="coerce")
feats = []
for sid, dams in cfg["dam"]["station_dams"].items():
    s = dam[dam["dam_name"].isin(dams)].groupby("obs_date")["outflow"].sum(min_count=1)
    s = s.asfreq("D")
    m28 = s.rolling(28, min_periods=14).mean()
    f = pd.DataFrame(
        {
            "d_ev_max7_rel28": s.rolling(7, min_periods=4).max() / (m28 + 1),  # 급증
            "d_ev_min7_rel28": s.rolling(7, min_periods=4).min() / (m28 + 1),  # 급감
            "d_ev_jump1": (s / (s.shift(1) + 1))
            .rolling(7, min_periods=4)
            .max(),  # 하루 사이 최대 증가배수
            "d_ev_drop1": (s / (s.shift(1) + 1))
            .rolling(7, min_periods=4)
            .min(),  # 하루 사이 최대 감소배수
        }
    )
    big = (s > 2 * m28).astype(float)
    idx = pd.Series(np.where(big == 1, np.arange(len(s)), np.nan), index=s.index).ffill()
    f["d_ev_days_since_surge"] = (np.arange(len(s)) - idx).clip(upper=60)
    f["station_id"] = sid
    feats.append(f.reset_index().rename(columns={"obs_date": "date"}))
ev = pd.concat(feats).sort_values("date")
df = pd.merge_asof(
    df.sort_values("date"),
    ev,
    on="date",
    by="station_id",
    direction="backward",
    tolerance=pd.Timedelta(days=3),
).sort_index()
ev_cols = [c for c in df.columns if c.startswith("d_ev_")]
print("이벤트 피처 결측률", df[ev_cols].isna().mean().round(2).to_dict())
print(
    "정답(log)과 상관",
    df[ev_cols + ["log10_target_cells"]].corr()["log10_target_cells"].round(3).to_dict(),
)

meta = json.loads((MODELS_DIR / "train_meta.json").read_text())
strategy, rounds = meta["strategy"], int(meta["best_iter"])
lab = df["target_valid"]
sets = {
    "valid2025": (lab & df.split.eq("train"), lab & df.split.eq("valid")),
    "roll2022": (lab & (df.year < 2022), lab & (df.year == 2022)),
    "roll2023": (lab & (df.year < 2023), lab & (df.year == 2023)),
    "roll2024": (lab & (df.year < 2024), lab & (df.year == 2024)),
    "test2026*": (lab & df.split.isin(["train", "valid"]), df["is_test"]),
}
rows = []
for name, (tr, va) in sets.items():
    d = apply_missing_strategy(df, strategy, tr)
    cols = feature_columns(d)
    for variant in ("base", "dam_events"):
        c = cols if variant == "dam_events" else [x for x in cols if x not in ev_cols]
        x_tr, cats = to_matrix(d[tr], c)
        x_va, _ = to_matrix(d[va], c, cats)
        pl = fit_lgb(x_tr, d.loc[tr, "log10_target_cells"].to_numpy(), num_rounds=rounds).predict(
            x_va
        )
        r = bloom_metrics(d.loc[va, "_truth"], np.clip(10**pl - 1, 0, None))
        rows.append({"variant": variant, "set": name, **r})
res = pd.DataFrame(rows)
for k in ("rmse_log10", "r2", "f1_over_threshold"):
    piv = res.pivot(index="variant", columns="set", values=k).round(3)
    piv["mean_val"] = piv[["valid2025", "roll2022", "roll2023", "roll2024"]].mean(axis=1).round(3)
    print(f"\n## {k}\n" + piv.to_string())
