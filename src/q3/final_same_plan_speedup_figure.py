"""Paper 6-3 research asset: same-plan mean B/M2 and B/M3 by core count."""
from __future__ import annotations

import argparse
import csv
import hashlib
import json
from pathlib import Path
import statistics

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("comparison", type=Path)
    parser.add_argument("output", type=Path)
    args = parser.parse_args()
    rows = list(csv.DictReader(args.comparison.open(encoding="utf-8")))
    assert len(rows) == 500
    assert {(r["case_id"], int(r["cores"])) for r in rows} == {
        (f"{i:03}", k) for i in range(1, 101) for k in range(1, 6)}
    points = []
    for k in range(1, 6):
        group = [r for r in rows if int(r["cores"]) == k]
        assert len(group) == 100
        assert all(int(r[n]) > 0 for r in group for n in ("baseline_cycles", "final_m2", "final_m3"))
        points.append({"cores": k, "pairs": len(group),
            "mean_B_over_M2": statistics.mean(int(r["baseline_cycles"]) / int(r["final_m2"]) for r in group),
            "mean_B_over_M3": statistics.mean(int(r["baseline_cycles"]) / int(r["final_m3"]) for r in group)})
    args.output.mkdir(parents=True, exist_ok=False)
    plt.rcParams.update({"font.family": "DejaVu Sans", "font.size": 10,
                         "axes.spines.top": False, "axes.spines.right": False,
                         "pdf.fonttype": 42, "svg.fonttype": "none"})
    fig, ax = plt.subplots(figsize=(6.3, 4.1), layout="constrained")
    ks = [p["cores"] for p in points]
    ax.plot(ks, [p["mean_B_over_M2"] for p in points], color="#C27335", marker="o", lw=1.7,
            label="P2: no L2 (same plans)")
    ax.plot(ks, [p["mean_B_over_M3"] for p in points], color="#137C83", marker="s", ls="--", lw=1.7,
            label="P3: read-only Cache (same plans)")
    ax.set_xticks(ks)
    ax.set_xlim(.8, 5.2)
    ax.set_ylim(0, 5.1)
    ax.set_xlabel("Core count")
    ax.set_ylabel("Mean speedup relative to official single core")
    ax.set_title("Same-plan comparison: mean(B / M2) and mean(B / M3)", fontsize=10)
    ax.legend(loc="upper left", frameon=False)
    ax.grid(axis="y", alpha=.22)
    artifacts = {}
    for suffix in ("png", "pdf", "svg"):
        path = args.output / f"p3-same-plan-speedup-by-core.{suffix}"
        fig.savefig(path, dpi=230)
        artifacts[path.name] = hashlib.sha256(path.read_bytes()).hexdigest()
    plt.close(fig)
    (args.output / "plot-data.json").write_text(json.dumps(points, indent=2) + "\n")
    metadata = {"input": args.comparison.as_posix(),
                "input_sha256": hashlib.sha256(args.comparison.read_bytes()).hexdigest(),
                "script_sha256": hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),
                "matplotlib": matplotlib.__version__, "cells": 500, "new_evaluations": 0,
                "scope": "100 identical-plan P2/P3 pairs per K. Common official single-core B per graph. Arithmetic mean of per-graph B/M, never meanG or ratio of total cycles.",
                "artifacts_sha256": artifacts}
    (args.output / "metadata.json").write_text(json.dumps(metadata, indent=2) + "\n")
    print(json.dumps({"output": args.output.as_posix(), "points": points, "new_evaluations": 0}))


if __name__ == "__main__":
    main()
