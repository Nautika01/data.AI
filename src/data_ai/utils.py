"""로깅, 시드 고정 등 보조 함수."""

from __future__ import annotations

import logging
import random

import numpy as np

from data_ai.config import SEED


def get_logger(name: str = "data_ai", level: int = logging.INFO) -> logging.Logger:
    logger = logging.getLogger(name)
    if not logger.handlers:
        handler = logging.StreamHandler()
        handler.setFormatter(
            logging.Formatter("%(asctime)s | %(levelname)s | %(name)s | %(message)s")
        )
        logger.addHandler(handler)
        logger.propagate = False
    logger.setLevel(level)
    return logger


def set_seed(seed: int = SEED) -> None:
    """재현성을 위해 파이썬·넘파이(및 설치된 경우 torch) 시드를 고정한다."""
    random.seed(seed)
    np.random.seed(seed)
    try:
        import torch

        torch.manual_seed(seed)
        torch.cuda.manual_seed_all(seed)
    except ImportError:
        pass
