"""赛题原文四张插图的「本队真实数据」重绘版。

数据来源（全部本地，不引入外部数据）：
  图1/图2 计算图素材 : data/raw/a/official-cases.zip::data/case_002.json（官方算例，只读）
  图2 切图方案       : results/a/board-feed-farmer/20260924/artifacts/case002/c5/plan.json
  图3 加速比汇总     : results/a/p123-report-farmer/20260924-full-v3/aggregate.json（E0 官方 evaluator）
  图4 硬件配置       : results/a/board-feed-farmer/20260924/artifacts/case001/c1official/result.json
                       + 赛题 1.5 节 L2 参数（问题3固定配置）

输出: figures/a/contest-figures-20260925/fig{1..4}_*.{pdf,png} + SOURCES.md
运行: .venv/Scripts/python.exe src/analysis/contest_figures/make_all.py
"""

from __future__ import annotations

import csv
import json
import zipfile
from collections import defaultdict
from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
from matplotlib import font_manager
from matplotlib.patches import FancyArrowPatch, FancyBboxPatch

ROOT = Path(__file__).resolve().parents[3]
OUT = ROOT / "figures" / "a" / "contest-figures-20260925"

# ---- 配色（沿用 board_charts 主色系，≤3 色彩群组 + 强调色）----
C_TENSOR = "#D6E8F5"   # 张量节点填充（浅蓝）
C_TENSOR_E = "#2E86AB"  # 张量描边（主蓝）
C_OP = "#FDEBD0"       # 操作节点填充（浅橙）
C_OP_E = "#D35400"     # 操作描边
C_ACCENT = "#E67E22"   # 强调（插入节点）
C_OK = "#27AE60"       # 正确/无开销
C_SG = ["#2E86AB", "#27AE60", "#F18F01", "#8E44AD", "#C0392B"]  # 子图着色
C_DDR = "#F5F5F5"
C_GRAY = "#7F8C8D"


def setup():
    for name in ("Microsoft YaHei", "SimHei", "Noto Sans CJK SC"):
        if any(f.name == name for f in font_manager.fontManager.ttflist):
            plt.rcParams["font.family"] = name
            break
    plt.rcParams.update({
        "axes.unicode_minus": False, "figure.dpi": 110, "savefig.dpi": 300,
        "axes.spines.top": False, "axes.spines.right": False,
    })


def save(fig, name):
    OUT.mkdir(parents=True, exist_ok=True)
    for suf in (".pdf", ".png"):
        fig.savefig(OUT / (name + suf), bbox_inches="tight")
    plt.close(fig)
    print("saved", name)


def box(ax, x, y, w, h, fc, ec, text, fs=9, lw=1.2, ls="-", tc="#2C3E50", bold=False, zorder=3, rounding=0.08):
    ax.add_patch(FancyBboxPatch((x, y), w, h, boxstyle=f"round,pad=0.02,rounding_size={rounding}",
                                fc=fc, ec=ec, lw=lw, ls=ls, zorder=zorder))
    ax.text(x + w / 2, y + h / 2, text, ha="center", va="center", fontsize=fs, color=tc,
            fontweight="bold" if bold else "normal", zorder=zorder + 1, linespacing=1.25)


def arrow(ax, x1, y1, x2, y2, color="#34495E", lw=1.3, ls="-", zorder=2):
    ax.add_patch(FancyArrowPatch((x1, y1), (x2, y2), arrowstyle="-|>", mutation_scale=11,
                                 color=color, lw=lw, linestyle=ls, zorder=zorder,
                                 shrinkA=1, shrinkB=1))


