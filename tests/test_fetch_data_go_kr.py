import importlib.util
import sys
from pathlib import Path

spec = importlib.util.spec_from_file_location(
    "fetch_data_go_kr", Path(__file__).resolve().parents[1] / "scripts" / "fetch_data_go_kr.py"
)
mod = importlib.util.module_from_spec(spec)
sys.modules["fetch_data_go_kr"] = mod
spec.loader.exec_module(mod)

SAMPLE = """<?xml version="1.0" encoding="UTF-8"?>
<response>
  <header><resultCode>00</resultCode><resultMsg>NORMAL SERVICE.</resultMsg></header>
  <body>
    <items>
      <item><ptNo>2022G05</ptNo><wmcymd>2026-08-18</wmcymd><cellCo>483,021</cellCo></item>
      <item><ptNo>2022G05</ptNo><wmcymd>2026-08-13</wmcymd><cellCo>49,400</cellCo></item>
    </items>
    <numOfRows>1000</numOfRows><pageNo>1</pageNo><totalCount>2</totalCount>
  </body>
</response>"""


def test_parse_page():
    rows, total, code, msg = mod.parse_page(SAMPLE)
    assert total == 2 and code == "00"
    assert rows[0] == {"ptNo": "2022G05", "wmcymd": "2026-08-18", "cellCo": "483,021"}


def test_resolve_key_unquotes_encoded(monkeypatch):
    monkeypatch.setenv("DATA_GO_KR_API_KEY", "abc%2Bdef%3D%3D")
    assert mod.resolve_key() == "abc+def=="
