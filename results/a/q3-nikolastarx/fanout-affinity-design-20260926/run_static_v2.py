"""One-shot frozen static comparison. No official evaluator or Task/Step call."""
import hashlib
import importlib.util
import json
from pathlib import Path
import sys
import traceback

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[3]
OFFICIAL = ROOT / "data/raw/a/official/code"
sys.path[:0] = [str(ROOT), str(OFFICIAL)]

FROZEN = {
    "src/q3/gap_dag.py": "b61b1e33fcddc3491b7c37b12b41f8314d9744909957528296c0684bf57fc219",
    "src/q3/gap_calendar.py": "0a5668036b5f6c651de9e48f726b6bef2264734e4d99cdc1159799269a9878b3",
    "src/q3/construct.py": "942450f2751eb5b0cf4817d392acdd6e4316e751c48ea8e84b509d4ce1e97d73",
    "data/raw/a/official/data/config.txt": "dcd10de54b23f8366428fb24e828812b1da9549e6eae4a3c3f38604fe5ae77b9",
    "data/raw/a/official/data/case_010.json": "fd0b07588473d8b2ce05fab4798808cbc7f60cf1638e05608adc3d62061b8775",
    "data/raw/a/official/data/case_015.json": "d27dfc39289fa442f29f597191ab6b05142ce6ad68b4396056b2adccb9c93253",
    "data/raw/a/official/data/case_065.json": "23342b7c3e75f58cec3d0bdaff89bf8d6f18de4930d35ec2ceade91670f0a400",
}
CASES = ("010", "015", "065")
CORES, BANDWIDTH, CROSS_DELAY = 5, 60, 500


def sha(data):
    return hashlib.sha256(data).hexdigest()


def canonical(data):
    return (json.dumps(data, sort_keys=True, separators=(",", ":")) + "\n").encode()


def boundary_counts(graph, core_by_op):
    eligible = set(core_by_op)
    tids = {t["id"] for t in graph["tensors"]}
    size = {t["id"]: t["size"] for t in graph["tensors"]}
    prod, cons, direct = {}, {}, []
    for edge in graph["edges"]:
        u, v = edge["source"], edge["target"]
        if u in eligible and v in tids:
            prod.setdefault(v, set()).add(core_by_op[u])
        elif u in tids and v in eligible:
            cons.setdefault(u, set()).add(core_by_op[v])
        elif u in eligible and v in eligible and u != v:
            direct.append((u, v, max(0, int(edge.get("data_size", 0)))))
    tensor_pairs = sum(len({(a, b) for a in prod.get(tid, ())
                            for b in cons.get(tid, ()) if a != b}) for tid in tids)
    tensor_bytes = sum(size[tid] * sum(a != b for a in prod.get(tid, ())
                                       for b in cons.get(tid, ())) for tid in tids)
    direct_pairs = sum(core_by_op[u] != core_by_op[v] for u, v, _ in direct)
    direct_bytes = sum(s for u, v, s in direct if core_by_op[u] != core_by_op[v])
    return {"tensor_pairs": tensor_pairs, "direct_pairs": direct_pairs,
            "cross_link_bytes": tensor_bytes + direct_bytes,
            "nominal_inserted_copy_bytes": 2 * (tensor_bytes + direct_bytes)}


def inspect(graph, index, plan, meta, derive):
    view = derive(graph, plan)
    mapping = {int(u): sg for u, sg in plan["node_to_subgraph"].items()}
    core_by_sg = view["core_by_subgraph"]
    core_by_op = {u: core_by_sg[sg] for u, sg in mapping.items()}
    orders = {core: {sg: i for i, sg in enumerate(seq)}
              for core, seq in enumerate(plan["core_schedules"])}
    if set(mapping) != set(index.ops):
        raise ValueError("non-COPY operation coverage mismatch")
    if len(set(mapping.values())) != len(mapping):
        raise ValueError("expected one operation per subgraph")
    dependencies = 0
    for u in index.ops:
        for v in index.succ[u]:
            dependencies += 1
            if core_by_op[u] == core_by_op[v] and (
                orders[core_by_op[u]][mapping[u]] >= orders[core_by_op[v]][mapping[v]]
            ):
                raise ValueError(f"intra-core dependency reversed: {u}->{v}")
    return {"plan_sha256": sha(canonical(plan)), "operations": len(mapping),
            "dependencies_checked": dependencies, "plan_validator": "passed",
            "modeled_compute_finish": meta["modeled_compute_finish"],
            "modeled_cross_chain_edges": meta["cross_chain_edges"],
            **boundary_counts(graph, core_by_op)}


def main():
    for name, expected in FROZEN.items():
        actual = sha((ROOT / name).read_bytes())
        if actual != expected:
            raise ValueError(f"frozen hash mismatch: {name}: {actual}")
    from src.q3.construct import Index, derive_multicore_plan
    from src.q3.gap_dag import construct as original_construct

    spec = importlib.util.spec_from_file_location("gap_dag_affinity_static", HERE / "gap_dag_affinity.py")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    rows = []
    for case in CASES:
        graph = json.loads((ROOT / f"data/raw/a/official/data/case_{case}.json").read_bytes())
        index = Index(graph)
        old_plan, old_meta = original_construct(index, CORES, BANDWIDTH, CROSS_DELAY)
        new_plan, new_meta = module.construct(index, CORES, BANDWIDTH, CROSS_DELAY)
        old = inspect(graph, index, old_plan, old_meta, derive_multicore_plan)
        new = inspect(graph, index, new_plan, new_meta, derive_multicore_plan)
        (HERE / f"case_{case}_old_plan.json").write_bytes(canonical(old_plan))
        (HERE / f"case_{case}_affinity_plan.json").write_bytes(canonical(new_plan))
        rows.append({"case": case, "same_plan": old_plan == new_plan,
                     "old": old, "affinity": new})
        (HERE / "static_v2_results.json").write_bytes(canonical({
            "scope": "one static old/new construction per case, no evaluator",
            "frozen": FROZEN, "cases_complete": len(rows), "rows": rows}))
    print(json.dumps({"cases_complete": len(rows),
                      "changed": [r["case"] for r in rows if not r["same_plan"]]},
                     sort_keys=True))


if __name__ == "__main__":
    try:
        main()
    except BaseException:
        (HERE / "static_v2_failure.txt").write_text(traceback.format_exc())
        raise SystemExit("static v2 stopped on first exception; see static_v2_failure.txt")
