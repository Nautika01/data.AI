"""앙상블 확인: LightGBM / XGBoost / CatBoost / 3모델 평균(soft voting) / 지점 원핫.

같은 피처·같은 검증 세트. xgboost, catboost 는 requirements 에 없으므로 따로 설치해야 한다:
    pip install xgboost catboost
결과는 docs/modeling_notes.md 「앙상블·지점 원핫 확인」 절 참고.
"""

from __future__ import annotations

import json

import catboost as cb
import numpy as np
import pandas as pd
import xgboost as xgb

from data_ai.config import MODELS_DIR, PROCESSED_DIR, RAW_DIR, SEED
from data_ai.evaluate import bloom_metrics
from data_ai.features import CATEGORICAL, apply_missing_strategy, feature_columns, to_matrix
from data_ai.models import fit_lgb
from data_ai.utils import set_seed

set_seed()
df = pd.read_parquet(PROCESSED_DIR / "bloom.parquet")
df["date"] = pd.to_datetime(df["date"])
algae = pd.read_csv(RAW_DIR / "algae_measure.csv", parse_dates=["chck_de"])
truth = algae.groupby(["station_id", "chck_de"])["iem_bgalage_cell_co"].mean().rename("_truth")
df = df.join(truth, on=["station_id", "target_date"])
df.loc[~df["is_test"], "_truth"] = df["target_cells"]
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


def numeric(x):
    x = x.copy()
    for c in CATEGORICAL:
        if c in x:
            x[c] = x[c].cat.codes.astype(float).replace(-1, np.nan)
    return x


rows = []
for name, (tr, va) in sets.items():
    d = apply_missing_strategy(df, strategy, tr)
    cols = feature_columns(d)
    x_tr, cats = to_matrix(d[tr], cols)
    x_va, _ = to_matrix(d[va], cols, cats)
    y = d.loc[tr, "log10_target_cells"].to_numpy()
    t = d.loc[va, "_truth"]
    preds = {}
    preds["lgb"] = fit_lgb(x_tr, y, num_rounds=rounds).predict(x_va)
    m = xgb.XGBRegressor(
        n_estimators=rounds * 2,
        learning_rate=0.03,
        max_depth=4,
        subsample=0.8,
        colsample_bytree=0.8,
        reg_lambda=1.0,
        min_child_weight=5,
        random_state=SEED,
        enable_categorical=True,
        tree_method="hist",
    )
    preds["xgb"] = m.fit(x_tr, y).predict(x_va)
    cat_idx = [i for i, c in enumerate(cols) if c in CATEGORICAL]
    a, b = x_tr.copy(), x_va.copy()
    for c in CATEGORICAL:
        if c in a:
            a[c] = a[c].astype(str).fillna("nan").replace("nan", "NA")
            b[c] = b[c].astype(str).fillna("nan").replace("nan", "NA")
    m = cb.CatBoostRegressor(
        iterations=rounds * 3,
        learning_rate=0.03,
        depth=5,
        l2_leaf_reg=3,
        random_seed=SEED,
        verbose=0,
        cat_features=cat_idx,
    )
    preds["cat"] = m.fit(a, y).predict(b)
    preds["vote3"] = (preds["lgb"] + preds["xgb"] + preds["cat"]) / 3
    preds["lgb+cat"] = (preds["lgb"] + preds["cat"]) / 2
    # 지점 원핫 (LightGBM 범주형 대신)
    oh_cols = [c for c in cols if c != "station_id"]
    xo_tr = pd.concat(
        [x_tr[oh_cols], pd.get_dummies(x_tr["station_id"], prefix="st").astype(int)], axis=1
    )
    xo_va = pd.concat(
        [x_va[oh_cols], pd.get_dummies(x_va["station_id"], prefix="st").astype(int)], axis=1
    ).reindex(columns=xo_tr.columns, fill_value=0)
    preds["lgb_onehot"] = fit_lgb(xo_tr, y, num_rounds=rounds).predict(xo_va)
    for k, pl in preds.items():
        r = bloom_metrics(t, np.clip(10**pl - 1, 0, None))
        rows.append({"variant": k, "set": name, **r})
res = pd.DataFrame(rows)
for k in ("rmse_log10", "r2", "f1_over_threshold"):
    piv = res.pivot(index="variant", columns="set", values=k).round(3)
    piv["mean_val"] = piv[["valid2025", "roll2022", "roll2023", "roll2024"]].mean(axis=1).round(3)
    print(f"\n## {k}\n" + piv.to_string())
