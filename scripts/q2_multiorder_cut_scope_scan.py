"""Static P2 prefix-cut scope under three deterministic topological orders."""
from __future__ import annotations

import hashlib
import heapq
import json
import re
import sys
import zipfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from src.q2_nikolastarx.dag_direct import DAGIndex  # noqa: E402

ZIP = ROOT / "data/raw/a/official-cases.zip"
OUT = ROOT / "results/a/q2-nikolastarx/multiorder-cut-scope-20260926/summary.json"
MODES = ("existing", "longest_tail_first", "shortest_tail_first")


def order_for(index, component, mode):
    if mode == "existing":
        return component
    members = set(component)
    degree = {u: len(index.pred[u] & members) for u in component}
    sign = -1 if mode == "longest_tail_first" else 1
    ready = [(sign * index.tail[u], u) for u, d in degree.items() if not d]
    heapq.heapify(ready)
    result = []
    while ready:
        _, u = heapq.heappop(ready)
        result.append(u)
        for v in index.succ[u] & members:
            degree[v] -= 1
            if degree[v] == 0:
                heapq.heappush(ready, (sign * index.tail[v], v))
    if len(result) != len(component):
        raise ValueError("topological order incomplete")
    return result


def scan_order(index, component, mode, internal):
    order = order_for(index, component, mode)
    pos = {u: i for i, u in enumerate(order)}
    n = len(order)
    count_delta = [0] * (n + 1)
    byte_delta = [0] * (n + 1)
    denominator = sum(index.tensors[t]["size"] for t in internal)
    for tid, (producers, consumers) in internal.items():
        first = min(pos[u] for u in producers) + 1
        last = max(pos[u] for u in consumers)
        if first <= last:
            count_delta[first] += 1
            count_delta[last + 1] -= 1
            size = index.tensors[tid]["size"]
            byte_delta[first] += size
            byte_delta[last + 1] -= size
    total = sum(index.duration(u) for u in order)
    prefix_work = count = bytes_out = 0
    minimum_count = minimum_bytes = None
    eligible = one = four = tiny = 0
    for k in range(1, n):
        prefix_work += index.duration(order[k - 1])
        count += count_delta[k]
        bytes_out += byte_delta[k]
        if min(prefix_work, total - prefix_work) * 10 < total:
            continue
        eligible += 1
        minimum_count = count if minimum_count is None else min(minimum_count, count)
        minimum_bytes = bytes_out if minimum_bytes is None else min(minimum_bytes, bytes_out)
        one += count <= 1
        four += count <= 4
        tiny += denominator > 0 and bytes_out * 100 <= denominator
    return {"eligible_prefixes": eligible, "minimum_crossing_tensors": minimum_count,
            "minimum_crossing_bytes": minimum_bytes, "at_most_one_prefixes": one,
            "at_most_four_prefixes": four, "at_most_one_percent_bytes_prefixes": tiny}


def main():
    rows = []
    with zipfile.ZipFile(ZIP) as archive:
        names = sorted(n for n in archive.namelist() if re.fullmatch(r"data/case_\d{3}\.json", n))
        if len(names) != 100:
            raise ValueError(f"expected 100 graphs, found {len(names)}")
        for name in names:
            index = DAGIndex(json.loads(archive.read(name)))
            component = max(index.components, key=lambda c: (len(c), sum(index.duration(u) for u in c)))
            if len(component) < 1000:
                continue
            members = set(component)
            internal = {tid: (index.producers[tid] & members, index.consumers[tid] & members)
                        for tid in index.tensors if index.producers[tid] & members and index.consumers[tid] & members}
            rows.append({"case": name.rsplit("/", 1)[-1].removesuffix(".json"),
                         "max_component_ops": len(component),
                         "max_component_cycles": sum(index.duration(u) for u in component),
                         "internal_tensor_count": len(internal),
                         "internal_tensor_bytes": sum(index.tensors[t]["size"] for t in internal),
                         "orders": {mode: scan_order(index, component, mode, internal) for mode in MODES}})
    metrics = ("at_most_one_prefixes", "at_most_four_prefixes", "at_most_one_percent_bytes_prefixes")
    coverage = {mode: {m: sum(row["orders"][mode][m] > 0 for row in rows) for m in metrics}
                for mode in MODES}
    coverage["union"] = {m: sum(any(row["orders"][mode][m] > 0 for mode in MODES) for row in rows)
                         for m in metrics}
    summary = {"scope": "Static topology only; three fixed orders are not an exhaustive cut search or an E0 guarantee.",
               "input_zip": ZIP.relative_to(ROOT).as_posix(),
               "input_zip_sha256": hashlib.sha256(ZIP.read_bytes()).hexdigest(),
               "graph_count_in_zip": len(names), "selected_graph_count": len(rows),
               "selection": "Largest weak contracted compute component has at least 1000 eligible operations; ties by cycles then first component.",
               "prefix_rule": "Both prefix and suffix have at least 10% of selected component max(1, cycles) work.",
               "denominator": "Sum size over distinct physical tensor IDs with eligible producer AND consumer in selected component.",
               "order_rules": {"existing": "DAGIndex component order", "longest_tail_first": "ready queue by descending DAGIndex.tail then op ID", "shortest_tail_first": "ready queue by ascending DAGIndex.tail then op ID"},
               "coverage": coverage, "cases": rows}
    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(json.dumps(summary, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({"selected_graph_count": len(rows), "coverage": coverage}))


if __name__ == "__main__":
    main()
