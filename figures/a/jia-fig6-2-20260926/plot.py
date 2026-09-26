# -*- coding: utf-8 -*-
"""图 6-2｜容量约束对流水阶段切分的影响（case044 / 4 核，P3 初稿 6.4、6.6.3）。

数据来源（全部固定提交）：
- 容量方案 pipeline_capacity：results/a/q3-yuanzhifang/pipeline-capacity-20260925/
  manifest.json detail（cuts [0,41,65,95,124]、stage_memory 静态估计）与 REPORT.md
  （官方峰值 [79584,516992,330752,18816]、UB 峰值全 0、P3=37581、搬运 121088 B、spill 0），
  固定提交 7edacdd97a7be36a402af20bc8bfa8a7454dbbe0。
- 计算均衡控制 pipeline_stages：results/a/q3-yuanzhifang/pipeline-20260924/manifest.json
  detail（cuts [0,28,58,91,124]）与 comparison.json（逐核官方内存峰值；P3=40927、
  搬运 135168 B、spill 0）；控制方案计划 sha256 44c66c84…（capacity 批次 controls 登记）。
- 仅首次装入早期候选：6.6.3 文字记载（P3=41738、spill 1,622,016 B、某阶段共同输入
  663552 B 超 L1 容量）；其切点/核归属元数据缺失，不绘制条带（缺项如实登记）。
"""
import csv
import os

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
from matplotlib.patches import Patch
from matplotlib.lines import Line2D

HERE = os.path.dirname(os.path.abspath(__file__))
C_TXT = "#2C3E50"
STAGE_COLORS = ["#2E86AB", "#5DA7CC", "#E67E22", "#F0B27A"]  # 阶段/核 0-3
C_STATIC = "#8E9BAA"
C_OFFICIAL = "#1A5276"
C_FAIL = "#C0392B"
plt.rcParams["font.family"] = "Microsoft YaHei"
plt.rcParams["axes.unicode_minus"] = False

VARIANT_LABEL = {
    "pipeline_stages": "计算均衡流水（控制，pipeline_stages）",
    "pipeline_capacity": "容量约束流水（pipeline_capacity）",
    "firstload_only": "仅首次装入早期候选（切点元数据缺失，未绘条带）",
}


def read_csv(name):
    with open(os.path.join(HERE, name), encoding="utf-8") as f:
        return list(csv.DictReader(f))


cuts = read_csv("cuts.csv")
cap_rows = read_csv("capacity.csv")

# ---- 自检：切点有序、首尾覆盖 0..124、核 0..3；字节单位一致 ----
by_variant = {}
for r in cuts:
    by_variant.setdefault(r["variant"], []).append(
        (int(r["start"]), int(r["end"]), int(r["core"])))
for v, segs in by_variant.items():
    segs.sort()
    assert segs[0][0] == 0 and segs[-1][1] == 124, (v, segs)
    for (s0, e0, c0), (s1, e1, c1) in zip(segs, segs[1:]):
        assert s1 == e0 and c1 == c0 + 1, (v, segs)
print("cuts self-check OK: contiguous, ordered, cover [0,124], cores 0..3")

cap_L1, cap_UB = 524288, 131072


def peaks(variant, space, kinds):
    out = {}
    for r in cap_rows:
        if r["variant"] == variant and r["space"] == space and any(
                k in r["evidence_type"] for k in kinds):
            out[r["evidence_type"]] = int(r["working_set"])
    return out


ctrl_official = [peaks("pipeline_stages", "L1", ["official_peak_core"])[f"official_peak_core{i}"]
                 for i in range(4)]
capa_static = [peaks("pipeline_capacity", "L1", ["static_modeled"])[f"static_modeled_stage{i}"]
               for i in range(4)]
capa_official = [peaks("pipeline_capacity", "L1", ["official_peak_stage"])[f"official_peak_stage{i}"]
                 for i in range(4)]
