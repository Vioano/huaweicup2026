"""Freeze six structure-diverse C04 candidates without any evaluator calls."""
from __future__ import annotations

import gzip
import hashlib
import json
from pathlib import Path
import sys
import time
import zipfile

ROOT = Path(__file__).absolute().parents[1]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / 'data/raw/a/official/code'))
from evaluation_validation import read_evaluation_config
from multicore_cut_evaluate_problem_2 import read_scene_b_config
from src.q2_nikolastarx.port_packet_adapter import build, _SOURCE
from src.q2_nikolastarx.packets import GraphIndex
from scripts.q2_c04_frozen_pilot import LIMITS

OUT = ROOT / 'results/a/q2-nikolastarx/c04-six-pilot-preparation-20260926'
CASES = (5, 16, 19, 25, 39, 75)


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def dump(path, value):
    path.write_text(json.dumps(value, ensure_ascii=False, indent=2, allow_nan=False) + '\n')


def shape(graph):
    ix = GraphIndex(graph)
    unseen = set(ix.ops)
    components = []
    while unseen:
        stack, count = [unseen.pop()], 0
        while stack:
            u = stack.pop()
            count += 1
            for v in ix.preds[u] | ix.succs[u]:
                if v in unseen:
                    unseen.remove(v)
                    stack.append(v)
        components.append(count)
    return {'eligible_ops': len(ix.ops), 'weak_components': len(components),
            'largest_component_ops': max(components),
            'join_ops': sum(len(ix.preds[u]) > 1 for u in ix.ops),
            'fork_ops': sum(len(ix.succs[u]) > 1 for u in ix.ops)}


def main():
    OUT.mkdir(parents=True, exist_ok=False)
    config_path = ROOT / 'data/raw/a/official/data/config.txt'
    config = {**read_evaluation_config(config_path), **read_scene_b_config(config_path)}
    summary_path = ROOT / 'results/a/q2-nikolastarx/hypergap-full500-audit-20260925/completed-summary.json'
    summary = json.loads(summary_path.read_bytes())
    control = {(int(r['case']), r['cores']): r for r in summary['rows']}
    scan = json.loads((ROOT / 'results/a/q2-nikolastarx/c04-static-scan-20260926/summary.json').read_bytes())
    scan_rows = {(r['case'], r['cores']): r for r in scan['rows']}
    archive_root = ROOT / 'results/a/q2-nikolastarx/hypergap-full500-archive-20260924T233302Z-s8ee'
    candidates = []
    with zipfile.ZipFile(ROOT / 'data/raw/a/official-cases.zip') as archive:
        for number in CASES:
            case = f'{number:03d}'
            raw = archive.read(f'data/case_{case}.json')
            graph = json.loads(raw)
            start = time.perf_counter()
            plan, detail = build(graph, 5, config, width=32)
            wall = time.perf_counter() - start
            canonical = json.dumps(plan, sort_keys=True, separators=(',', ':')).encode()
            assert hashlib.sha256(canonical).hexdigest() == scan_rows[number, 5]['canonical_plan_sha256']
            plan_path = OUT / f'{case}-k5-plan.json'
            plan_path.write_bytes(canonical + b'\n')
            detail_path = OUT / f'{case}-k5-static.json.gz'
            detail_raw = (json.dumps(detail, ensure_ascii=False, indent=2, allow_nan=False) + '\n').encode()
            detail_path.write_bytes(gzip.compress(detail_raw, mtime=0))
            prior = control[number, 5]
            assert hashlib.sha256(raw).hexdigest() == prior['graph_sha256']
            controls = []
            for name, expected in [('plan.json.gz', prior['plan_sha256']),
                                   ('result.json.gz', prior['official']['result_sha256'])]:
                matches = list(archive_root.glob(f'cases-*/{case}-k5/{name}'))
                assert len(matches) == 1
                path = matches[0]
                assert hashlib.sha256(gzip.decompress(path.read_bytes())).hexdigest() == expected
                controls.append({'path': path.relative_to(ROOT).as_posix(), 'sha256': sha(path),
                                 'uncompressed_sha256': expected})
            candidates.append({'case': case, 'cores': 5,
                'plan_path': plan_path.relative_to(ROOT).as_posix(), 'plan_sha256': sha(plan_path),
                'static_detail_path': detail_path.relative_to(ROOT).as_posix(),
                'static_detail_sha256': sha(detail_path),
                'canonical_plan_sha256': hashlib.sha256(canonical).hexdigest(),
                'graph_sha256': hashlib.sha256(raw).hexdigest(), 'shape': shape(graph),
                'static_copy_bytes': detail['physical_pre_step2_copy_bytes'],
                'offline_construction_seconds': wall,
                'control_solver_commit': summary['solver_commit'],
                'control_makespan': prior['official']['makespan'],
                'control_movement': prior['official']['movement'], 'control_artifacts': controls})
    files = list((ROOT / 'src/q2_nikolastarx').glob('*.py'))
    files.extend([_SOURCE, ROOT / 'docs/a/source-manifest.json', Path(__file__),
                  ROOT / 'scripts/q2_c04_static_scan.py', summary_path])
    doc = {'scope': 'c04-six-frozen-plans', 'limits': LIMITS,
           'width': 32, 'candidates': candidates,
           'output_path': 'output/c04-six-e0-run-20260926',
           'config_sha256': sha(config_path),
           'official_zip_sha256': sha(ROOT / 'data/raw/a/official-cases.zip'),
           'source_sha256': {p.relative_to(ROOT).as_posix(): sha(p) for p in sorted(files)},
           'selection': 'Targeted mechanism falsification, not a holdout: 005/016 large connected DAG controls; 019 fragmented graph; 025 small repeated components; 039 reduction trees; 075 connected DAG with large static COPY savings. Static savings do not predict Makespan.',
           'timing_scope': 'Construction is offline and measured in-process. It is not cold solver wall or a final algorithm benchmark.',
           'promotion': 'Require valid E0 and matching zero-spill/COPY ledgers, plus Makespan wins in at least two distinct structure classes. Quality losses are retained. Only then consider a frozen online incumbent+C04 selector and separate full500 gate; otherwise stop C04 and prepare paper from completed c665.'}
    dump(OUT / 'manifest.json', doc)
    print(json.dumps({'output': OUT.relative_to(ROOT).as_posix(), 'cells': len(candidates),
                      'E0': 0, 'E1': 0, 'E2': 0, 'manifest_sha256': sha(OUT / 'manifest.json')}))


if __name__ == '__main__':
    main()
