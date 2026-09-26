# -*- coding: utf-8 -*-
"""图 6-2｜容量约束对流水阶段切分的影响（case044 / 4 核，P3 初稿 6.4、6.6.3）。

三方案（全部固定提交原件，哈希核对见 audit.sources）：
- balanced = pipeline_stages（控制）：cuts [0,28,58,91,124]，P3=40,927 cycles，
  搬运 135,168 B，spill 0，逐核官方 L1 峰（源索引 0..3）[19680,430080,473600,22912]。
- resident = pipeline_capacity（容量约束）：cuts [0,41,65,95,124]，P3=37,581 cycles，
  搬运 121,088 B，spill 0，官方 L1 峰 [79584,516992,330752,18816]，
  静态模型（式 6-12）[79584,516864,330752,17792]。
- first_load = pipeline_cold_setup（仅首次装入早期候选）：cuts [0,41,70,98,124]，
  P3=41,738 cycles，added_copy 1,731,840 B，spill 1,622,016 B，官方 L1 峰
  [79584,516992,188160,15744]，静态共同输入（源索引 0..3）
  [73440,663552,186368,7040]，Cache hit 1,622,016 / miss 1,007,840 B。
三方案官方 UB 峰值均为 0。图内编号顺序 = balanced/resident/first_load；
数组一律用源索引 0..3，展示核编号 = 源索引 + 1（核1..4）。
"""
import csv
import os

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
from matplotlib.lines import Line2D
from matplotlib.patches import Patch

HERE = os.path.dirname(os.path.abspath(__file__))
C_TXT = "#2C3E50"
STAGE_COLORS = ["#2E86AB", "#5DA7CC", "#E67E22", "#F0B27A"]  # 源索引 0..3 → 核1..4
C_BAL = "#2E86AB"
C_RES = "#1A5276"
C_FL = "#E67E22"
C_STATIC = "#8E9BAA"
C_CAP = "#C0392B"
plt.rcParams["font.family"] = "Microsoft YaHei"
plt.rcParams["axes.unicode_minus"] = False


def read_csv(name):
    with open(os.path.join(HERE, name), encoding="utf-8") as f:
        return list(csv.DictReader(f))


cuts = read_csv("cuts.csv")
cap_sum = read_csv("capacity.csv")
cap_det = read_csv("capacity_detail.csv")

by_variant = {}
for r in cuts:
    by_variant.setdefault(r["variant"], []).append(
        (int(r["start"]), int(r["end"]), int(r["core"])))
assert set(by_variant) == {"balanced", "resident", "first_load"}
for v, segs in by_variant.items():
    segs.sort()
    assert segs[0][0] == 0 and segs[-1][1] == 124 and len(segs) == 4
    for (s0, e0, c0), (s1, e1, c1) in zip(segs, segs[1:]):
        assert s1 == e0 and c1 == c0 + 1
print("cuts self-check OK: 3 variants x 4 contiguous segments covering [0,124], cores 1..4")

kb = 1024
cap_L1, cap_UB = 524288 / kb, 131072 / kb

measured = {}
for r in cap_sum:
    measured[(r["variant"], r["space"])] = int(r["working_set"]) / kb

# 静态量一律先以字节（B）保存，绘图时只做一次 B→KiB
static_model_res_bytes = {
    int(r["evidence_type"].replace("static_modeled_stage", "")):
        int(r["working_set"])
    for r in cap_det if r["evidence_type"].startswith("static_modeled")}
static_shared_fl_bytes = {
    int(r["evidence_type"].replace("static_shared_input_stage", "")):
        int(r["working_set"])
    for r in cap_det if r["evidence_type"].startswith("static_shared_input")}
assert sorted(static_model_res_bytes) == [0, 1, 2, 3]
assert sorted(static_shared_fl_bytes) == [0, 1, 2, 3]
assert static_shared_fl_bytes[1] == 663552  # 源索引 1 = 展示阶段2
print("static arrays OK: resident modeled",
      static_model_res_bytes, "| first_load shared-input",
      static_shared_fl_bytes)

