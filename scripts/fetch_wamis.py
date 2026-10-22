"""WAMIS(국가수자원관리종합정보시스템) OpenAPI 로 낙동강 하천 수위·유량 일자료를 받아 저장한다.

- 인증키 불필요. 단, API 가 8080 포트를 쓰므로 회사·학교 네트워크에서는 차단될 수 있다.
- 수집 대상(관측소·항목)은 configs/wamis_stations.yaml 에 적는다.
- 산출물
    data/external/wamis_daily.csv : date, kind(wl=수위 m, fw=유량 m³/s), obscd, obsnm, station,
                                    bloom_sites, value  (long 형식, 관측소×항목×일 1행)
    reports/wamis_qc.csv          : 관측소별 기간·결측·0값·음수·이상값·최장 공백 점검표

예)
  python scripts/fetch_wamis.py                       # 2016-01-01 ~ 오늘
  python scripts/fetch_wamis.py --start 2020-01-01 --end 2026-09-10
  python scripts/fetch_wamis.py --list-stations wl    # 수위 관측소 목록만 출력(코드 확인용)

API (http://www.wamis.go.kr:8080/wamis/openapi/wkw/)
  wl_dubwlobs?basin=2&output=json                     수위 관측소 목록
  flw_dubobs?basin=2&output=json                      유량 관측소 목록
  wl_dtdata?obscd=…&startdt=YYYYMMDD&enddt=YYYYMMDD   일 수위  (ymd, wl)
  flw_dtdata?obscd=…&startdt=…&enddt=…                일 유량  (ymd, fw)
"""

from __future__ import annotations

import argparse
import re
import sys
import time
from datetime import date
from pathlib import Path

import pandas as pd
import requests
import yaml

BASE_URL = "http://www.wamis.go.kr:8080/wamis/openapi/wkw"
ENDPOINTS = {
    #  kind: (관측소 목록, 일자료, 값 필드)
    #  2026-10-22 팀원 PC 진단으로 확인: 유량 목록은 flw_dubobsif
    "wl": ("wl_dubwlobs", "wl_dtdata", "wl"),
    "fw": ("flw_dubobsif", "flw_dtdata", "fw"),
}
# 일자료 주소가 다를 수 있어 후보를 순서대로 시도하고, 처음 성공한 주소를 기억한다.
DAILY_CANDIDATES = {
    "wl": ["wl_dtdata", "wl_dtdataif", "wl_dtdata_if"],
    "fw": ["flw_dtdata", "flw_dtdataif", "flw_dtdata_if", "flw_dtobsdata"],
}
_DAILY_PATH: dict[str, str] = {}
KIND_LABEL = {"wl": "수위(m)", "fw": "유량(m³/s)"}
ROOT = Path(__file__).resolve().parents[1]
DEFAULT_CONFIG = ROOT / "configs" / "wamis_stations.yaml"
DEFAULT_OUT = ROOT / "data" / "external" / "wamis_daily.csv"
DEFAULT_QC = ROOT / "reports" / "wamis_qc.csv"


# ──────────────────────────────── HTTP ────────────────────────────────
def get_json(path: str, params: dict, base_url: str = BASE_URL, retries: int = 3) -> dict:
    """WAMIS JSON 응답을 dict 로 반환. 일시 오류는 지수 백오프로 재시도."""
    url = f"{base_url.rstrip('/')}/{path}"
    q = {**params, "output": "json"}
    last: Exception | None = None
    for i in range(retries):
        try:
            r = requests.get(url, params=q, timeout=60)
            r.raise_for_status()
            return r.json()
        except (requests.ConnectionError, requests.Timeout) as e:
            last = e
            time.sleep(2**i)
        except requests.HTTPError as e:
            if 500 <= e.response.status_code < 600 and i < retries - 1:
                last = e
                time.sleep(2**i)
                continue
            raise
    raise ConnectionError(
        f"WAMIS 접속 실패({url}). 8080 포트가 막힌 네트워크일 수 있습니다. "
        f"다른 네트워크(집·휴대폰 테더링)에서 다시 실행해 보세요.\n원인: {last}"
    )


def extract_list(payload: dict | list) -> list[dict]:
    """응답에서 레코드 리스트를 찾는다.

    {'list': [...]} 가 기본, 키가 달라도(중첩 포함) 첫 리스트를 쓴다.
    """
    if isinstance(payload, list):
        return payload
    if not isinstance(payload, dict):
        return []
    if "list" in payload and isinstance(payload["list"], list):
        return payload["list"]
    for v in payload.values():
        if isinstance(v, list) and (not v or isinstance(v[0], dict)):
            return v
    for v in payload.values():  # 한 단계 더 들어가 본다 ({"result": {"list": [...]}} 등)
        if isinstance(v, dict):
            found = extract_list(v)
            if found:
                return found
    return []


