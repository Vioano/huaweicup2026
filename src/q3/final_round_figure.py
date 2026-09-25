"""Plot only the independently audited fixed full500 comparison; no evaluations."""
from __future__ import annotations

import argparse
import csv
import hashlib
import json
from pathlib import Path
import platform

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("comparison", type=Path)
    parser.add_argument("summary", type=Path)
    parser.add_argument("output", type=Path)
    args = parser.parse_args()
    rows = list(csv.DictReader(args.comparison.open(encoding="utf-8")))
    summary = json.loads(args.summary.read_text())
    assert len(rows) == summary["cells"] == 500
    assert {(r["case_id"], int(r["cores"])) for r in rows} == {
        (f"{i:03}", k) for i in range(1, 101) for k in range(1, 6)}
    args.output.mkdir(parents=True, exist_ok=False)
    plt.rcParams.update({"font.family": "DejaVu Sans", "font.size": 9,
                         "axes.spines.top": False, "axes.spines.right": False,
                         "pdf.fonttype": 42, "svg.fonttype": "none"})
    fig, axes = plt.subplots(1, 3, figsize=(11.1, 3.3), layout="constrained")
    old, new = "#65758A", "#137C83"
    ax = axes[0]
    ks = list(range(1, 6))
    ax.bar([k-.18 for k in ks], [summary["by_core"][str(k)]["forest_mean_b_over_m"] for k in ks],
           width=.36, color=old, label="Forest baseline")
    ax.bar([k+.18 for k in ks], [summary["by_core"][str(k)]["final_mean_b_over_m"] for k in ks],
           width=.36, color=new, hatch="//", label="Final fixed selector")
    ax.set(xticks=ks, xlabel="Core count", ylabel="Mean single-core baseline / P3",
           title="(a) Whole-suite solution quality", ylim=(0, None))
    ax.legend(frameon=False, fontsize=8)
    ax = axes[1]
    k5 = [r for r in rows if int(r["cores"]) == 5]
    for column, color, style, label in [("forest_g", old, "-", "Forest baseline"),
                                       ("final_g", new, "--", "Final fixed selector")]:
        vals = sorted(float(r[column]) for r in k5)
        ax.step(vals, [(i+1)/100 for i in range(100)], where="post", color=color,
                linestyle=style, linewidth=1.8, label=label)
    ax.axvline(1, color="#999999", linewidth=.8, linestyle=":")
    ax.set(xlabel="Same-plan G = P2 / P3 (K=5)", ylabel="Fraction of 100 graphs",
           title="(b) Cache benefit distribution", ylim=(0, 1.02))
    ax.legend(frameon=False, fontsize=8, loc="lower right")
    ax = axes[2]
    vals = sorted(float(r["solver_wall_seconds"]) for r in rows)
    assert all(t > 0 for t in vals)
    ax.step(vals, [(i+1)/500 for i in range(500)], where="post", color=new, linewidth=1.8)
    ax.set(xscale="log", xlabel="End-to-end solver wall (seconds, log)",
           ylabel="Fraction of 500 cells", title="(c) Final solver latency", ylim=(0, 1.02))
    for ax in axes:
        ax.grid(axis="y", alpha=.2, zorder=0)
        ax.set_axisbelow(True)
    outputs = []
    for suffix in ("pdf", "svg", "png"):
        target = args.output / f"p3-final-full500.{suffix}"
        fig.savefig(target, dpi=180)
        outputs.append({"file": target.name, "sha256": hashlib.sha256(target.read_bytes()).hexdigest()})
    plt.close(fig)
    metadata = {"input_comparison_sha256": hashlib.sha256(args.comparison.read_bytes()).hexdigest(),
                "input_summary_sha256": hashlib.sha256(args.summary.read_bytes()).hexdigest(),
                "plot_source_sha256": hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),
                "solver_commit": summary["source_solver_commit"],
                "runner_commit": summary["source_runner_commit"],
                "python": platform.python_version(), "matplotlib": matplotlib.__version__,
                "outputs": outputs,
                "caption": "One fixed solver, all 100 graphs at each of 1-5 cores. Panel (a) uses arithmetic means of per-graph ratios; (b) uses exact same-plan P2/P3 at five cores; (c) includes construction and online official evaluations. One fresh process per cell; OS page cache is uncontrolled. No confidence intervals or true-device performance claim. Baseline and final curves may coincide."}
    (args.output / "metadata.json").write_text(json.dumps(metadata, indent=2) + "\n")
    print(json.dumps({"figure_directory": str(args.output), "new_evaluations": 0}))


if __name__ == "__main__":
    main()
