"""Read-only analysis of saved 044/K5 and prior 044/K3 results (stdlib only)."""
from collections import Counter, defaultdict
import gzip
from hashlib import sha256
import json
from pathlib import Path
import subprocess
import zipfile

ROOT = Path(__file__).resolve().parents[3]
COMMIT = "9c5f87548cc7588465a638e032993969b5cac891"
CELL = "results/a/q1-unified-v4-full500-20260925-s59/20260924T1952Z-s59ee/cells/044/k5/"
PUBLIC = ROOT / "results/a/p1-shared-full-core-probe-20260925/public"
OUT = Path(__file__).with_name("derived.json")


def digest(b):
    return sha256(b).hexdigest()


def fixed(name):
    b = subprocess.check_output(["git", "show", f"{COMMIT}:{CELL}{name}"], cwd=ROOT)
    return json.loads(gzip.decompress(b) if name.endswith(".gz") else b), digest(b)


def local(name):
    b = (PUBLIC / name).read_bytes()
    return json.loads(gzip.decompress(b) if name.endswith(".gz") else b), digest(b)


def trace_account(trace):
    work, counts = Counter(), Counter()
    for event in trace["traceEvents"]:
        if event.get("ph") == "X" and event.get("cat", "").startswith("PIPE_"):
            key = f"{event['args']['core_id']}:{event['cat']}"
            work[key] += event["dur"]
            counts[key] += 1
    return {"observed_pipe_event_duration_sums": dict(sorted(work.items())),
            "pipe_event_counts": dict(sorted(counts.items())),
            "interpretation": "Event duration sums per Pipe, not core utilization or a critical-path decomposition."}


def plan_account(graph, plan):
    op = {o["id"]: o for o in graph["ops"]}
    compute = {int(k) for k in plan["node_to_subgraph"]}
    tensor = {t["id"]: t for t in graph["tensors"]}
    mapping = {int(u): t for u, t in plan["node_to_subgraph"].items()}
    owner = {t: core for core, order in enumerate(plan["core_schedules"]) for t in order}
    producers, consumers = defaultdict(set), defaultdict(set)
    adjacency = defaultdict(set)
    for edge in graph["edges"]:
        a, b = edge["source"], edge["target"]
        if a in op and b in tensor:
            producers[b].add(a)
        elif a in tensor and b in op:
            consumers[a].add(b)
        elif a in compute and b in compute:
            adjacency[a].add(b)
            adjacency[b].add(a)
    for tid in tensor:
        for a in producers[tid] & compute:
            for b in consumers[tid] & compute:
                adjacency[a].add(b)
                adjacency[b].add(a)
    multiplicity = Counter()
    external = set()
    for tid, t in tensor.items():
        if not (producers[tid] & compute) and (consumers[tid] & compute):
            external.add(tid)
            tasks = {mapping[u] for u in consumers[tid] & compute}
            multiplicity[len(tasks)] += t["size"]
    remaining = set(compute)
    components = []
    while remaining:
        anchor = min(remaining)
        remaining.remove(anchor)
        stack, nodes = [anchor], {anchor}
        while stack:
            u = stack.pop()
            for v in adjacency[u] & remaining:
                remaining.remove(v)
                nodes.add(v)
                stack.append(v)
        work = Counter()
        for u in nodes:
            work[op[u]["pipe"]] += op[u]["cycles"]
        inputs = {tid for tid in external if consumers[tid] & nodes}
        components.append({"anchor": anchor, "ops": len(nodes),
                           "core_counts": dict(sorted(Counter(owner[mapping[u]] for u in nodes).items())),
                           "raw_pipe_work": dict(sorted(work.items())),
                           "external_input_union_bytes": sum(tensor[i]["size"] for i in inputs)})
    return {"core_schedule_lengths": list(map(len, plan["core_schedules"])),
            "compute_component_count": len(components),
            "compute_components": sorted(components, key=lambda c: c["anchor"]),
            "external_compute_input_tensors": len(external),
            "external_unique_bytes": sum(tensor[i]["size"] for i in external),
            "external_bytes_by_task_multiplicity": dict(sorted(multiplicity.items())),
            "external_task_input_bytes": sum(n * size for n, size in multiplicity.items()),
            "external_repeat_bytes_beyond_unique": sum((n - 1) * size for n, size in multiplicity.items())}


def timeline_account(result):
    return [{"core": c["core_id"], "tasks": len(c["tasks"]),
             "task_interval_sum": sum(t["duration"] for t in c["tasks"]),
             "last_task_end": c["tasks"][-1]["end"] if c["tasks"] else None,
             "between_task_gaps": [b["start"] - a["end"] for a, b in zip(c["tasks"], c["tasks"][1:])],
             "task_intervals": [{k: t[k] for k in ("task_id", "start", "end", "duration")}
                                for t in c["tasks"]]}
            for c in result["per_core_timeline"]]


def main():
    if OUT.exists():
        raise FileExistsError(OUT)
    with zipfile.ZipFile(ROOT / "data/raw/a/official-cases.zip") as archive:
        graph_bytes = archive.read("data/case_044.json")
    graph = json.loads(graph_bytes)
    saved = {}
    for name in ("plan.json", "result.json.gz", "trace.json.gz", "run-derived.json"):
        saved[name] = fixed(name)
    prior = {}
    for name in ("plan.json", "result.json.gz", "trace.json.gz", "diagnostics.json"):
        prior[name] = local(name)
    output = {"scope": "Saved artifacts only; no constructor, Task compiler, evaluator, or response call",
              "new_calls": {"constructor": 0, "Task_compiler": 0, "solver": 0,
                            "E0": 0, "E1": 0, "E2": 0, "response": 0},
              "sources": {"v4_commit": COMMIT, "graph_zip_member_sha256": digest(graph_bytes),
                          "v4_objects_sha256": {k: v[1] for k, v in saved.items()},
                          "prior_public_files_sha256": {k: v[1] for k, v in prior.items()}},
              "v4_k5": {"makespan": saved["result.json.gz"][0]["makespan"],
                        "movement": saved["result.json.gz"][0]["data_movement_bytes"],
                        "memory_peak_by_core": saved["result.json.gz"][0]["memory_peak_by_core"],
                        "task_dependency_pairs": saved["result.json.gz"][0]["task_dependencies"],
                        "plan": plan_account(graph, saved["plan.json"][0]),
                        "timeline": timeline_account(saved["result.json.gz"][0]),
                        "trace": trace_account(saved["trace.json.gz"][0])},
              "prior_k3_full_core": {"makespan": prior["result.json.gz"][0]["makespan"],
                                     "movement": prior["result.json.gz"][0]["data_movement_bytes"],
                                     "memory_peak_by_core": prior["result.json.gz"][0]["memory_peak_by_core"],
                                     "plan": plan_account(graph, prior["plan.json"][0]),
                                     "timeline": timeline_account(prior["result.json.gz"][0]),
                                     "trace": trace_account(prior["trace.json.gz"][0])}}
    with OUT.open("x") as f:
        json.dump(output, f, indent=2, sort_keys=True)
        f.write("\n")


if __name__ == "__main__":
    main()
