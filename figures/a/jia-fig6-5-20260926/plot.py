# -*- coding: utf-8 -*-
"""图 6-5｜冷读启动竞争与关键路径分解（case044 / 5 核，前缀机制单格）。

绘图只读交付包内四张 CSV（prefix_ops / critical_path_ops / evidence_points /
path_contributions），不读取包外文件；CSV 由 extract_inputs.py 从两项固定来源
生成并核对哈希（28e8c7dd 提交的 prefix-realized-path audit.json 与
pipeline-prefix-linux evidence.tar.gz，成员 official-p3.json.gz 解压前 SHA
d4cdf8db… 与审计 official_result_sha256 一致）。

面板 A：四条冷读前缀的实际时间轴（每前缀一行，COPY_IN 真实 start/end，
条宽=持续时间）+ 已核关键路径行（366 操作按类型着色，含跨核等待空隙）。
每条前缀行标注条件共享模型完成下界（式 6-18）与官方完成事件；
仅前缀 2 的冷读位于已核关键路径开头（同 op_id 可核），据此画一条
前缀→关键路径的证据连接线；其余前缀与关键路径的连接无审计证据，不画。

面板 B：三类证据点图——乐观独占值（模型推导）、条件共享模型界（研究界）、
官方实测（E0 结果）用不同标记；横轴为对数刻度（数值跨 123–38,024 cycles）。
三类数不是三个可执行算法的实测成绩，图例与图注分别标明身份。

运行（工作目录=仓库根）：
  .venv/Scripts/python.exe figures/a/jia-fig6-5-20260926/plot.py
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
C_COPYIN = "#2E86AB"
C_COPYOUT = "#5DA7CC"
C_CONV = "#E67E22"
C_RELU = "#D35400"
C_ADD = "#F5B041"
C_BOUND = "#7D3C98"     # 条件模型界
C_MEAS = "#C0392B"      # 官方实测
C_OPT = "#7F8C8D"       # 乐观独占值

plt.rcParams["font.family"] = "Microsoft YaHei"
plt.rcParams["axes.unicode_minus"] = False
plt.rcParams["font.size"] = 8

MAKESPAN = 38024
EXCL_BOUND = 29780
SHARED_BOUND = 36592


def read_csv(name):
    with open(os.path.join(HERE, name), encoding="utf-8") as f:
        return list(csv.DictReader(f))


prefix_ops = read_csv("prefix_ops.csv")
cp_ops = read_csv("critical_path_ops.csv")
evidence = read_csv("evidence_points.csv")
contrib = {r["component"]: int(r["cycles"]) for r in read_csv("path_contributions.csv")}

# ---- 断言：端点与官方值一致 ----
assert len(prefix_ops) == 40 and len(cp_ops) == 366
for r in prefix_ops + cp_ops:
    assert 0 <= int(r["start"]) <= int(r["end"]) <= MAKESPAN
    assert int(r["end"]) - int(r["start"]) == int(r["duration"])
for k in ("1", "2", "3", "4"):
    mx = max(int(r["end"]) for r in prefix_ops if r["prefix_id"] == "prefix" + k)
    ev = {e["cycles"] for e in evidence
          if e["object"] == "prefix" + k and e["evidence_type"] == "official_measured"}
    assert mx == int(ev.pop()), (k, mx)
assert max(int(r["end"]) for r in cp_ops) == MAKESPAN
assert contrib["duration_excess_above_minimum"] == MAKESPAN - EXCL_BOUND == 8244
assert (contrib["COPY_IN"] + contrib["COPY_OUT"] + contrib["CONV"] + contrib["RELU"]
        + contrib["ADD"] + contrib["cross_lag"]) == MAKESPAN
# 前缀 2 的操作 = 已核关键路径开头（同 op_id 序列，可画证据连接线）
p2 = [r["op_id"] for r in prefix_ops if r["prefix_id"] == "prefix2"]
assert p2 == [r["op_id"] for r in cp_ops[:len(p2)]], "prefix2 not at critical-path head"

C_OP = {"COPY_IN": C_COPYIN, "COPY_OUT": C_COPYOUT,
        "CONV": C_CONV, "RELU": C_RELU, "ADD": C_ADD}

# ================= 绘图 =================
fig = plt.figure(figsize=(6.5, 8.4))
gs = fig.add_gridspec(2, 1, height_ratios=[1.1, 0.95],
                      hspace=0.5, left=0.155, right=0.96, top=0.935, bottom=0.075)
ax_g = fig.add_subplot(gs[0])
ax_e = fig.add_subplot(gs[1])

# ---- 面板 A：前缀甘特 + 已核关键路径 ----
ROWS = [("prefix1", "前缀1·核2"), ("prefix2", "前缀2·核3"),
        ("prefix3", "前缀3·核4"), ("prefix4", "前缀4·核5"),
        ("cp", "已核关键路径\n(366 操作)")]
row_y = {name: len(ROWS) - 1 - i for i, (name, _) in enumerate(ROWS)}
# 核号为展示核号（原始 core_id+1）；prefix1..4 分别在原始核 1/2/3/4（展示核 2/3/4/5）
by_prefix = defaultdict(list)
for r in prefix_ops:
    by_prefix[r["prefix_id"]].append((int(r["start"]), int(r["end"]) - int(r["start"])))
for name, _ in ROWS[:4]:
    y = row_y[name]
    ax_g.broken_barh(by_prefix[name], (y - 0.32, 0.64),
                     color=C_COPYIN, linewidth=0, zorder=3)

# 关键路径行：366 操作按类型着色
by_op = defaultdict(list)
for r in cp_ops:
    by_op[r["op"]].append((int(r["start"]), int(r["end"]) - int(r["start"])))
ycp = row_y["cp"]
for op, segs in by_op.items():
    ax_g.broken_barh(segs, (ycp - 0.32, 0.64), color=C_OP[op], linewidth=0, zorder=3)

# 每条前缀：条件模型完成下界（紫虚线）与官方完成事件（红点线）
for k in ("1", "2", "3", "4"):
    y = row_y["prefix" + k]
    flb = int(next(e["cycles"] for e in evidence
                   if e["object"] == "prefix" + k and e["evidence_type"] == "conditional_shared_bound"))
    fin = int(next(e["cycles"] for e in evidence
                   if e["object"] == "prefix" + k and e["evidence_type"] == "official_measured"))
    ax_g.plot([flb, flb], [y - 0.45, y + 0.45], color=C_BOUND, lw=1.1, ls="--", zorder=4)
    ax_g.plot([fin, fin], [y - 0.45, y + 0.45], color=C_MEAS, lw=1.1, ls=":", zorder=4)
# 整体端点
ax_g.axvline(MAKESPAN, color=C_MEAS, lw=1.0, ls=":", zorder=4)

# 证据支持的连接线：仅前缀 2（其 7 次冷读 = 关键路径开头同 op_id 序列）
y_p2 = row_y["prefix2"]
ax_g.annotate("", xy=(int(cp_ops[6]["end"]), ycp + 0.45),
              xytext=(16847, y_p2 - 0.45),
              arrowprops=dict(arrowstyle="->", color=C_MEAS, lw=0.9, ls="--"))

ax_g.set_yticks([row_y[n] for n, _ in ROWS])
ax_g.set_yticklabels([lab for _, lab in ROWS], fontsize=7.5)
ax_g.set_xlim(0, MAKESPAN * 1.05)
ax_g.set_ylim(-0.6, len(ROWS) + 0.85)
ax_g.set_xlabel("时间（cycles，绝对时间）", fontsize=8)
ax_g.set_title("面板 A｜case044/k5 四条冷读前缀实际时间轴与已核关键路径（官方 makespan 38,024）",
               fontsize=8, color=C_TXT, pad=4, loc="left")
ax_g.tick_params(labelsize=8)
ax_g.legend(handles=
            [Patch(color=C_COPYIN, label="冷读 COPY_IN（前缀 40 笔，全部 miss）"),
             Patch(color=C_CONV, label="关键路径 CONV"),
             Patch(color=C_RELU, label="关键路径 RELU"),
             Patch(color=C_ADD, label="关键路径 ADD"),
             Patch(color=C_COPYIN, alpha=1.0, label="关键路径 COPY_IN/COPY_OUT"),
             Line2D([0], [0], color=C_BOUND, lw=1.1, ls="--",
                    label="条件共享模型完成下界（式 6-18）"),
             Line2D([0], [0], color=C_MEAS, lw=1.1, ls=":",
                    label="官方完成事件 / makespan（E0）"),
             Line2D([0], [0], color=C_MEAS, lw=0.9, ls="--", marker=">",
                    label="证据连接：前缀2 冷读=关键路径开头")],
            fontsize=7, loc="upper left", ncol=2, frameon=False,
            handlelength=1.3, columnspacing=0.9)

# ---- 面板 B：三类证据点图（对数横轴）----
objects = ["prefix1", "prefix2", "prefix3", "prefix4", "overall"]
OBJ_LAB = {"prefix1": "前缀1（W=3,577）", "prefix2": "前缀2（W=8,603）",
           "prefix3": "前缀3（W=3,112）", "prefix4": "前缀4（W=123）",
           "overall": "整体 makespan"}
STYLE = {
    "exclusive_optimistic": (C_OPT, "o", "乐观独占值（模型推导，非实测）"),
    "conditional_shared_bound": (C_BOUND, "s", "条件共享模型界（式 6-18 研究界）"),
    "official_measured": (C_MEAS, "D", "官方实测（E0 结果）"),
}
ev_map = {(e["object"], e["evidence_type"]): int(e["cycles"]) for e in evidence}
ys = {o: len(objects) - 1 - i for i, o in enumerate(objects)}
for obj in objects:
    trio = [("exclusive_optimistic", ev_map[(obj, "exclusive_optimistic")]),
            ("conditional_shared_bound", ev_map[(obj, "conditional_shared_bound")]),
            ("official_measured", ev_map[(obj, "official_measured")])]
    xs = [v for _, v in trio]
    ax_e.plot(xs, [ys[obj]] * 3, color="#BDC3C7", lw=0.8, ls=":", zorder=1)
    for etype, v in trio:
        col, mk, _ = STYLE[etype]
        ax_e.scatter([v], [ys[obj]], s=34, color=col, marker=mk, zorder=3, linewidths=0)
        ax_e.annotate("{:,}".format(v), (v, ys[obj]), textcoords="offset points",
                      xytext=(0, 7) if etype == "exclusive_optimistic" else ((17, 7) if etype == "conditional_shared_bound" else (0, -13)),
                      ha="center", fontsize=7,
                      color=col if etype != "exclusive_optimistic" else "#5D6D7E")
ax_e.set_yticks([ys[o] for o in objects])
ax_e.set_yticklabels([OBJ_LAB[o] for o in objects], fontsize=7.5)
ax_e.set_xscale("log")
ax_e.set_xlim(100, 60000)
ax_e.set_ylim(-0.6, len(objects) - 0.3)
ax_e.set_xlabel("周期（cycles，对数刻度；同一对象三点为不同口径，非三个算法的成绩）", fontsize=8)
ax_e.set_title("面板 B｜乐观独占值 29,780 → 条件模型界 36,592 → 官方实测 38,024（case044/k5）",
               fontsize=8, color=C_TXT, pad=4, loc="left")
ax_e.tick_params(labelsize=8)
ax_e.legend(handles=[Line2D([0], [0], color=col, marker=mk, ls="", markersize=6, label=lab)
                     for (_, (col, mk, lab)) in STYLE.items()],
            fontsize=7.5, loc="upper left", frameon=False)

svg_path = os.path.join(HERE, "figure.svg")
png_path = os.path.join(HERE, "figure.png")
fig.savefig(svg_path, format="svg")
fig.savefig(png_path, format="png", dpi=300)
print("figure.svg / figure.png written")
print("panelA rows: 4 prefixes (40 cold COPY_IN) + critical path 366 ops; link drawn only for prefix2")
print("panelB: 5 objects x 3 evidence types = 15 points, log x-scale")
