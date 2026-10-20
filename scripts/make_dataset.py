"""대회 번들(data/raw) → data/processed/bloom.parquet 결합 스크립트.

python scripts/make_dataset.py                      # configs/bloom.yaml, data/raw
python scripts/make_dataset.py --bundle-dir <경로>
"""

from __future__ import annotations

import argparse
from pathlib import Path

from data_ai.bloom import build_dataset, load_config
from data_ai.config import PROCESSED_DIR, PROJECT_ROOT, ensure_dirs
from data_ai.utils import get_logger, set_seed


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--config", type=Path, default=PROJECT_ROOT / "configs" / "bloom.yaml")
    ap.add_argument("--bundle-dir", type=Path, default=None)
    args = ap.parse_args()

    set_seed()
    ensure_dirs()
    log = get_logger()
    cfg = load_config(args.config)
    df = build_dataset(cfg, args.bundle_dir)
    out = PROCESSED_DIR / f"{cfg['output']}.parquet"
    df.to_parquet(out, index=False)
    df.to_csv(out.with_suffix(".csv"), index=False, encoding="utf-8-sig")
    log.info("저장: %s (%d행 × %d열)", out, *df.shape)


if __name__ == "__main__":
    main()
