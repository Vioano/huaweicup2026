# -*- coding: utf-8 -*-
"""图 5-4｜通信、容量与调度耦合的典型正反例（case003/k2 R05 + S16 全量对照）。

绘图只读交付包内五张 CSV（events / markers / results / bytes / tradeoff），
不读取包外文件；CSV 由 extract_inputs.py 从两项固定来源生成并核对哈希
（S15 result.zip @e6ae3699、S16 report.json @70f2e8bd，见该脚本与 audit.sources）。

面板 1（v3）：同轴真实核/Pipe 操作时间条——每方案每核一个泳道块，块内 4 条
Pipe 独立子行（固定垂直偏移、互不重叠），操作条以真实 start/end 绘制
（broken_barh 传入 (start, end-start)，宽度=持续时间）；task（SUBGRAPH）区间
仅作浅灰整核背景，不计入任何操作计数。端点线由所属方案泳道包络计算。
面板 2：搬运量分解——extra_ddr 一律指新增 COPY（added_copy_bytes），
scheduled 合计单独列示，二者不混用。
面板 3：S16 全量 500 格 Δ 散点（绝对量；旧额外 DDR=0 的 120 格不算相对变化）；
图例置于轴下预留空白（不删点、不截断坐标）。

运行（工作目录=仓库根）：
  .venv/Scripts/python.exe figures/a/jia-fig5-4-20260926/plot.py
"""
import csv
import os
from collections import defaultdict

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
from matplotlib.lines import Line2D
from matplotlib.patches import Patch

HERE = os.path.dirname(os.path.abspath(__file__))
C_TXT = "#2C3E50"
C_SEED = "#7F8C8D"
C_REC = "#2E86AB"
C_CAP = "#C0392B"
C_PIPE = {
    "PIPE_MTE2": "#2E86AB",   # 搬入
    "PIPE_MTE3": "#5DA7CC",   # 搬出
    "PIPE_V": "#E67E22",      # 计算
    "PIPE_M": "#C0392B",      # trace 原始管道类别，身份不做推断
}
C_TASK = "#BDC3C7"
PIPES_TOPDOWN = ["PIPE_MTE2", "PIPE_MTE3", "PIPE_V", "PIPE_M"]   # 块内自上而下
PIPES = PIPES_TOPDOWN[::-1]                                     # 绘图自块底向块顶
PIPE_SHORT = {"PIPE_MTE2": "MTE2", "PIPE_MTE3": "MTE3", "PIPE_V": "V", "PIPE_M": "M"}

plt.rcParams["font.family"] = "Microsoft YaHei"
plt.rcParams["axes.unicode_minus"] = False
plt.rcParams["font.size"] = 8


def read_csv(name):
    with open(os.path.join(HERE, name), encoding="utf-8") as f:
        return list(csv.DictReader(f))


events = read_csv("events.csv")
markers = read_csv("markers.csv")
results = {r["variant"]: r for r in read_csv("results.csv")}
bytes_rows = {r["variant"]: r for r in read_csv("bytes.csv")}
tradeoff = read_csv("tradeoff.csv")

MAKESPAN = {"seed": 248166, "recovered": 254508}
VARIANT_NAME = {"seed": "seed（旧初解）", "recovered": "rec（recovered，R05 恢复候选）"}

# ---- 断言：结果表与官方值一致；extra_ddr=新增 COPY，与 scheduled 合计分开 ----
assert set(results) == {"seed", "recovered"}
for v in ("seed", "recovered"):
    r = results[v]
    assert int(r["makespan"]) == MAKESPAN[v], r
    assert int(r["extra_ddr"]) == int(bytes_rows[v]["extra"]), (v, r, bytes_rows[v])
    assert int(r["scheduled_copy_bytes"]) == int(bytes_rows[v]["total"])
    assert int(bytes_rows[v]["base"]) + int(bytes_rows[v]["extra"]) == int(bytes_rows[v]["total"])
    assert int(bytes_rows[v]["extra"]) in (5067158, 3923290)
assert int(results["seed"]["extra_ddr"]) == 5067158 and int(results["recovered"]["extra_ddr"]) == 3923290
assert int(results["seed"]["scheduled_copy_bytes"]) == 6351422 and int(results["recovered"]["scheduled_copy_bytes"]) == 5207554

