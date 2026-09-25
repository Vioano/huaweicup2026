"""Research-only R4 memory key contract and bounded synthetic probe.

The release word is adapted from archived Pro R4 ``reuse_prekey.py`` (see
docs/a/P1_MEMORY_KEY_CONTRACT.md). It is not a general graph-isomorphism key.
No evaluator or solver is imported or called here.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import os
from pathlib import Path
import platform
import sys

ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))
FIXTURE_HASHES = {
    "graph.json": "a1d705aac7ee8d9dfc5c864f8ddc76a9a18f1e7594385eb94a859c0aac241cd7",
    "plan.json": "f663fb1c0bd7771354de60a03e57dfa2d9ea6fd5c40594edeac7a52b838e9fe3",
    "reproduce.py": "317fb00214184f11554347f21db7cc6d7276bcb2dd6276f4d21f14d1d5172b2a",
}


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def source_scope(capacity, bandwidth):
    """Reject any drift from the frozen full official code/config manifest."""
    manifest = json.loads((ROOT / "docs/a/source-manifest.json").read_text())
    official = ROOT / "data/raw/a/official"
    listed = {row["path"]: row for row in manifest["files"]
              if row["path"].startswith("code/") or row["path"] == "data/config.txt"}
    actual = {"code/" + p.name for p in (official / "code").glob("*.py")}
    actual.add("data/config.txt")
    if actual != set(listed):
        raise ValueError("official code/config file set differs from frozen manifest")
    hashes = {}
    for relative, row in sorted(listed.items()):
        path = official / relative
        if path.stat().st_size != row["bytes"] or sha(path) != row["sha256"]:
            raise ValueError(f"frozen official source drift: {relative}")
        hashes[relative] = row["sha256"]
    code_word = "".join(f"{p}\t{h}\n" for p, h in hashes.items() if p.startswith("code/"))
    if hashlib.sha256(code_word.encode()).hexdigest() != manifest["official_code_hash"]:
        raise ValueError("official aggregate code hash mismatch")
    # Deliberately process-local: Python set layout may depend on this runtime.
    runtime = (os.getpid(), sys.executable, platform.python_implementation(),
               tuple(sys.version_info[:3]), sys.implementation.cache_tag,
               sys.maxsize, tuple(sys.hash_info), os.environ.get("PYTHONHASHSEED"))
    # Cover imported q1 helpers too, rather than only the direct adapters.
    # No hot reload or concurrent source edits are supported by this contract.
    helper_paths = sorted((ROOT / "src/q1").glob("*.py")) + [
        ROOT / "AI chats/P1多Pipe链构造证明/附件/r1-p1_s6607/p1_phase_cut.py",
        Path(__file__),
    ]
    cache_impl = ROOT / "src/review/p1_memory_response_cache.py"
    if cache_impl.exists():
        helper_paths.append(cache_impl)
    helpers = {str(p.relative_to(ROOT)): sha(p) for p in helper_paths}
    return (tuple(sorted(hashes.items())), tuple(sorted(helpers.items())), runtime,
            tuple(sorted(capacity.items())), bandwidth)


def release_word(view, nodes):
    """R4 word: rank tensor IDs, then keep CPython set traversal unchanged."""
    ns = set(nodes)
    if not ns:
        raise ValueError("empty compute member set")
    tids = sorted(set().union(*(view.in_t[u] | view.out_t[u] for u in ns)))
    rank = {tid: i for i, tid in enumerate(tids)}
    return tuple((tuple(rank[t] for t in set(sorted(view.in_t[u]))),
                  tuple(rank[t] for t in set(sorted(view.out_t[u]))))
                 for u in sorted(ns))


def assert_compute_incidence(view, nodes, prepared):
    """Check actual Step3 compute input/output lists, including their order."""
    for u in sorted(set(nodes)):
        if list(prepared["in_tids"][u]) != sorted(view.in_t[u]):
            raise ValueError(f"actual input incidence differs at compute op {u}")
        if list(prepared["out_tids"][u]) != sorted(view.out_t[u]):
            raise ValueError(f"actual output incidence differs at compute op {u}")


def memory_key(family, nodes, scope, prepared):
    """Usable only after actual official Task compute incidence was checked."""
    nodes = tuple(nodes)
    if scope != source_scope(family.capacity, family.bandwidth):
        raise ValueError("memory key scope is stale or not bound to current sources/runtime")
    assert_compute_incidence(family.view, nodes, prepared)
    return (scope, family.prekey(nodes), release_word(family.view, nodes))


def _compiled(graph, plan, capacity, bandwidth, expected, accounting):
    # The official call compiles expected Tasks. Attempt budget is reserved first.
    from src.q1.response_compile import _official_modules
    from src.q1.compiled_memory_response import _check_original, _task
    scene, plans, step3, validation = _official_modules()
    validation.validate_graph(graph)
    _check_original(graph, capacity)
    view = plans.derive_multicore_plan(graph, plan)
    validation.validate_task_order(view)
    if accounting["task_compile_attempts_reserved"] + expected > 4:
        raise ValueError("four-Task compile budget exceeded")
    accounting["task_compile_attempts_reserved"] += expected
    tasks, _, traffic, _ = scene._build_scene_a_tasks(graph, plan, bandwidth, capacity)
    accounting["task_compiles_confirmed_completed"] += len(tasks)
    if len(tasks) != expected or traffic["spill_added_copy_bytes"]:
        raise ValueError("unexpected Task count or spill in synthetic probe")
    converted = {}
    for task_id, prepared in tasks.items():
        if prepared["step3"].get("execution_contract_validated") is not True:
            raise ValueError("Step3 execution contract was not validated")
        converted[task_id], _ = _task(task_id, prepared, capacity, bandwidth, step3)
    return tasks, converted, traffic


def _fraction(value):
    return str(value)


def execute(fixture_dir, output):
    from src.q1.variable_packet import Family
    from src.q1.response_oracle import quotient, simulate
    from src.q1.response_compile import _official_modules
    from src.q1.packet_dp import _TaskProjection

    files = {name: fixture_dir / name for name in FIXTURE_HASHES}
    if any(not path.is_file() for path in files.values()):
        raise ValueError("local graph.json, plan.json and reproduce.py are required")
    if any(sha(path) != FIXTURE_HASHES[name] for name, path in files.items()):
        raise ValueError("local synthetic fixture hash differs from frozen counterexample")
    graph = json.loads(files["graph.json"].read_text())
    plan = json.loads(files["plan.json"].read_text())
    capacity, bandwidth = {"L1": 80, "UB": 80}, 60  # synthetic, not official capacity
    reproduce = files["reproduce.py"].read_text()
    if ('CAPACITY = {"L1": 80, "UB": 80}' not in reproduce or
            'Family(graph, 1, CAPACITY, 60)' not in reproduce):
        raise ValueError("synthetic fixture capacity/bandwidth source differs")
    scope = source_scope(capacity, bandwidth)
    scene, _, _, _ = _official_modules()
    gate = scene.read_scene_a_config(ROOT / "data/raw/a/official/data/config.txt")[
        "task_same_core_wait_cycles"]
    family = Family(graph, 1, capacity, bandwidth)
    if len(family.chains) != 2 or len(graph["ops"]) != 8:
        raise ValueError("fixture must have exactly two private chains")
    if set(plan["node_to_subgraph"].values()) != {0, 1} or plan["core_schedules"] != [[0, 1]]:
        raise ValueError("fixture must contain the two expected serial Tasks")
    rows = []
    accounting = {"task_compile_attempts_reserved": 0,
                  "task_compiles_confirmed_completed": 0,
                  "fraction_response_attempts": 0,
                  "fraction_responses_completed": 0,
                  "solver": 0, "E0": 0, "E1": 0, "E2": 0}
    try:
        # Two one-Task projections, then one two-Task full original graph.
        for chain_index, nodes in enumerate(family.chains):
            projected = _TaskProjection(graph, family.view).graph(nodes)
            projected_plan = {"node_to_subgraph": {str(u): 0 for u in nodes},
                              "core_schedules": [[0]]}
            prepared, converted, traffic = _compiled(projected, projected_plan, capacity,
                                                     bandwidth, 1, accounting)
            task = converted[0]
            key = memory_key(family, nodes, scope, prepared[0])
            accounting["fraction_response_attempts"] += 1
            response = simulate([[task]], gate)
            accounting["fraction_responses_completed"] += 1
            rows.append({"kind": "projected-chain", "chain": chain_index,
                         "nodes": list(nodes), "key": repr(key),
                         "signature": task.signature(), "traffic": traffic,
                         "rational_makespan": _fraction(response["makespan"])})
        whole_prepared, whole_tasks, traffic = _compiled(
            graph, plan, capacity, bandwidth, 2, accounting)
        for i, nodes in enumerate(family.chains):
            key = memory_key(family, nodes, scope, whole_prepared[i])
            task = whole_tasks[i]
            rows.append({"kind": "whole-task", "chain": i, "nodes": list(nodes),
                         "old_prekey": repr(family.prekey(nodes)), "key": repr(key),
                         "signature": task.signature()})
        accounting["fraction_response_attempts"] += 1
        response = quotient([[whole_tasks[0], whole_tasks[1]]], gate)
        accounting["fraction_responses_completed"] += 1
        whole = rows[2:]
        checks = {"old_prekey_equal": whole[0]["old_prekey"] == whole[1]["old_prekey"],
                  "memory_key_differs": whole[0]["key"] != whole[1]["key"],
                  "raw_signature_differs": whole[0]["signature"] != whole[1]["signature"],
                  "projected_keys_match": all(rows[i]["key"] == whole[i]["key"] for i in (0, 1)),
                  "projected_signatures_match": all(rows[i]["signature"] == whole[i]["signature"] for i in (0, 1))}
        if not all(checks.values()):
            raise ValueError(f"counterexample checks failed: {checks}")
        report = {"status": "success", "kind": "synthetic-contract-only-NOT-E0",
                  "scope": repr(scope), "fixture_sha256": {n: sha(p) for n, p in files.items()},
                  "checks": checks, "rows": rows, "whole_traffic": traffic,
                  "whole_rational_quotient": repr(response), "calls": accounting}
    except Exception as error:
        report = {"status": "failed", "error": f"{type(error).__name__}: {error}",
                  "calls": accounting}
        (output / "report.json").write_text(json.dumps(report, indent=2, default=str))
        raise
    (output / "report.json").write_text(json.dumps(report, indent=2, default=str))


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--fixture-dir", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--execute", action="store_true")
    args = parser.parse_args()
    if not args.execute:
        parser.error("explicit --execute is required; no compilation was started")
    args.output.mkdir(parents=False, exist_ok=False)
    execute(args.fixture_dir, args.output)


if __name__ == "__main__":
    main()
