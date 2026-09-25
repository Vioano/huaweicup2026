"""Read-only structural prerequisites and conditional bounds; no Task compilation."""
from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
import subprocess
import time
import zipfile

from src.q1.capacity_return import author
from src.review.p1_return_cut_resource_bound import graph_resources
from src.review.p1_two_task_resource_bound import solve

ROOT = Path(__file__).resolve().parents[2]


def audit(case_ids, cores):
    started = time.perf_counter()
    sha = lambda raw: hashlib.sha256(raw).hexdigest()
    manifest = json.loads((ROOT / 'docs/a/source-manifest.json').read_text())
    expected = {r['path']: r['sha256'] for r in manifest['files']}
    config_raw = (ROOT / 'data/raw/a/official/data/config.txt').read_bytes()
    assert sha(config_raw) == expected['data/config.txt']
    config = dict(line.split() for line in config_raw.decode().splitlines()
                  if len(line.split()) == 2 and not line.startswith('#'))
    bandwidth = int(config['bandwidth'])
    gate = int(config['task_same_core_wait_cycles'])
    archive = ROOT / manifest['case_archive']['path']
    assert sha(archive.read_bytes()) == manifest['case_archive']['sha256']
    paths = [Path(__file__), ROOT / 'src/review/p1_two_task_resource_bound.py',
             ROOT / 'src/review/p1_return_cut_resource_bound.py', Path(author.__file__)]
    for name in ('schedule_step1.py', 'schedule_step2.py', 'schedule_step3.py'):
        path = ROOT / 'data/raw/a/official/code' / name
        assert sha(path.read_bytes()) == expected['code/' + name]
        paths.append(path)
    rows = []
    with zipfile.ZipFile(archive) as z:
        for case in case_ids:
            raw = z.read(f'data/case_{case}.json')
            assert sha(raw) == expected[f'data/case_{case}.json']
            graph = json.loads(raw)
            view, chains, _, _, _ = author.recognize(graph)
            bridges = [sorted(view.out_t[c[-2]] & view.in_t[c[-1]]) for c in chains]
            resources = graph_resources(graph, cores, bandwidth)
            condition = all(bridges) and resources['b'] >= resources['a']
            rows.append(dict(case_id=case, cores=cores, graph_sha256=sha(raw),
                             private_homogeneous_recognizer_passed=True,
                             chain_count=len(chains),
                             final_V_to_M_tensor_counts=[len(v) for v in bridges],
                             structural_sufficient_conditions=condition,
                             no_spill='not checked; this remains a conditional bound',
                             resources=resources, gate=gate,
                             two_task_resource_bound=solve(**resources, gate=gate) if condition else None))
    return dict(kind='structural prerequisites and conditional two-Task resource bounds; NOT E0',
                source_commit=subprocess.check_output(['git', 'rev-parse', 'HEAD'], cwd=ROOT, text=True).strip(),
                file_sha256={str(p.relative_to(ROOT)): sha(p.read_bytes()) for p in paths},
                config_sha256=sha(config_raw), official_archive_sha256=manifest['case_archive']['sha256'],
                rows=rows, calls=dict(solver=0, Task_compile=0, response=0, E0=0, E1=0, E2=0),
                metadata_wall_seconds=time.perf_counter() - started)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--cases', required=True)
    parser.add_argument('--cores', required=True, type=int)
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args()
    cases = args.cases.split(',')
    if len(set(cases)) != len(cases) or not all(c in {f'{i:03d}' for i in range(1, 101)} for c in cases):
        raise ValueError('unique official case IDs required')
    if args.output.exists():
        raise FileExistsError(args.output)
    result = audit(cases, args.cores)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    with args.output.open('x') as f:
        json.dump(result, f, indent=2)
        f.write('\n')
    print(json.dumps({'cases': cases, 'output': str(args.output), 'calls': result['calls']}))


if __name__ == '__main__':
    main()
