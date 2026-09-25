"""Read-only audit of official P3 cache events for case 044.

Run from the repository root: python3 results/a/q3-nikolastarx/prefix-cache-critical-audit-20260925/analyze_cache.py
This script reads archived official outputs; it never invokes an evaluator.
"""

import collections
import gzip
import hashlib
import json
from pathlib import Path


ROOT = Path(__file__).resolve().parents[4]
BASE = ROOT / "results/a/q3-nikolastarx"
SOURCES = {
    "prefix": BASE / "pipeline-prefix-linux-20260925/receipt-public/artifacts/044-result.json.gz",
    "capacity": BASE / "pipeline-capacity-two-shot-20260925/evaluation/044/result.json.gz",
}
OFFICIAL = ROOT / "data/raw/a/official/code/multicore_cut_evaluate_problem_3.py"
ARCHIVE = BASE / "pipeline-prefix-linux-20260925/run-local/evidence.tar.gz"


def sha256(path):
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def audit(path):
    with gzip.open(path, "rt") as stream:
        result = json.load(stream)
    events = result["cache_events"]
    accesses = collections.defaultdict(list)
    inserts = []
    for event in events:
        if event["event"] in ("hit", "miss"):
            accesses[event["tensor_id"]].append(event)
        elif event["event"] == "insert":
            inserts.append(event)
        else:
            raise ValueError("unexpected cache event: " + str(event["event"]))
    first_miss = [e for seq in accesses.values() for e in seq[:1] if e["event"] == "miss"]
    repeat_miss = [e for seq in accesses.values() for e in seq[1:] if e["event"] == "miss"]
    repeat_hit = [e for seq in accesses.values() for e in seq[1:] if e["event"] == "hit"]
    first_hit = [e for seq in accesses.values() for e in seq[:1] if e["event"] == "hit"]
    key_sizes = {str(key): seq[0]["size_bytes"] for key, seq in accesses.items()}
    if any(e["size_bytes"] != key_sizes[str(key)] for key, seq in accesses.items() for e in seq):
        raise ValueError("same cache key has inconsistent size")
    summary = {
        "makespan_cycles": result["makespan"],
        "capacity_bytes": result["cache_capacity_bytes"],
        "total_accesses": len(first_miss) + len(repeat_miss) + len(repeat_hit) + len(first_hit),
        "distinct_keys": len(accesses),
        "first_miss_count": len(first_miss),
        "first_miss_bytes": sum(e["size_bytes"] for e in first_miss),
        "repeat_miss_count": len(repeat_miss),
        "repeat_miss_bytes": sum(e["size_bytes"] for e in repeat_miss),
        "repeat_hit_count": len(repeat_hit),
        "repeat_hit_bytes": sum(e["size_bytes"] for e in repeat_hit),
        "first_hit_count": len(first_hit),
        "insert_count": len(inserts),
        "evicted_key_count": sum(len(e["evicted_tensor_ids"]) for e in inserts),
        "unique_key_bytes": sum(key_sizes.values()),
        "unused_capacity_bytes": result["cache_capacity_bytes"] - sum(key_sizes.values()),
        "repeated_keys": sorted(str(k) for k, seq in accesses.items() if len(seq) > 1),
        "official_cache_stats": result["cache_stats"],
    }
    assert summary["first_hit_count"] == 0
    assert summary["first_miss_count"] + summary["repeat_miss_count"] == result["cache_stats"]["copy_in_misses"]
    assert summary["repeat_hit_count"] == result["cache_stats"]["copy_in_hits"]
    assert summary["first_miss_bytes"] + summary["repeat_miss_bytes"] == result["cache_stats"]["miss_bytes"]
    assert summary["repeat_hit_bytes"] == result["cache_stats"]["hit_bytes"]
    return summary, key_sizes


def main():
    audits = {name: audit(path) for name, path in SOURCES.items()}
    prefix, capacity = audits["prefix"], audits["capacity"]
    report = {
        "source_sha256": {str(p.relative_to(ROOT)): sha256(p) for p in [*SOURCES.values(), OFFICIAL, ARCHIVE]},
        "prefix": prefix[0],
        "capacity": capacity[0],
        "same_key_sizes": prefix[1] == capacity[1],
        "makespan_improvement_cycles": capacity[0]["makespan_cycles"] - prefix[0]["makespan_cycles"],
    }
    print(json.dumps(report, indent=2, ensure_ascii=False, sort_keys=True))


if __name__ == "__main__":
    main()
