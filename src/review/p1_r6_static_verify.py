"""Independent, stdlib-only readback of R6's saved static witnesses.

No solver, official helper, Task compiler, response model, or evaluator import.
The conceptual X/Y/J groups never become a submission plan.
"""
from __future__ import annotations

import argparse
from collections import Counter, defaultdict, deque
from hashlib import sha256
import json
from pathlib import Path
import zipfile


ROOT = Path(__file__).resolve().parents[2]
ARCHIVE = ROOT / "output/p1-r6-wave-inputs-20260925/p1-r6-wave-inputs-20260925.zip"
WITNESSES = ROOT / "AI chats/P1多Pipe链构造证明/附件/R6_p1_r6_s6607__results__repro__static_cut_audit.json"
OUTPUT = ROOT / "results/a/p1-r6-local-audit-20260925/static-verification.json"
BW = 60
EXPECTED_ARCHIVE_SHA256 = "4924c14414e59bedaa67d880344278099d23936aa3435ab42490c93c622b6d97"
EXPECTED_WITNESSES_SHA256 = "fb99903b7affb72bd949d213ff18766871ccfc028500cacdf95a27f57201ce10"


def require(ok, message):
    if not ok:
        raise AssertionError(message)


def digest(data):
    return sha256(data).hexdigest()


def adjacency(graph):
    """Direct op edges plus producer x consumer through tensors, then COPY paths."""
    op_ids = {o["id"] for o in graph["ops"]}
    compute = {o["id"] for o in graph["ops"] if o["op"] not in ("COPY_IN", "COPY_OUT")}
    full = {u: set() for u in op_ids}
    producers, consumers = defaultdict(set), defaultdict(set)
    for e in graph["edges"]:
        a, b = e["source"], e["target"]
        if a in op_ids and b in op_ids and a != b:
            full[a].add(b)
        elif a in op_ids and b not in op_ids:
            producers[b].add(a)
        elif a not in op_ids and b in op_ids:
            consumers[a].add(b)
    for t, ps in producers.items():
        for u in ps:
            full[u].update(v for v in consumers[t] if v != u)
    succ = {u: set() for u in compute}
    for u in compute:
        pending = list(full[u])
        seen_copy = set()
        while pending:
            v = pending.pop()
            if v in compute:
                if v != u:
                    succ[u].add(v)
            elif v not in seen_copy:
                seen_copy.add(v)
                pending.extend(full[v])
    return compute, succ, producers, consumers


def task_heights(compute, succ, plan):
    mapping = {int(u): t for u, t in plan["node_to_subgraph"].items()}
    require(set(mapping) == compute, "old plan compute coverage")
    schedules = plan["core_schedules"]
    tasks = set(mapping.values())
    listed = [t for order in schedules for t in order]
    require(len(listed) == len(tasks) and set(listed) == tasks, "old Task schedule coverage")
    nexts = {t: set() for t in tasks}
    prevs = {t: set() for t in tasks}
    for u, vs in succ.items():
        a = mapping[u]
        for v in vs:
            b = mapping[v]
            if a != b:
                nexts[a].add(b)
                prevs[b].add(a)
    degree = {t: len(prevs[t]) for t in tasks}
    ready = deque(sorted(t for t, d in degree.items() if not d))
    height = {t: 0 for t in tasks}
    seen = 0
    while ready:
        t = ready.popleft()
        seen += 1
        for v in sorted(nexts[t]):
            height[v] = max(height[v], height[t] + 1)
            degree[v] -= 1
            if degree[v] == 0:
                ready.append(v)
    require(seen == len(tasks), "old data Task graph cycle")
    for core, order in enumerate(schedules):
        hs = [height[t] for t in order]
        require(all(a < b for a, b in zip(hs, hs[1:])), f"core {core} heights not strictly increasing")
        require(len(hs) == len(set(hs)), f"core {core} has two Tasks at one height")
    return mapping, {str(k): v for k, v in sorted(Counter(height.values()).items())}, height, len(tasks)


def boundary_for_touched(tensors, producers, consumers, op_by_id, mapping, groups, old_task):
    """Count only boundary COPYs on T; all other Tasks keep their grouping."""
    touched = [tid for tid in tensors if (producers[tid] | consumers[tid]) & old_task]
    tally = {}
    for tid in touched:
        p, c = producers[tid], consumers[tid]
        eligible_c = {u for u in c if u in mapping}
        original_out = any(op_by_id[u]["op"] == "COPY_OUT" for u in c)
        counts = []
        for group in groups:
            lp, lc = p & group, c & group
            read = bool(lc) and not bool(lp)
            write = bool(lp) and (original_out or not eligible_c or bool(eligible_c - group))
            counts.append((int(read), int(write)))
        tally[tid] = tuple(map(sum, zip(*counts)))
    return tally


