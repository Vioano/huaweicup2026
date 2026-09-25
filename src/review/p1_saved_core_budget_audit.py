"""Read fixed official artifacts to quantify a prospective idle-core closure.

This is an offline diagnostic, not a new solver score or runtime measurement.
No constructors, Task compilation or evaluator functions are imported/called.
"""
from __future__ import annotations
import argparse
import gzip
import hashlib
import io
import json
from pathlib import Path
import re
import statistics
import subprocess

ROOT = Path(__file__).resolve().parents[2]
DATA_COMMIT = "0e0d7cd327c51cc6ac365e01f4b6a7d2b28f9297"
FEED_PATH = "results/a/q1-unified-v4-full500-20260925-s59/20260924T1952Z-s59ee/board-feed-500.json"
FEED_SHA = "4cd79828999ad56dc00d34a79cc0dcd921fff783e5aaf793b0c84924b0f10764"
SOLVER = "a0537aeb72dc702af86d67d3194587d581ac207c"


def blob(path):
    return subprocess.check_output(["git", "show", f"{DATA_COMMIT}:{path}"], cwd=ROOT)


def audit():
    raw = blob(FEED_PATH)
    assert hashlib.sha256(raw).hexdigest() == FEED_SHA
    rows = json.loads(raw)["records"]
    assert len(rows) == 500
    by = {}
    for row in rows:
        assert row["status"] == "ok" and row["problem"] == "P1"
        assert row["solver_commit"] == SOLVER and row["evaluator"]["route"] == "E0"
        cells = by.setdefault(row["case_id"], {})
        assert row["cores"] not in cells
        cells[row["cores"]] = row
    assert len(by) == 100 and all(set(v) == set(range(1, 6)) for v in by.values())
    baselines = {}
    for case, cells in sorted(by.items()):
        ids = [x["identity"] for x in cells.values()]
        for key in ("graph_sha256", "config_sha256", "official_sha256"):
            assert len({x[key] for x in ids}) == 1
        entry = cells[1]["baseline"]["result"]
        assert all(x["baseline"]["result"] == entry for x in cells.values())
        raw = blob(entry["path"])
        assert hashlib.sha256(raw).hexdigest() == entry["sha256"]
        # Fixed saved schema starts with scene/makespan. Stream through EOF for
        # gzip integrity without materializing the large operation timeline.
        with gzip.GzipFile(fileobj=io.BytesIO(raw)) as f:
            prefix = f.read(1024)
            while f.read(1 << 20):
                pass
        match = re.match(rb'\s*\{\s*"scene"\s*:\s*"A",\s*"makespan"\s*:\s*(\d+)\s*,', prefix)
        assert match
        baselines[case] = dict(makespan=int(match[1]), **entry)
    summaries, selections = [], []
    for budget in range(1, 6):
        old_speeds, closure_speeds, wall_sums = [], [], []
        extra_delta = 0
        cycle_wins = traffic_only_wins = lower_cores = 0
        for case, cells in sorted(by.items()):
            old = cells[budget]
            chosen = min((cells[j] for j in range(1, budget + 1)),
                         key=lambda x: (x["metrics"]["makespan_cycles"],
                                        x["metrics"]["ddr_bytes"], -x["cores"]))
            o, n = old["metrics"], chosen["metrics"]
            base = baselines[case]["makespan"]
            old_speeds.append(base / o["makespan_cycles"])
            closure_speeds.append(base / n["makespan_cycles"])
            wall_sums.append(sum(cells[j]["metrics"]["solver_wall_seconds"] for j in range(1, budget + 1)))
            extra_delta += n["extra_ddr_bytes"] - o["extra_ddr_bytes"]
            cycle_wins += n["makespan_cycles"] < o["makespan_cycles"]
            traffic_only_wins += n["makespan_cycles"] == o["makespan_cycles"] and n["ddr_bytes"] < o["ddr_bytes"]
            lower_cores += chosen["cores"] < budget
            selections.append(dict(case=case, budget=budget, chosen_original_cores=chosen["cores"],
                source_plan_sha256=chosen["identity"]["plan_sha256"], current_plan_sha256=old["identity"]["plan_sha256"],
                current_makespan=o["makespan_cycles"], chosen_original_makespan=n["makespan_cycles"],
                speedup_delta=closure_speeds[-1]-old_speeds[-1],
                extra_ddr_delta=n["extra_ddr_bytes"]-o["extra_ddr_bytes"],
                chosen_constructor=chosen["parameters"]["selected"]))
        summaries.append(dict(budget=budget, cells=100, current_mean=statistics.mean(old_speeds),
            historical_closure_mean_NOT_new_score=statistics.mean(closure_speeds),
            selected_lower_core_count=lower_cores, cycle_improved_count=cycle_wins,
            only_ddr_improved_count=traffic_only_wins, extra_ddr_total_delta=extra_delta,
            sum_old_solver_walls_mean_NOT_new_wall=statistics.mean(wall_sums),
            sum_old_solver_walls_max_NOT_new_wall=max(wall_sums)))
    return dict(kind="saved-official-core-budget-envelope-NOT-new-algorithm-score", data_commit=DATA_COMMIT,
        feed_path=FEED_PATH, feed_sha256=FEED_SHA, solver_source=SOLVER,
        proof_condition="Append empty core schedules only; preserve existing IDs/order/config. New solver must construct and rank online.",
        no_claims=["new official full500", "new solver end-to-end wall", "case-ID routing", "proved global P1 optimum"],
        baselines=baselines, summaries=summaries, selections=selections,
        calls=dict(solver=0, Task=0, response=0, E0=0, E1=0, E2=0))


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    result = audit()
    args.output.parent.mkdir(parents=True, exist_ok=True)
    with args.output.open("x") as f:
        json.dump(result, f, indent=2)
        f.write("\n")
    print(json.dumps(result["summaries"]))

if __name__ == "__main__":
    main()
