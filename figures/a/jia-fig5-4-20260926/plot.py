# -*- coding: utf-8 -*-
"""图 5-4｜通信、容量与调度耦合的典型正反例（case003/k2 R05 + S16 全量对照）。

数据（全部固定提交）：
- S15 单例配对：e6ae3699870c78b11c8c47b0fa9001249a428e1c 的
  results/a/q2-nikolastarx/pro-r05-official-pair-20260925/result.zip
  （SHA-256 c90065d9…；seed=旧初解 248,166 cycles / scheduled COPY 6,351,422 B；
  recovered=R05 恢复候选 254,508 cycles / 5,207,554 B；两方案 spill=0）。
- S16 全量对照：70f2e8bd8e850f1d49c924a86b654b29c24e087f 的
  results/a/q2-nikolastarx/secondary-ddr-full500-20260925/report.json
  （前版 2794ceba vs 主方法 c665，500 格配对）。
运行：.venv/Scripts/python.exe figures/a/jia-fig5-4-20260926/plot.py（工作目录=仓库根）。
"""
import csv
import json
import os
import zipfile
from collections import Counter

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
from matplotlib.lines import Line2D
from matplotlib.patches import Patch

HERE = os.path.dirname(os.path.abspath(__file__))
REF = os.path.normpath(os.path.join(HERE, "..", "..", "..", ".workbuddy", "refs", "p2-54"))
C_TXT = "#2C3E50"
C_SEED = "#7F8C8D"
C_REC = "#2E86AB"
C_CAP = "#C0392B"
plt.rcParams["font.family"] = "Microsoft YaHei"
plt.rcParams["axes.unicode_minus"] = False

MAKESPAN = {"seed": 248166, "recovered": 254508}
LABEL = {"seed": "seed（旧初解）", "recovered": "recovered（R05 恢复候选）"}

z = zipfile.ZipFile(os.path.join(REF, "r05-result.zip"))
report = json.loads(open(os.path.join(REF, "s16-report.json"), encoding="utf-8").read())
batch = json.loads(z.read("output/batch.json"))

res, traces = {}, {}
for r in batch["rows"]:
    label = r["label"]
    res[label] = json.loads(z.read(f"output/{label}/result.json"))
    traces[label] = json.loads(z.read(f"output/{label}/trace.json"))
    assert res[label]["makespan"] == MAKESPAN[label], (label, res[label]["makespan"])
plan_sha = {r["label"]: r["plan_sha256"] for r in batch["rows"]}
print("results OK:", {k: res[k]["makespan"] for k in res})

# ---------- events.csv：两方案全部 X 事件 ----------
events = []
eid = 0
for v in ("seed", "recovered"):
    for e in traces[v]["traceEvents"]:
        if e.get("ph") != "X":
            continue
        core = e["args"].get("core_id")
        start = int(e["args"].get("start", e["ts"]))
        end = int(e["args"].get("end", e["ts"] + e["dur"]))
        events.append({"variant": v, "event_id": eid,
                       "op_id": e["name"].split("#")[-1].strip() if "#" in e["name"] else e["name"],
                       "core": core, "pipe": e["cat"], "start": start, "end": end})
        eid += 1
for v in ("seed", "recovered"):
    mx = max(r["end"] for r in events if r["variant"] == v)
    assert mx == MAKESPAN[v], (v, mx)
print("events rows:", len(events), "| endpoints == makespan OK")

markers = []
for v in ("seed", "recovered"):
    markers.append({"variant": v, "kind": "makespan_end", "event_id": MAKESPAN[v]})
    mte2 = [r["end"] for r in events if r["variant"] == v and r["pipe"] == "PIPE_MTE2"]
    markers.append({"variant": v, "kind": "last_copy_in_end", "event_id": max(mte2)})
    markers.append({"variant": v, "kind": "first_op_start", "event_id": 0})

# ---------- bytes.csv ----------
bytes_rows = []
for v in ("seed", "recovered"):
    dm = res[v]["data_movement_bytes"]
    bytes_rows.append({"variant": v, "base": dm["original_graph_copy_bytes"],
                       "extra": dm["added_copy_bytes"],
                       "total": dm["scheduled_copy_bytes"]})
    assert dm["spill_added_copy_bytes"] == 0
print("bytes:", [(b["variant"], b["base"], b["extra"], b["total"]) for b in bytes_rows])