# ---------------------------------------------------------------- 图1
def fig1(d):
    t = {x["id"]: x for x in d["tensors"]}
    fig, (axL, axR) = plt.subplots(1, 2, figsize=(12.6, 5.6),
                                   gridspec_kw={"width_ratios": [1, 2.35]})
    for ax in (axL, axR):
        ax.set_xlim(0, 10); ax.set_ylim(0, 10); ax.axis("off")

    # 左：原始 Matmul 语义（对应题面 1.2 节）
    axL.set_title("原始 Matmul 计算过程（题面语义）", fontsize=12, fontweight="bold")
    box(axL, 0.4, 5.2, 2.4, 2.6, "#EAF2F8", C_TENSOR_E, "左矩阵\n$[m,k]$", fs=11)
    box(axL, 3.6, 5.2, 2.4, 2.6, "#EAF2F8", C_TENSOR_E, "右矩阵\n$[k,n]$", fs=11)
    box(axL, 6.8, 5.2, 2.4, 2.6, "#EAF2F8", C_TENSOR_E, "结果\n$[m,n]$", fs=11)
    axL.text(3.2, 6.5, "$\\times$", fontsize=16, ha="center")
    axL.text(6.4, 6.5, "$=$", fontsize=16, ha="center")
    # k 维切 4 块
    for yy in (6.0, 6.8, 7.6):
        axL.plot([0.4, 2.8], [yy, yy], color=C_ACCENT, lw=0.9, ls="--")
        axL.plot([3.6, 6.0], [yy, yy], color=C_ACCENT, lw=0.9, ls="--")
    axL.annotate("按 $k$ 维切 4 块\n（$k$ 维分块乘）", xy=(1.6, 6.8), xytext=(0.6, 2.9),
                 fontsize=10, color=C_ACCENT,
                 arrowprops=dict(arrowstyle="->", color=C_ACCENT))
    axL.text(5.0, 1.6, "单次大矩阵乘 → 4 个分块乘 + 归并\n即下方细粒度计算图（case_002 实测）",
             ha="center", fontsize=9.5, color="#566573")

    # 右：真实细粒度计算图（case_002 诱导子图）
    axR.set_title("细粒度计算图 — case_002 真实片段（节点 id / 字节数 / cycles 为实测值）",
                  fontsize=12, fontweight="bold")
    # DDR 带
    axR.add_patch(FancyBboxPatch((0.15, 8.55), 9.7, 1.15, boxstyle="round,pad=0.02,rounding_size=0.08",
                                 fc=C_DDR, ec="#BDC3C7", ls="--", zorder=1))
    axR.text(0.35, 9.45, "DDR", fontsize=9, color=C_GRAY, style="italic")
    box(axR, 0.5, 8.7, 1.9, 0.8, C_TENSOR, C_TENSOR_E, "T…000 · 1536 B", fs=8.5)
    box(axR, 3.0, 8.7, 1.9, 0.8, C_TENSOR, C_TENSOR_E, "T…002 · 4608 B\n(共享权重)", fs=8.5)
    box(axR, 7.6, 8.7, 1.9, 0.8, C_TENSOR, C_TENSOR_E, "T…594 · 1536 B\n(最终输出)", fs=8.5)

    # COPY_IN 层
    box(axR, 0.7, 7.0, 1.5, 0.7, C_OP, C_OP_E, "COPY_IN\nid=1 · MTE2", fs=8)
    box(axR, 3.2, 7.0, 1.5, 0.7, C_OP, C_OP_E, "COPY_IN\nid=2 · MTE2", fs=8)
    arrow(axR, 1.45, 8.7, 1.45, 7.75)
    arrow(axR, 3.95, 8.7, 3.95, 7.75)

    # L1 张量
    box(axR, 0.6, 5.6, 1.7, 0.75, C_TENSOR, C_TENSOR_E, "T…001 · L1\n1536 B", fs=8.5)
    box(axR, 3.1, 5.6, 1.7, 0.75, C_TENSOR, C_TENSOR_E, "T…003 · L1\n4608 B", fs=8.5)
    arrow(axR, 1.45, 7.0, 1.45, 6.4)
    arrow(axR, 3.95, 7.0, 3.95, 6.4)

    # 4 路 MATMUL（真实 id/cycles）
    xs = [0.45, 2.65, 4.85, 7.05]
    mids = ["id=3", "id=5", "id=7", "id=9"]
    rids = ["id=4", "id=6", "id=8", "id=10"]
    for x, mi in zip(xs, mids):
        box(axR, x, 3.9, 1.7, 0.75, C_OP, C_OP_E, f"MATMUL {mi}\nPIPE_M · 300cyc", fs=8)
        arrow(axR, 1.45 if x < 2 else 3.95, 5.6, x + 0.85, 4.7)
    for x, ri in zip(xs, rids):
        box(axR, x, 2.35, 1.7, 0.7, C_OP, C_OP_E, f"RELU {ri}\nPIPE_V", fs=8)
        arrow(axR, x + 0.85, 3.9, x + 0.85, 3.08)

    # ADD 汇合（2 路入画 + 省略号）
    box(axR, 3.3, 1.0, 1.9, 0.7, C_OP, C_OP_E, "ADD id=1999\nPIPE_V", fs=8.5)
    for x in xs[:2]:
        arrow(axR, x + 0.85, 2.35, 4.0 if x == xs[0] else 4.5, 1.75)
    axR.text(6.4, 1.9, "……（4 路两两归并）", fontsize=8, color=C_GRAY)
    arrow(axR, 5.2, 1.35, 7.6, 1.35, ls="--")
    box(axR, 7.6, 1.0, 1.7, 0.7, C_OP, C_OP_E, "COPY_OUT\nid=2197 · MTE3", fs=8)
    arrow(axR, 8.45, 1.0, 8.45, 0.55)
    axR.text(8.45, 0.3, "回写 DDR", fontsize=8, ha="center", color=C_GRAY)

    # 图例
    box(axR, 5.6, 8.75, 0.42, 0.3, C_TENSOR, C_TENSOR_E, "", fs=6)
    axR.text(6.1, 8.9, "张量节点 Tensor", fontsize=8, va="center")
    box(axR, 5.6, 8.3, 0.42, 0.3, C_OP, C_OP_E, "", fs=6)
    axR.text(6.1, 8.45, "操作节点 Op", fontsize=8, va="center")
    save(fig, "fig1-example-computational-graph")


