# -*- coding: utf-8 -*-
"""图 5-4｜通信、容量与调度耦合的典型正反例（case003/k2 R05 + S16 全量对照）。

绘图只读交付包内五张 CSV（events / markers / results / bytes / tradeoff），
不读取包外文件；CSV 由 extract_inputs.py 从两项固定来源生成并核对哈希
（S15 result.zip @e6ae3699、S16 report.json @70f2e8bd，见该脚本与 audit.sources）。

面板 1（v2）：同轴真实核/Pipe 操作时间条——每方案每核一行，操作按 trace 原始
管道类别（PIPE_MTE2/MTE3/V/M）以真实 start/end 画条，task（SUBGRAPH）区间仅作
浅灰背景，不计入任何操作计数（v1 的 500-cycle 活跃桶热条已弃用）。
面板 2：搬运量分解——extra_ddr 一律指新增 COPY（added_copy_bytes），
scheduled 合计单独列示，二者不混用。
面板 3：S16 全量 500 格 Δ 散点（绝对量展示；旧额外 DDR=0 的 120 格不算相对变化）。

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
SHORT = {"seed": "seed", "recovered": "rec"}   # 面板 1 行标签用短名，全称在标题/图例给出

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

# ================= 绘图 =================
fig = plt.figure(figsize=(6.5, 8.0))
gs = fig.add_gridspec(3, 1, height_ratios=[1.05, 0.9, 1.2],
                      hspace=0.52, left=0.105, right=0.965, top=0.94, bottom=0.065)
ax_t = fig.add_subplot(gs[0])
ax_b = fig.add_subplot(gs[1])
ax_s = fig.add_subplot(gs[2])

# ---- 面板 1：真实核/Pipe 操作时间条（task 仅作浅灰背景，不入计数）----
rows = [("seed", 1), ("seed", 2), ("recovered", 1), ("recovered", 2)]
ymax = max(MAKESPAN.values())
op_by_row = {rc: defaultdict(list) for rc in rows}
task_by_row = {rc: [] for rc in rows}
for r in events:
    rc = (r["variant"], int(r["core"]))
    if r["pipe"] == "SUBGRAPH":
        task_by_row[rc].append((int(r["start"]), int(r["end"])))
    else:
        op_by_row[rc][r["pipe"]].append((int(r["start"]), int(r["end"])))

for ri, rc in enumerate(rows):
    y = len(rows) - 1 - ri
    v, c = rc
    # task 背景条（浅灰，行高 0.86）
    ax_t.broken_barh(task_by_row[rc], (y - 0.43, 0.86),
                     color=C_TASK, alpha=0.35, linewidth=0, zorder=1)
    # 真实操作条（按管道类别，行高 0.44）
    for pipe, segs in op_by_row[rc].items():
        ax_t.broken_barh(segs, (y - 0.22, 0.44),
                         color=C_PIPE[pipe], linewidth=0, zorder=3)

# 端点线只画在所属方案的两行范围内（seed 上两行 / rec 下两行）
for v, y_top in (("seed", 3), ("recovered", 1)):
    ax_t.plot([MAKESPAN[v], MAKESPAN[v]], [y_top - 0.55, y_top + 1.5 + 0.55],
              color=C_CAP, linestyle="--", linewidth=1.0, zorder=4)

ax_t.set_yticks([len(rows) - 1 - i for i in range(len(rows))])
ax_t.set_yticklabels(["%s 核%d" % (SHORT[v], c) for v, c in rows], fontsize=8)
ax_t.set_xlim(0, ymax * 1.06)
ax_t.set_ylim(-0.65, 5.45)
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
ax_b.set_ylim(0, 9.6)
ax_b.set_title("面板 2｜S15 R05 @e6ae369 搬运量分解：新增 COPY −22.57%、总 COPY −18.01%，Makespan 反升 +2.56%",
               fontsize=8, color=C_TXT, pad=4, loc="left")
# 图例移到右上空白区（柱顶最高 6.35+标签，y>7 无数据），不盖数值
ax_b.legend(fontsize=8, loc="upper right", frameon=False)
ax_b.tick_params(labelsize=8)

# ---- 面板 3：S16 全量 500 格散点（绝对量；图例移右上——Δcycles≤0，右半无数据）----
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
ax_s.legend(fontsize=8, loc="upper right", markerscale=1.5, frameon=False)
ax_s.tick_params(labelsize=8)

svg_path = os.path.join(HERE, "figure.svg")
png_path = os.path.join(HERE, "figure.png")
fig.savefig(svg_path, format="svg")
fig.savefig(png_path, format="png", dpi=300)
print("figure.svg / figure.png written")
print("panel1 rows: real op bars by PIPE_*, task as background only;  zero-duration events:",
      sum(1 for r in events if int(r["start"]) == int(r["end"])))
print("markers:", {v: mk_line[v] for v in ("seed", "recovered")})
