"""One-shot, read-only 005/K5 plan-quotient audit. No official module is imported."""
from __future__ import annotations

from collections import defaultdict, deque
from hashlib import sha256
import gzip
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[4]
OUT = Path(__file__).resolve().parent
FILES = {
    "graph": ("data/raw/a/official/data/case_005.json", "c2b378c882a3039e3d66bac6cbcba39317107339b6f38d5bce1b09379839799f"),
    "plan": ("results/a/q3-nikolastarx/layered-one-shot-20260925/candidate/case_005_multicore_res.json", "2885b28a512598e4bae525c7bf4b214ac9b2452de19425603fcdea2ae8e7038a"),
    "prepared": ("results/a/q3-nikolastarx/layered-one-shot-20260925/run/prepared.json.gz", "91c9e4ff2995d091922f7ae1b0975de98174a9487a1d0458a05c60535beb5c44"),
    "trace": ("results/a/q3-nikolastarx/layered-one-shot-20260925/run/p3.json.gz", "3c51fac6f14a7c2fdafad3eef6694fb8f38d473e00534c25cd4dadff13cfa0d8"),
    "step1_source": ("data/raw/a/official/code/schedule_step1.py", "d8fe721ff3dbe036e34a20c00cce6430960860000a49eb467e63465f76b84034"),
    "p3_source": ("data/raw/a/official/code/multicore_cut_evaluate_problem_3.py", "eab1504dead881f4b67c0f0498cbc2dbbd9039dc3c9d198c6af58773c127eeb0"),
}
TARGETS = (1000000048, 1000001471)  # fixed trace keys, not a case-selection rule


def read(name):
    rel, expected = FILES[name]
    path = ROOT / rel
    raw = path.read_bytes()
    actual = sha256(raw).hexdigest()
    if actual != expected:
        raise RuntimeError(f"frozen {name} SHA differs: {actual}")
    if name in ("step1_source", "p3_source"):
        return raw
    return json.loads(gzip.decompress(raw) if path.suffix == ".gz" else raw)


def acyclic(nodes, arcs):
    succ = {u: set() for u in nodes}
    indeg = dict.fromkeys(nodes, 0)
    for u, v in arcs:
        if u != v and v not in succ[u]:
            succ[u].add(v)
            indeg[v] += 1
    q = deque(u for u in nodes if indeg[u] == 0)
    seen = 0
    while q:
        u = q.popleft()
        seen += 1
        for v in succ[u]:
            indeg[v] -= 1
            if indeg[v] == 0:
                q.append(v)
    return seen == len(nodes), seen, len(nodes)


