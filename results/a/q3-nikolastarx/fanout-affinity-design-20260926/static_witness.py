"""Frozen, read-only case_010 fanout witness scan; see FREEZE.md."""
import collections
import hashlib
import json
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[4]
INPUTS = (
    (ROOT / "data/raw/a/official/data/case_010.json",
     "fd0b07588473d8b2ce05fab4798808cbc7f60cf1638e05608adc3d62061b8775"),
    (ROOT / "results/a/q3-nikolastarx/gap-probe-20260925/run/cells/010-k5-unified-general-gap-e0/evidence/gap/plan.json",
     "4e9b1c875014bad7800596def5097ffcdcd224d5737ac2d8fdf096bc88af1a89"),
)
objects = []
for path, expected in INPUTS:
    data = path.read_bytes()
    actual = hashlib.sha256(data).hexdigest()
    if actual != expected:
        raise SystemExit(f"input hash mismatch: {path}: {actual}")
    objects.append(json.loads(data))
graph, plan = objects
eligible = {o["id"] for o in graph["ops"] if o["op"] not in ("COPY_IN", "COPY_OUT")}
mapping = {int(o): sg for o, sg in plan["node_to_subgraph"].items()}
if set(mapping) != eligible:
    raise SystemExit("saved plan operation coverage mismatch")
core_by_sg = {sg: core for core, order in enumerate(plan["core_schedules"]) for sg in order}
if len(core_by_sg) != len(mapping):
    raise SystemExit("expected one subgraph per eligible operation")
core = {op: core_by_sg[sg] for op, sg in mapping.items()}
tensor_ids = {t["id"] for t in graph["tensors"]}
producers, consumers = collections.defaultdict(set), collections.defaultdict(set)
for edge in graph["edges"]:
    src, dst = edge["source"], edge["target"]
    if src in eligible and dst in tensor_ids:
        producers[dst].add(src)
    elif src in tensor_ids and dst in eligible:
        consumers[src].add(dst)
choices = []
for tensor in sorted(graph["tensors"], key=lambda t: t["id"]):
    tid = tensor["id"]
    if len(producers[tid]) != 1 or len(consumers[tid]) < 2:
        continue
    producer = next(iter(producers[tid]))
    pcore = core[producer]
    counts = collections.Counter(core[c] for c in consumers[tid])
    remote = {c: n for c, n in counts.items() if c != pcore}
    if not remote:
        continue
    tier = 0 if any(n >= 2 for n in remote.values()) else 1 if len(remote) >= 2 else 2
    choices.append((tier, tid, tensor, producer, pcore, counts, remote))
if not choices:
    raise SystemExit("no qualifying tensor")
tier, tid, tensor, producer, pcore, counts, remote = min(choices)
sys.path.insert(0, str(ROOT))
from src.q3.construct import Index  # validation and contraction, no scheduling
from src.q3.gap_dag import chain_dag
chain_data = chain_dag(Index(graph), 1, 0)
if chain_data is None:
    raise SystemExit("selected graph rejected by existing chain_dag")
chains = chain_data[0]
owner = {op: j for j, chain in enumerate(chains) for op in chain}
print(json.dumps({
    "witness_tier": tier,
    "tensor_id": tid,
    "tensor_size_bytes": tensor["size"],
    "tensor_pos": tensor["pos"],
    "producer_op": producer,
    "producer_core": pcore,
    "consumer_ops_by_core": {str(c): sorted(o for o in consumers[tid] if core[o] == c) for c in sorted(counts)},
    "chain_by_op": {str(o): owner[o] for o in sorted({producer} | consumers[tid])},
    "remote_consumer_edges": sum(remote.values()),
    "distinct_remote_core_pairs": len(remote),
    "distinct_remote_cores": sorted(remote),
}, indent=2))