# ---- 绘图：3 行真实条带（顺序 balanced/resident/first_load）+ L1/UB 分面 ----
fig = plt.figure(figsize=(6.5, 7.8))
gs = fig.add_gridspec(4, 2, height_ratios=[1.0, 1.0, 1.0, 1.55],
                      hspace=0.62, wspace=0.25,
                      left=0.09, right=0.97, top=0.90, bottom=0.17)
ax_b1 = fig.add_subplot(gs[0, :])
ax_b2 = fig.add_subplot(gs[1, :], sharex=ax_b1)
ax_b3 = fig.add_subplot(gs[2, :], sharex=ax_b1)
ax_l1 = fig.add_subplot(gs[3, 0])
ax_ub = fig.add_subplot(gs[3, 1])

ROWS = [
    ("balanced", ax_b1, "① balanced 计算均衡（控制）：P3=40,927 cycles｜搬运 135,168 B｜spill 0"),
    ("resident", ax_b2, "② resident 容量约束：P3=37,581 cycles｜搬运 121,088 B｜spill 0"),
    ("first_load", ax_b3, "③ first_load 仅首次装入：P3=41,738 cycles｜spill 1,622,016 B"),
]
for variant, ax, headline in ROWS:
    segs = sorted(by_variant[variant])
    for (s, e, c) in segs:
        ax.broken_barh([(s, e - s)], (0, 1), facecolors=STAGE_COLORS[c - 1],
                       edgecolor="white", linewidth=0.6)
        ax.text((s + e) / 2, 0.5, f"核{c}", ha="center", va="center",
                fontsize=6.2, color="white", fontweight="bold")
    for (s, e, c) in segs[1:]:
        ax.axvline(s, color=C_TXT, linestyle="--", linewidth=0.7)
        ax.text(s, 1.05, str(s), ha="center", va="bottom", fontsize=5.9, color=C_TXT)
    ax.set_ylim(0, 1.42)
    ax.set_yticks([])
    ax.set_title(headline, fontsize=7.3, color=C_TXT, pad=13, loc="left")
    for i in range(0, 125, 25):
        ax.axvline(i, color="#D5DBDB", linewidth=0.4, zorder=0)

ax_b3.set_xlim(0, 124)
ax_b3.set_xticks([0, 25, 50, 75, 100, 124])
ax_b3.set_xlabel("作业计算位置（position，共 124 个；11 个作业）", fontsize=7.5)
for ax in (ax_b1, ax_b2):
    plt.setp(ax.get_xticklabels(), visible=False)
fig.text(0.5, 0.955, "case044 / 4 核：容量约束对流水阶段切分的影响（三方案切点；颜色=核/阶段归属，虚线=切点）",
         ha="center", fontsize=8.8, color=C_TXT)

# ---- L1 分面：三方案实测峰值 + resident 静态估计 + first_load 静态共同输入标记 ----
x = [0, 1, 2, 3]          # 源索引 0..3
w = 0.18
# 四系列互不重叠：x-1.5w / x-0.5w / x+0.5w / x+1.5w
ax_l1.bar([i - 1.5 * w for i in x], [19680 / kb, 430080 / kb, 473600 / kb, 22912 / kb],
          width=w, color=C_BAL, alpha=0.95, label="① balanced 官方峰值")
ax_l1.bar([i - 0.5 * w for i in x], [79584 / kb, 516992 / kb, 330752 / kb, 18816 / kb],
          width=w, color=C_RES, alpha=0.95, label="② resident 官方峰值")
ax_l1.bar([i + 0.5 * w for i in x], [79584 / kb, 516992 / kb, 188160 / kb, 15744 / kb],
          width=w, color=C_FL, alpha=0.95, label="③ first_load 官方峰值（发生 spill）")
ax_l1.bar([i + 1.5 * w for i in x], [static_model_res_bytes[i] / kb for i in x], width=w,
          color=C_STATIC, alpha=0.85, hatch="//", edgecolor="white", linewidth=0.4,
          label="② resident 静态估计（非实测）")
