"""make_dataset 단계. 과제 선정 후 구현한다."""

from __future__ import annotations

from data_ai.config import ensure_dirs
from data_ai.utils import get_logger, set_seed


def main() -> None:
    set_seed()
    ensure_dirs()
    log = get_logger()
    log.info("make_dataset: 아직 구현되지 않았습니다. 과제 선정 후 작성하세요.")


if __name__ == "__main__":
    main()