# ---- 断言：events 核编号规范化且可逆 ----
for r in events:
    assert int(r["core"]) in (1, 2) and int(r["core"]) == int(r["source_core_id"]) + 1
    assert 0 <= int(r["start"]) <= int(r["end"])
for v in ("seed", "recovered"):
    assert max(int(r["end"]) for r in events if r["variant"] == v) == MAKESPAN[v]

# ---- 几何断言（F54-R04 判据）：SUBGRAPH 与操作分别检查条形终点 <= makespan ----
for v in ("seed", "recovered"):
    sub = [r for r in events if r["variant"] == v]
    sg = [r for r in sub if r["pipe"] == "SUBGRAPH"]
    ops = [r for r in sub if r["pipe"] != "SUBGRAPH"]
    assert max(int(r["end"]) for r in sg) <= MAKESPAN[v], (v, "SUBGRAPH")
    assert max(int(r["end"]) for r in ops) <= MAKESPAN[v], (v, "ops")

# ---- 断言：markers 六条引用真实事件且周期一致 ----
ev_idx = {(r["variant"], r["event_id"]): r for r in events}
mk_line = {}
for m in markers:
    ev_ = ev_idx[(m["variant"], m["event_id"])]
    val = int(ev_[m["endpoint"]])
    assert val == int(m["cycles"]), (m, val)
    mk_line.setdefault(m["variant"], {})[m["kind"]] = (m["event_id"], m["endpoint"], val)
for v in ("seed", "recovered"):
    assert set(mk_line[v]) == {"makespan_end", "last_copy_in_end", "first_op_start"}
    assert mk_line[v]["makespan_end"][2] == MAKESPAN[v]

# ---- 断言：tradeoff 500 格；相对变化全精度（对非零分母 isclose 复核）----
import math
assert len(tradeoff) == 500
for t in tradeoff:
    db, od = int(t["delta_bytes"]), int(t["old_ddr"])
    if od == 0:
        assert t["relative_ddr"] == "", t
    else:
        assert math.isclose(float(t["relative_ddr"]), db / od, rel_tol=1e-7, abs_tol=1e-9), t
assert int(results["seed"]["makespan"]) == 248166

# ---- 事件数据收集：broken_barh 输入一律 (start, end-start)（F54-R04-1）----
task_by_row = {rc: [] for rc in (("seed", 1), ("seed", 2), ("recovered", 1), ("recovered", 2))}
op_by_row = {rc: {p: [] for p in PIPES} for rc in task_by_row}
for r in events:
    rc = (r["variant"], int(r["core"]))
    s, e = int(r["start"]), int(r["end"])
    seg = (s, e - s)                       # (left, width)
    assert s + (e - s) == e                # 几何一致性：left+width==end
    if r["pipe"] == "SUBGRAPH":
        task_by_row[rc].append(seg)
    else:
        op_by_row[rc][r["pipe"]].append(seg)
for rc, segs in task_by_row.items():
    v = rc[0]
    for s, w in segs:
        assert s + w <= MAKESPAN[v], (rc, s, w)
for rc, bypipe in op_by_row.items():
    v = rc[0]
    for p, segs in bypipe.items():
        for s, w in segs:
            assert s + w <= MAKESPAN[v], (rc, p, s, w)
n_ops = sum(len(segs) for bypipe in op_by_row.values() for segs in bypipe.values())
n_tasks = sum(len(s) for s in task_by_row.values())
assert n_tasks == 26910 and n_ops == 40475, (n_tasks, n_ops)

# ---- 泳道布局常量（F54-R04-2/3）：每核 4 条 Pipe 独立子行 ----
# 块内子行 y = base + i（i=0..3 对应 PIPES 顺序），条形高 0.7，task 背景覆盖整块
# y 越大越靠上：seed 两块在上、recovered 两块在下（与 v2 行序一致：seed核1/核2/rec核1/核2）
BLOCK_BASE = {("recovered", 2): 0.0, ("recovered", 1): 4.0,
              ("seed", 2): 8.7, ("seed", 1): 12.7}