# ---------------------------------------------------------------- 图2
def fig2(d):
    ops = {x["id"]: x for x in d["ops"]}
    t = {x["id"]: x for x in d["tensors"]}
    plan = json.loads((ROOT / "results/a/board-feed-farmer/20260924/artifacts/case002/c5/plan.json")
                      .read_text(encoding="utf-8"))
    n2s = {int(k): v for k, v in plan["node_to_subgraph"].items()}
    assert n2s[10] == 1 and n2s[20] == 2 and n2s[1999] == 199 and n2s[3] == 1

    fig, (axA, axB) = plt.subplots(1, 2, figsize=(12.6, 5.2),
                                   gridspec_kw={"width_ratios": [1.45, 1]})
    for ax in (axA, axB):
        ax.set_xlim(0, 10); ax.set_ylim(0, 10); ax.axis("off")

    # (a) 情况1：子图间插入数据搬运节点 —— 真实边界
    axA.set_title("(a) 情况1：跨子图边界插入数据搬运节点（case_002 · 5核方案真实边界）",
                  fontsize=11.5, fontweight="bold")
    axA.text(5, 9.3, "切图前（原始计算图）", fontsize=10, ha="center", color="#566573")
    box(axA, 0.4, 7.6, 2.1, 0.8, C_OP, C_SG[0], "RELU id=10\nsgid=1", fs=8.5)
    box(axA, 0.4, 5.9, 2.1, 0.8, C_OP, C_SG[1], "RELU id=20\nsgid=2", fs=8.5)
    box(axA, 3.6, 6.75, 2.5, 0.8, C_TENSOR, C_TENSOR_E, "T…011 / T…023 · UB\n1536 B", fs=8.5)
    box(axA, 7.2, 6.75, 2.2, 0.8, C_OP, C_SG[2], "ADD id=1999\nsgid=199", fs=8.5)
    arrow(axA, 2.5, 8.0, 3.6, 7.35); arrow(axA, 2.5, 6.3, 3.6, 6.95)
    arrow(axA, 6.1, 7.15, 7.2, 7.15)
    axA.plot([3.35, 3.35], [5.6, 8.7], color=C_GRAY, lw=0.8, ls=":")

    axA.text(5, 4.9, "切图后（场景 A：子图 = Task，跨 Task 必经 DDR 中转）",
             fontsize=10, ha="center", color="#566573")
    y0 = 3.3
    for row, (rid, sg, col) in enumerate([(10, 1, C_SG[0]), (20, 2, C_SG[1])]):
        yy = y0 - row * 1.7
        box(axA, 0.3, yy, 1.75, 0.85, C_OP, col, f"RELU id={rid}\nsgid={sg}", fs=8.5)
        # 插入的 COPY 链（强调色虚线框）
        axA.add_patch(FancyBboxPatch((2.55, yy - 0.28), 4.9, 1.4, boxstyle="round,pad=0.02,rounding_size=0.1",
                                     fc="none", ec=C_ACCENT, lw=1.4, ls=(0, (4, 2)), zorder=1))
        box(axA, 2.75, yy, 1.35, 0.8, "#FDF2E9", C_ACCENT, "COPY_OUT\nMTE3", fs=8)
        box(axA, 4.45, yy, 1.15, 0.8, C_DDR, C_ACCENT, "DDR", fs=9, bold=True)
        box(axA, 5.95, yy, 1.35, 0.8, "#FDF2E9", C_ACCENT, "COPY_IN\nMTE2", fs=8)
        arrow(axA, 2.05, yy + 0.42, 2.75, yy + 0.42)
        arrow(axA, 4.10, yy + 0.42, 4.45, yy + 0.42)
        arrow(axA, 5.60, yy + 0.42, 5.95, yy + 0.42)
        arrow(axA, 7.30, yy + 0.42, 8.0, yy + 0.42)
    box(axA, 8.0, y0 - 0.85, 1.7, 2.0, C_OP, C_SG[2], "ADD\nid=1999\nsgid=199", fs=8.5)
    axA.text(5.0, 2.05 - 1.55, "红色虚线框 = 官方 evaluator 按规则自动插入的搬运节点",
             fontsize=9, ha="center", color=C_ACCENT)
    axA.text(5.0, 0.55, "该边界新增 DDR 搬运 = 2 × (1536 B 写 + 1536 B 读) = 6144 B（按张量 size 实测）",
             fontsize=9.5, ha="center", color="#2C3E50",
             bbox=dict(boxstyle="round,pad=0.35", fc="#FEF9E7", ec=C_ACCENT, lw=0.8))

    # (b) 情况2未触发：共享输入聚合于同一子图
    axB.set_title("(b) 情况2未触发：共享输入聚合于同一子图", fontsize=11.5, fontweight="bold")
    box(axB, 3.1, 6.6, 3.6, 0.9, C_TENSOR, C_TENSOR_E, "T…003 · L1\n4608 B（共享权重）", fs=9)
    xs = [0.5, 2.75, 5.0, 7.25]
    for x, mi in zip(xs, ["id=3", "id=5", "id=7", "id=9"]):
        box(axB, x, 4.4, 1.85, 0.8, C_OP, C_SG[0], f"MATMUL {mi}\nsgid=1", fs=8.5)
        arrow(axB, 4.9, 6.6, x + 0.92, 5.25)
    axB.add_patch(FancyBboxPatch((0.25, 4.1), 9.3, 1.5, boxstyle="round,pad=0.02,rounding_size=0.1",
                                 fc="none", ec=C_SG[0], lw=1.3, ls=(0, (4, 2)), zorder=1))
    axB.text(5, 3.55, "Subgraph id = 1（同一子图 → 核内直接复用，不经 DDR）",
             fontsize=9, ha="center", color=C_SG[0])
    axB.text(5, 2.2, "√ case_002 · 5核方案：跨子图共享张量数 = 0", fontsize=11, ha="center",
             color=C_OK, fontweight="bold")
    axB.text(5, 1.25, "切图阶段将共享输入的消费者聚合于同一子图，\n避免了情况2的重复读取开销",
             fontsize=9, ha="center", color="#566573")
    save(fig, "fig2-partition-copy-insertion")


