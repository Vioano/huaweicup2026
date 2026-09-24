"""Exercise the CLI on archived pilot bytes, never on new scoring calls.

The reordered manifest and terminal summary are interface fixtures only.
The temporary feed is deleted and must never be published as fresh500 data.
"""
import copy
import gzip
import hashlib
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile

ROOT = Path(__file__).resolve().parents[4]
HERE = Path(__file__).resolve().parent
PILOT = ROOT / 'results/a/q2-nikolastarx/gap-solver-pilot-20260925/run'
MANIFEST = ROOT / 'results/a/q2-nikolastarx/gap-full500-20260925/manifest.json'

def main():
    original = json.loads((PILOT / 'summary.json').read_bytes())
    manifest = json.loads(MANIFEST.read_bytes())
    coordinates = [(r['case'], r['cores']) for r in original['rows']]
    by = {(r['case'], r['cores']): r for r in manifest['rows']}
    manifest['rows'] = [by[c] for c in coordinates] + [
        r for r in manifest['rows'] if (r['case'], r['cores']) not in coordinates]
    manifest_bytes = (json.dumps(manifest) + '\n').encode()
    summary = copy.deepcopy(original)
    summary['status'] = 'completed'
    summary['manifest_sha256'] = hashlib.sha256(manifest_bytes).hexdigest()
    env = {k: v for k, v in os.environ.items() if k != 'PYTHONPATH'}
    env['PYTHONDONTWRITEBYTECODE'] = '1'
    with tempfile.TemporaryDirectory(prefix='p2-export-source-fixture-') as tmp, \
            tempfile.TemporaryDirectory(prefix='.export-fixture-', dir=HERE) as out:
        source = Path(tmp)
        (source / 'manifest.json').write_bytes(manifest_bytes)
        (source / 'summary.json').write_text(json.dumps(summary))
        for case, k in coordinates:
            cell = f'{case}-k{k}'
            for rel in ('plan.json', 'result.json', 'solver-process/process.json',
                        'e0-process/process.json', 'online/solver.json'):
                raw_path = PILOT / cell / rel
                data = raw_path.read_bytes() if raw_path.exists() else gzip.decompress(
                    raw_path.with_suffix(raw_path.suffix + '.gz').read_bytes())
                dest = source / cell / rel
                dest.parent.mkdir(parents=True, exist_ok=True)
                dest.write_bytes(data)
        command = [sys.executable, '-B', str(ROOT / 'scripts/q2_gap_stream_export.py'),
                   '--summary', str(source / 'summary.json'), '--manifest', str(source / 'manifest.json'),
                   '--output-root', out, '--run-id', 'fixture-only-never-publish', '--shard', '0',
                   '--producer-session', 'nikolastarx/s-8ee33b891eb94c529bf5be94bb5d8894',
                   '--task-url', 'https://github.com/huaweibei123/huaweicup2026/issues/33',
                   '--runtime-id', 'fixture-only', '--source-reference', 'fixture-only/summary.json', '--final']
        first = json.loads(subprocess.check_output(command, cwd=ROOT, env=env))
        second = json.loads(subprocess.check_output(command, cwd=ROOT, env=env))
        assert first == second and first['records'] == 4 and first['evaluations'] == 0
        checked = subprocess.check_output([sys.executable, '-B', 'src/benchmark_board/protocol.py',
                                          first['feed'], '--submission'], cwd=ROOT, env=env).decode()
        print(checked.strip())
    print('Fixture deleted; 0 scoring calls, 0 enqueue, 0 publishing. No fresh500 claim.')

if __name__ == '__main__':
    main()