# ─────────────────────────── 관측소 이름 매칭 ───────────────────────────
def normalize(name: str) -> str:
    """'구미보(하류)' → '구미보하', '강정 고령보 하류' → '강정고령보하'."""
    s = re.sub(r"[\s()\[\]·ㆍ\-_]", "", str(name))
    s = s.replace("하류", "하").replace("상류", "상")
    return s


def resolve_code(name: str, stations: pd.DataFrame) -> str:
    """이름으로 관측소 코드를 찾는다. 정확히 하나면 반환, 아니면 후보를 보여 주고 중단."""
    target = normalize(name)
    norm = stations["obsnm"].map(normalize)
    exact = stations[norm == target]
    if len(exact) == 1:
        return str(exact["obscd"].iloc[0])
    partial = stations[norm.str.contains(re.escape(target)) | norm.map(lambda s: s in target)]
    if len(partial) == 1:
        return str(partial["obscd"].iloc[0])
    cands = partial if len(partial) else stations
    msg = (
        f"'{name}' 관측소를 하나로 정할 수 없습니다 (후보 {len(partial)}개). "
        "configs/wamis_stations.yaml 의 obscd 에 코드를 직접 적어 주세요.\n"
        + cands[["obscd", "obsnm"]].head(15).to_string(index=False)
    )
    raise LookupError(msg)


def list_stations(kind: str, basin: str, base_url: str = BASE_URL) -> pd.DataFrame:
    path = ENDPOINTS[kind][0]
    rows = extract_list(get_json(path, {"basin": basin}, base_url))
    df = pd.DataFrame(rows)
    if df.empty or not {"obscd", "obsnm"} <= set(df.columns):
        print(
            f"  [경고] {path} 관측소 목록이 비어 있거나 obscd/obsnm 열이 없습니다 "
            f"(응답 앞부분: {str(rows)[:200]}). configs/wamis_stations.yaml 의 obscd 를 "
            f"직접 적거나 --probe {kind} 로 응답을 확인하세요."
        )
        return pd.DataFrame(columns=["obscd", "obsnm"])
    df["obscd"] = df["obscd"].astype(str).str.strip()
    df["obsnm"] = df["obsnm"].astype(str).str.strip()
    return df


# ───────────────────────────── 일자료 수집 ─────────────────────────────
def year_ranges(start: date, end: date) -> list[tuple[date, date]]:
    """[start, end] 를 연 단위 구간으로 나눈다 (한 번에 긴 기간을 요청하면 잘리는 경우 대비)."""
    out = []
    y = start.year
    while y <= end.year:
        a = max(start, date(y, 1, 1))
        b = min(end, date(y, 12, 31))
        out.append((a, b))
        y += 1
    return out


def parse_daily(rows: list[dict], value_key: str) -> pd.DataFrame:
    """[{'ymd': '20160101', 'wl': '1.23'}, …] → DataFrame(date, value). 빈값·문자는 NaN."""
    if not rows:
        return pd.DataFrame(columns=["date", "value"])
    df = pd.DataFrame(rows)
    date_col = next((c for c in df.columns if c.lower() in ("ymd", "obsymd", "date")), None)
    if date_col is None or value_key not in df.columns:
        raise RuntimeError(f"일자료 응답 형식이 다릅니다. 열: {list(df.columns)}")
    out = pd.DataFrame(
        {
            "date": pd.to_datetime(df[date_col].astype(str).str.replace("-", ""), format="%Y%m%d"),
            "value": pd.to_numeric(
                df[value_key].astype(str).str.replace(",", "").str.strip(), errors="coerce"
            ),
        }
    )
    return out.dropna(subset=["date"]).drop_duplicates("date").sort_values("date")


def fetch_daily(
    kind: str, obscd: str, start: date, end: date, base_url: str = BASE_URL, sleep: float = 0.3
) -> pd.DataFrame:
    _, default_path, value_key = ENDPOINTS[kind]
    parts = []
    for a, b in year_ranges(start, end):
        params = {"obscd": obscd, "startdt": a.strftime("%Y%m%d"), "enddt": b.strftime("%Y%m%d")}
        if kind in _DAILY_PATH:
            rows = extract_list(get_json(_DAILY_PATH[kind], params, base_url))
        else:  # 첫 호출: 후보 주소를 순서대로 시도해 성공(레코드 있음) 한 주소를 기억
            rows = []
            for cand in [default_path] + [c for c in DAILY_CANDIDATES[kind] if c != default_path]:
                payload = get_json(cand, params, base_url)
                rows = extract_list(payload)
                failed = (
                    isinstance(payload, dict)
                    and str(payload.get("result", {}).get("code", "")).lower() == "failure"
                )
                if rows and not failed:
                    _DAILY_PATH[kind] = cand
                    print(f"  일자료 주소 확인: {kind} → {cand}")
                    break
                time.sleep(sleep)
            if kind not in _DAILY_PATH:
                raise RuntimeError(
                    f"{KIND_LABEL[kind]} 일자료 주소를 찾지 못했습니다 "
                    f"(시도: {DAILY_CANDIDATES[kind]}). 마지막 응답: {str(payload)[:200]}"
                )
        parts.append(parse_daily(rows, value_key))
        time.sleep(sleep)
    df = pd.concat(parts, ignore_index=True) if parts else pd.DataFrame(columns=["date", "value"])
    return df.drop_duplicates("date").sort_values("date").reset_index(drop=True)