# ---------------------------------------------------------------- 图3
def fig3():
    agg = json.loads((ROOT / "results/a/p123-report-farmer/20260924-full-v3/aggregate.json")
                     .read_text(encoding="utf-8"))["P1"]
    by = agg["by_cores"]; ks = ["2", "3", "4", "5"]
    xs = [1, 2, 3, 4, 5]
    mean = [1.0] + [by[k]["mean_speedup"] for k in ks]
    med = [1.0] + [by[k]["median_speedup"] for k in ks]
    ref = [1.0] + [by[k]["reference"] for k in ks]
    n_valid = by["2"]["speedup_valid_n"]; n_total = by["2"]["cells_n"]

    fig, ax = plt.subplots(figsize=(6.4, 4.4))
    ax.plot(xs, mean, "o-", color="#2E86AB", lw=2, ms=6, label="平均加速比", zorder=3)
    ax.plot(xs, med, "s--", color="#F18F01", lw=1.8, ms=5.5, label="中位数加速比", zorder=3)
    ax.plot(xs, ref, "^:", color=C_GRAY, lw=1.4, ms=5, label="外部参考基准", zorder=2)
    ax.axhline(1.0, color="#BDC3C7", lw=1, ls="-", zorder=1)
    ax.text(5.02, 1.0, "单核基准 = 1", fontsize=8.5, color=C_GRAY, va="center")
    for x, y in zip(xs, mean):
        if x == 1: continue
        ax.annotate(f"{y:.2f}", (x, y), textcoords="offset points", xytext=(0, 9),
                    ha="center", fontsize=9, color="#2E86AB", fontweight="bold")
    for x, y in zip(xs, med):
        if x == 1: continue
        ax.annotate(f"{y:.2f}", (x, y), textcoords="offset points", xytext=(0, -16),
                    ha="center", fontsize=8.5, color="#D68910")
    ax.set_xticks(xs)
    ax.set_xlabel("核心数 $N$"); ax.set_ylabel("加速比（相对单核 Makespan）")
    ax.set_ylim(0.55, 3.6); ax.set_xlim(0.7, 5.4)
    ax.grid(alpha=0.25, ls="--")
    ax.legend(loc="upper left")
    ax.set_title("问题1（场景A）1~5 核平均加速比 — 100 官方算例", fontsize=12, fontweight="bold")
    ax.text(0.02, 0.03,
            f"数据：aggregate.json（官方 E0 evaluator，冻结单核基线）\n"
            f"有效加速比 n={n_valid}/{n_total} 算例·核（其余缺失/失败不计入）",
            transform=ax.transAxes, ha="left", va="bottom", fontsize=8, color=C_GRAY)
    save(fig, "fig3-speedup-curves")


