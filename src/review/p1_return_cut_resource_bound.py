"""Resource relaxation of a fixed private-chain return-cut class, not an E0 certificate.

No Task compilation, candidate construction, response simulation, or evaluator.
The mathematical premises and numeric scope are in P1_RETURN_CUT_RESOURCE_BOUND.md.
"""
from __future__ import annotations

import argparse
from fractions import Fraction
import hashlib
import json
from pathlib import Path
import subprocess
import time
import zipfile

from src.q1.capacity_return import author

ROOT = Path(__file__).resolve().parents[2]


def relaxation(a, b, c, d_prefix, d_return, d_whole, counts):
    values = (a, b, c, d_prefix, d_return, d_whole, *counts)
    if not counts or any(type(x) is not int or x < 0 for x in values):
        raise ValueError('nonnegative integer resources and nonempty core counts required')
    if min(a, b, c) < 1:
        raise ValueError('positive compute work required')
    delta = d_prefix + d_return - d_whole
    if delta < 0:
        raise ValueError('cut must not remove mandatory external service')
    total_service, span = sum(counts) * d_whole, a + b + c
    largest = sorted(counts, reverse=True)
    candidates = [Fraction(max(counts) * b), Fraction(max(counts) * (a + c))]
    for m in range(len(counts) + 1):
        candidates.append(Fraction(b * total_service + delta * span * sum(largest[:m]),
                                   b + delta * m))
    continuous = max(candidates)

    def cuts_at(t):
        return [max(0, (n * span - t + b - 1) // b) for n in counts]

    def feasible(t):
        cuts = cuts_at(t)
        return (all(x <= n for x, n in zip(cuts, counts)) and
                max(counts) * b <= t and total_service + delta * sum(cuts) <= t)

    low = max(max(counts) * b, max(counts) * (a + c), total_service)
    high = max(max(counts) * span, total_service)  # zero cuts is resource-feasible
    while low < high:
        middle = (low + high) // 2
        if feasible(middle):
            high = middle
        else:
            low = middle + 1
    assert feasible(low) and (low == 0 or not feasible(low - 1))
    assert continuous <= low
    return dict(continuous_lower_bound=str(continuous), integer_cut_lower_bound=low,
                minimum_required_cut_counts_at_bound=cuts_at(low),
                resource_feasible_at_bound=True, resource_feasible_one_cycle_below=False,
                delta_service_per_cut=delta, whole_service=total_service)


def graph_resources(graph, cores, bandwidth):
    if type(cores) is not int or cores < 1 or type(bandwidth) is not int or bandwidth < 1:
        raise ValueError('positive integer cores and bandwidth required')
    view, chains, _, _, _ = author.recognize(graph)
    eligible = {u for chain in chains for u in chain}
    chain = chains[0]

    def service(nodes):
        members = set(nodes)
        touched = set().union(*(view.in_t[u] | view.out_t[u] for u in members))
        total = 0
        for tid in touched:
            producers = view.producers[tid] & eligible
            consumers = view.consumers[tid] & eligible
            output = any(view.ops[u]['op'] == 'COPY_OUT' for u in view.consumers[tid])
            copy_in = bool(consumers & members) and not (producers & members)
            copy_out = bool(producers & members) and (output or not consumers or consumers - members)
            count = int(bool(copy_in)) + int(bool(copy_out))
            total += count * max(1, (view.tensors[tid]['size'] + bandwidth - 1) // bandwidth)
        return total

    return dict(a=max(1, view.ops[chain[0]]['cycles']),
                b=sum(max(1, view.ops[u]['cycles']) for u in chain[1:-1]),
                c=max(1, view.ops[chain[-1]]['cycles']),
                d_prefix=service(chain[:-1]), d_return=service(chain[-1:]),
                d_whole=service(chain), counts=[len(chains[k::cores]) for k in range(cores)])


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--cases', required=True)
    parser.add_argument('--cores', type=int, required=True)
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args()
    if args.output.exists():
        raise FileExistsError(args.output)
    cases = args.cases.split(',')
    if len(cases) != len(set(cases)) or any(c not in {f'{i:03d}' for i in range(1, 101)} for c in cases):
        raise ValueError('unique official case IDs required')
    start = time.perf_counter()
    digest = lambda raw: hashlib.sha256(raw).hexdigest()
    manifest = json.loads((ROOT / 'docs/a/source-manifest.json').read_text())
    files = {v['path']: v for v in manifest['files']}
    config = (ROOT / 'data/raw/a/official/data/config.txt').read_bytes()
    assert digest(config) == files['data/config.txt']['sha256']
    bandwidth = int(next(line.split()[1] for line in config.decode().splitlines()
                         if line.startswith('bandwidth ')))
    archive = ROOT / manifest['case_archive']['path']
    assert digest(archive.read_bytes()) == manifest['case_archive']['sha256']
    rows = []
    with zipfile.ZipFile(archive) as z:
        for case in cases:
            raw = z.read(f'data/case_{case}.json')
            assert digest(raw) == files[f'data/case_{case}.json']['sha256']
            resources = graph_resources(json.loads(raw), args.cores, bandwidth)
            rows.append(dict(case_id=case, cores=args.cores, graph_sha256=digest(raw),
                             resources=resources, relaxation=relaxation(**resources)))
    result = dict(kind='exact-service return-cut resource relaxation; NOT official E0 optimum certificate',
                  source_commit=subprocess.check_output(['git', 'rev-parse', 'HEAD'], cwd=ROOT, text=True).strip(),
                  script_sha256=digest(Path(__file__).read_bytes()), config_sha256=digest(config),
                  calls=dict(solver=0, Task_compile=0, response=0, E0=0, E1=0, E2=0),
                  rows=rows, metadata_wall_seconds=time.perf_counter() - start)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    with args.output.open('x') as out:
        json.dump(result, out, indent=2)
        out.write('\n')
    print(json.dumps({'rows': len(rows), 'output': str(args.output), 'calls': result['calls']}))


if __name__ == '__main__':
    main()