# ③ first_load 源索引 1（展示阶段2）的静态共同输入 663,552 B → 648 KiB（仅一次换算）
ax_l1.plot([1], [static_shared_fl_bytes[1] / kb], "^", color="#6C3483", markersize=5,
           zorder=6, label="③ 阶段2（源索引1）静态共同输入 663,552 B（非官方峰值）")
ax_l1.axhline(cap_L1, color=C_CAP, linestyle="--", linewidth=1.2)
ax_l1.text(3.42, cap_L1 + 10, "L1 容量 512 KiB", ha="right", va="bottom",
           fontsize=6.3, color=C_CAP)
ax_l1.set_xticks(x)
ax_l1.set_xticklabels(["核1", "核2", "核3", "核4"], fontsize=7)
ax_l1.set_ylabel("L1 工作集（KiB）", fontsize=7.3)
ax_l1.set_ylim(0, 715)
ax_l1.set_title("L1 分面（斜纹=静态估计，非实测；实测=实心）", fontsize=7.4, color=C_TXT, pad=4)
ax_l1.tick_params(labelsize=7)

# ---- UB 分面：三方案官方 UB 峰值均为 0（实测记录）----
ax_ub.bar([i - 1.5 * w for i in x], [0] * 4, width=w, color=C_BAL, alpha=0.95)
ax_ub.bar([i - 0.5 * w for i in x], [0] * 4, width=w, color=C_RES, alpha=0.95)
ax_ub.bar([i + 0.5 * w for i in x], [0] * 4, width=w, color=C_FL, alpha=0.95)
ax_ub.bar([i + 1.5 * w for i in x], [0] * 4, width=w, color=C_STATIC, alpha=0.85,
          hatch="//", edgecolor="white", linewidth=0.4)
ax_ub.axhline(cap_UB, color=C_CAP, linestyle="--", linewidth=1.2)
ax_ub.text(1.5, cap_UB + 4, "UB 容量 128 KiB", ha="center", va="bottom",
           fontsize=6.3, color=C_CAP)
ax_ub.text(1.5, cap_UB * 0.42,
           "三方案官方 UB 峰值均为 0 B\n（各自 P3 result 实测记录；非估计值）",
           ha="center", va="center", fontsize=6.4, color=C_TXT)
ax_ub.set_xticks(x)
ax_ub.set_xticklabels(["核1", "核2", "核3", "核4"], fontsize=7)
ax_ub.set_ylabel("UB 工作集（KiB）", fontsize=7.3)
ax_ub.set_ylim(0, 155)
ax_ub.set_title("UB 分面", fontsize=7.4, color=C_TXT, pad=4)
ax_ub.tick_params(labelsize=7)

handles = [
    Patch(facecolor=C_BAL, alpha=0.95, label="① balanced 官方峰值（实测）"),
    Patch(facecolor=C_RES, alpha=0.95, label="② resident 官方峰值（实测）"),
    Patch(facecolor=C_STATIC, alpha=0.85, hatch="//", edgecolor="white",
          label="② resident 静态估计（非实测）"),
    Patch(facecolor=C_FL, alpha=0.95, label="③ first_load 官方峰值（实测，spill>0）"),
    Line2D([0], [0], marker="^", color="#6C3483", linestyle="", markersize=5,
           label="③ 阶段2（源索引1）静态共同输入 663,552 B（静态量，非官方峰值）"),
    Line2D([0], [0], color=C_CAP, linestyle="--", label="固定容量线"),
]
fig.legend(handles=handles, loc="lower center", ncol=2, fontsize=6.0,
           framealpha=0.92, bbox_to_anchor=(0.5, 0.008))

fig.savefig(os.path.join(HERE, "figure.svg"), format="svg")
fig.savefig(os.path.join(HERE, "figure.png"), format="png", dpi=300)
print("figure.svg / figure.png written (single run, fixed 6.5x7.8in layout)")