# ---------------------------------------------------------------- 图4
def fig4():
    fig, ax = plt.subplots(figsize=(10.5, 6.2))
    ax.set_xlim(0, 10); ax.set_ylim(0, 10); ax.axis("off")

    # NPU 外框
    ax.add_patch(FancyBboxPatch((0.3, 4.35), 9.4, 5.3, boxstyle="round,pad=0.02,rounding_size=0.12",
                                fc="#FBFCFC", ec="#5D6D7E", lw=1.6))
    ax.text(0.55, 9.3, "NPU（$N$ 个同构 AI 核心，本队实测 $N$ = 1~5）", fontsize=11,
            fontweight="bold", color="#2C3E50")

    # Core 0 详细
    cx = 0.65
    ax.add_patch(FancyBboxPatch((cx, 4.6), 3.1, 4.35, boxstyle="round,pad=0.02,rounding_size=0.1",
                                fc="white", ec="#2E86AB", lw=1.4))
    ax.text(cx + 1.55, 8.6, "Core 0", fontsize=10.5, ha="center", fontweight="bold", color="#2E86AB")
    # 计算单元
    box(ax, cx + 0.18, 7.0, 1.3, 1.25, "#EAF2F8", C_TENSOR_E,
        "Cube 单元\nL0A / L0B / L0C\nPIPE_M", fs=7.5)
    box(ax, cx + 1.62, 7.0, 1.3, 1.25, "#EAF2F8", C_TENSOR_E,
        "Vector 单元\nVReg\nPIPE_V", fs=7.5)
    # 搬运单元
    box(ax, cx + 0.18, 6.15, 2.74, 0.62, "#FEF5E7", C_OP_E,
        "数据搬运单元\nPIPE_MTE2 ↓  |  PIPE_MTE3 ↑", fs=7.5)
    # 缓存
    box(ax, cx + 0.18, 5.35, 1.3, 0.62, C_TENSOR, C_TENSOR_E, "L1\n512 KB", fs=8.5)
    box(ax, cx + 1.62, 5.35, 1.3, 0.62, C_TENSOR, C_TENSOR_E, "UB\n128 KB", fs=8.5)
    ax.text(cx + 1.55, 4.85, "私有缓存（核内计算与驻留）", fontsize=7.5, ha="center", color=C_GRAY)

    # Core 1..4 简化
    for i in range(1, 5):
        cx2 = 4.0 + (i - 1) * 1.42
        fc = "white" if i < 4 else "#F8F9F9"
        ax.add_patch(FancyBboxPatch((cx2, 4.6), 1.3, 4.35, boxstyle="round,pad=0.02,rounding_size=0.1",
                                    fc=fc, ec="#AEB6BF", lw=1.1))
        ax.text(cx2 + 0.65, 8.6, f"Core {i}" if i < 4 else "…", fontsize=9.5, ha="center",
                color="#5D6D7E", fontweight="bold")
        if i < 4:
            for yy, tt in [(7.5, "Cube | Vector"), (6.55, "MTE2/MTE3"), (5.75, "L1 | UB")]:
                ax.text(cx2 + 0.65, yy, tt, fontsize=6.8, ha="center", color="#7F8C8D")
        else:
            ax.text(cx2 + 0.65, 6.6, "同构\n核心\n（结构\n同 Core 0）", fontsize=7.5,
                    ha="center", color="#95A5A6")

    # 总线
    ax.add_patch(FancyBboxPatch((0.3, 3.45), 9.4, 0.62, boxstyle="round,pad=0.02,rounding_size=0.08",
                                fc="#EBEDEF", ec="#85929E", lw=1.2))
    ax.text(5.0, 3.76, "系统总线 / NoC（核间数据通路）", fontsize=9.5, ha="center", color="#2C3E50")

    # L2
    ax.add_patch(FancyBboxPatch((0.3, 2.45), 9.4, 0.62, boxstyle="round,pad=0.02,rounding_size=0.08",
                                fc="#E8F8F5", ec="#27AE60", lw=1.2))
    ax.text(5.0, 2.76, "L2 只读 Cache · 1 MB · 250 B/cycle（问题3启用，复用多核共享输入）",
            fontsize=9.5, ha="center", color="#1E8449")

    # DDR
    ax.add_patch(FancyBboxPatch((0.3, 0.7), 9.4, 1.15, boxstyle="round,pad=0.02,rounding_size=0.1",
                                fc="#F2F3F4", ec="#5D6D7E", lw=1.4))
    ax.text(5.0, 1.45, "DDR 核外主存", fontsize=11, ha="center", fontweight="bold", color="#2C3E50")
    ax.text(5.0, 1.0, "共享总带宽 60 B/cycle —— COPY_IN / COPY_OUT / 缓存换入 / 缓存换出 全部计入",
            fontsize=9, ha="center", color="#566573")

    # 通路箭头
    for xx in (1.6, 5.0, 8.4):
        arrow(ax, xx, 4.55, xx, 4.12, lw=1.1)
        arrow(ax, xx, 3.4, xx, 3.12, lw=1.1)
        arrow(ax, xx, 2.4, xx, 1.9, lw=1.1)
    ax.text(5.0, 0.3, "配置参数取自 case001/c1official/result.json：L1 = 524288 B · UB = 131072 B · DDR 共享带宽 = 60 B/cycle",
            fontsize=7.5, ha="center", color=C_GRAY)
    save(fig, "fig4-hardware-architecture")


