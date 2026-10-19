"""실제 데이터와 같은 열 구조의 샘플 데이터를 생성한다 (파이프라인·노트북 점검용).

실제 데이터가 준비되기 전에 `make sample` 로 생성해 두고, 실제 파일이 들어오면 삭제한다.
생성 위치: data/sample/raw/, data/sample/external/  (configs/bloom.yaml 의 열 이름과 동일)
"""

from __future__ import annotations

import argparse
from pathlib import Path

import numpy as np
import pandas as pd

from data_ai.config import DATA_DIR

# 공식 대상 지점 5곳. 댐·ASOS 매핑은 초안이며 실제 데이터 확인 후 sites.csv 에서 수정한다.
SITES = [
    # site_code, site_name, basin, site_type, dam_name, asos_id, lat, lon
    ("2011G26", "해평", "낙동강", "river", "안동댐", 279, 36.20, 128.37),
    ("2011G56", "강정·고령", "낙동강", "river", "안동댐", 143, 35.84, 128.45),
    ("2020G33", "칠서", "낙동강", "river", "합천댐", 155, 35.39, 128.49),
    ("2022G05", "물금·매리", "낙동강", "river", "밀양댐", 288, 35.31, 128.99),
    ("3008G30", "대청호 회남", "금강", "dam", "대청댐", 131, 36.42, 127.57),
]
ASOS_OFFSET = {279: -0.3, 143: 0.9, 155: 1.2, 288: 1.8, 131: 0.0}
DAMS = {"안동댐": (1248, 279), "합천댐": (790, 155), "밀양댐": (74, 288), "대청댐": (1490, 131)}


def make_weather(rng, dates):
    rows = []
    doy = dates.dayofyear.to_numpy()
    season = np.sin(2 * np.pi * (doy - 110) / 365.25)
    summer = np.clip(season, 0, None)
    for sid, off in ASOS_OFFSET.items():
        temp = 12.5 + off + 13 * season + rng.normal(0, 2.2, len(dates))
        rain_p = 0.15 + 0.35 * summer
        rain = np.where(
            rng.random(len(dates)) < rain_p, rng.gamma(1.2, 12, len(dates)) * (1 + 2 * summer), 0.0
        )
        solar = np.clip(12 + 9 * season - 0.12 * rain + rng.normal(0, 2, len(dates)), 1, None)
        rows.append(
            pd.DataFrame(
                {
                    "지점": sid,
                    "일시": dates.strftime("%Y-%m-%d"),
                    "평균기온(°C)": temp.round(1),
                    "최고기온(°C)": (temp + 5 + rng.normal(0, 1, len(dates))).round(1),
                    "최저기온(°C)": (temp - 5 + rng.normal(0, 1, len(dates))).round(1),
                    "일강수량(mm)": rain.round(1),
                    "평균 풍속(m/s)": np.clip(rng.gamma(2, 0.9, len(dates)), 0.2, None).round(1),
                    "합계 일사량(MJ/m2)": solar.round(2),
                    "합계 일조시간(hr)": np.clip(
                        solar / 2.2 + rng.normal(0, 1, len(dates)), 0, 13
                    ).round(1),
                    "평균 상대습도(%)": np.clip(
                        65 + 10 * summer + 0.3 * rain + rng.normal(0, 6, len(dates)), 20, 100
                    ).round(0),
                }
            )
        )
    return pd.concat(rows, ignore_index=True)


def make_dam(rng, dates, weather):
    rows = []
    cap = {d: c for d, (c, _) in DAMS.items()}
    for dam, (_, asos) in DAMS.items():
        w = (
            weather[weather["지점"] == asos]
            .set_index("일시")["일강수량(mm)"]
            .reindex(dates.strftime("%Y-%m-%d"))
        )
        rain = w.to_numpy()
        scale = cap[dam] / 1490
        inflow = scale * (
            25 + 6 * np.convolve(rain, np.ones(3) / 3, mode="same") + rng.gamma(2, 4, len(dates))
        )
        outflow = np.empty(len(dates))
        storage = np.empty(len(dates))
        s = 0.6 * cap[dam]
        for i in range(len(dates)):
            out = scale * 30 + 0.4 * (s - 0.6 * cap[dam]) / 30 + rng.normal(0, 3 * scale)
            out = max(out, 2 * scale)
            s = np.clip(s + (inflow[i] - out) * 86400 / 1e6, 0.2 * cap[dam], cap[dam])
            outflow[i], storage[i] = out, s
        rows.append(
            pd.DataFrame(
                {
                    "댐명": dam,
                    "일자": dates.strftime("%Y-%m-%d"),
                    "강우량(mm)": np.nan_to_num(rain).round(1),
                    "저수위(EL.m)": (50 + 30 * storage / cap[dam]).round(2),
                    "저수량(백만m3)": storage.round(1),
                    "저수율(%)": (100 * storage / cap[dam]).round(1),
                    "유입량(m3/s)": inflow.round(1),
                    "총방류량(m3/s)": outflow.round(1),
                }
            )
        )
    return pd.concat(rows, ignore_index=True)


