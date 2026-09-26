# -*- coding: utf-8 -*-
"""图 4-3｜输入错峰前后的多核执行时间线（case051 / 3 核，stage-j 配对）。

数据全部来自固定提交 059056ce1ee999e634049e5e5baf72566832effe 的
results/a/q1-yuanzhifang-stage-j/stage-j-20260925（control/paced 配对，
k3 链-核映射一致，PREPARED.md：诊断单元、非 P1 全量均值）。
- control：makespan 291222 cycles，extra_ddr 9,045,304 B
- paced：  makespan 278618 cycles，extra_ddr 9,045,350 B
- 两者首轮（task 0..2 + 跨核收集 task 3）完全一致：
  大输入完成 6570、首轮 Task 完成 10028、远端部分结果返回 11040 cycles。
- 归约尾（末条 task 收全量部分结果）起点：control 291076 / paced 278472。
布局：每行=一个方案；左列全量绝对时间轴（cycles），右列为首轮 [0,12000] 放大。
行序自上而下：核1/2/3 × PIPE_MTE2/MTE3/V（事件表源索引 0..2，展示 +1）。
"""
import csv
import os

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
from matplotlib.lines import Line2D
from matplotlib.patches import Patch
from matplotlib.ticker import FuncFormatter

HERE = os.path.dirname(os.path.abspath(__file__))

C_TXT = "#2C3E50"
C_OP = {
    "COPY_IN": "#2E86AB",   # 搬入（含大输入 32KiB 档）
    "COPY_OUT": "#5DA7CC",  # 搬出
    "RELU": "#E67E22",      # 计算
    "ADD": "#F0B27A",       # 计算
    "REDUCE": "#C0392B",    # 归约
}
C_TASK = "#BDC3C7"
C_BOX = "#FDF3D8"
C_TAIL = "#F5CBA7"
C_M1, C_M2, C_M3 = "#7D3C98", "#1E8449", "#B7950B"

plt.rcParams["font.family"] = "Microsoft YaHei"
plt.rcParams["axes.unicode_minus"] = False
plt.rcParams["font.size"] = 8


def read_csv(name):
    with open(os.path.join(HERE, name), encoding="utf-8") as f:
        return list(csv.DictReader(f))


events = read_csv("events.csv")
results = {r["variant"]: r for r in read_csv("results.csv")}
markers = read_csv("markers.csv")

# ---- 自检：结果表与官方值一致 ----
assert set(results) == {"control", "paced"}
assert results["control"]["makespan"] == "291222" and results["paced"]["makespan"] == "278618"
assert results["control"]["extra_ddr"] == "9045304" and results["paced"]["extra_ddr"] == "9045350"
assert results["control"]["plan_hash"] != results["paced"]["plan_hash"]
mk = {v: int(results[v]["makespan"]) for v in results}

mk_line = {}   # variant -> {kind: cycle}
for r in markers:
    mk_line.setdefault(r["variant"], {})[r["kind"]] = int(r["event_id"].split("=")[-1])
for v in ("control", "paced"):
    m = mk_line[v]
    assert m["input_done"] == 6570 and m["task_done"] == 10028 and m["remote_return"] == 11040
    assert 0 < m["reduce_tail_start"] < mk[v]

MARKERS = [(6570, C_M1, "大输入完成 6570"),
           (10028, C_M2, "首轮 Task 完成 10028"),
           (11040, C_M3, "远端返回 11040")]

ROWS = [(c, p) for c in (0, 1, 2) for p in ("PIPE_MTE2", "PIPE_MTE3", "PIPE_V")]
# 展示顺序自上而下：核1 MTE2/MTE3/V、核2 …、核3 …（y 越大越靠上）
ROW_Y = {rc: (2 - rc[0]) * 3 + (2 - pi) for rc in ROWS for pi in [ROWS.index(rc) % 3]}
ROW_LABEL = ["核3 V", "核3 MTE3", "核3 MTE2", "核2 V", "核2 MTE3", "核2 MTE2",
             "核1 V", "核1 MTE3", "核1 MTE2"]

ev_by = {v: {rc: [] for rc in ROWS} for v in ("control", "paced")}
task_by = {v: {c: [] for c in (0, 1, 2)} for v in ("control", "paced")}
op_total = 0
for r in events:
    v = r["variant"]
    if r["pipe"] == "SUBGRAPH":
        task_by[v][int(r["core"])].append((int(r["start"]), int(r["end"])))
    else:
        op = r["event_id"].split("#")[0]
        assert op in C_OP, op
        ev_by[v][(int(r["core"]), r["pipe"])].append(
            (int(r["start"]), int(r["end"]), op))
        op_total += 1
# 两方案 pipe 操作总数：control 2373 + paced 2396
assert op_total == 2373 + 2396, op_total

fig = plt.figure(figsize=(6.5, 7.2), dpi=100)
gs = fig.add_gridspec(2, 2, width_ratios=[2.1, 1.0], wspace=0.06,
                      left=0.085, right=0.985, top=0.94, bottom=0.145, hspace=0.42)