BLOCK_HALF = 0.45          # task 背景上下超出子行网格的半高
SPAN = 3.0                 # 块内 4 子行跨 0..3
# 方案泳道包络（端点线纵范围由此导出，不硬编码）：方案两块的并集
ENVELOPE = {}
for v in ("seed", "recovered"):
    bases = [BLOCK_BASE[(v, c)] for c in (1, 2)]
    ENVELOPE[v] = (min(bases) - BLOCK_HALF, max(bases) + SPAN + BLOCK_HALF)

# ================= 绘图 =================
fig = plt.figure(figsize=(6.5, 8.9))
gs = fig.add_gridspec(3, 1, height_ratios=[1.5, 0.72, 1.05],
                      hspace=0.55, left=0.145, right=0.965, top=0.94,
                      bottom=0.135)
ax_t = fig.add_subplot(gs[0])
ax_b = fig.add_subplot(gs[1])
ax_s = fig.add_subplot(gs[2])

# ---- 面板 1：真实核/Pipe 子泳道时间条 ----
ymax = max(MAKESPAN.values())
for rc, base in BLOCK_BASE.items():
    v, c = rc
    # task 浅灰整核背景（覆盖块内全部子行）
    ax_t.broken_barh(task_by_row[rc], (base - BLOCK_HALF, SPAN + 2 * BLOCK_HALF),
                     color=C_TASK, alpha=0.35, linewidth=0, zorder=1)
    # 4 条 Pipe 各自子行，真实 (start, width)
    for i, p in enumerate(PIPES):
        ax_t.broken_barh(op_by_row[rc][p], (base + i - 0.35, 0.7),
                         color=C_PIPE[p], linewidth=0, zorder=3)
    # 块分隔与核名标注
    ax_t.axhline(base + SPAN + 0.75, color="#D5D8DC", lw=0.6, zorder=0)

# 端点线：由所属方案泳道包络计算（F54-R04-3）
for v in ("seed", "recovered"):
    lo, hi = ENVELOPE[v]
    ax_t.plot([MAKESPAN[v], MAKESPAN[v]], [lo, hi],
              color=C_CAP, linestyle="--", linewidth=1.0, zorder=4)

yticks, ylabels = [], []
for rc, base in BLOCK_BASE.items():
    for i, p in enumerate(PIPES):
        yticks.append(base + i)
        ylabels.append(PIPE_SHORT[p])
ax_t.set_yticks(yticks)
ax_t.set_yticklabels(ylabels, fontsize=7.5)
# 核名（两级标注，置于 y 轴 pipe 标签左侧更远处，避免与 pipe 行标签重叠）
for (v, c), base in BLOCK_BASE.items():
    ax_t.text(-0.105, base + SPAN / 2, ("seed" if v == "seed" else "rec") + "\n核%d" % c,
              transform=ax_t.get_yaxis_transform(), ha="right", va="center",
              fontsize=7.5, color=C_TXT, clip_on=False, linespacing=1.1)
ax_t.set_xlim(0, ymax * 1.06)
ax_t.set_ylim(-0.75, max(e[1] for e in ENVELOPE.values()) + 4.0)
ax_t.set_xlabel("时间（cycles，绝对时间）", fontsize=8)
ax_t.set_title("面板 1｜S15 R05 @e6ae369 配对时间线（seed=旧初解，rec=recovered=R05 恢复候选；case003/k2）",
               fontsize=8, color=C_TXT, pad=4, loc="left")
ax_t.tick_params(labelsize=8)
ax_t.legend(handles=
            [Patch(color=C_PIPE["PIPE_MTE2"], label="PIPE_MTE2 搬入"),
             Patch(color=C_PIPE["PIPE_MTE3"], label="PIPE_MTE3 搬出"),
             Patch(color=C_PIPE["PIPE_V"], label="PIPE_V 计算"),
             Patch(color=C_PIPE["PIPE_M"], label="PIPE_M"),
             Patch(facecolor=C_TASK, alpha=0.35, label="task（SUBGRAPH）背景"),
             Line2D([0], [0], color=C_CAP, ls="--", lw=1.0,
                    label="端点=各自 E0 makespan（248,166 / 254,508）")],
            fontsize=7.5, loc="upper left", ncol=2, frameon=False,
            handlelength=1.2, columnspacing=1.0)

