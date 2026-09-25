"""Copy and verify the frozen 068/K5 Forest P3/P2 same-plan control.

The central board blob store is read-only input. This program never scores.
"""
from __future__ import annotations

import argparse
import gzip
import hashlib
import json
from pathlib import Path


ROOT = Path(__file__).resolve().parents[4]
HERE = Path(__file__).resolve().parent
SNAPSHOT = ROOT / 'results/a/q3-nikolastarx/forest-current-headroom-20260925/cells-snapshot.json'
PAIR = ROOT / 'results/a/q3-nikolastarx/forest-cachepair-delta-20260925/manifest.json'
EXPECTED = {
    'plan': '955cfb794f0c82641b6d4c1411591c77dafc0458a2c1731184fee809aef16ff1',
    'P3': 'be67f6aad45f80bb5075ac852a85fa25576655e5be1114a1bb31e35dc71a9306',
    'P2': 'e73cee38af3018a2dc3d39a7b03996bfb4f23ff8d6ec4f663eb31f6b0174910d',
}


def digest(raw: bytes) -> str:
    return hashlib.sha256(raw).hexdigest()


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument('--board-blobs', type=Path, required=True)
    args = ap.parse_args()
    board_blobs = args.board_blobs.resolve(strict=True)
    snap = json.loads(SNAPSHOT.read_bytes())
    pair = json.loads(PAIR.read_bytes())
    cell = next(x['best'] for x in snap['cells']
                if x['case_id'] == '068' and x['cores'] == 5)
    row = next(x for x in pair['records']
               if x['case_id'] == '068' and x['cores'] == 5)
    assert cell['run_id'] == 'q3-forest-full500-20260925-s59'
    assert cell['solver_commit'] == '311322b996c0948e8a6a9c7ec6ddfe6ae41fbee1'
    assert cell['status'] == 'ok' and cell['eligible'] is True
    assert row['action'] == 'reuse_existing_p2' and row['same_plan_bytes'] is True
    assert row['forest_plan']['sha256'] == row['c2_plan']['sha256'] == EXPECTED['plan']
    assert row['reused_p2']['source_plan_sha256'] == EXPECTED['plan']
    assert cell['identity']['plan_sha256'] == EXPECTED['plan']
    assert cell['artifacts']['result']['sha256'] == EXPECTED['P3']
    assert row['reused_p2']['sha256'] == EXPECTED['P2']
    assert all(row[k] == cell['identity'][k] for k in
               ('graph_sha256', 'config_sha256', 'official_sha256'))

    target = HERE / 'control'
    target.mkdir(exist_ok=False)
    output = {}
    for kind in ('plan', 'P3', 'P2'):
        sha = EXPECTED[kind]
        blob = (board_blobs / sha).read_bytes()
        assert digest(blob) == sha
        filename = {'plan': 'old_plan.json', 'P3': 'old_p3.json.gz',
                    'P2': 'old_p2.json.gz'}[kind]
        (target / filename).write_bytes(blob)
        source_path = (row['forest_plan']['path'] if kind == 'plan' else
                       row['forest_p3_result'] if kind == 'P3' else
                       row['reused_p2']['path'])
        output[kind] = {'path': str((target / filename).relative_to(ROOT)),
                        'sha256': sha, 'source_path': source_path, 'bytes': len(blob)}
    old_plan = json.loads((target / 'old_plan.json').read_bytes())
    old_p3 = json.loads(gzip.decompress((target / 'old_p3.json.gz').read_bytes()))
    old_p2 = json.loads(gzip.decompress((target / 'old_p2.json.gz').read_bytes()))
    assert set(old_plan) == {'node_to_subgraph', 'core_schedules'}
    assert len(old_plan['core_schedules']) == 5
    assert old_p3['problem'] == 3 and old_p3['num_cores'] == old_p2['num_cores'] == 5
    assert old_p3['makespan'] == cell['metrics']['makespan_cycles'] == 116345
    assert old_p2['makespan'] == row['reused_p2']['historical_no_l2_makespan'] == 131631

    identity = cell['identity']
    control = {
        'schema': 'layered-control-v1', 'case_id': '068', 'cores': 5,
        'source_commit': cell['solver_commit'],
        'source_feed_path': str(SNAPSHOT.relative_to(ROOT)),
        'source_feed_sha256': digest(SNAPSHOT.read_bytes()),
        'pair_manifest_path': str(PAIR.relative_to(ROOT)),
        'pair_manifest_sha256': digest(PAIR.read_bytes()),
        'identity': identity, 'artifacts': output,
        'M3': old_p3['makespan'], 'M2': old_p2['makespan'],
        'pair_evidence': {
            **{k: row[k] for k in ('graph_sha256', 'config_sha256', 'official_sha256')},
            'plan_sha256': EXPECTED['plan'], 'cores': 5, 'route': 'E0',
            'result': {'path': row['reused_p2']['path'], 'sha256': EXPECTED['P2']},
        },
        'source_note': 'Bytes copied from central board blobs; no new official call.',
    }
    (HERE / 'old_control.json').write_text(json.dumps(control, ensure_ascii=False, indent=2) + '\n')
    print(json.dumps({'control_sha256': digest((HERE / 'old_control.json').read_bytes()),
                      'M3': control['M3'], 'M2': control['M2'], 'official_calls': 0}))


if __name__ == '__main__':
    main()
