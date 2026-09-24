"""Run each frozen official singlecore CLI once, in independent subprocesses.

Only the outer batch driver is ours. Official files, configuration and CLI are
unchanged. The timeout is an operational guard, not an official scoring rule.
"""
from __future__ import annotations

import argparse
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime, timezone
import gzip
import hashlib
import json
import os
from pathlib import Path
import platform
import subprocess
import sys
import time

ROOT = Path(__file__).resolve().parents[2]


def utc():
    return datetime.now(timezone.utc).isoformat().replace('+00:00', 'Z')


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def write(path, value):
    tmp = path.with_suffix('.tmp')
    tmp.write_text(json.dumps(value, ensure_ascii=False, indent=2) + '\n')
    tmp.replace(path)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output', type=Path, required=True)
    parser.add_argument('--workers', type=int, default=8)
    parser.add_argument('--timeout', type=int, default=600)
    args = parser.parse_args()
    if not 1 <= args.workers <= 8 or args.timeout < 1:
        parser.error('workers must be 1..8; timeout must be positive')
    out = (ROOT / args.output).resolve()
    if not out.is_relative_to(ROOT / 'results/benchmark-board'):
        parser.error('output must be below results/benchmark-board')
    out.mkdir(parents=True, exist_ok=False)
    official = ROOT / 'data/raw/a/official'
    manifest = json.loads((ROOT / 'docs/a/source-manifest.json').read_text())
    expected = {r['path']: r['sha256'] for r in manifest['files']}
    for name, expected_hash in expected.items():
        if sha(official / name) != expected_hash:
            raise ValueError('frozen source mismatch: ' + name)
    start = time.monotonic()
    common = dict(schema='official-singlecore-batch-v1', started_at=utc(),
                  runner_commit=subprocess.check_output(['git', 'rev-parse', 'HEAD'], cwd=ROOT, text=True).strip(),
                  runner_sha256=sha(Path(__file__)),
                  official_code_hash=manifest['official_code_hash'],
                  source_manifest_sha256=sha(ROOT / 'docs/a/source-manifest.json'),
                  config_sha256=expected['data/config.txt'],
                  python=platform.python_version(), platform=platform.platform(),
                  machine=platform.machine(), cpu_count=os.cpu_count(),
                  workers=args.workers, timeout_seconds=args.timeout,
                  lock_sha256=sha(ROOT / 'uv.lock'),
                  policy='one unmodified E0 singlecore CLI per case; no retries; timeout is not an official limit')
    write(out / 'manifest.json', common)
    records = []

    def run(case):
        target = out / case
        target.mkdir()
        command = [sys.executable, '-B', 'data/raw/a/official/code/singlecore_evaluate.py',
                   f'data/raw/a/official/data/case_{case}.json',
                   '--config', 'data/raw/a/official/data/config.txt',
                   '--output', str((target / 'result.json').relative_to(ROOT)),
                   '--trace-output', str((target / 'trace.json').relative_to(ROOT)),
                   '--log-output', str((target / 'result.log').relative_to(ROOT))]
        receipt = dict(case_id=case, started_at=utc(), graph_sha256=expected[f'data/case_{case}.json'],
                       config_sha256=common['config_sha256'], official_code_hash=common['official_code_hash'],
                       entrypoint='singlecore_evaluate.evaluate_singlecore', official_calls=1,
                       command=['python'] + command[1:], timeout_seconds=args.timeout)
        begin = time.monotonic()
        with (target / 'stdout.log').open('wb') as stdout, (target / 'stderr.log').open('wb') as stderr:
            proc = subprocess.Popen(command, cwd=ROOT, stdout=stdout, stderr=stderr,
                                    env=dict(os.environ, PYTHONDONTWRITEBYTECODE='1'))
            try:
                receipt['returncode'] = proc.wait(timeout=args.timeout)
                receipt['status'] = 'ok' if proc.returncode == 0 else 'failed'
            except subprocess.TimeoutExpired:
                proc.kill()
                proc.wait()
                receipt.update(status='timeout', returncode=proc.returncode)
        receipt.update(finished_at=utc(), wall_seconds=time.monotonic()-begin)
        if receipt['status'] == 'ok':
            result = json.loads((target / 'result.json').read_text())
            if result.get('scene') != 'A' or result.get('num_cores') != 1 or result.get('execution_mode') != 'singlecore':
                raise ValueError('unexpected official result identity')
            receipt['makespan_cycles'] = result['makespan']
        receipt['artifacts'] = {}
        for name in ('result.json', 'trace.json'):
            path = target / name
            if path.exists():
                raw = path.read_bytes()
                zipped = path.with_suffix(path.suffix + '.gz')
                zipped.write_bytes(gzip.compress(raw, mtime=0))
                receipt['artifacts'][name] = dict(path=str(zipped.relative_to(ROOT)),
                                                 sha256=sha(zipped), raw_sha256=hashlib.sha256(raw).hexdigest(),
                                                 bytes=len(raw), gzip_bytes=zipped.stat().st_size)
                # The compressed bytes reproduce the complete untouched CLI output.
                if gzip.decompress(zipped.read_bytes()) != raw:
                    raise ValueError('compression round trip mismatch')
                path.unlink()
        write(target / 'run.json', receipt)
        return receipt

    # Prioritise the board's two admitted cases, then smaller inputs for early coverage.
    cases = [f'{n:03d}' for n in range(1, 101)]
    cases.sort(key=lambda c: (c not in ('002', '044'), (official / f'data/case_{c}.json').stat().st_size))
    with ThreadPoolExecutor(max_workers=args.workers) as pool:
        pending = {pool.submit(run, case): case for case in cases}
        for future in as_completed(pending):
            receipt = future.result()
            records.append(receipt)
            report = dict(common, updated_at=utc(), elapsed_seconds=time.monotonic()-start,
                          completed=len(records), target=100,
                          counts={s:sum(r['status']==s for r in records) for s in ('ok','failed','timeout')},
                          results=sorted(records, key=lambda r:r['case_id']))
            write(out / 'progress.json', report)
            print(json.dumps({k:receipt.get(k) for k in ('case_id','status','makespan_cycles','wall_seconds')}, ensure_ascii=False), flush=True)
    report['finished_at'] = utc()
    write(out / 'progress.json', report)
    print(json.dumps({'complete':len(records), 'counts':report['counts'], 'elapsed_seconds':report['elapsed_seconds']}), flush=True)


if __name__ == '__main__':
    main()