def main():
    graph, plan, prep, trace = (read(k) for k in ("graph", "plan", "prepared", "trace"))
    read("step1_source")
    read("p3_source")
    ops = {o["id"]: o for o in graph["ops"]}
    tensors = {t["id"]: t for t in graph["tensors"]}
    compute = {u for u, o in ops.items() if not o["op"].startswith("COPY")}
    prod, cons, direct = defaultdict(set), defaultdict(set), []
    for e in graph["edges"]:
        u, v = e["source"], e["target"]
        if u in ops and v in tensors:
            prod[v].add(u)
        elif u in tensors and v in ops:
            cons[u].add(v)
        elif u in ops and v in ops:
            direct.append((u, v))
        else:
            raise RuntimeError(f"unrecognized raw edge {e}")
    op_edges = set(direct)
    for tid in tensors:
        op_edges.update((u, v) for u in prod[tid] for v in cons[tid])
    raw_dag = acyclic(set(ops), op_edges)
    if not raw_dag[0]:
        raise RuntimeError("raw op graph cyclic")
    compute_edges = {(u, v) for u, v in op_edges if u in compute and v in compute}
    pred = defaultdict(set)
    for u, v in compute_edges:
        pred[v].add(u)
    mapping = {int(u): sg for u, sg in plan["node_to_subgraph"].items()}
    schedules = plan["core_schedules"]
    if set(mapping) != compute or len(mapping) != len(set(mapping.values())):
        raise RuntimeError("base plan is not singleton complete")
    owner = {sg: c for c, words in enumerate(schedules) for sg in words}
    if set(owner) != set(mapping.values()):
        raise RuntimeError("schedule does not cover subgraphs")
    op_for_sg = {sg: u for u, sg in mapping.items()}

    def ancestors(v):
        got, q = set(), list(pred[v])
        while q:
            u = q.pop()
            if u not in got:
                got.add(u)
                q.extend(pred[u] - got)
        return got

    candidate_map = dict(mapping)
    candidate_sched = [list(w) for w in schedules]
    detail = []
    for tid in TARGETS:
        events = [e for e in trace["cache_events"] if e.get("tensor_id") == tid]
        misses = [e for e in events if e["event"] == "miss"]
        inserts = [e for e in events if e["event"] == "insert"]
        if len(misses) < 2 or not inserts:
            raise RuntimeError(f"target {tid} not repeated cold misses")
        pilot = min(misses, key=lambda e: e["time"])
        c, copy_id = pilot["core_id"], pilot["op_id"]
        task = prep["task_return"][0][str(c)]
        local_out = set(task["out_tids"][str(copy_id)])
        if tid not in local_out:
            raise RuntimeError("trace copy does not produce target tensor")
        consumers = [u for u in compute if owner[mapping[u]] == c and tid in task["in_tids"].get(str(u), [])]
        if len(consumers) != 1:
            raise RuntimeError(f"target {tid} lacks unique pilot consumer: {consumers}")
        target = consumers[0]
        old_sg = mapping[target]
        rank = schedules[c].index(old_sg)
        anc = ancestors(target)
        first_independent = None
        for j in range(rank - 1, -1, -1):
            prior = op_for_sg[schedules[c][j]]
            if prior not in anc:
                first_independent = j
                break
        if first_independent is None:
            raise RuntimeError(f"target {tid} has no earlier independent pilot compute")
        span = schedules[c][first_independent:rank + 1]
        first_sg = span[0]
        for sg in span:
            candidate_map[op_for_sg[sg]] = first_sg
        candidate_sched[c] = [sg for sg in candidate_sched[c] if sg == first_sg or sg not in set(span)]
        detail.append({"tensor_id": tid, "pilot_core": c, "pilot_copy_id": copy_id,
                       "pilot_issue": pilot["time"], "first_insert": inserts[0]["time"],
                       "consumer": target, "old_rank": rank, "first_independent_rank": first_independent,
                       "first_independent_op": op_for_sg[first_sg], "merged_compute_count": len(span),
                       "all_between_after_first_are_ancestors": all(op_for_sg[sg] in anc for sg in span[1:-1]),
                       "prior_immediate_compute_preds": sorted(pred[target]),
                       "old_prepared_copy_index": task["seq"].index(copy_id),
                       "old_prepared_consumer_index": task["seq"].index(target),
                       "raw_step1_relative_order_known": False})
    quot = {(candidate_map[u], candidate_map[v]) for u, v in compute_edges if candidate_map[u] != candidate_map[v]}
    quotient_dag = acyclic(set(candidate_map.values()), quot)
    local_order_ok = True
    for c, words in enumerate(candidate_sched):
        rank = {sg: i for i, sg in enumerate(words)}
        for u, v in compute_edges:
            if owner[mapping[u]] == c and owner[mapping[v]] == c and rank[candidate_map[u]] > rank[candidate_map[v]]:
                local_order_ok = False
    result = {"schema": "one-shot-static-merge-audit-v1", "input_sha256": {k: v[1] for k, v in FILES.items()},
              "raw_ops": len(ops), "raw_edges": len(graph["edges"]), "raw_op_arcs": len(op_edges),
              "raw_op_dag": raw_dag, "compute_ops": len(compute), "compute_arcs": len(compute_edges),
              "target_detail": detail, "candidate_quotient_dag": quotient_dag,
              "candidate_quotient_arcs": len(quot), "candidate_local_order_ok": local_order_ok,
              "limitation": "No original Step1 raw_seq in archived prepared; no official Task/Step called. COPY order inside merged bucket, memory frontier, and runtime effect remain unknown."}
    (OUT / "STATIC_MERGE_AUDIT.json").write_text(json.dumps(result, indent=2) + "\n")
    if quotient_dag[0] and local_order_ok:
        out_plan = {"node_to_subgraph": {str(u): candidate_map[u] for u in sorted(candidate_map)}, "core_schedules": candidate_sched}
        (OUT / "STATIC_CANDIDATE_UNVALIDATED.json").write_text(json.dumps(out_plan, indent=2) + "\n")


if __name__ == "__main__":
    main()
