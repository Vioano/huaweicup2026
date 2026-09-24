"""Replay preserved official FIFO Cache events; do not run an evaluator.

Classifications describe the observed trace, not avoidable traffic or predicted
Makespan gains. In particular, delaying a duplicate read can hurt parallelism.
"""
from __future__ import annotations

import argparse
from collections import Counter, OrderedDict, defaultdict
import csv
import gzip
import hashlib
import heapq
import json
from pathlib import Path


MISS_KINDS = ("oversize", "first_access", "miss_in_flight", "after_eviction")


def require(condition, message):
    if not condition:
        raise ValueError(message)


def analyze(result):
    require(result.get("problem") == 3 and result.get("cache_mode") == "read_only",
            "requires official P3 read-only result")
    capacity = result["cache_capacity_bytes"]
    entries = [(core["core_id"], op) for core in result["per_core_timeline"]
               for op in core["ops"]]
    timeline = {(core, op["op_id"]): op for core, op in entries}
    require(len(entries) == len(timeline), "duplicate timeline operation key")
    resident = OrderedDict()
    accessed, inserted, seen_ops = set(), set(), set()
    pending = defaultdict(list)
    bytes_by_kind, count_by_kind = Counter(), Counter()
    used = 0
    evictions = reinsertions = zero_insert_binding_unavailable = 0
    previous_time = -1
    for event in result["cache_events"]:
        now, kind, tid, size = (event[k] for k in
                                ("time", "event", "tensor_id", "size_bytes"))
        require(now >= previous_time, "cache event time moved backwards")
        previous_time = now
        op_key = event["core_id"], event["op_id"]
        op = timeline[op_key]
        zero_key_omitted = (kind == "insert" and size == 0 and
                            "cache_tensor_id" not in op)
        require(op["op"] == "COPY_IN" and
                (zero_key_omitted or op.get("cache_tensor_id") == tid),
                "cache event/timeline binding mismatch")
        zero_insert_binding_unavailable += zero_key_omitted
        if kind == "insert":
            require(op["end"] == now, "insertion is not at COPY_IN completion")
            require(tid not in resident and 0 <= size <= capacity,
                    "invalid insertion")
            expected_evictions = []
            while resident and used + size > capacity:
                old, old_size = resident.popitem(last=False)
                used -= old_size
                expected_evictions.append(old)
            require(expected_evictions == event["evicted_tensor_ids"],
                    "eviction order does not match FIFO")
            evictions += len(expected_evictions)
            reinsertions += tid in inserted
            resident[tid] = size
            inserted.add(tid)
            used += size
            require(used == event["used_bytes"], "resident byte count mismatch")
            continue
        require(kind in {"hit", "miss"}, "unknown cache event")
        require(op_key not in seen_ops and op["start"] == now and size > 0,
                "duplicate or incorrectly timed access event")
        seen_ops.add(op_key)
        require((kind == "hit") == (tid in resident), "hit/miss residency mismatch")
        require(op["cache_hit"] == (kind == "hit"), "timeline hit mismatch")
        require(op["memory_path"] == ("CACHE_READ" if kind == "hit" else "DDR"),
                "timeline bandwidth pool mismatch")
        while pending[tid] and pending[tid][0] <= now:
            heapq.heappop(pending[tid])
        if kind == "hit":
            require(resident[tid] == size, "logical tensor changed size")
            label = "hit"
        elif size > capacity:
            label = "oversize"
        elif tid not in accessed:
            label = "first_access"
        elif pending[tid]:
            label = "miss_in_flight"
        else:
            require(tid in inserted, "unexplained cacheable repeat miss")
            label = "after_eviction"
        count_by_kind[label] += 1
        bytes_by_kind[label] += size
        if kind == "miss":
            heapq.heappush(pending[tid], op["end"])
        accessed.add(tid)
    stats = result["cache_stats"]
    require(bytes_by_kind["hit"] == stats["hit_bytes"], "hit bytes mismatch")
    require(sum(bytes_by_kind[k] for k in MISS_KINDS) == stats["miss_bytes"],
            "miss bytes mismatch")
    require(count_by_kind["hit"] == stats["copy_in_hits"], "hit count mismatch")
    require(sum(count_by_kind[k] for k in MISS_KINDS) == stats["copy_in_misses"],
            "miss count mismatch")
    final_entries = [{"tensor_id": tid, "size_bytes": size}
                     for tid, size in resident.items()]
    require(final_entries == result["cache_final_entries"], "final FIFO mismatch")
    require(used == result["cache_used_bytes_final"], "final capacity mismatch")
    return {**{f"{kind}_bytes": bytes_by_kind[kind] for kind in ("hit", *MISS_KINDS)},
            **{f"{kind}_count": count_by_kind[kind] for kind in ("hit", *MISS_KINDS)},
            "fifo_evictions": evictions, "fifo_reinsertions": reinsertions,
            "distinct_read_keys": len(accessed), "distinct_inserted_keys": len(inserted),
            "zero_insert_binding_unavailable_count": zero_insert_binding_unavailable}