# ---------- tradeoff.csv ----------
tradeoff = []
zero_old_ddr = 0
cat_count = Counter()
for c in report["cells"]:
    dc = c["new_makespan"] - c["old_makespan"]
    db = c["new_extra"] - c["old_extra"]
    rel = "" if c["old_extra"] == 0 else round(db / c["old_extra"], 6)
    if c["old_extra"] == 0:
        zero_old_ddr += 1
    if c["new_makespan"] < c["old_makespan"] and db < 0:
        cat = "both_down"
    elif c["new_makespan"] < c["old_makespan"] and db == 0:
        cat = "mk_down_ddr_same"
    elif c["new_makespan"] < c["old_makespan"]:
        cat = "mk_down_ddr_up"
    elif c["new_makespan"] == c["old_makespan"] and db == 0:
        cat = "unchanged"
    else:
        cat = "other"
    cat_count[cat] += 1
    tradeoff.append({"case": c["case"], "cores": c["cores"],
                     "old_makespan": c["old_makespan"], "new_makespan": c["new_makespan"],
                     "old_ddr": c["old_extra"], "new_ddr": c["new_extra"],
                     "delta_cycles": dc, "delta_bytes": db, "relative_ddr": rel,
                     "category": cat})
assert len(tradeoff) == 500
print("categories:", dict(cat_count), "| old_ddr==0 cells:", zero_old_ddr)