# ──────────────────────────────── QC ────────────────────────────────
def qc_report(daily: pd.DataFrame, start: date, end: date) -> pd.DataFrame:
    """관측소×항목별 점검표. 이상값은 0 을 뺀 값 기준 Q3 + 3·IQR 초과(또는 Q1 − 3·IQR 미만)."""
    expected = (pd.Timestamp(end) - pd.Timestamp(start)).days + 1
    rows = []
    keys = ["kind", "obscd", "obsnm", "station"]
    for key, g in daily.groupby(keys, sort=False):
        v = g["value"]
        obs = g.dropna(subset=["value"]).sort_values("date")
        gaps = obs["date"].diff().dt.days.dropna()
        nz = v[v != 0]  # 0 은 별도 집계하므로 이상값 판정에서 제외
        q1, q3 = nz.quantile(0.25), nz.quantile(0.75)
        iqr = q3 - q1
        hi, lo = q3 + 3 * iqr, q1 - 3 * iqr
        row = dict(zip(keys, key, strict=True))
        row.update(
            {
                "bloom_sites": g["bloom_sites"].iloc[0],
                "first_date": obs["date"].min().date() if len(obs) else None,
                "last_date": obs["date"].max().date() if len(obs) else None,
                "expected_days": expected,
                "n_obs": int(v.notna().sum()),
                "n_missing": int(expected - v.notna().sum()),
                "missing_pct": round(100 * (1 - v.notna().sum() / expected), 2),
                "n_zero": int((v == 0).sum()),
                "n_negative": int((v < 0).sum()),
                "n_outlier": int(((nz > hi) | (nz < lo)).sum()) if iqr > 0 else 0,
                "max_gap_days": int(gaps.max()) if len(gaps) else None,
                "has_2026_may_sep": bool(
                    ((obs["date"] >= "2026-05-01") & (obs["date"] <= "2026-09-30")).any()
                ),
                "note": g["note"].iloc[0] if "note" in g else "",
            }
        )
        rows.append(row)
    return pd.DataFrame(rows)


# ─────────────────────────────── probe ──────────────────────────────
PROBE_PATHS = {
    "fw": ["flw_dubobsif", "flw_dubobs", "flw_dubfobs"],
    "wl": ["wl_dubwlobs", "wl_dubwlobsif"],
}
PROBE_PARAMS = [{"basin": "2"}, {"basin": "2", "oper": "y"}, {}, {"bbsnnm": "낙동강"}]


def probe(kind: str, base_url: str, key: str = "") -> None:
    """후보 주소·변수 조합을 하나씩 호출해 상태와 응답 앞부분을 그대로 출력한다 (원인 진단용)."""
    import json

    print(f"== {KIND_LABEL[kind]} 관측소 목록 진단 (base {base_url}) ==")
    for path in PROBE_PATHS[kind]:
        for params in PROBE_PARAMS:
            q = {**params, "output": "json"}
            if key:
                q["key"] = key
            url = f"{base_url.rstrip('/')}/{path}"
            try:
                r = requests.get(url, params=q, timeout=30)
                body = r.text.strip().replace("\n", " ")
                n = 0
                try:
                    n = len(extract_list(json.loads(body)))
                except Exception:
                    pass
                print(f"[{r.status_code}] {path} {params} → 레코드 {n}개 | {body[:300]}")
            except Exception as e:  # noqa: BLE001 - 진단 출력용
                print(f"[ERR] {path} {params} → {e}")
    print("\n위 출력에서 '레코드 N개'가 0보다 큰 줄의 path·params 를 알려 주세요.")


# ─────────────────────────────── main ───────────────────────────────
def load_config(path: Path) -> dict:
    cfg = yaml.safe_load(path.read_text(encoding="utf-8"))
    for st in cfg["stations"]:
        st.setdefault("obscd", {})
        st.setdefault("bloom_sites", [])
        st.setdefault("note", "")
        bad = set(st["kinds"]) - set(ENDPOINTS)
        if bad:
            sys.exit(f"{st['name']}: 알 수 없는 kind {bad} (wl, fw 만 가능)")
    return cfg


