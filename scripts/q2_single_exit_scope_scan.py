"""Read-only P2 topology scan; no evaluator or scheduling claim."""
from __future__ import annotations

import argparse
import json
import re
import sys
import zipfile
from collections import Counter
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from src.q2_nikolastarx.dag_direct import DAGIndex  # noqa: E402

ZIP = ROOT / "data/raw/a/official-cases.zip"
DEFAULT_OUTPUT = ROOT / "results/a/q2-nikolastarx/single-exit-scope-20260926/summary.json"


def scan_case(name: str, graph: dict) -> dict:
    index = DAGIndex(graph)
    # Index.components are weakly connected components of the contracted compute DAG.
    # A tie is resolved by first occurrence in its deterministic topological order.
    component = max(index.components, key=lambda c: (len(c), sum(index.duration(u) for u in c)))
    members = set(component)
    position = {u: i for i, u in enumerate(component)}
    n = len(component)
    cycles = sum(index.duration(u) for u in component)
    count_delta = [0] * (n + 1)
    bytes_delta = [0] * (n + 1)
    incident_tensors = set()
    for tid, tensor in index.tensors.items():
        producers = index.producers[tid] & members
        consumers = index.consumers[tid] & members
        if producers or consumers:
            incident_tensors.add(tid)
        if producers and consumers:
            # A tensor crosses prefix k iff one producer is before k and one
            # consumer is at/after k. Count the physical tensor ID once.
            first = min(position[u] for u in producers) + 1
            last = max(position[u] for u in consumers)
            if first <= last:
                count_delta[first] += 1
                count_delta[last + 1] -= 1
                bytes_delta[first] += tensor["size"]
                bytes_delta[last + 1] -= tensor["size"]
    denominator = sum(index.tensors[tid]["size"] for tid in incident_tensors)
    prefix_cycles = crossing_count = crossing_bytes = 0
    eligible = one = tiny = both = 0
    minimum_count = minimum_bytes = None
    for k in range(1, n):
        prefix_cycles += index.duration(component[k - 1])
        crossing_count += count_delta[k]
        crossing_bytes += bytes_delta[k]
        if 10 * min(prefix_cycles, cycles - prefix_cycles) < cycles:
            continue
        eligible += 1
        minimum_count = crossing_count if minimum_count is None else min(minimum_count, crossing_count)
        minimum_bytes = crossing_bytes if minimum_bytes is None else min(minimum_bytes, crossing_bytes)
        is_one = crossing_count == 1
        is_tiny = denominator > 0 and 100 * crossing_bytes <= denominator
        one += is_one
        tiny += is_tiny
        both += is_one and is_tiny
    return {
        "case": name.rsplit("/", 1)[-1].removesuffix(".json"),
        "component_count": len(index.components),
        "eligible_ops": len(index.ops),
        "max_component_ops": n,
        "max_component_cycles": cycles,
        "incident_tensor_count": len(incident_tensors),
        "incident_tensor_bytes": denominator,
        "nontrivial_prefixes": eligible,
        "minimum_crossing_tensor_count": minimum_count,
        "minimum_crossing_tensor_bytes": minimum_bytes,
        "one_tensor_prefixes": one,
        "one_percent_bytes_prefixes": tiny,
        "both_prefixes": both,
    }


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    args = parser.parse_args()
    with zipfile.ZipFile(ZIP) as archive:
        names = sorted(n for n in archive.namelist() if re.fullmatch(r"data/case_\d{3}\.json", n))
        if len(names) != 100:
            raise ValueError(f"expected 100 official graphs, found {len(names)}")
        rows = [scan_case(name, json.loads(archive.read(name))) for name in names]

    def covered(key: str, subset: list[dict]) -> int:
        return sum(row[key] > 0 for row in subset)

    by_size = {}
    for threshold in (100, 500, 1000, 5000):
        subset = [row for row in rows if row["max_component_ops"] >= threshold]
        by_size[str(threshold)] = {
            "graphs": len(subset),
            "one_tensor_graphs": covered("one_tensor_prefixes", subset),
            "one_percent_bytes_graphs": covered("one_percent_bytes_prefixes", subset),
            "both_graphs": covered("both_prefixes", subset),
        }
    summary = {
        "scope": "Static topology and physical tensor incidence only; no capacity, priority timing, or official Makespan claim.",
        "input_zip": ZIP.relative_to(ROOT).as_posix(),
        "nontrivial_prefix_definition": "Prefix of deterministic topological order in largest weakly connected contracted compute-DAG component; prefix and suffix each have at least 10% of that component's max(1, cycles) work.",
        "denominator_definition": "Sum of size over distinct physical tensor IDs with at least one eligible producer or consumer in the selected component.",
        "graph_count": len(rows),
        "coverage": {
            "nontrivial_prefix_graphs": covered("nontrivial_prefixes", rows),
            "one_tensor_graphs": covered("one_tensor_prefixes", rows),
            "one_percent_bytes_graphs": covered("one_percent_bytes_prefixes", rows),
            "both_graphs": covered("both_prefixes", rows),
        },
        "by_max_component_ops_at_least": by_size,
        "minimum_crossing_count_histogram": dict(sorted(Counter(str(r["minimum_crossing_tensor_count"]) for r in rows).items(), key=lambda x: int(x[0]))),
        "cases": rows,
    }
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(summary, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({"coverage": summary["coverage"], "by_size": by_size}, ensure_ascii=False))


if __name__ == "__main__":
    main()