ub_official = [r for r in cap_rows if r["space"] == "UB" and r["evidence_type"] == "official_peak"]
fail_peak = [int(r["working_set"]) for r in cap_rows
             if r["evidence_type"] == "reported_static_shared_input_exceeds"][0]
print("control official L1 peaks:", ctrl_official)
print("capacity static L1:", capa_static)
print("capacity official L1 peaks:", capa_official)
print("official UB peaks:", [int(r["working_set"]) for r in ub_official])
print("firstload-only reported shared input:", fail_peak)

# ---- 绘图 ----
fig = plt.figure(figsize=(6.5, 7.6))
gs = fig.add_gridspec(4, 2, height_ratios=[1.0, 1.0, 1.0, 1.5], hspace=0.55, wspace=0.25)
ax_b1 = fig.add_subplot(gs[0, :])
ax_b2 = fig.add_subplot(gs[1, :], sharex=ax_b1)
ax_b3 = fig.add_subplot(gs[2, :], sharex=ax_b1)
ax_l1 = fig.add_subplot(gs[3, 0])
ax_ub = fig.add_subplot(gs[3, 1])

# ---- 三行阶段条带（共同横轴：作业计算位置 0..124）----
def draw_bands(ax, variant, headline):
    segs = sorted(by_variant[variant])
    for (s, e, c) in segs:
        ax.broken_barh([(s, e - s)], (0, 1), facecolors=STAGE_COLORS[c],
                       edgecolor="white", linewidth=0.6)
        ax.text((s + e) / 2, 0.5, f"核{c}", ha="center", va="center",
                fontsize=6.3, color="white", fontweight="bold")
    for (s, e, c) in segs[1:]:
        ax.axvline(s, color=C_TXT, linestyle="--", linewidth=0.8)
        ax.text(s, 1.06, f"切点 {s}", ha="center", va="bottom", fontsize=6.0, color=C_TXT)
    ax.set_ylim(0, 1.55)
    ax.set_yticks([])
    ax.set_title(headline, fontsize=7.6, color=C_TXT, pad=14, loc="left")


draw_bands(ax_b1, "pipeline_stages",
           "① 计算均衡流水 pipeline_stages：P3=40,927 cycles｜总额外搬运 135,168 B｜spill 0"
           "（各阶段计算量 1,928/1,947/1,883/1,914 cycles，接近均衡）")
draw_bands(ax_b2, "pipeline_capacity",
           "② 容量约束流水 pipeline_capacity：P3=37,581 cycles｜总额外搬运 121,088 B｜spill 0"
           "（式 (6-12) 驻留筛选后切点前移/后调，阶段计算量 2,822/1,388/1,728/1,734 cycles）")
ax_b3.set_xlim(0, 124)
ax_b3.set_yticks([])
ax_b3.set_xlabel("作业计算位置（position，共 124 个；11 个作业）", fontsize=7.5)
ax_b3.text(0.01, 0.52,
           "③ 仅首次装入早期候选：切点/核归属元数据缺失（缺项），不绘制条带；"
           "实测 P3=41,738 cycles、spill 1,622,016 B——差于控制方案，促成式 (6-12)。",
           fontsize=6.6, color=C_FAIL, va="center")
ax_b3.set_xticks([0, 28, 41, 58, 65, 91, 95, 124], minor=False)
ax_b3.set_xticklabels(["0", "28", "41", "58", "65", "91/95", "", "124"], fontsize=6.8)
for ax in (ax_b1, ax_b2):
    plt.setp(ax.get_xticklabels(), visible=False)
fig.text(0.5, 0.965, "case044 / 4 核：容量约束对流水阶段切分的影响（三方案切点对比；切点为阶段边界，颜色=阶段/核归属）",
         ha="center", fontsize=9.0, color=C_TXT)

# ---- L1 / UB 容量分面 ----
x = [0, 1, 2, 3]
w = 0.27
kb = 1024

