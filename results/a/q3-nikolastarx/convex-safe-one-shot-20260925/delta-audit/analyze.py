"""Read-only comparison of the two saved, official P3 operation timelines."""

from collections import defaultdict
from hashlib import sha256
from pathlib import Path
import gzip
import json


ROOT = Path(__file__).resolve().parents[5]
OLD = ROOT / "results/a/q3-nikolastarx/layered-one-shot-20260925/run/p3.json.gz"
NEW = ROOT / "results/a/q3-nikolastarx/convex-safe-one-shot-20260925/run/p3.json.gz"
EXPECTED = {
    OLD: "3c51fac6f14a7c2fdafad3eef6694fb8f38d473e00534c25cd4dadff13cfa0d8",
    NEW: "385b30788297034a655329507f88ea0a3295d3d3d4f383c24f9c4c2952eb2ce0",
}


def load(path):
    assert sha256(path.read_bytes()).hexdigest() == EXPECTED[path]
    with gzip.open(path, "rt") as fh:
        return json.load(fh)


def summarize(result):
    cores = {}
    ops = {}
    for core in result["per_core_timeline"]:
        by_pipe = defaultdict(int)
        records = core["ops"]
        for op in records:
            by_pipe[op["pipe"]] += op["duration"]
            ops[op["op_id"]] = (core["core_id"], op)
        cores[str(core["core_id"])] = {
            "last_end": max(op["end"] for op in records),
            "pipe_busy_cycles": dict(by_pipe),
        }
    return cores, ops


old = load(OLD)
new = load(NEW)
oc, oo = summarize(old)
nc, no = summarize(new)
shared = oo.keys() & no.keys()
delays = sorted(
    (
        (no[i][1]["end"] - oo[i][1]["end"], i, oo[i][0], no[i][0], oo[i][1]["op"],
         oo[i][1]["pipe"], oo[i][1]["end"], no[i][1]["end"])
        for i in shared
    ),
    reverse=True,
)[:15]
out = {
    "source_sha256": {"old": EXPECTED[OLD], "new": EXPECTED[NEW]},
    "makespan": {"old": old["makespan"], "new": new["makespan"]},
    "cache": {"old": old["cache_stats"], "new": new["cache_stats"]},
    "cores": {k: {"old": oc[k], "new": nc[k]} for k in sorted(oc)},
    "op_id_sets": {"old": len(oo), "new": len(no), "shared": len(shared)},
    "largest_matching_op_end_delays": [
        {"delta": d, "op_id": i, "old_core": c0, "new_core": c1,
         "op": op, "pipe": pipe, "old_end": e0, "new_end": e1}
        for d, i, c0, c1, op, pipe, e0, e1 in delays
    ],
}
print(json.dumps(out, ensure_ascii=False, indent=2))
