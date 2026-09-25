"""Exact arithmetic on archived evidence; no evaluator, constructor, or simulator."""
from fractions import Fraction
from pathlib import Path
import csv
import hashlib
import json

ROOT = Path(__file__).resolve().parents[4]
BASE = ROOT / "results/a/q3-nikolastarx"
SOURCE = "311322b996c0948e8a6a9c7ec6ddfe6ae41fbee1"


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def value(number):
    return {"exact": str(number), "decimal": float(number)}


def main():
    snapshot_path = BASE / "forest-current-headroom-20260925/cells-snapshot.json"
    identity_path = BASE / "forest-current-headroom-20260925/summary.json"
    bounds_path = BASE / "global-bounds-20260925/bounds.csv"
    static_path = BASE / "query-flow-static-repair-20260925/run/summary.json"
    identities = json.loads(identity_path.read_text())
    assert sha(snapshot_path) == identities["selected_cells_snapshot_sha256"]
    assert sha(bounds_path) == identities["bound_csv_sha256"]
    snapshot = json.loads(snapshot_path.read_text())
    cells = {c["case_id"]: c["best"] for c in snapshot["cells"] if c["cores"] == 5}
    assert set(cells) == {f"{i:03}" for i in range(1, 101)}
    with bounds_path.open() as stream:
        baselines = {r["case_id"]: r for r in csv.DictReader(stream) if r["cores"] == "5"}
    current = Fraction(0)
    for case, record in cells.items():
        b = baselines[case]
        assert record["solver_commit"] == SOURCE and record["eligible"] and record["baseline_verified"]
        assert b["graph_sha256"] == record["identity"]["graph_sha256"]
        assert b["baseline_result_sha256"] == record["baseline"]["result"]["sha256"]
        current += Fraction(b["official_baseline_cycles"]) / Fraction(str(record["metrics"]["makespan_cycles"])) / 100
    static = json.loads(static_path.read_text())
    increment = Fraction(0)
    rows = []
    for candidate in static["rows"]:
        case = candidate["case"]
        assert case in {"071", "069"} and candidate["cores"] == 5
        record = cells[case]
        graph_path = f"data/raw/a/official/data/case_{case}.json"
        assert static["source_input_sha256"][graph_path] == record["identity"]["graph_sha256"]
        assert static["official_code_sha256"] == record["identity"]["official_sha256"]
        assert static["source_input_sha256"]["data/raw/a/official/data/config.txt"] == record["identity"]["config_sha256"]
        plan = static_path.parent / f"case_{case}_multicore_res.json"
        bound_path = static_path.parent / f"{case}-bound.json"
        assert sha(plan) == candidate["plan_sha256"]
        bound = json.loads(bound_path.read_text())
        lower = Fraction(bound["with_cross_core_delay"]["lower_bound_cycles"])
        assert lower == candidate["compute_bound"]
        b = Fraction(baselines[case]["official_baseline_cycles"])
        old = Fraction(str(record["metrics"]["makespan_cycles"]))
        delta = max(Fraction(0), b / lower - b / old) / 100
        increment += delta
        rows.append({"case": case, "B": value(b), "old_M": value(old),
                     "fixed_plan_lower_bound": value(lower), "plan_sha256": sha(plan),
                     "bound_sha256": sha(bound_path), "maximum_mean_increment": value(delta)})
    assert len(rows) == 2
    result = {
        "scope": "Only replace 071/K5 and 069/K5 by these exact R8 plans; keep other 98 plans. Conditional on legality and the archived fixed-plan lower-bound proof. Not an official new batch or global optimum bound.",
        "source_algorithm": SOURCE,
        "current_full_mean": value(current),
        "mean_gap_to_five": value(5 - current),
        "optimistic_increment": value(increment),
        "optimistic_new_mean_cap": value(current + increment),
        "can_only_these_two_plans_cross_five": current + increment > 5,
        "cases": rows,
        "new_calls": {"E0": 0, "E1": 0, "E2": 0, "Task": 0, "construct": 0, "pipe_bound": 0},
        "inputs": {str(p.relative_to(ROOT)): sha(p) for p in (snapshot_path, identity_path, bounds_path, static_path)},
        "script_sha256": sha(Path(__file__)),
    }
    destination = Path(__file__).with_name("result.json")
    with destination.open("x") as stream:
        json.dump(result, stream, ensure_ascii=False, indent=2)
        stream.write("\n")
    print(json.dumps({k: result[k] for k in ("current_full_mean", "optimistic_increment", "optimistic_new_mean_cap", "can_only_these_two_plans_cross_five")}))


if __name__ == "__main__":
    main()
