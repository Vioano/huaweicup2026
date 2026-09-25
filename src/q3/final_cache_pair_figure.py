"""Render archived same-plan P2/P3 pairs; never invoke a solver or evaluator."""
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
    args.output.mkdir(parents=True, exist_ok=False)
    plt.rcParams.update({"font.family": "DejaVu Sans", "font.size": 9,
                         "axes.spines.top": False, "axes.spines.right": False,
                         "pdf.fonttype": 42, "svg.fonttype": "none"})
    fig, axes = plt.subplots(2, 3, figsize=(11.3, 6.4), layout="constrained")
    cells = []
    values = [int(r[name]) for r in rows for name in ("final_m2", "final_m3")]
    assert min(values) > 0
    for k, ax in enumerate(axes.flat, start=1):
        if k == 6:
            break
        subset = sorted((r for r in rows if int(r["cores"]) == k), key=lambda r: r["case_id"])
        p2 = [int(r["final_m2"]) for r in subset]
        p3 = [int(r["final_m3"]) for r in subset]
        gains = [a / b for a, b in zip(p2, p3)]
        cells.append([str(k), "100", f"{statistics.mean(gains):.6f}"])
        ax.plot(range(1, 101), p2, color="#C27335", lw=1.1, label="P2: no L2")
        ax.plot(range(1, 101), p3, color="#137C83", lw=1.1, ls="--", label="P3: read-only Cache")
        ax.set_yscale("log")
        ax.set_ylim(min(values) / 1.3, max(values) * 1.3)
        ax.set_xlim(1, 100)
        ax.set_xticks([1, 25, 50, 75, 100], ["001", "025", "050", "075", "100"])
        ax.set_title(f"({chr(96+k)}) {k} core" + ("s" if k > 1 else ""), loc="left")
        ax.set_xlabel("Case ID")
        ax.set_ylabel("Makespan (cycles, log)")
        ax.grid(axis="y", alpha=.22)
    ax = axes.flat[5]
    ax.axis("off")
    ax.set_title("(f) Same-plan Cache gain", loc="left")
    table = ax.table(cellText=cells, colLabels=["Cores", "Pairs", "Mean G"],
                     cellLoc="center", bbox=[.04, .28, .92, .59])
    table.auto_set_font_size(False)
    table.set_fontsize(9)
    for (row, _), cell in table.get_celld().items():
        cell.set_edgecolor("#D2D8DE")
        if row == 0:
            cell.set_facecolor("#EEF2F4")
            cell.set_text_props(weight="bold")
    ax.text(.04, .21, "G = P2 / P3 for the identical plan.\nMean = arithmetic mean of 100 ratios.\nMatching curves can overlap.",
            transform=ax.transAxes, va="top", fontsize=9, linespacing=1.5)
    handles, labels = axes.flat[0].get_legend_handles_labels()
    fig.legend(handles, labels, loc="outside upper center", ncols=2, frameon=False)
    artifacts = {}
    for suffix in ("png", "pdf", "svg"):
        path = args.output / f"p3-same-plan-cache-comparison.{suffix}"
        fig.savefig(path, dpi=220)
        artifacts[path.name] = hashlib.sha256(path.read_bytes()).hexdigest()
    plt.close(fig)
    metadata = {"input": args.comparison.as_posix(),
                "input_sha256": hashlib.sha256(args.comparison.read_bytes()).hexdigest(),
                "script_sha256": hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),
                "matplotlib": matplotlib.__version__, "cells": 500, "new_evaluations": 0,
                "scope": "Archived final selected plans, paired P2/P3, identical graph/config/cores/plan. Shared log cycle scale across all five panels.",
                "artifacts_sha256": artifacts}
    (args.output / "metadata.json").write_text(json.dumps(metadata, indent=2) + "\n")
    print(json.dumps({"output": args.output.as_posix(), "cells": 500, "new_evaluations": 0}))


if __name__ == "__main__":
    main()
