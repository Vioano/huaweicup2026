"""Read-only coverage ceiling for one frozen full-500 P3 solver.

The lower bounds are deliberately loose. This program neither constructs nor
evaluates plans; it only joins three existing, frozen evidence files by case.
"""

from __future__ import annotations

import csv
import hashlib
import json
from pathlib import Path


ROOT = Path(__file__).resolve().parents[4]
COVERAGE = ROOT / "results/a/q3-nikolastarx/layered-coverage-static-20260925/coverage.jsonl"
BOUNDS = ROOT / "results/a/q3-nikolastarx/global-bounds-20260925/bounds.csv"
SNAPSHOT = ROOT / "results/a/q3-nikolastarx/forest-current-headroom-20260925/cells-snapshot.json"
SOLVER = "311322b996c0948e8a6a9c7ec6ddfe6ae41fbee1"
RUN = "q3-forest-full500-20260925-s59"
ALGORITHM = "q3-forest-memory-witness"


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def main() -> None:
    coverage_rows = [json.loads(line) for line in COVERAGE.read_text().splitlines()]
    assert len(coverage_rows) == 100
    coverage = {row["case_id"]: row for row in coverage_rows}
    assert len(coverage) == 100
    recognized = {
        case_id: row
        for case_id, row in coverage.items()
        if row["status"] == "recognized_and_decomposed"
    }
    assert len(recognized) == 22

    with BOUNDS.open(newline="") as stream:
        bound_rows = [row for row in csv.DictReader(stream) if row["cores"] == "5"]
    assert len(bound_rows) == 100
    bounds = {row["case_id"]: row for row in bound_rows}
    assert len(bounds) == 100

    snapshot = json.loads(SNAPSHOT.read_text())
    cells = snapshot["cells"]
    assert len(cells) == 500
    five = {cell["case_id"]: cell["best"] for cell in cells if cell["cores"] == 5}
    assert len(five) == 100
    assert set(coverage) == set(bounds) == set(five)
    for case_id, record in five.items():
        assert record["status"] == "ok" and record["baseline_verified"]
        assert record["solver_commit"] == SOLVER
        assert record["run_id"] == RUN and record["algorithm_id"] == ALGORITHM
        identity = record["identity"]
        baseline_identity = record["baseline"]
        for key in ("graph_sha256", "config_sha256", "official_sha256"):
            assert identity[key] == baseline_identity[key]
        assert identity["graph_sha256"] == bounds[case_id]["graph_sha256"]

    rows = []
    for case_id in sorted(recognized):
        record = five[case_id]
        bound = bounds[case_id]
        assert record["identity"]["graph_sha256"] == bound["graph_sha256"] == coverage[case_id]["graph_sha256"]
        baseline = float(bound["official_baseline_cycles"])
        lower = float(bound["lower_bound_cycles"])
        makespan = float(record["metrics"]["makespan_cycles"])
        speedup = float(record["metrics"]["baseline_speedup"])
        assert lower > 0 and makespan >= lower
        assert abs(speedup - baseline / makespan) < 1e-9
        slack = (baseline / lower - speedup) / 100.0
        rows.append({
            "case_id": case_id,
            "track_count": recognized[case_id]["track_count"],
            "baseline_cycles": int(baseline),
            "current_p3_cycles": int(makespan),
            "compute_only_lower_cycles": int(lower),
            "current_speedup": speedup,
            "loose_speedup_ceiling": baseline / lower,
            "max_mean_increment_if_others_fixed": slack,
        })

    current_mean = sum(
        float(record["metrics"]["baseline_speedup"]) for record in five.values()
    ) / 100.0
    four = [row for row in rows if row["track_count"] == 4]
    assert len(four) == 5
    four_slack = sum(row["max_mean_increment_if_others_fixed"] for row in four)
    recognized_slack = sum(row["max_mean_increment_if_others_fixed"] for row in rows)
    deficit = 5.0 - current_mean
    assert 0 < four_slack < deficit < recognized_slack

    result = {
        "schema": "p3-layered-coverage-ceiling-v1",
        "source_sha256": {str(path.relative_to(ROOT)): sha256(path) for path in (COVERAGE, BOUNDS, SNAPSHOT)},
        "solver_commit": SOLVER,
        "full500_cells": len(cells),
        "current_k5_mean_speedup": current_mean,
        "k5_mean_deficit_to_5": deficit,
        "four_track_count": len(four),
        "four_track_cases": [row["case_id"] for row in four],
        "four_track_loose_mean_increment_ceiling": four_slack,
        "mean_even_if_all_four_track_hit_compute_lower": current_mean + four_slack,
        "all_recognized_count": len(rows),
        "all_recognized_loose_mean_increment_ceiling": recognized_slack,
        "required_fraction_of_recognized_loose_slack": deficit / recognized_slack,
        "rows": rows,
        "interpretation": "Compute-only bounds are optimistic and need not be achievable. Four-track-only work cannot reach mean 5 if every other case remains fixed; all 22 recognized cases have enough loose headroom in principle, not a constructive guarantee.",
    }
    print(json.dumps(result, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
