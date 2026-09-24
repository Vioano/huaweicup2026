"""Audit a completed P3 witness feed against fixed calendar and baseline bytes; no scoring."""
from __future__ import annotations

import argparse
import gzip
import hashlib
import json
import math
from pathlib import Path
import statistics
import subprocess

ROOT = Path(__file__).resolve().parents[1]
OLD_COMMIT = "a709f9fcbd423999b8e3a756fd577f8602c5bfa5"
OLD_FEED = "results/a/q3-nikolastarx/calendar-full500-20260925-s59/20260924T1905Z-s59ee/board-feed-500-with-baselines.json"
OLD_SHA = "5e02bdb87619697130e73b62de853c0c477842972f268ef03d3818cb49bd4140"


def sha(raw):
    return hashlib.sha256(raw).hexdigest()


def old_feed():
    raw = subprocess.check_output(["git", "show", f"{OLD_COMMIT}:{OLD_FEED}"], cwd=ROOT)
    if sha(raw) != OLD_SHA:
        raise RuntimeError("fixed calendar feed bytes changed")
    return json.loads(raw)


def percentile(values, q):
    ordered = sorted(values)
    return ordered[max(0, math.ceil(q * len(ordered)) - 1)]


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("feed", type=Path)
    p.add_argument("output", type=Path)
    args = p.parse_args()
    feed_path, out = args.feed.resolve(), args.output.resolve()
    if out.parent != feed_path.parent or out.exists() or not feed_path.is_relative_to(ROOT):
        p.error("input and fresh output must share the result directory")
    raw = feed_path.read_bytes()
    fresh, old = json.loads(raw), old_feed()
    if len(fresh["records"]) != 500 or len(old["records"]) != 500:
        raise RuntimeError("both feeds must cover 500 coordinates")
    a = {(r["case_id"], r["cores"]): r for r in fresh["records"]}
    b = {(r["case_id"], r["cores"]): r for r in old["records"]}
    target = {(f"{i:03d}", k) for i in range(1, 101) for k in range(1, 6)}
    if set(a) != target or set(b) != target:
        raise RuntimeError("coordinate set differs")
    baseline = {}
    for case, _ in sorted(target):
        if case in baseline:
            continue
        ref = a[(case, 1)]["baseline"]["result"]
        stored = ROOT / ref["path"]
        compressed = stored.read_bytes()
        if sha(compressed) != ref["sha256"]:
            raise RuntimeError("baseline artifact hash differs")
        baseline[case] = json.loads(gzip.decompress(compressed))["makespan"]
    result = {
        "scope": "read-only arithmetic from fixed official E0 result and baseline bytes; no new solver/evaluator calls",
        "witness_feed": {"path": feed_path.relative_to(ROOT).as_posix(), "sha256": sha(raw)},
        "calendar_feed": {"commit": OLD_COMMIT, "path": OLD_FEED, "sha256": OLD_SHA},
        "cases": 100,
        "coordinates": 500,
        "by_core": {},
    }
    all_wall = []
    for core in range(1, 6):
        pairs = [(a[(f"{i:03d}", core)], b[(f"{i:03d}", core)]) for i in range(1, 101)]
        if any(x["status"] != "ok" or y["status"] != "ok" for x, y in pairs):
            raise RuntimeError("incomplete comparison")
        speedups = [baseline[x["case_id"]] / x["metrics"]["makespan_cycles"] for x, _ in pairs]
        walls = [x["metrics"]["solver_wall_seconds"] for x, _ in pairs]
        all_wall.extend(walls)
        out_core = {
            "mean_speedup_vs_official_onecore": statistics.mean(speedups),
            "makespan_vs_calendar": {
                "win": sum(x["metrics"]["makespan_cycles"] < y["metrics"]["makespan_cycles"] for x, y in pairs),
                "tie": sum(x["metrics"]["makespan_cycles"] == y["metrics"]["makespan_cycles"] for x, y in pairs),
                "loss": sum(x["metrics"]["makespan_cycles"] > y["metrics"]["makespan_cycles"] for x, y in pairs),
            },
            "mean_solver_wall_seconds": statistics.mean(walls),
            "median_solver_wall_seconds": statistics.median(walls),
            "p95_solver_wall_seconds_nearest_rank": percentile(walls, .95),
            "max_solver_wall_seconds": max(walls),
        }
        for field in ("ddr_bytes", "extra_ddr_bytes", "spill_bytes", "cache_hit_rate"):
            new_values = [x["metrics"][field] for x, _ in pairs]
            old_values = [y["metrics"][field] for _, y in pairs]
            if any(v is None for v in new_values + old_values):
                raise RuntimeError("missing measured side metric " + field)
            out_core[field] = {"mean": statistics.mean(new_values),
                               "vs_calendar_lower": sum(x < y for x, y in zip(new_values, old_values)),
                               "vs_calendar_equal": sum(x == y for x, y in zip(new_values, old_values)),
                               "vs_calendar_higher": sum(x > y for x, y in zip(new_values, old_values))}
        result["by_core"][str(core)] = out_core
    result["all_cores_solver_wall_seconds"] = {
        "mean": statistics.mean(all_wall), "median": statistics.median(all_wall),
        "p95_nearest_rank": percentile(all_wall, .95), "max": max(all_wall)}
    out.write_text(json.dumps(result, ensure_ascii=False, indent=2, allow_nan=False) + "\n")
    print(json.dumps({"audit": out.relative_to(ROOT).as_posix(), "sha256": sha(out.read_bytes()),
                      "mean_speedup_k5": result["by_core"]["5"]["mean_speedup_vs_official_onecore"],
                      "k5_makespan": result["by_core"]["5"]["makespan_vs_calendar"]}))


if __name__ == "__main__":
    main()