def verify_witness(case, graph, plan, audit, mapping, succ, producers, consumers):
    op_by_id = {o["id"]: o for o in graph["ops"]}
    tensors = {t["id"]: t["size"] for t in graph["tensors"]}
    reports = []
    for w in audit["cut_witnesses"]:
        task = w["original_task"]
        old = {u for u, t in mapping.items() if t == task}
        labels = ("export_X", "donor_early_Y", "join_late_J")
        groups = [set(w["parts"][name]["members"]) for name in labels]
        x, y, j = groups
        require(all(groups) and not (x & y or x & j or y & j) and set.union(*groups) == old,
                f"{case}/{task}: X/Y/J nonempty disjoint exact coverage")
        require(w["export_parent"] in x and w["join"] in j, f"{case}/{task}: anchor membership")
        require(len(old) == w["original_task_ops"], f"{case}/{task}: old Task size")
        parts = {u: i for i, group in enumerate(groups) for u in group}
        cross = Counter()
        for u in old:
            for v in succ[u] & old:
                if parts[u] != parts[v]:
                    cross[(parts[u], parts[v])] += 1
        require(set(cross) <= {(0, 2), (1, 2)}, f"{case}/{task}: forbidden local edge {cross}")
        require(cross[(0, 2)] > 0 and cross[(1, 2)] > 0, f"{case}/{task}: missing fork/join interface")
        old_tally = boundary_for_touched(tensors, producers, consumers, op_by_id, mapping, [old], old)
        new_tally = boundary_for_touched(tensors, producers, consumers, op_by_id, mapping, groups, old)
        rows = []
        for tid in sorted(old_tally):
            a, b = old_tally[tid], new_tally[tid]
            delta = (b[0] - a[0], b[1] - a[1])
            if delta != (0, 0):
                size = tensors[tid]
                rows.append({"tensor_id": tid, "old": list(a), "new": list(b),
                             "change": list(delta), "size": size,
                             "copy_byte_change": sum(delta) * size,
                             "service_change": sum(delta) * max(1, (size + BW - 1) // BW)})
        claimed = w["boundary"]
        claimed_rows = {row["tensor_id"]: row for row in claimed["rows"]}
        require({r["tensor_id"] for r in rows} == set(claimed_rows), f"{case}/{task}: changed tensor set")
        for row in rows:
            other = claimed_rows[row["tensor_id"]]
            require(all(row[key] == other[key] for key in row), f"{case}/{task}: tensor row {row['tensor_id']}")
        bytes_delta = sum(r["copy_byte_change"] for r in rows)
        service_delta = sum(r["service_change"] for r in rows)
        require((bytes_delta, service_delta) ==
                (claimed["copy_byte_change"], claimed["service_change"]), f"{case}/{task}: totals")
        reports.append({"original_task": task, "part_sizes": list(map(len, groups)),
                        "local_cross_edges": {"X_to_J": cross[(0, 2)], "Y_to_J": cross[(1, 2)]},
                        "changed_tensors": len(rows), "copy_byte_change": bytes_delta,
                        "service_change": service_delta, "row_agreement": True})
    return reports


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--input-zip", type=Path, default=ARCHIVE)
    parser.add_argument("--witnesses", type=Path, default=WITNESSES)
    parser.add_argument("--output", type=Path, default=OUTPUT)
    args = parser.parse_args()
    require(not args.output.exists(), f"refuse overwrite: {args.output}")
    archive_bytes = args.input_zip.read_bytes()
    audit_bytes = args.witnesses.read_bytes()
    require(digest(archive_bytes) == EXPECTED_ARCHIVE_SHA256, "R6 input archive SHA-256 mismatch")
    require(digest(audit_bytes) == EXPECTED_WITNESSES_SHA256, "R6 witness SHA-256 mismatch")
    author = json.loads(audit_bytes)
    output = {"kind": "independent_stdlib_read_only_R6_static_witness_verification",
              "inputs_sha256": {"archive": digest(archive_bytes), "author_witness": digest(audit_bytes)},
              "call_ledger": {"solver": 0, "Task_compiler": 0, "response": 0, "E0": 0, "E1": 0, "E2": 0},
              "scope": "Original graph + old plan; contracted dependencies, old data Task heights, five X/Y/J memberships and local boundary-COPY deltas. No new plan, Task compilation, spill, or timing prediction.",
              "cases": {}}
    with zipfile.ZipFile(args.input_zip) as z:
        manifest = json.loads(z.read("MANIFEST.json"))
        files = {x["path"]: x for x in manifest["files"]}
        for case in ("005", "085"):
            gp, pp = f"data/case_{case}.json", f"v4/{case}/plan.json"
            gb, pb = z.read(gp), z.read(pp)
            for path, data in ((gp, gb), (pp, pb)):
                require(len(data) == files[path]["bytes"] and digest(data) == files[path]["sha256"],
                        f"{case}: archive manifest mismatch {path}")
            graph, plan = json.loads(gb), json.loads(pb)
            require(digest(gb) == author[case]["graph_sha256"], f"{case}: graph witness hash")
            require(digest(pb) == author[case]["old_plan_sha256"], f"{case}: old plan witness hash")
            compute, succ, producers, consumers = adjacency(graph)
            mapping, counts, heights, n_task = task_heights(compute, succ, plan)
            require(counts == author[case]["old_data_task_dag_height_counts"], f"{case}: height counts")
            require(n_task == author[case]["old_task_count"], f"{case}: Task count")
            reports = verify_witness(case, graph, plan, author[case], mapping, succ, producers, consumers)
            expected = (26500, 457) if case == "005" else (95876, 1626)
            require(len(reports) == (2 if case == "005" else 3), f"{case}: witness count")
            require(all((w["copy_byte_change"], w["service_change"]) == expected for w in reports),
                    f"{case}: expected per-cut delta")
            output["cases"][case] = {"graph_sha256": digest(gb), "old_plan_sha256": digest(pb),
                                      "compute_ops": len(compute), "old_tasks": n_task,
                                      "old_data_task_height_counts": counts,
                                      "all_core_orders_strictly_increasing_height": True,
                                      "at_most_one_task_per_core_height": True,
                                      "witnesses": reports}
    args.output.parent.mkdir(parents=True, exist_ok=True)
    with args.output.open("x", encoding="utf-8") as f:
        json.dump(output, f, ensure_ascii=False, indent=2, sort_keys=True)
        f.write("\n")


if __name__ == "__main__":
    main()
