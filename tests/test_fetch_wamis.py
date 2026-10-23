import importlib.util
import sys
from datetime import date
from pathlib import Path

import pandas as pd
import pytest

ROOT = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location("fetch_wamis", ROOT / "scripts" / "fetch_wamis.py")
mod = importlib.util.module_from_spec(spec)
sys.modules["fetch_wamis"] = mod
spec.loader.exec_module(mod)

STATIONS = pd.DataFrame(
    {
        "obscd": ["2001601", "2001602", "2001603", "2001604", "2013611"],
        "obsnm": ["구미대교", "구미보(하류)", "강정 고령보 하류", "성주군(성주대교)", "성주"],
    }
)


def test_normalize_handles_spaces_parens_and_suffix():
    assert mod.normalize("구미보(하류)") == "구미보하"
    assert mod.normalize("강정 고령보 하류") == "강정고령보하"
    assert mod.normalize("창녕함안보 상류") == "창녕함안보상"


def test_resolve_code_exact_and_fuzzy():
    assert mod.resolve_code("구미대교", STATIONS) == "2001601"
    assert mod.resolve_code("구미보하", STATIONS) == "2001602"
    assert mod.resolve_code("강정고령보하", STATIONS) == "2001603"
    assert mod.resolve_code("성주대교", STATIONS) == "2001604"  # 괄호 안 이름 우선, '성주' 와 구분


def test_resolve_code_ambiguous_raises_with_candidates():
    with pytest.raises(LookupError) as e:
        mod.resolve_code("대교", STATIONS)
    assert "2001601" in str(e.value) and "2001604" in str(e.value)


def test_extract_list_variants():
    assert mod.extract_list({"count": 2, "list": [{"a": 1}, {"a": 2}]}) == [{"a": 1}, {"a": 2}]
    assert mod.extract_list({"result": {"code": 0}, "data": [{"a": 1}]}) == [{"a": 1}]
    assert mod.extract_list([{"a": 1}]) == [{"a": 1}]
    assert mod.extract_list({"result": {"code": 0}}) == []


def test_year_ranges_splits_by_year():
    r = mod.year_ranges(date(2024, 3, 5), date(2026, 2, 1))
    assert r == [
        (date(2024, 3, 5), date(2024, 12, 31)),
        (date(2025, 1, 1), date(2025, 12, 31)),
        (date(2026, 1, 1), date(2026, 2, 1)),
    ]


def test_parse_daily_coerces_values():
    rows = [
        {"ymd": "20160101", "wl": "1.23"},
        {"ymd": "20160102", "wl": ""},
        {"ymd": "20160103", "wl": "1,234.5"},
        {"ymd": "20160103", "wl": "9"},  # 중복 날짜는 첫 값만
    ]
    df = mod.parse_daily(rows, "wl")
    assert list(df["date"].dt.strftime("%Y-%m-%d")) == ["2016-01-01", "2016-01-02", "2016-01-03"]
    assert df["value"].tolist()[0] == 1.23
    assert pd.isna(df["value"].tolist()[1])
    assert df["value"].tolist()[2] == 1234.5


def test_parse_daily_wrong_schema_raises():
    with pytest.raises(RuntimeError):
        mod.parse_daily([{"foo": "20160101", "bar": "1"}], "wl")


def test_fetch_daily_uses_mocked_api(monkeypatch):
    calls = []

    def fake_get_json(path, params, base_url=mod.BASE_URL, retries=3):
        calls.append((path, params["startdt"], params["enddt"]))
        y = params["startdt"][:4]
        return {"list": [{"ymd": f"{y}0601", "fw": "10.5"}, {"ymd": f"{y}0602", "fw": "0"}]}

    monkeypatch.setattr(mod, "get_json", fake_get_json)
    monkeypatch.setattr(mod.time, "sleep", lambda *_: None)
    mod._DAILY_PATH.clear()
    df = mod.fetch_daily("fw", "X", date(2024, 1, 1), date(2025, 12, 31))
    assert [c[0] for c in calls] == ["flw_dtdata", "flw_dtdata"]
    assert calls[0][1:] == ("20240101", "20241231")
    assert len(df) == 4 and df["value"].tolist() == [10.5, 0.0, 10.5, 0.0]


def test_qc_report_counts_gaps_zeros_outliers():
    dates = pd.to_datetime(
        [f"2026-01-{d:02d}" for d in (1, 2, 3, 4, 5, 6, 8, 9, 10)] + ["2026-05-10"]
    )
    daily = pd.DataFrame(
        {
            "date": dates,
            "kind": "wl",
            "obscd": "A",
            "obsnm": "칠곡보상류",
            "station": "칠곡보상",
            "bloom_sites": "HP;GJGR",
            "value": [1.0, 0.0, 1.1, 1.2, 1.0, 1.1, 0.9, 1.0, 1.2, 50.0],
            "note": "0값 제외",
        }
    )
    qc = mod.qc_report(daily, date(2026, 1, 1), date(2026, 1, 12))
    assert len(qc) == 1
    r = qc.iloc[0]
    assert r["expected_days"] == 12 and r["n_obs"] == 10 and r["n_missing"] == 2
    assert r["n_zero"] == 1 and r["n_negative"] == 0
    assert r["n_outlier"] == 1  # 50.0 만 이상값, 0 은 n_zero 로만 집계
    assert r["max_gap_days"] == 120  # 2026-01-10 → 2026-05-10
    assert bool(r["has_2026_may_sep"]) is True
    assert r["note"] == "0값 제외"


def test_default_config_loads_and_has_12_series():
    cfg = mod.load_config(mod.DEFAULT_CONFIG)
    n = sum(len(st["kinds"]) for st in cfg["stations"])
    assert n == 12
    assert {st["name"] for st in cfg["stations"]} >= {"구미대교", "삼랑진교", "창녕함안보상"}


def test_fetch_daily_falls_back_to_next_candidate_path(monkeypatch):
    def fake_get_json(path, params, base_url=mod.BASE_URL, retries=3):
        if path == "flw_dtdata":
            return {"result": {"code": "failure", "msg": "경로가 올바르지 않습니다!"}}
        return {"list": [{"ymd": params["startdt"], "fw": "3.3"}]}

    monkeypatch.setattr(mod, "get_json", fake_get_json)
    monkeypatch.setattr(mod.time, "sleep", lambda *_: None)
    mod._DAILY_PATH.clear()
    df = mod.fetch_daily("fw", "X", date(2024, 1, 1), date(2024, 12, 31))
    assert mod._DAILY_PATH["fw"] == "flw_dtdataif"
    assert df["value"].tolist() == [3.3]
