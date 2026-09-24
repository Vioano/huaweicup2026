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
},)


def member_row(row, spec):
    """Allow only the original attempt for its declared shard and coordinate."""
    if row.get('problem') != spec['problem'] or row.get('algorithm_id') != spec['algorithm_id']:
        return False
    if row.get('solver_commit') != spec['solver_commit'] or row.get('revision') != 1:
        return False
    case, cores = row.get('case_id'), row.get('cores')
    if not isinstance(case, str) or len(case) != 3 or not case.isdecimal() or type(cores) is not int or cores not in range(1, 6):
        return False
    for run_id, first, last in spec['members']:
        if first <= int(case) <= last:
            return row.get('run_id') == run_id and row.get('attempt_id') == f'{run_id}-p2-{case}-k{cores}'
    return False


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
    return record_ids_digest(rows) == spec['record_ids_sha256']