# ---- 面板 2：搬运量分解（新增 COPY 与 scheduled 合计分列）----
x = [0, 1]
w = 0.24
base_v = [int(bytes_rows[v]["base"]) / 1e6 for v in ("seed", "recovered")]
extra_v = [int(bytes_rows[v]["extra"]) / 1e6 for v in ("seed", "recovered")]
total_v = [int(bytes_rows[v]["total"]) / 1e6 for v in ("seed", "recovered")]
ax_b.bar([i - w for i in x], base_v, width=w, color="#5DA7CC", label="基础 COPY")
ax_b.bar(x, extra_v, width=w, color="#E67E22", label="新增 COPY（extra_ddr）")
ax_b.bar([i + w for i in x], total_v, width=w, color="#1A5276", alpha=0.55,
         label="scheduled 合计（基础+新增）")
for i, v in enumerate(("seed", "recovered")):
    b, e, t = (int(bytes_rows[v]["base"]), int(bytes_rows[v]["extra"]),
               int(bytes_rows[v]["total"]))
    ax_b.text(i - w, b / 1e6 + 0.1, f"{b:,}", ha="center", fontsize=7.5)
    ax_b.text(i, e / 1e6 + 0.1, f"{e:,}", ha="center", fontsize=7.5)
    ax_b.text(i + w, t / 1e6 + 0.1, f"{t:,}", ha="center", fontsize=7.5)
ax_b.set_xticks(x)
ax_b.set_xticklabels(["① seed（旧初解，248,166 cycles）", "② recovered（R05 恢复候选，254,508 cycles）"],
                     fontsize=8)
ax_b.set_ylabel("搬运量（10^6 B）", fontsize=8)
ax_b.set_ylim(0, 12)
ax_b.set_title("面板 2｜S15 R05 @e6ae369 搬运量分解：新增 COPY −22.57%、总 COPY −18.01%，Makespan 反升 +2.56%",
               fontsize=8, color=C_TXT, pad=4, loc="left")
ax_b.legend(fontsize=8, loc="upper right", frameon=False)
ax_b.tick_params(labelsize=8)

# ---- 面板 3：S16 全量 500 格散点；图例移到轴下预留空白（F54-R05）----
CAT_STYLE = {
    "both_down": ("#27AE60", "同降（55 格）", "o"),
    "mk_down_ddr_up": ("#E67E22", "Makespan 降但 DDR 升（199 格）", "s"),
    "mk_down_ddr_same": ("#2980B9", "Makespan 降且 DDR 不变（14 格）", "D"),
    "unchanged": ("#BDC3C7", "两项均不变（232 格）", "."),
}
for cat, (col, lab, mk) in CAT_STYLE.items():
    pts = [(int(t["delta_cycles"]), int(t["delta_bytes"]) / 1e6)
           for t in tradeoff if t["category"] == cat]
    ax_s.scatter([p[0] for p in pts], [p[1] for p in pts], s=8, color=col, marker=mk,
                 alpha=0.75, label=lab, linewidths=0)
ax_s.axhline(0, color="#7F8C8D", linewidth=0.7)
ax_s.axvline(0, color="#7F8C8D", linewidth=0.7)
ax_s.set_xlabel("ΔMakespan = 新−旧（cycles，负=改善）", fontsize=8)
ax_s.set_ylabel("Δ额外 DDR（10^6 B，正=退化）", fontsize=8)
ax_s.set_title("面板 3｜S16 @70f2e8bd 全量 500 格（2794ceba→c665）：周期/额外 DDR 取舍（绝对量）",
               fontsize=8, color=C_TXT, pad=4, loc="left")
# 图例在轴下两行，不遮任何数据点（不删点、不截断坐标）
ax_s.legend(fontsize=7.5, loc="upper center", bbox_to_anchor=(0.5, -0.16),
            ncol=2, frameon=False, markerscale=1.4, columnspacing=1.6)
ax_s.tick_params(labelsize=8)

svg_path = os.path.join(HERE, "figure.svg")
png_path = os.path.join(HERE, "figure.png")
fig.savefig(svg_path, format="svg")
fig.savefig(png_path, format="png", dpi=300)
print("figure.svg / figure.png written")
print("panel1: broken_barh (start, end-start); tasks=%d ops=%d; envelopes=%s"
      % (n_tasks, n_ops, {v: ENVELOPE[v] for v in ENVELOPE}))
print("panel3 legend below axes; all 500 cells drawn")
