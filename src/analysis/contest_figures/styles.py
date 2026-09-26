"""甲方绘图全局样式：字体、配色、变体主题。

所有 contest_figures 脚本共用；换数据/换主题只改这里。
"""

from __future__ import annotations

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
from matplotlib import font_manager

# ---- 字体 ----
def setup():
    for name in ("Microsoft YaHei", "SimHei", "Noto Sans CJK SC"):
        if any(f.name == name for f in font_manager.fontManager.ttflist):
            plt.rcParams["font.family"] = name
            break
    plt.rcParams.update({
        "axes.unicode_minus": False, "figure.dpi": 110, "savefig.dpi": 300,
        "axes.spines.top": False, "axes.spines.right": False,
        "legend.frameon": False, "legend.fontsize": 9,
    })
    return plt

# ---- 语义配色（≤3 色彩群组 + 强调色，沿用 board_charts 主色系）----
C_TENSOR = "#D6E8F5"; C_TENSOR_E = "#2E86AB"
C_OP = "#FDEBD0"; C_OP_E = "#D35400"
C_ACCENT = "#E67E22"; C_OK = "#27AE60"
C_DDR = "#F5F5F5"; C_GRAY = "#7F8C8D"
C_SG = ["#2E86AB", "#27AE60", "#F18F01", "#8E44AD", "#C0392B"]

# ---- 变体主题（每图多类型供论文挑选）----
THEMES = {
    # classic：规范版（验收基线），白底、实色
    "classic": {
        "bg": "#FFFFFF", "panel_bg": "#FBFCFC", "grid": (0.25, "--"),
        "cmap": "magma", "line_cycle": ["#2E86AB", "#F18F01", "#27AE60", "#A23B72", "#7F8C8D"],
        "alpha": 1.0, "edge_width": 1.3,
    },
    # modern：高级感（微渐变底、柔网格、粗主线条）
    "modern": {
        "bg": "#FAFBFD", "panel_bg": "#F4F7FB", "grid": (0.35, "-"),
        "cmap": "viridis", "line_cycle": ["#1F6FB2", "#E67E22", "#16A085", "#8E44AD", "#5D6D7E"],
        "alpha": 0.95, "edge_width": 1.8,
    },
    # heat：热力/浓色（"花里胡哨"档，用于热力条、时间热力、密度底纹）
    "heat": {
        "bg": "#FFFFFF", "panel_bg": "#FFF9F2", "grid": (0.2, ":"),
        "cmap": "inferno", "line_cycle": ["#D35400", "#2E86AB", "#F1C40F", "#C0392B", "#8E44AD"],
        "alpha": 0.9, "edge_width": 1.6,
    },
}

def apply_theme(theme: str):
    t = THEMES[theme]
    plt.rcParams["axes.facecolor"] = t["panel_bg"]
    plt.rcParams["figure.facecolor"] = t["bg"]
    plt.rcParams["savefig.facecolor"] = t["bg"]
    return t
