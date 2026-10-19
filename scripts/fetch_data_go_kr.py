"""공공데이터포털(data.go.kr) XML API를 페이지 단위로 호출해 CSV로 저장한다.

인증키는 .env 의 DATA_GO_KR_API_KEY 에서 읽는다(저장소에 절대 넣지 않는다).
포털의 "Decoding" 키를 넣는 것을 권장하며, "Encoding" 키(%2B, %3D 포함)를 넣어도 자동으로 복원한다.

예) 조류경보제 조회서비스
  python scripts/fetch_data_go_kr.py \\
      --endpoint https://apis.data.go.kr/1480523/nieragainstalgae \\
      --path <오퍼레이션명: 포털 '요청변수' 표 위의 URL 마지막 부분> \\
      --param ptNo=2022G05 --param startDate=20180101 --param endDate=20261231 \\
      --out data/raw/algae_api_2022G05.csv

요청변수 이름(ptNo, startDate 등)은 포털 상세 페이지의 '요청변수' 표와
참고문서(xlsx)에 적힌 그대로 쓴다.
"""

from __future__ import annotations

import argparse
import os
import sys
import time
import urllib.parse
import xml.etree.ElementTree as ET
from pathlib import Path

import pandas as pd
import requests
from dotenv import load_dotenv


def resolve_key(env_name: str = "DATA_GO_KR_API_KEY") -> str:
    load_dotenv()
    key = os.getenv(env_name, "").strip()
    if not key:
        sys.exit(f"{env_name} 가 .env 에 없습니다. 포털 '일반 인증키(Decoding)'를 넣어 주세요.")
    if "%" in key:  # Encoding 키를 넣은 경우 → 원문으로 복원 (requests 가 다시 인코딩함)
        key = urllib.parse.unquote(key)
    return key


def parse_page(xml_text: str) -> tuple[list[dict], int, str, str]:
    """표준 응답(header/body/items/item)을 파싱해 (rows, totalCount, resultCode, resultMsg) 반환."""
    root = ET.fromstring(xml_text)
    code = (root.findtext(".//header/resultCode") or "").strip()
    msg = (root.findtext(".//header/resultMsg") or "").strip()
    total = int(root.findtext(".//body/totalCount") or 0)
    rows = [{child.tag: (child.text or "").strip() for child in item} for item in root.iter("item")]
    return rows, total, code, msg


def fetch_all(
    endpoint: str,
    path: str,
    params: dict[str, str],
    key: str,
    num_rows: int = 1000,
    sleep: float = 0.2,
    max_pages: int = 10_000,
) -> pd.DataFrame:
    url = endpoint.rstrip("/") + ("/" + path.lstrip("/") if path else "")
    rows: list[dict] = []
    page = 1
    while page <= max_pages:
        q = {"serviceKey": key, "pageNo": page, "numOfRows": num_rows, **params}
        r = requests.get(url, params=q, timeout=60)
        r.raise_for_status()
        page_rows, total, code, msg = parse_page(r.text)
        if code not in ("00", "0", ""):
            sys.exit(f"API 오류 resultCode={code} resultMsg={msg}\n응답 앞부분: {r.text[:300]}")
        rows.extend(page_rows)
        print(f"page {page}: {len(page_rows)}행 (누적 {len(rows)}/{total})")
        if not page_rows or len(rows) >= total:
            break
        page += 1
        time.sleep(sleep)
    return pd.DataFrame(rows)


def main() -> None:
    ap = argparse.ArgumentParser(
        description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter
    )
    ap.add_argument(
        "--endpoint", required=True, help="예: https://apis.data.go.kr/1480523/nieragainstalgae"
    )
    ap.add_argument("--path", default="", help="오퍼레이션명 (엔드포인트 뒤에 붙는 경로)")
    ap.add_argument(
        "--param", action="append", default=[], help="요청변수 key=value (여러 번 지정 가능)"
    )
    ap.add_argument("--out", type=Path, required=True)
    ap.add_argument("--num-rows", type=int, default=1000)
    ap.add_argument("--key-env", default="DATA_GO_KR_API_KEY")
    args = ap.parse_args()

    params = dict(p.split("=", 1) for p in args.param)
    df = fetch_all(args.endpoint, args.path, params, resolve_key(args.key_env), args.num_rows)
    args.out.parent.mkdir(parents=True, exist_ok=True)
    df.to_csv(args.out, index=False, encoding="utf-8-sig")
    print(f"저장: {args.out} ({len(df)}행 × {df.shape[1]}열)")
    if len(df):
        print("열 이름:", ", ".join(df.columns))


if __name__ == "__main__":
    main()
