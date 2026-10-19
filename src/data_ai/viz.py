"""보고서·노트북 공통 시각화 설정 (한글 폰트, 팔레트, 스타일)."""

from __future__ import annotations

import matplotlib as mpl
import matplotlib.pyplot as plt
from matplotlib import font_manager

# 범주형 팔레트: 고정 순서로 사용(순환 금지). 1~3번은 산점도에서도 구분 가능.
SERIES = ["#2a78d6", "#eb6834", "#1baf7a", "#eda100", "#e87ba4", "#008300", "#6250d6", "#e34948"]
# 순차형(단일 색상, 연함→진함)
SEQUENTIAL = ["#cde2fb", "#9ec5f4", "#6da7ec", "#3987e5", "#256abf", "#184f95", "#0d366b"]
# 경보 단계 상태 색 (정상/관심/경계/대발생). 상태 색은 범례 라벨과 함께만 사용.
ALERT_COLORS = {0: "#898781", 1: "#fab219", 2: "#ec835a", 3: "#d03b3b"}
ALERT_NAMES = {0: "정상", 1: "관심", 2: "경계", 3: "대발생"}
INK = "#0b0b0b"
INK_SECONDARY = "#52514e"
MUTED = "#898781"
GRID = "#e1e0d9"
SURFACE = "#fcfcfb"

_KO_FONTS = ["Malgun Gothic", "AppleGothic", "NanumGothic", "Noto Sans CJK KR", "WenQuanYi Zen Hei"]


def set_korean_font() -> str | None:
    """설치된 한글 폰트를 찾아 matplotlib 기본 폰트로 지정한다."""
    installed = {f.name for f in font_manager.fontManager.ttflist}
    for name in _KO_FONTS:
        if name in installed:
            mpl.rcParams["font.family"] = name
            mpl.rcParams["axes.unicode_minus"] = False
            return name
    return None


def apply_style() -> None:
    """얇은 마크, 옅은 격자, 불필요한 테두리 제거."""
    set_korean_font()
    mpl.rcParams.update(
        {
            "figure.facecolor": SURFACE,
            "axes.facecolor": SURFACE,
            "axes.edgecolor": "#c3c2b7",
            "axes.spines.top": False,
            "axes.spines.right": False,
            "axes.grid": True,
            "grid.color": GRID,
            "grid.linewidth": 0.6,
            "axes.axisbelow": True,
            "axes.titleweight": "semibold",
            "axes.titlesize": 12,
            "axes.labelcolor": INK_SECONDARY,
            "xtick.color": MUTED,
            "ytick.color": MUTED,
            "text.color": INK,
            "lines.linewidth": 1.6,
            "lines.markersize": 5,
            "legend.frameon": False,
            "figure.dpi": 110,
            "savefig.dpi": 150,
            "savefig.bbox": "tight",
        }
    )
    plt.rcParams["axes.prop_cycle"] = mpl.cycler(color=SERIES)


def alert_lines(ax, thresholds: dict[str, float] | None = None, axis: str = "y") -> None:
    """경보 기준선(관심·경계·대발생)을 점선으로 표시하고 라벨을 붙인다."""
    from data_ai.bloom import ALERT_THRESHOLDS

    thresholds = thresholds or ALERT_THRESHOLDS
    level_of = {"관심": 1, "경계": 2, "대발생": 3}
    for name, v in thresholds.items():
        color = ALERT_COLORS[level_of[name]]
        if axis == "y":
            ax.axhline(v, color=color, linestyle=(0, (4, 3)), linewidth=1)
            ax.annotate(
                name,
                xy=(1.0, v),
                xycoords=("axes fraction", "data"),
                xytext=(4, 0),
                textcoords="offset points",
                va="center",
                fontsize=8,
                color=INK_SECONDARY,
            )
        else:
            ax.axvline(v, color=color, linestyle=(0, (4, 3)), linewidth=1)