# ---------------------------------------------------------------- main
def main():
    setup()
    z = zipfile.ZipFile(ROOT / "data/raw/a/official-cases.zip")
    d2 = json.loads(z.read("data/case_002.json").decode("utf-8"))
    fig1(d2)
    fig2(d2)
    fig3()
    fig4()

    # 溯源表
    src = f"""# 赛题四图重绘 — 数据溯源（生成于 2026-09-25）

| 图 | 文件 | 数据来源 | 说明 |
|---|---|---|---|
| 图1 | fig1-example-computational-graph.pdf/png | `data/raw/a/official-cases.zip::data/case_002.json`（只读原件） | 矩阵乘算例真实片段：COPY_IN(id=1/2)→MATMUL(id=3/5/7/9, PIPE_M, 300 cycles)→RELU(id=4/6/8/10, PIPE_V)→ADD(id=1999)→COPY_OUT(id=2197)；节点 id/张量 size/cycles 均为算例原值 |
| 图2 | fig2-partition-copy-insertion.pdf/png | 同上 + `results/a/board-feed-farmer/20260924/artifacts/case002/c5/plan.json` | 跨子图边界取自真实切图方案：RELU(sgid=1)·RELU(sgid=2)→ADD(sgid=199)；插入节点按场景A规则；跨子图共享张量数=0 为脚本实测统计 |
| 图3 | fig3-speedup-curves.pdf/png | `results/a/p123-report-farmer/20260924-full-v3/aggregate.json` | P1 场景A，官方 E0 evaluator；冻结单核基线（official singlecore_evaluate.py）；有效 n={80}/100·核 |
| 图4 | fig4-hardware-architecture.pdf/png | `results/a/board-feed-farmer/20260924/artifacts/case001/c1official/result.json` | L1=524288 B、UB=131072 B、DDR 总带宽=60 B/cycle；L2 参数为赛题 1.5 节固定配置（1 MB / 250 B/cycle） |

生成脚本：`src/analysis/contest_figures/make_all.py`（重跑即全量重绘）。
局限：图3 为 1~5 核汇总口径，未含逐算例分布；场景 B（P2）暂无实测数据，未绘制。
"""
    (OUT / "SOURCES.md").write_text(src, encoding="utf-8")
    print("SOURCES.md written")


if __name__ == "__main__":
    main()
