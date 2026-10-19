"""데이터 로딩·저장."""

from __future__ import annotations

from pathlib import Path

import pandas as pd

from data_ai.config import PROCESSED_DIR, RAW_DIR

_READERS = {
    ".csv": pd.read_csv,
    ".parquet": pd.read_parquet,
    ".xlsx": pd.read_excel,
    ".json": pd.read_json,
}


def read_table(path: str | Path, **kwargs) -> pd.DataFrame:
    """확장자에 따라 적절한 pandas 리더로 테이블을 읽는다."""
    path = Path(path)
    try:
        reader = _READERS[path.suffix.lower()]
    except KeyError as e:
        raise ValueError(f"지원하지 않는 파일 형식: {path.suffix}") from e
    return reader(path, **kwargs)


def load_raw(name: str, **kwargs) -> pd.DataFrame:
    """data/raw/<name> 파일을 읽는다."""
    return read_table(RAW_DIR / name, **kwargs)


def save_processed(df: pd.DataFrame, name: str) -> Path:
    """data/processed/<name>.parquet 로 저장하고 경로를 반환한다."""
    PROCESSED_DIR.mkdir(parents=True, exist_ok=True)
    out = PROCESSED_DIR / f"{name}.parquet"
    df.to_parquet(out, index=False)
    return out


def load_processed(name: str) -> pd.DataFrame:
    return pd.read_parquet(PROCESSED_DIR / f"{name}.parquet")
