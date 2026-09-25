"""Explicit read-only collections of existing benchmark attempts.

The collection is a view, never a new run or a second measurement. Its final
fingerprint was calculated from the 500 one-record feeds at the fixed source
commit, using each raw record's canonical SHA-256 ledger ID.
"""
from __future__ import annotations

import hashlib
import json


COMPOSITES = ({
    'id': 'composite:q2-activecore-full500-20260925-s59',
    'label': 'P2 active-core · 四分片原始批次',
    'problem': 'P2',
    'algorithm_id': 'q2-adaptive-budget',
    'solver_commit': '2794ceba93acc1f7fc119154f61082511843d4b3',
    'source_commit': '60afc38b327680fbda0ff10182e3e05a01edd72d',
    'manifest_path': 'results/a/q2-nikolastarx/active-core-full500-20260925-s59/manifest.json',
    'manifest_sha256': '46ca4a4e77271d2051828f4fffa8df2e3cb143d098d1a683f841691efc3824ce',
    'record_ids_sha256': 'c6e658c375bd70fa085fdf737a24fdc7386bf64d729f911f74056ac4e60d2172',
    'members': (
        ('q2-activecore-full500-20260925-s59-s01', 1, 25),
        ('q2-activecore-full500-20260925-s59-s02', 26, 50),
        ('q2-activecore-full500-20260925-s59-s03', 51, 75),
        ('q2-activecore-full500-20260925-s59-s04', 76, 100),
    ),
}, {
    'id': 'composite:q3-r9f-final-full500-20260926-s3172',
    'label': 'P3 R9F · 原400格与缺格100格',
    'problem': 'P3',
    'algorithm_id': 'q3-fifth-core-final-fixed',
    'solver_commit': 'f6fd8153375a7fb64f9af2c8f36c35356fb7d878',
    'source_commit': '2c24a0eec7671abf9745f48b5eea0146b98a5aae',
    'manifest_path': 'results/a/q3-nikolastarx/r9f-final-full500-20260926/COMPOSITE_MANIFEST.json',
    'manifest_sha256': '8e6bca56a9e198154ad6ca6d835a29a1081ae0a736f17bd0935637d0e1df8c96',
    'member_sha256': 'f51adbea55c3cf4a3baf2e4e8c140720eccf122f62be289947c2022ba7a7a59f',
    'record_ids_sha256': 'f9d38c4ac668879541474c52030873ca420dd1f4355289f38b96ad1d260502b2',
    'members': (
        ('q3-r9f-final-full500-20260926-s3172', 1, 80),
        ('q3-r9f-final-full500-completion100-20260926-s3172', 81, 100),
    ),
    # The original run reached 080/k4, then included 082/k4 before its
    # deadline. The second run covered exactly the other 100 coordinates.
    'run_overrides': {
        '080-k5': 'q3-r9f-final-full500-completion100-20260926-s3172',
        '082-k4': 'q3-r9f-final-full500-20260926-s3172',
    },
    'attempt_id_template': '{run_id}-P3-{case_id}-k{cores}-fifth-core-final-fixed',
})


def member_row(row, spec):
    """Allow only the original attempt for its declared shard and coordinate."""
    if row.get('problem') != spec['problem'] or row.get('algorithm_id') != spec['algorithm_id']:
        return False
    if row.get('solver_commit') != spec['solver_commit'] or row.get('revision') != 1:
        return False
    case, cores = row.get('case_id'), row.get('cores')
    if not isinstance(case, str) or len(case) != 3 or not case.isdecimal() or type(cores) is not int or cores not in range(1, 6):
        return False
    run_id = next((run for run, first, last in spec['members'] if first <= int(case) <= last), None)
    run_id = spec.get('run_overrides', {}).get(f'{case}-k{cores}', run_id)
    if run_id is None or row.get('run_id') != run_id:
        return False
    template = spec.get('attempt_id_template', '{run_id}-p2-{case_id}-k{cores}')
    return row.get('attempt_id') == template.format(run_id=run_id, case_id=case, cores=cores)


def record_ids_digest(rows):
    coordinates = sorted([row['case_id'], row['cores'], row['id']] for row in rows)
    data = json.dumps(coordinates, ensure_ascii=False, sort_keys=True,
                      separators=(',', ':'), allow_nan=False).encode()
    return hashlib.sha256(data).hexdigest()


def verified(rows, spec):
    """Require the exact fixed 500 records, with official admitted denominators."""
    if len(rows) != 500 or len({(r['case_id'], r['cores']) for r in rows}) != 500:
        return False
    if not all(member_row(r, spec) and r.get('status') == 'ok' and r.get('eligible')
               and r.get('baseline_verified') and r.get('evaluator', {}).get('route') == 'E0'
               and r.get('baseline', {}).get('route') == 'E0' for r in rows):
        return False
    if spec['problem'] == 'P3' and not all(r.get('cache_pair_verified')
            and (r.get('cache_pair') or {}).get('route') == 'E0' for r in rows):
        return False
    return record_ids_digest(rows) == spec['record_ids_sha256']
