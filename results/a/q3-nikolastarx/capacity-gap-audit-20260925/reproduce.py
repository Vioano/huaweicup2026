"""Read saved 044 evidence; never call the evaluator or construct a task."""
import gzip
import hashlib
import json
from collections import defaultdict
from pathlib import Path

ROOT = Path(__file__).resolve().parents[4]
RUN = ROOT / "results/a/q3-nikolastarx/pipeline-capacity-two-shot-20260925"
PLAN = RUN / "case_044_multicore_res.json"
RESULT = RUN / "evaluation/044/result.json.gz"
GRAPH = ROOT / "data/raw/a/official/data/case_044.json"
EXPECTED = {
    PLAN: "e959272c4330eb75e524190eadaee382c85263896c82dfc910ecffc31bb40c44",
    RESULT: "506a8d65c65b7bcd2957e2b20f31ba117fb3a244b9c366ff2342c421df626cd5",
}
for path, digest in EXPECTED.items():
    assert hashlib.sha256(path.read_bytes()).hexdigest() == digest
graph = json.loads(GRAPH.read_text())
plan = json.loads(PLAN.read_text())
result = json.loads(gzip.decompress(RESULT.read_bytes()))
ops = {o["id"]: o for o in graph["ops"] if o["op"] not in {"COPY_IN", "COPY_OUT"}}
adj = {u: set() for u in ops}
producers, consumers = defaultdict(set), defaultdict(set)
for edge in graph["edges"]:
    a, b = edge["source"], edge["target"]
    if a in ops and b in ops:
        adj[a].add(b); adj[b].add(a)
    elif a in ops:
        producers[b].add(a)
    elif b in ops:
        consumers[a].add(b)
for tid in producers.keys() & consumers.keys():
    for u in producers[tid]:
        for v in consumers[tid]:
            adj[u].add(v); adj[v].add(u)
remaining, components = set(ops), []
while remaining:
    start = min(remaining)
    remaining.remove(start)
    stack, component = [start], set()
    while stack:
        u = stack.pop()
        component.add(u)
        for v in adj[u] & remaining:
            remaining.remove(v); stack.append(v)
    components.append(component)
components.sort(key=min)
assert len(components) == 11 and all(len(c) == 124 for c in components)
first = components[0]
core_by_sg = {sg: c for c, schedule in enumerate(plan["core_schedules"]) for sg in schedule}
core_by_op = {int(u): core_by_sg[sg] for u, sg in plan["node_to_subgraph"].items()}
windows = []
for core in result["per_core_timeline"]:
    c, timeline = core["core_id"], core["ops"]
    job = [x for x in timeline if x["op_id"] in first and core_by_op[x["op_id"]] == c]
    assert job
    start, end = min(x["start"] for x in job), max(x["end"] for x in job)
    copies = [x for x in timeline if x["op"] == "COPY_IN"]
    windows.append({
        "core": c, "first_job_compute_window": [start, end],
        "window_span_cycles": end - start,
        "copy_in_interval_intersection_cycles": sum(
            max(0, min(end, x["end"]) - max(start, x["start"])) for x in copies),
        "copy_in_reported_duration_wholly_inside": sum(
            x["duration"] for x in copies if start <= x["start"] and x["end"] <= end),
        "copy_in_reported_duration_all": sum(x["duration"] for x in copies),
    })
windows.sort(key=lambda x: x["core"])
last = windows[-1]
final_core = next(x for x in result["per_core_timeline"] if x["core_id"] == last["core"])
first_output = min(x["end"] for x in final_core["ops"]
                   if x["op"] == "COPY_OUT" and x["end"] >= last["first_job_compute_window"][1])
summary = {
    "plan_sha256": EXPECTED[PLAN], "result_sha256": EXPECTED[RESULT],
    "components": len(components), "component_sizes": [len(c) for c in components],
    "first_component_min_op_id": min(first), "windows": windows,
    "first_output_end": first_output, "final_makespan": result["makespan"],
    "tail_after_first_output": result["makespan"] - first_output,
    "duration_definition": "COPY_IN interval intersection measures overlap with each first-job compute window; saved op duration is elapsed op time, not exclusive critical-path contribution",
}
dest = Path(__file__).with_name("summary.json")
dest.write_text(json.dumps(summary, indent=2) + "\n")
print(dest)