axes = {}
for row, v in enumerate(("control", "paced")):
    axL = fig.add_subplot(gs[row, 0])
    axR = fig.add_subplot(gs[row, 1], sharey=axL)
    axes[(v, "L")] = axL
    axes[(v, "R")] = axR
    name = "control（基线）" if v == "control" else "paced（输入错峰）"
    tag = "a" if v == "control" else "b"
    axL.set_title("%s %s：case051 / 3 核，makespan %s cycles" % (tag, name, results[v]["makespan"]),
                  fontsize=8.5, color=C_TXT, pad=4)

    # 首轮底色（task 0..3 = 大输入 + 计算 + 跨核收集）与归约尾底色
    for ax in (axL, axR):
        ax.axvspan(0, 11174, color=C_BOX, zorder=0)
    axL.axvspan(mk_line[v]["reduce_tail_start"], mk[v], color=C_TAIL, zorder=0)
    axL.text((mk_line[v]["reduce_tail_start"] + mk[v]) / 2, -0.62, "归约尾",
             ha="center", va="center", fontsize=8, color="#A04000")

    # task 区间（灰）覆盖该核三条 pipe 行
    for c in (0, 1, 2):
        for s, e in task_by[v][c]:
            for p in ("PIPE_MTE2", "PIPE_MTE3", "PIPE_V"):
                y = ROW_Y[(c, p)]
                axL.broken_barh([(s, e - s)], (y - 0.42, 0.84), color=C_TASK, alpha=0.45, zorder=1)
                axR.broken_barh([(s, e - s)], (y - 0.42, 0.84), color=C_TASK, alpha=0.45, zorder=1)

    # 操作条
    for (c, p), lst in ev_by[v].items():
        y = ROW_Y[(c, p)]
        segs = {}
        for s, e, op in lst:
            segs.setdefault(op, []).append((s, e - s))
        for ax in (axL, axR):
            for op, ss in segs.items():
                ax.broken_barh(ss, (y - 0.4, 0.8), color=C_OP[op], linewidth=0, zorder=3)

    # 标记线：大输入完成 / 首轮 Task 完成 / 远端返回（数值并入图例，不在面板内加文字，避免遮挡）
    for x, col, lab in MARKERS:
        for ax in (axL, axR):
            ax.axvline(x, color=col, lw=0.9, ls="--", zorder=4)

    # 轴设置
    axL.set_xlim(0, mk["control"])
    axR.set_xlim(0, 12200)
    axL.set_ylim(-0.75, 9.15)
    axL.set_yticks(range(9))
    axL.set_yticklabels(ROW_LABEL, fontsize=8)
    axR.tick_params(labelleft=False)
    axL.set_xlabel("时间（cycles）", fontsize=8)
    axR.set_xlabel("首轮放大（cycles）", fontsize=8)
    axR.set_xticks([0, 3000, 6000, 9000, 12000])
    axL.xaxis.set_major_formatter(FuncFormatter(lambda x, _: ("%dk" % (x // 1000)) if x else "0"))
    axR.xaxis.set_major_formatter(FuncFormatter(lambda x, _: ("%dk" % (x // 1000)) if x else "0"))
    for ax in (axL, axR):
        ax.set_ylim(-0.75, 9.15)
        for sp in ("top", "right"):
            ax.spines[sp].set_visible(False)
        ax.tick_params(labelsize=8, colors=C_TXT)
        # 核块分隔线
        for yy in (2.5, 5.5):
            ax.axhline(yy, color="#D5D8DC", lw=0.6, zorder=1)

# makespan 数值标注（左图右端）
for v in ("control", "paced"):
    axL = axes[(v, "L")]
    axL.annotate("makespan %s" % results[v]["makespan"],
                 xy=(mk[v], 8.95), xytext=(-2, 0), textcoords="offset points",
                 ha="right", va="center", fontsize=8, color=C_TXT)

# 图例（底部统一）
handles = [
    Patch(color=C_OP["COPY_IN"], label="COPY_IN 搬入"),
    Patch(color=C_OP["COPY_OUT"], label="COPY_OUT 搬出"),
    Patch(color=C_OP["RELU"], label="RELU 计算"),
    Patch(color=C_OP["ADD"], label="ADD 计算"),
    Patch(color=C_OP["REDUCE"], label="REDUCE 归约"),
    Patch(facecolor=C_TASK, alpha=0.45, label="task 区间"),
    Patch(facecolor=C_BOX, label="首轮（task 0–3）"),
    Patch(facecolor=C_TAIL, label="归约尾（末条 task）"),
    Line2D([0], [0], color=C_M1, ls="--", lw=0.9, label="大输入完成 6570"),
    Line2D([0], [0], color=C_M2, ls="--", lw=0.9, label="首轮 Task 完成 10028"),
    Line2D([0], [0], color=C_M3, ls="--", lw=0.9, label="远端返回 11040"),
]
fig.legend(handles=handles, loc="lower center", ncol=4, fontsize=8,
           frameon=False, bbox_to_anchor=(0.5, 0.008), handlelength=1.2, columnspacing=0.9)

svg_path = os.path.join(HERE, "figure.svg")
png_path = os.path.join(HERE, "figure.png")
fig.savefig(svg_path)
fig.savefig(png_path, dpi=200)
print("saved", svg_path, png_path)
print("self-check OK: markers 6570/10028/11040 both variants; reduce tails",
      mk_line["control"]["reduce_tail_start"], mk_line["paced"]["reduce_tail_start"])