# L1 分面
ax_l1.bar([i - w for i in x], [v / kb for v in ctrl_official], width=w,
          color=C_OFFICIAL, alpha=0.9, label="① 控制方案官方峰值")
ax_l1.bar(x, [v / kb for v in capa_static], width=w,
          color=C_STATIC, alpha=0.75, hatch="//", edgecolor="white",
          linewidth=0.4, label="② 容量方案静态估计（式 6-12 模型）")
ax_l1.plot([i + w for i in x], [v / kb for v in capa_official], "D",
           color="#1A2530", markersize=4.2, label="② 容量方案官方峰值")
ax_l1.axhline(cap_L1 / kb, color=C_CAP if (C_CAP := "#C0392B") else "#C0392B",
              linestyle="--", linewidth=1.2)
ax_l1.text(0.02, cap_L1 / kb + 8, "L1 容量 512 KiB", ha="left", va="bottom",
           fontsize=6.4, color=C_CAP)
ax_l1.axhline(fail_peak / kb, color=C_FAIL, linestyle=":", linewidth=1.1)
ax_l1.text(3.45, fail_peak / kb - 18, f"③ 早期候选报告共同输入 {fail_peak/kb:g} KiB（超容量→spill）",
           fontsize=6.0, color=C_FAIL, ha="right", va="top")
ax_l1.set_xticks(x)
ax_l1.set_xticklabels(["核/阶段0", "核/阶段1", "核/阶段2", "核/阶段3"], fontsize=7)
ax_l1.set_ylabel("L1 工作集（KiB）", fontsize=7.5)
ax_l1.set_ylim(0, 720)
ax_l1.set_title("L1 分面：静态估计（斜纹）与官方峰值（实心/菱形）分用标记", fontsize=7.6, color=C_TXT, pad=4)
ax_l1.tick_params(labelsize=7)

# UB 分面
ub_vals = [int(r["working_set"]) / kb for r in ub_official]
ax_ub.bar([i - w / 2 for i in x], [0] * 4, width=w, color=C_OFFICIAL)
ax_ub.axhline(cap_UB / kb, color=C_CAP, linestyle="--", linewidth=1.2)
ax_ub.text(1.5, cap_UB / kb + 4, "UB 容量 128 KiB", ha="center", va="bottom",
           fontsize=6.4, color=C_CAP)
ax_ub.text(1.5, cap_UB / kb * 0.45,
           "两方案官方 UB 峰值均为 0 B\n（REPORT.md / comparison.json 实测记录；\n非估计值）",
           ha="center", va="center", fontsize=6.6, color=C_TXT)
ax_ub.set_xticks(x)
ax_ub.set_xticklabels(["核/阶段0", "核/阶段1", "核/阶段2", "核/阶段3"], fontsize=7)
ax_ub.set_ylabel("UB 工作集（KiB）", fontsize=7.5)
ax_ub.set_ylim(0, 155)
ax_ub.set_title("UB 分面", fontsize=7.6, color=C_TXT, pad=4)
ax_ub.tick_params(labelsize=7)

legend_items = [
    Patch(facecolor=C_OFFICIAL, alpha=0.9, label="① 控制方案官方峰值（实测）"),
    Patch(facecolor=C_STATIC, alpha=0.75, hatch="//", edgecolor="white", label="② 静态估计（式 6-12 模型，非实测）"),
    Line2D([0], [0], marker="D", color="#1A2530", linestyle="", markersize=4.2, label="② 官方峰值（实测）"),
    Line2D([0], [0], color="#C0392B", linestyle="--", label="固定容量线"),
]
ax_ub.legend(handles=legend_items, loc="upper left", fontsize=5.8, framealpha=0.92)

fig.savefig(os.path.join(HERE, "figure.svg"), format="svg", bbox_inches="tight")
fig.savefig(os.path.join(HERE, "figure.png"), format="png", dpi=300, bbox_inches="tight")
print("figure.svg / figure.png written")
