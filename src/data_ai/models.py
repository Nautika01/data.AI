"""모델 학습·저장·불러오기."""

from __future__ import annotations

from pathlib import Path
from typing import Any

import joblib

from data_ai.config import MODELS_DIR


def save_model(model: Any, name: str) -> Path:
    MODELS_DIR.mkdir(parents=True, exist_ok=True)
    path = MODELS_DIR / f"{name}.joblib"
    joblib.dump(model, path)
    return path


def load_model(name: str) -> Any:
    return joblib.load(MODELS_DIR / f"{name}.joblib")
