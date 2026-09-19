"""Reproducible synthetic sine fitting; not a result from a competition dataset."""

from __future__ import annotations

import argparse
import hashlib
import json
import platform
import shlex
import subprocess
import sys
from datetime import datetime, timezone
from importlib.metadata import version
from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
from scipy.optimize import least_squares

ROOT = Path(__file__).resolve().parents[1]
PERIOD_MM = 30 * np.pi
TRUE_R_MM, TRUE_BETA_RAD, TRUE_C_MM = 18.0, 0.8, 220.0


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def git_output(*args: str) -> str | None:
    try:
        return subprocess.check_output(
            ["git", "-C", str(ROOT), *args], text=True, stderr=subprocess.DEVNULL
        ).strip()
    except (OSError, subprocess.CalledProcessError):
        return None


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--seed", type=int, default=2026)
    parser.add_argument("--noise-std", type=float, default=0.8, help="Gaussian noise, mm")
    parser.add_argument("--outliers", type=int, default=18)
    args = parser.parse_args()
    n = 240
    if not np.isfinite(args.noise_std) or args.noise_std < 0 or not 0 <= args.outliers <= n:
        parser.error("noise-std must be finite and nonnegative; outliers must be 0..240")
    if args.seed < 0:
        parser.error("seed must be nonnegative")

    rng = np.random.default_rng(args.seed)
    x = np.linspace(0, PERIOD_MM, n, endpoint=False)
    angle = 2 * np.pi * x / PERIOD_MM
    design = np.column_stack((np.sin(angle), np.cos(angle), np.ones(n)))
    truth = TRUE_R_MM * np.sin(angle + TRUE_BETA_RAD) + TRUE_C_MM
    observed = truth + rng.normal(0, args.noise_std, n)
    is_outlier = np.zeros(n, dtype=bool)
    is_outlier[rng.choice(n, args.outliers, replace=False)] = True
    observed[is_outlier] += 20.0

    results, figures = ROOT / "results/demo", ROOT / "figures/demo"
    results.mkdir(parents=True, exist_ok=True)
    figures.mkdir(parents=True, exist_ok=True)
    pd.DataFrame({
        "x_mm": x, "truth_mm": truth, "observed_mm": observed, "is_outlier": is_outlier
    }).to_csv(results / "input.csv", index=False)

    ols = np.linalg.lstsq(design, observed, rcond=None)[0]
    robust = least_squares(lambda coef: design @ coef - observed, ols, loss="soft_l1", f_scale=1.0)
    if not robust.success:
        raise RuntimeError(f"Soft-L1 solver failed: {robust.message}")

    metrics, predictions = [], {"x_mm": x, "truth_mm": truth, "observed_mm": observed}
    fig, ax = plt.subplots(figsize=(8, 4.5), layout="constrained")
    ax.scatter(x, observed, s=10, color="#8896a3", alpha=0.65, label="Synthetic observations")
    ax.plot(x, truth, color="#111827", linestyle="--", label="Known truth")
    for name, coef, color in [("ols", ols, "#2563eb"), ("soft_l1", robust.x, "#d97706")]:
        fitted = design @ coef
        values = {
            "method": name, "seed": args.seed, "n": n,
            "R_mm": float(np.hypot(coef[0], coef[1])), "P_mm": float(PERIOD_MM),
            "beta_rad": float(np.arctan2(coef[1], coef[0])), "C_mm": float(coef[2]),
            "rmse_truth_mm": float(np.sqrt(np.mean((fitted - truth) ** 2))),
            "rmse_observed_mm": float(np.sqrt(np.mean((fitted - observed) ** 2))),
        }
        if not all(np.isfinite(v) for k, v in values.items() if k != "method"):
            raise RuntimeError(f"Non-finite result: {name}")
        metrics.append(values)
        predictions[f"{name}_mm"] = fitted
        ax.plot(x, fitted, color=color, label=name)
    pd.DataFrame(metrics).to_csv(results / "metrics.csv", index=False)
    pd.DataFrame(predictions).to_csv(results / "predictions.csv", index=False)
    ax.set(xlabel="x (mm)", ylabel="y (mm)", title=f"Synthetic sine fit | seed={args.seed}")
    ax.legend(fontsize=8)
    ax.grid(alpha=0.15)
    fig.savefig(figures / "fit.png", dpi=180)
    fig.savefig(figures / "fit.pdf")
    plt.close(fig)

    output_paths = [results / "metrics.csv", results / "predictions.csv", figures / "fit.png", figures / "fit.pdf"]
    record = {
        "data_kind": "synthetic", "generated_at_utc": datetime.now(timezone.utc).isoformat(),
        "command": shlex.join(["uv", "run", "python", "src/demo.py", *sys.argv[1:]]),
        "parameters": vars(args), "n": n, "outlier_shift_mm": 20.0,
        "truth": {"R_mm": TRUE_R_MM, "P_mm": float(PERIOD_MM), "beta_rad": TRUE_BETA_RAD, "C_mm": TRUE_C_MM},
        "solver": {"loss": "soft_l1", "f_scale_mm": 1.0, "success": bool(robust.success), "message": str(robust.message)},
        "python": platform.python_version(), "platform": platform.system(),
        "packages": {name: version(name) for name in ["numpy", "scipy", "pandas", "matplotlib"]},
        "git_commit": git_output("rev-parse", "HEAD"), "git_status": git_output("status", "--porcelain"),
        "sha256": {p.relative_to(ROOT).as_posix(): sha256(p) for p in [
            results / "input.csv", Path(__file__), ROOT / "uv.lock", *output_paths
        ]},
        "limitations": "One synthetic seed; known fixed period. Truth RMSE is unavailable for unlabeled real data. No competition claim.",
    }
    (results / "run.json").write_text(json.dumps(record, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    print(pd.DataFrame(metrics).to_string(index=False))
    print("Wrote results/demo/{input,predictions,metrics}.csv, run.json and figures/demo/fit.{png,pdf}")


if __name__ == "__main__":
    main()
