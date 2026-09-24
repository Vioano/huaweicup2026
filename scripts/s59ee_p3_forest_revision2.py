"""Draft revision 2 baseline evidence from a fixed, already archived E0 source.

This reads existing forest feeds; it never starts a solver or evaluator.
The draft directory is separate from every revision 1 feed and scoring artifact.
"""
from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
import subprocess

ROOT = Path(__file__).resolve().parents[1]
BATCH = ROOT / 'results/a/q3-nikolastarx/forest-full500-20260925-s59/20260924T2122Z-s59ee'
SOURCE_COMMIT = '5228e2e09d05be1d0b9e723439aed6b5885e380b'
SOURCE_FEED = ('results/a/q3-nikolastarx/witness-full500-20260925-s59/'
               '20260924T2032Z-s59ee/board-feed-500-with-baselines.json')
GROUP_RUN = 'q3-forest-full500-20260925-s59'


def fixed_blob(repo: Path, path: str) -> bytes:
    return subprocess.run(['git', '-C', str(repo), 'show', f'{SOURCE_COMMIT}:{path}'],
                          check=True, capture_output=True).stdout


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--baseline-repo', type=Path, required=True,
                        help='Repository containing the fixed witness archive commit')
    parser.add_argument('--draft-dir', type=Path, required=True)
    args = parser.parse_args()
    draft = args.draft_dir.resolve()
    if draft != BATCH / 'revision2-baseline-draft' or draft.exists():
        parser.error('draft must be a fresh revision2-baseline-draft under the fixed batch')
    source = json.loads(fixed_blob(args.baseline_repo, SOURCE_FEED))
    by_case = {}
    for row in source['records']:
        case = row['case_id']
        baseline = row.get('baseline')
        if baseline is None:
            raise ValueError(f'fixed source lacks baseline for {case}')
        if case in by_case and by_case[case] != baseline:
            raise ValueError(f'inconsistent fixed source baseline for {case}')
        by_case[case] = baseline
    if len(by_case) != 100:
        raise ValueError('fixed source must cover 100 unique cases')

    originals = []
    for shard in range(1, 11):
        path = BATCH / f'board-feed-s{shard:02}-50.json'
        feed = json.loads(path.read_text(encoding='utf-8'))
        if len(feed['records']) != 50:
            raise ValueError(f'shard {shard} has incomplete feed')
        originals.append(feed)
    rows = [r for f in originals for r in f['records']]
    if (len(rows) != 500 or len({r['attempt_id'] for r in rows}) != 500
            or len({(r['case_id'], r['cores']) for r in rows}) != 500
            or {r['run_id'] for r in rows} != {GROUP_RUN}
            or any(r['revision'] != 1 or r['status'] != 'ok' or r.get('baseline') is not None for r in rows)):
        raise ValueError('revision 1 forest identity/coverage changed')
    for row in rows:
        baseline = by_case[row['case_id']]
        if any(baseline[key] != row['identity'][key]
               for key in ('graph_sha256', 'config_sha256', 'official_sha256')):
            raise ValueError(f'baseline identity mismatch for {row["case_id"]}')

    blobs = {}
    for case, baseline in by_case.items():
        ref = baseline['result']
        raw = fixed_blob(args.baseline_repo, ref['path'])
        if hashlib.sha256(raw).hexdigest() != ref['sha256']:
            raise ValueError(f'fixed baseline bytes changed for {case}')
        blobs[case] = raw
    draft.mkdir(parents=True)
    for case, raw in blobs.items():
        path = draft / 'baseline' / case / 'result.json.gz'
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(raw)
    for shard, feed in enumerate(originals, 1):
        for row in feed['records']:
            case = row['case_id']
            baseline = dict(by_case[case])
            baseline['result'] = {
                'path': (draft / 'baseline' / case / 'result.json.gz').relative_to(ROOT).as_posix(),
                'sha256': by_case[case]['result']['sha256'],
            }
            row['baseline'] = baseline
            row['revision'] = 2
            row['notes'].append(f'Baseline evidence added from fixed source {SOURCE_COMMIT}; '
                                'revision 1 solver result and attempt are unchanged.')
        output = draft / f'board-feed-s{shard:02}-revision2.json'
        output.write_text(json.dumps(feed, ensure_ascii=False, indent=2, allow_nan=False) + '\n',
                          encoding='utf-8')
    print(json.dumps({'draft': draft.relative_to(ROOT).as_posix(), 'records': 500,
                      'source_commit': SOURCE_COMMIT, 'baseline_blobs': len(blobs)}))


if __name__ == '__main__':
    main()