def make_algae(rng, dates, weather, dam):
    rows = []
    wt = weather.assign(d=pd.to_datetime(weather["일시"])).set_index(["지점", "d"])["평균기온(°C)"]
    out = dam.assign(d=pd.to_datetime(dam["일자"])).set_index(["댐명", "d"])["총방류량(m3/s)"]
    for code, name, _basin, _stype, dam_name, asos, _, _ in SITES:
        start = dates[0] + pd.Timedelta(days=int(rng.integers(0, 400)))
        # 매주 월요일 측정, 5%는 결측(유량 증가 시 미채수 등), 겨울(12~2월)은 격주
        mondays = pd.date_range(start, dates[-1], freq="W-MON")
        temp_series = wt.loc[asos].rolling(14, min_periods=1).mean()
        prev = 0.0
        site_base = rng.normal(0, 0.4)
        for d in mondays:
            if d.month in (12, 1, 2) and d.isocalendar().week % 2:
                continue
            if rng.random() < 0.05:
                continue
            water_temp = 0.9 * temp_series.get(d, 15.0) + 3 + rng.normal(0, 0.8)
            drive = 2.0 * np.clip((water_temp - 19) / 8, -1, 1.3) + site_base
            if dam_name:
                o = out.loc[dam_name].rolling(14, min_periods=1).mean().get(d, 30.0)
                drive += 0.6 * np.clip((30 - o) / 20, -1, 1)
            latent = 0.65 * prev + 0.35 * (3.2 + drive) + rng.normal(0, 0.55)
            prev = latent
            cells = float(np.exp(np.log(10) * np.clip(latent, 0, 6.3)))
            chla = max(0.5, 2 + 4 * latent + rng.normal(0, 2))
            rows.append(
                {
                    "pt_no": code,
                    "pt_nm": name,
                    "wmcymd": d.strftime("%Y-%m-%d"),
                    "iem_bgalage_cell_co": int(round(cells)) if rng.random() > 0.02 else np.nan,
                    "iem_temp": round(water_temp, 1),
                    "iem_ph": round(7.6 + 0.08 * latent + rng.normal(0, 0.2), 1),
                    "iem_tran": round(max(0.2, 1.8 - 0.15 * latent + rng.normal(0, 0.3)), 1),
                    "iem_turb": round(max(0.5, 5 + 2 * latent + rng.normal(0, 3)), 1),
                    "iem_do": round(9 - 0.15 * (water_temp - 15) + rng.normal(0, 0.8), 1),
                    "iem_chla": round(chla, 1),
                }
            )
    return pd.DataFrame(rows)


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--out", type=Path, default=DATA_DIR / "sample")
    ap.add_argument("--start", default="2018-01-01")
    ap.add_argument("--end", default="2026-08-31")
    ap.add_argument("--seed", type=int, default=42)
    args = ap.parse_args()

    rng = np.random.default_rng(args.seed)
    dates = pd.date_range(args.start, args.end, freq="D")
    raw, ext = args.out / "raw", args.out / "external"
    raw.mkdir(parents=True, exist_ok=True)
    ext.mkdir(parents=True, exist_ok=True)

    weather = make_weather(rng, dates)
    dam = make_dam(rng, dates, weather)
    algae = make_algae(rng, dates, weather, dam)
    sites = pd.DataFrame(
        SITES,
        columns=[
            "site_code",
            "site_name",
            "basin",
            "site_type",
            "dam_name",
            "asos_id",
            "lat",
            "lon",
        ],
    )
    # 평가용 sample_submission 흉내: 2026년 기준일과 +7일에 가장 가까운 측정일.
    # 열 이름(pt_no, base_date, target_date, iem_bgalage_cell_co)은 배포본을 확인해 맞출 것.
    a = algae.assign(d=pd.to_datetime(algae["wmcymd"]))
    sub_rows = []
    for code, g in a[a["d"].dt.year >= 2026].groupby("pt_no"):
        dates_site = g["d"].sort_values().to_numpy()
        for base in dates_site:
            diff = np.abs((dates_site - (base + np.timedelta64(7, "D"))) / np.timedelta64(1, "D"))
            j = int(np.argmin(diff))
            if diff[j] <= 3:
                sub_rows.append(
                    {
                        "pt_no": code,
                        "base_date": pd.Timestamp(base).strftime("%Y-%m-%d"),
                        "target_date": pd.Timestamp(dates_site[j]).strftime("%Y-%m-%d"),
                        "iem_bgalage_cell_co": 0,
                    }
                )
    submission = pd.DataFrame(sub_rows)

    sites.to_csv(ext / "sites.csv", index=False, encoding="utf-8-sig")
    weather.to_csv(ext / "kma_asos_daily.csv", index=False, encoding="utf-8-sig")
    dam.to_csv(ext / "dam_daily.csv", index=False, encoding="utf-8-sig")
    algae.to_csv(raw / "algae_alert.csv", index=False, encoding="utf-8-sig")
    submission.to_csv(raw / "sample_submission.csv", index=False, encoding="utf-8-sig")
    print(
        f"샘플 생성 완료 → {args.out}\n"
        f"  조류 {len(algae)}행, 기상 {len(weather)}행, 댐 {len(dam)}행, "
        f"제출양식 {len(submission)}행"
    )


if __name__ == "__main__":
    main()
