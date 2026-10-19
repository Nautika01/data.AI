"""원본(조류경보제·기상·댐 운영) → data/processed/bloom.parquet 결합 스크립트.

사용법:
  python scripts/make_dataset.py                       # data/raw, data/external 사용
  python scripts/make_dataset.py --sample              # data/sample/{raw,external} 사용
  python scripts/make_dataset.py --config configs/bloom.yaml --raw-dir ... --external-dir ...
"""

from __future__ import annotations

import argparse
from pathlib import Path

from data_ai.bloom import build_dataset, load_config
from data_ai.config import DATA_DIR, EXTERNAL_DIR, PROCESSED_DIR, PROJECT_ROOT, RAW_DIR, ensure_dirs
from data_ai.utils import get_logger, set_seed


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--config", type=Path, default=PROJECT_ROOT / "configs" / "bloom.yaml")
    ap.add_argument("--raw-dir", type=Path, default=RAW_DIR)
    ap.add_argument("--external-dir", type=Path, default=EXTERNAL_DIR)
    ap.add_argument("--sample", action="store_true", help="data/sample 의 샘플 데이터를 사용")
    args = ap.parse_args()
    if args.sample:
        args.raw_dir = DATA_DIR / "sample" / "raw"
        args.external_dir = DATA_DIR / "sample" / "external"

    set_seed()
    ensure_dirs()
    log = get_logger()
    cfg = load_config(args.config)
    df = build_dataset(cfg, args.raw_dir, args.external_dir)
    out = PROCESSED_DIR / f"{cfg['output']}.parquet"
    df.to_parquet(out, index=False)
    df.to_csv(out.with_suffix(".csv"), index=False, encoding="utf-8-sig")
    log.info("저장: %s (%d행 × %d열)", out, *df.shape)


if __name__ == "__main__":
    main()