def sha(raw):
    return hashlib.sha256(raw).hexdigest()


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("feed", type=Path)
    parser.add_argument("artifact_root", type=Path)
    parser.add_argument("output", type=Path)
    args = parser.parse_args()
    feed_raw = args.feed.read_bytes()
    records = json.loads(feed_raw)["records"]
    identities = {(r["algorithm_id"], r["solver_commit"]) for r in records}
    require(len(identities) == 1, "requires one fixed algorithm/source")
    keys = {(r["case_id"], r["cores"]) for r in records}
    expected = {(f"{i:03}", k) for i in range(1, 101) for k in range(1, 6)}
    require(len(records) == 500 and keys == expected, "requires exact full500 feed")
    require(not args.output.exists(), "output already exists")
    rows = []
    for record in sorted(records, key=lambda r: (r["cores"], r["case_id"])):
        require(record["status"] == "ok" and record["problem"] == "P3", "invalid feed cell")
        reference = record["artifacts"]["result"]
        raw = (args.artifact_root / reference["path"]).read_bytes()
        require(sha(raw) == reference["sha256"], "result hash mismatch")
        result = json.loads(gzip.decompress(raw) if reference["path"].endswith(".gz") else raw)
        require(result["makespan"] == record["metrics"]["makespan_cycles"] and
                result["num_cores"] == record["cores"], "result/feed metrics mismatch")
        rows.append({"case_id": record["case_id"], "cores": record["cores"],
                     "makespan_cycles": result["makespan"],
                     "cache_hit_rate": result["cache_stats"]["hit_rate"],
                     "spill_bytes": result["data_movement_bytes"]["spill_added_copy_bytes"],
                     **analyze(result), "result_path": reference["path"],
                     "result_sha256": reference["sha256"]})
    totals = {}
    for cores in range(1, 6):
        group = [r for r in rows if r["cores"] == cores]
        totals[cores] = {key: sum(r[key] for r in group) for key in group[0]
                         if key.endswith(("_bytes", "_count")) or key.startswith("fifo_")}
        totals[cores]["mean_byte_hit_rate"] = sum(r["cache_hit_rate"] for r in group) / 100
    args.output.mkdir(parents=True)
    with (args.output / "cells.csv").open("w", newline="") as stream:
        writer = csv.DictWriter(stream, fieldnames=list(rows[0]))
        writer.writeheader()
        writer.writerows(rows)
    summary = {"schema": "q3-cache-trace-audit-v1", "algorithm_source": list(identities)[0],
               "feed_sha256": sha(feed_raw), "script_sha256": sha(Path(__file__).read_bytes()),
               "records": len(rows), "evaluation_calls": 0, "totals_by_cores": totals,
               "classification_order": ["hit", *MISS_KINDS],
               "limits": "Observed fixed-plan traces only. Oversize takes priority over other miss causes. A repeat miss with a prior unfinished DDR read is miss_in_flight, even if the key was previously evicted. Byte totals are not cycles saved; events do not prove capacity or read sequencing is the critical path. No P2/P3 speedup inferred."}
    (args.output / "summary.json").write_text(json.dumps(summary, indent=2) + "\n")
    print(json.dumps(summary))


if __name__ == "__main__":
    main()