def write_csv(name, rows, header):
    with open(os.path.join(HERE, name), "w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=header, extrasaction="ignore")
        w.writeheader()
        w.writerows(rows)


write_csv("events.csv", events, ["variant", "event_id", "op_id", "core", "pipe", "start", "end"])
write_csv("markers.csv", markers, ["variant", "kind", "event_id"])
write_csv("results.csv",
          [{"variant": v, "case": "003", "cores": 2, "makespan": MAKESPAN[v],
            "extra_ddr": res[v]["data_movement_bytes"]["scheduled_copy_bytes"],
            "plan_hash": plan_sha[v]} for v in ("seed", "recovered")],
          ["variant", "case", "cores", "makespan", "extra_ddr", "plan_hash"])
write_csv("bytes.csv", bytes_rows, ["variant", "base", "extra", "total"])
write_csv("tradeoff.csv", tradeoff,
          ["case", "cores", "old_makespan", "new_makespan", "old_ddr", "new_ddr",
           "delta_cycles", "delta_bytes", "relative_ddr", "category"])

# ---------- 绘图：三面板 ----------
fig = plt.figure(figsize=(6.5, 7.2))
gs = fig.add_gridspec(3, 1, height_ratios=[1.0, 0.95, 1.25],
                      hspace=0.5, left=0.11, right=0.96, top=0.92, bottom=0.07)
ax_t = fig.add_subplot(gs[0])
ax_b = fig.add_subplot(gs[1])
ax_s = fig.add_subplot(gs[2])

# ---- 面板 1：配对时间线（每核占用密度热条，500-cycle bin）----
BIN = 500
rows = [("seed", 0), ("seed", 1), ("recovered", 0), ("recovered", 1)]
ymax = max(MAKESPAN.values())
for ri, (v, c) in enumerate(rows):
    y = len(rows) - 1 - ri
    sel = [r for r in events if r["variant"] == v and r["core"] == c]
    nbins = ymax // BIN + 1
    active = [0] * nbins
    for r in sel:
        for b in range(r["start"] // BIN, min(r["end"] // BIN, nbins - 1) + 1):
            active[b] += 1
    mx = max(max(active), 1)
    for bi, cnt in enumerate(active):
        if cnt:
            ax_t.barh(y, BIN, left=bi * BIN, height=0.8,
                      color=C_REC if v == "recovered" else C_SEED,
                      alpha=min(0.25 + 0.75 * cnt / mx, 1.0), linewidth=0)
    ax_t.axvline(MAKESPAN[v], color=C_CAP, linestyle="--", linewidth=1.1)
    ax_t.text(MAKESPAN[v] - 3000, y + 0.28, f"{LABEL[v]} 端点 {MAKESPAN[v]:,}",
              fontsize=5.8, color=C_CAP, ha="right")
ax_t.set_yticks([len(rows) - 1 - i for i in range(len(rows))])
ax_t.set_yticklabels([f"{LABEL[v]}·核{c+1}" for v, c in rows], fontsize=6.3)
ax_t.set_xlim(0, ymax * 1.06)
ax_t.set_ylim(-0.6, len(rows) - 0.3)
ax_t.set_xlabel("周期（cycles，绝对时间；色深=该 500-cycle 桶内活跃操作数）", fontsize=6.8)
ax_t.set_title("面板 1｜case003/k2 配对时间线（seed vs recovered，端点=各自 E0 makespan）",
               fontsize=7.6, color=C_TXT, pad=4, loc="left")
ax_t.tick_params(labelsize=6.5)

# ---- 面板 2：搬运量分解 ----
x = [0, 1]
w = 0.24
base_v = [b["base"] / 1e6 for b in bytes_rows]
extra_v = [b["extra"] / 1e6 for b in bytes_rows]
total_v = [b["total"] / 1e6 for b in bytes_rows]
ax_b.bar([i - w for i in x], base_v, width=w, color="#5DA7CC",
         label="基础 COPY（original_graph_copy_bytes）")
ax_b.bar(x, extra_v, width=w, color="#E67E22",
         label="新增 COPY（added_copy_bytes，切分新增）")
ax_b.bar([i + w for i in x], total_v, width=w, color="#1A5276", alpha=0.55,
         label="scheduled COPY 合计（=基础+新增）")
for i, b in enumerate(bytes_rows):
    ax_b.text(i - w, b["base"] / 1e6 + 0.08, f"{b['base']:,}", ha="center", fontsize=5.6)
    ax_b.text(i, b["extra"] / 1e6 + 0.08, f"{b['extra']:,}", ha="center", fontsize=5.6)
    ax_b.text(i + w, b["total"] / 1e6 + 0.08, f"{b['total']:,}", ha="center", fontsize=5.6)
ax_b.set_xticks(x)
ax_b.set_xticklabels([f"① {LABEL['seed']}\n（官方 248,166 cycles）",
                      f"② {LABEL['recovered']}\n（官方 254,508 cycles）"], fontsize=6.6)
ax_b.set_ylabel("搬运量（10^6 B）", fontsize=7.2)
ax_b.set_ylim(0, 8.6)
ax_b.set_title("面板 2｜搬运量分解：COPY 减少 18.0% 但 Makespan 反升 2.56%（负例）",
               fontsize=7.6, color=C_TXT, pad=4, loc="left")
ax_b.legend(fontsize=5.8, loc="upper center", ncol=1)
ax_b.tick_params(labelsize=6.5)

# ---- 面板 3：S16 全量 500 格散点 ----
CAT_STYLE = {
    "both_down": ("#27AE60", "同降（55 格）", "o"),
    "mk_down_ddr_up": ("#E67E22", "Makespan 降但 DDR 升（199 格）", "s"),
    "mk_down_ddr_same": ("#2980B9", "Makespan 降且 DDR 不变（14 格）", "D"),
    "unchanged": ("#BDC3C7", "两项均不变（232 格）", "."),
}
for cat, (col, lab, mk) in CAT_STYLE.items():
    pts = [(t["delta_cycles"], t["delta_bytes"] / 1e6) for t in tradeoff if t["category"] == cat]
    ax_s.scatter([p[0] for p in pts], [p[1] for p in pts], s=7, color=col, marker=mk,
                 alpha=0.75, label=lab, linewidths=0)
ax_s.axhline(0, color="#7F8C8D", linewidth=0.7)
ax_s.axvline(0, color="#7F8C8D", linewidth=0.7)
ax_s.set_xlabel("ΔMakespan = 新−旧（cycles，负=改善）", fontsize=7.2)
ax_s.set_ylabel("Δ额外 DDR（10^6 B，正=退化）", fontsize=7.2)
ax_s.set_title("面板 3｜S16 完整 500 格：周期/额外 DDR 取舍（绝对量展示，保留改善/持平/退化）",
               fontsize=7.6, color=C_TXT, pad=4, loc="left")
ax_s.legend(fontsize=5.8, loc="lower right", markerscale=1.6)
ax_s.tick_params(labelsize=6.5)

fig.savefig(os.path.join(HERE, "figure.svg"), format="svg")
fig.savefig(os.path.join(HERE, "figure.png"), format="png", dpi=300)
print("figure.svg / figure.png written")
