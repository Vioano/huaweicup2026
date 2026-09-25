"""Compare one existing fixed run against display-only reference numbers.

Offline arithmetic only: never import a solver, fetch a feed, or select historical
winners. Reference identity and rounding method remain unverified.
"""
import csv
import hashlib
import json
import math
from pathlib import Path
from statistics import mean

HERE = Path(__file__).resolve().parent
SNAPSHOT = HERE.parent / "forest-current-headroom-20260925/cells-snapshot.json"
SOURCE = "311322b996c0948e8a6a9c7ec6ddfe6ae41fbee1"
RUN = "q3-forest-full500-20260925-s59"
CONFIG = "dcd10de54b23f8366428fb24e828812b1da9549e6eae4a3c3f38604fe5ae77b9"
OFFICIAL = "de11a83db8d7c47ed328b15a7df71d613a833b16cd23ee9fe877999578a1ace0"
FIGURE1 = {2: 2.28, 3: 3.23, 4: 4.09, 5: 4.76}


def main():
    rows = list(csv.DictReader((HERE / "reference-image-2.csv").open()))
    assert len(rows) == 100
    reference = {r["case_id"]: r for r in rows}
    assert len(reference) == 100 and set(reference) == {f"{n:03d}" for n in range(1, 101)}
    snapshot = json.loads(SNAPSHOT.read_text())
    cells = {}
    for cell in snapshot["cells"]:
        key = (cell["case_id"], cell["cores"])
        assert key not in cells
        r = cell["best"]
        assert r["problem"] == cell["problem"] == "P3"
        assert r["run_id"] == RUN and r["solver_commit"] == SOURCE
        assert r["algorithm_id"] == "q3-forest-memory-witness"
        assert r["status"] == "ok" and r["eligible"] and r["baseline_verified"]
        assert (r["case_id"], r["cores"]) == key
        assert r["evaluator"]["route"] == "E0"
        for identity in [r["identity"], r["baseline"]]:
            assert identity["config_sha256"] == CONFIG
            assert identity["official_sha256"] == OFFICIAL
        assert r["identity"]["graph_sha256"] == r["baseline"]["graph_sha256"]
        value = r["metrics"]["baseline_speedup"]
        assert math.isfinite(value) and value > 0
        cells[key] = value
    assert set(cells) == {(f"{i:03d}", k) for i in range(1, 101) for k in range(1, 6)}

    figure1 = {}
    figure2 = {}
    gaps = []
    for k in range(2, 6):
        current = mean(cells[(f"{i:03d}", k)] for i in range(1, 101))
        target = FIGURE1[k]
        figure1[k] = {"current_full100_mean": current, "screenshot_display": target,
                      "numeric_difference": current - target,
                      "exceeds_display_number": current > target,
                      "exceeds_display_plus_0_005": current > target + 0.005}
        pairs = []
        for case, row in reference.items():
            if row[f"k{k}"] == "":
                continue
            shown = float(row[f"k{k}"])
            assert shown > 0 and math.isfinite(shown)
            actual = cells[(case, k)]
            delta = actual - shown
            pairs.append((actual, shown, delta))
            gaps.append({"case_id": case, "cores": k, "current_fixed_run": actual,
                         "screenshot_display": shown, "numeric_difference": delta})
        figure2[k] = {"transcribed_cells": len(pairs),
                      "current_full100_mean": current,
                      "mean_of_transcribed_display_values": mean(p[1] for p in pairs) if pairs else None,
                      "current_above_display_plus_0_005": sum(p[2] > 0.005 for p in pairs),
                      "current_below_display_minus_0_005": sum(p[2] < -0.005 for p in pairs),
                      "within_0_005_of_display": sum(abs(p[2]) <= 0.005 for p in pairs)}
    summary = {"schema": "q3-display-reference-comparison-v1", "solver_commit": SOURCE,
               "run_id": RUN, "snapshot_as_of": snapshot["as_of"],
               "snapshot_sha256": hashlib.sha256(SNAPSHOT.read_bytes()).hexdigest(),
               "reference_csv_sha256": hashlib.sha256((HERE / "reference-image-2.csv").read_bytes()).hexdigest(),
               "figure1": figure1, "figure2": figure2,
               "largest_numeric_deficits": sorted([g for g in gaps if g["numeric_difference"] < -0.005],
                                                    key=lambda g: g["numeric_difference"])[:20],
               "scope": "One existing fixed solver snapshot, all 500 identities checked; no new result blobs rehashed or evaluator run. Screenshot scenario, baseline, source and rounding policy unverified. +/-0.005 is a sensitivity band, not an asserted rounding rule. Numeric comparison is not certified algorithm dominance.",
               "calls": {"Task": 0, "E0": 0, "solver": 0},
               "historical_winner_selection": False}
    (HERE / "comparison.json").write_text(json.dumps(summary, ensure_ascii=False, indent=2) + "\n")
    with (HERE / "numeric-differences.csv").open("w", newline="") as stream:
        writer = csv.DictWriter(stream, fieldnames=list(gaps[0]), lineterminator="\n")
        writer.writeheader()
        writer.writerows(gaps)
    print(json.dumps({"figure1": figure1, "figure2": figure2}, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