def main() -> None:
    ap = argparse.ArgumentParser(
        description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter
    )
    ap.add_argument("--config", type=Path, default=DEFAULT_CONFIG)
    ap.add_argument("--start", help="YYYY-MM-DD (기본: 설정 파일의 start)")
    ap.add_argument("--end", help="YYYY-MM-DD (기본: 오늘)")
    ap.add_argument("--out", type=Path, default=DEFAULT_OUT)
    ap.add_argument("--qc", type=Path, default=DEFAULT_QC)
    ap.add_argument("--base-url", default=BASE_URL)
    ap.add_argument(
        "--sleep", type=float, default=0.6, help="요청 사이 대기(초). 연결 끊김이 잦으면 늘린다"
    )
    ap.add_argument("--list-stations", choices=list(ENDPOINTS), help="관측소 목록만 출력하고 종료")
    ap.add_argument(
        "--probe", choices=list(ENDPOINTS), help="후보 주소·변수로 호출해 원본 응답을 출력(진단)"
    )
    ap.add_argument(
        "--key", default="", help="WAMIS 인증키 (필요한 경우만; 환경변수 WAMIS_KEY 도 가능)"
    )
    args = ap.parse_args()
    import os

    key = args.key or os.getenv("WAMIS_KEY", "")
    if args.probe:
        probe(args.probe, args.base_url, key)
        return

    cfg = load_config(args.config)
    basin = str(cfg.get("basin", "2"))

    if args.list_stations:
        df = list_stations(args.list_stations, basin, args.base_url)
        cols = [c for c in ("obscd", "obsnm", "mngorg", "bbsnnm", "sbsncd") if c in df.columns]
        print(df[cols].to_string(index=False))
        return

    start = date.fromisoformat(args.start or cfg.get("start", "2016-01-01"))
    end = date.fromisoformat(args.end) if args.end else date.today()
    print(f"기간 {start} ~ {end}, 설정 {args.config.relative_to(ROOT)}")

    # 1) 관측소 목록 → 코드 확정 (목록은 코드가 비어 있는 항목이 있는 kind 만 조회)
    need = {
        kind
        for st in cfg["stations"]
        for kind in st["kinds"]
        if not str(st["obscd"].get(kind) or "").strip()
    }
    catalog = {
        k: (
            list_stations(k, basin, args.base_url)
            if k in need
            else pd.DataFrame(columns=["obscd", "obsnm"])
        )
        for k in ENDPOINTS
    }
    jobs: list[dict] = []
    for st in cfg["stations"]:
        for kind in st["kinds"]:
            code = str(st["obscd"].get(kind) or "").strip()
            if not code:
                if catalog[kind].empty:
                    sys.exit(
                        f"{st['name']}({kind}): 관측소 목록을 받지 못해 코드를 정할 수 없습니다. "
                        f"`python scripts/fetch_wamis.py --probe {kind}` 결과를 공유하거나 "
                        "configs/wamis_stations.yaml 의 obscd 에 코드를 직접 적어 주세요."
                    )
                code = resolve_code(st["name"], catalog[kind])
            match = catalog[kind].loc[catalog[kind]["obscd"] == code, "obsnm"]
            obsnm = match.iloc[0] if len(match) else st["name"]
            jobs.append({**st, "kind": kind, "code": code, "obsnm": obsnm})
            print(f"  {KIND_LABEL[kind]:9s} {st['name']:8s} → {code} {obsnm}")

    # 2) 일자료 수집
    frames = []
    for j in jobs:
        df = fetch_daily(j["kind"], j["code"], start, end, args.base_url, args.sleep)
        df["kind"], df["obscd"], df["obsnm"], df["station"] = (
            j["kind"],
            j["code"],
            j["obsnm"],
            j["name"],
        )
        df["bloom_sites"] = ";".join(j["bloom_sites"])
        df["note"] = j["note"]
        frames.append(df)
        print(
            f"  {KIND_LABEL[j['kind']]:9s} {j['name']:8s} {len(df):6d}행  "
            f"결측 {int(df['value'].isna().sum())}  0값 {int((df['value'] == 0).sum())}"
        )
    daily = pd.concat(frames, ignore_index=True)
    daily = daily[["date", "kind", "obscd", "obsnm", "station", "bloom_sites", "value", "note"]]

    # 3) 저장
    args.out.parent.mkdir(parents=True, exist_ok=True)
    daily.drop(columns="note").assign(date=daily["date"].dt.date).to_csv(
        args.out, index=False, encoding="utf-8-sig"
    )
    qc = qc_report(daily, start, end)
    args.qc.parent.mkdir(parents=True, exist_ok=True)
    qc.to_csv(args.qc, index=False, encoding="utf-8-sig")
    print(f"\n저장: {args.out} ({len(daily)}행), {args.qc} ({len(qc)}행)")
    print(qc.drop(columns=["note", "bloom_sites"]).to_string(index=False))


if __name__ == "__main__":
    main()
