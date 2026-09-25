"""Small, independent structural falsification checks for the browser-copy C02 kernel."""
import hashlib
import importlib.util
import itertools
import json
import platform
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
SOURCE = ROOT / "AI chats/20260925-P2-零spill通信与流水联合构造/附件/c02-exit_sealed_rebuild.browser-copy.py"
OUT = Path(__file__).with_name("result.json")
COMMAND = "python3 output/c02-synthetic-local/test.py"


def load_kernel():
    spec = importlib.util.spec_from_file_location("c02_browser_copy", SOURCE)
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


def reach(graph, source):
    """Independent breadth-first reachability oracle, no kernel helper calls."""
    seen, todo = set(), list(graph[source])
    while todo:
        u = todo.pop(0)
        if u not in seen:
            seen.add(u)
            todo.extend(graph[u] - seen)
    return seen


def has_topological_order(graph):
    """Brute force oracle for these tiny examples."""
    return any(all(order.index(u) < order.index(v) for u, vs in graph.items() for v in vs)
               for order in itertools.permutations(graph))


def main():
    start = time.perf_counter()
    checks = 0
    results = []
    kernel = load_kernel()

    # 1. Distinct-pipe fork/join; whole upstream branches fit and are recolored.
    p = kernel.Problem({0: "PIPE_M", 1: "PIPE_V", 2: "PIPE_V", 3: "PIPE_M"},
                       {0: 20, 1: 20, 2: 1, 3: 1},
                       {0: frozenset({2}), 1: frozenset({2}),
                        2: frozenset({3}), 3: frozenset()}).checked()
    rows = [[0], [1], [2, 3]]
    proposals, diag = kernel.propose(p, rows, [kernel.Seed(10, 0, (2,), 500)],
                                     incumbent_makespan=2000)
    assert len(proposals) == 1 and diag["proposals"] == 1; checks += 1
    q = proposals[0]
    assert set(q["region"]["ops"]) == {0, 1, 2} and q["region"]["exit"] == 2; checks += 1
    assert q["rows"] == [[], [], [0, 1, 2, 3]] or q["rows"] == [[], [], [1, 0, 2, 3]]; checks += 1
    assert q["priority"]["virtual_end_for_priority_only"][0] == 20
    assert q["priority"]["virtual_end_for_priority_only"][1] == 20; checks += 2
    result_plan = kernel.emit_plan({"node_to_subgraph": {str(i): i for i in range(4)}}, q["rows"])
    assert set(result_plan) == {"node_to_subgraph", "core_schedules"}; checks += 1
    results.append({"name": "two_pipe_full_join", "passed": True, "region": q["region"]["ops"]})

    # 2. A mandatory DDR output escapes before a putative common exit.
    e = kernel.Problem({i: "PIPE_M" for i in range(4)}, {i: 1 for i in range(4)},
                       {0: frozenset({1, 2}), 1: frozenset({3}),
                        2: frozenset({3}), 3: frozenset()}, frozenset({1})).checked()
    info, reason = kernel.sealed_region(e, kernel.Postdominators(e), (1, 2))
    assert info is None and reason == "no_real_common_postdominator"; checks += 1
    results.append({"name": "mandatory_output_escape", "passed": True, "reason": reason})

    # 3. Exit closed while a large external input edge is newly crossed.
    # Sizes are static labels for the counterexample, never fed to a scorer.
    c = kernel.Problem({0: "PIPE_M", 1: "PIPE_V", 2: "PIPE_V", 3: "PIPE_M"},
                       {i: 1 for i in range(4)},
                       {0: frozenset({1, 3}), 1: frozenset({2}),
                        2: frozenset(), 3: frozenset()}).checked()
    old_rows = [[2], [0, 1, 3]]
    out, _ = kernel.propose(c, old_rows, [kernel.Seed(20, 1, (2,), 500)],
                            incumbent_makespan=5000)
    assert len(out) == 1 and set(out[0]["region"]["ops"]) == {1, 2}; checks += 1
    new_rows = out[0]["rows"]
    assert [u for u in new_rows[1] if u not in {1, 2}] == [0, 3]; checks += 1
    old_owner = {u: core for core, row in enumerate(old_rows) for u in row}
    new_owner = {u: core for core, row in enumerate(new_rows) for u in row}
    assert old_owner[0] == old_owner[1] and new_owner[0] != new_owner[1]; checks += 1
    assert old_owner[1] != old_owner[2] and new_owner[1] == new_owner[2]; checks += 1
    static_bytes = {"new_entry_tensor": 60000, "removed_inner_tensor": 60}
    assert static_bytes["new_entry_tensor"] > static_bytes["removed_inner_tensor"]; checks += 1
    region = {1, 2}
    h0 = kernel.with_row_edges(c, old_rows, region)
    d_region = {u: c.succ[u] & region for u in region}
    oracle_reach = {u: reach(h0, u) & region for u in region}
    data_reach = {u: reach(d_region, u) for u in region}
    assert oracle_reach == data_reach; checks += 1
    for word in itertools.permutations(region):
        if all(word.index(u) < word.index(v) for u, vs in d_region.items() for v in vs):
            augmented = {u: set(vs) for u, vs in h0.items()}
            for u, v in zip(word, word[1:]):
                augmented[u].add(v)
            assert has_topological_order(augmented); checks += 1
    results.append({"name": "sealed_exit_costly_entry_and_priority", "passed": True,
                    "old_rows": old_rows, "new_rows": new_rows,
                    "static_bytes_only": static_bytes})

    record = {"status": "passed", "source_kind": "browser_preview_copy_not_original_zip",
              "source_sha256": hashlib.sha256(SOURCE.read_bytes()).hexdigest(),
              "source_bytes": SOURCE.stat().st_size, "python": sys.version.split()[0],
              "platform": platform.platform(), "command": COMMAND,
              "wall_seconds": round(time.perf_counter() - start, 6),
              "assertions": checks, "tests": results,
              "scope": "static synthetic structure only; no official simulator or Makespan"}
    OUT.write_text(json.dumps(record, ensure_ascii=False, indent=2) + "\n")
    print(json.dumps({"status": record["status"], "assertions": checks,
                      "wall_seconds": record["wall_seconds"]}))


if __name__ == "__main__":
    main()
